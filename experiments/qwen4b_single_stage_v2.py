"""Paired single-stage minimal prompt revision plus new development variants."""
import hashlib
import json
import re
import time

from experiments.qwen4b_gpu_selection_first import (
    ROOT, torch, AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, emit)
from experiments.selection_response_probe import process_selection


RULES = '''补充选择规则：题目未指定环境或租户，而候选给出不同范围的所问属性值时，选取两种范围的证据用于澄清，不默认生产环境。匹配范围的记录明确说所问属性已更新但新值未知时，选取该未知记录；不选未说明所问属性的审计、格式或操作人记录。题目询问某说法是否已确认时，已确认旧值和未核实新说法都是解释无法确认所需的证据，可同时选取，不能把未核实说法当成事实。'''


def main(*, rules=RULES):
    paths = {'reference': ROOT / 'results/qwen4b_staged_selection_v2.jsonl',
             'cases': ROOT / 'results/qwen4b_prompt_selection_v2.md',
             'variants': ROOT / 'experiments/single_stage_evidence_variants_v1.json'}
    sources = {k: p.read_bytes() for k, p in paths.items()}
    reference = [json.loads(s) for s in sources['reference'].decode('utf-8-sig').splitlines()]
    baseline = reference[0]['prompts']['selection']
    prompts = {'baseline': baseline, 'minimal': rules + '\n' + baseline}
    cases = [json.loads(s) for s in re.findall(r'```json\n(.*?)\n```', sources['cases'].decode('utf-8'), re.S)]
    cases = [c for c in cases if c['event'] == 'input']
    assert len(cases) == 15
    cases += json.loads(sources['variants'])['cases']
    assert len(cases) == 21 and torch.cuda.is_available()
    emit(dict(event='frozen', source_hashes={k: hashlib.sha256(v).hexdigest() for k, v in sources.items()},
              prompts=prompts, prompt_hashes={k: hashlib.sha256(v.encode()).hexdigest() for k, v in prompts.items()},
              mode='single_stage_no_annotations'))
    for case in cases:
        digest = hashlib.sha256(json.dumps(case['pack'], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        if 'input_sha256' in case:
            assert digest == case['input_sha256']
        case['input_sha256'] = digest
        emit(case)
    torch.set_num_threads(4)
    path = ROOT / 'models/Qwen3-4B-Instruct-2507'
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(path, local_files_only=True, trust_remote_code=False,
        dtype=torch.float16, device_map={'': 'cuda:0'}, low_cpu_mem_usage=True,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16))
    model.eval()
    assert all(p.device.type == 'cuda' for p in model.parameters())
    torch.cuda.synchronize()
    emit(dict(event='loaded', seconds=time.perf_counter()-started))
    torch.cuda.reset_peak_memory_stats()
    calls, results = [], []

    def generate(pack, *, case_id, arm):
        user = json.dumps(pack, ensure_ascii=False, separators=(',', ':'))
        inputs = tokenizer.apply_chat_template([dict(role='system', content=prompts[arm]),
            dict(role='user', content=user)], tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors='pt').to('cuda:0')
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(**inputs, do_sample=False, max_new_tokens=192)
        torch.cuda.synchronize()
        n = inputs['input_ids'].shape[-1]
        call = dict(event='call', case_id=case_id, arm=arm, pack=pack,
            raw=tokenizer.decode(output[0][n:], skip_special_tokens=True),
            input_sha256=hashlib.sha256(user.encode()).hexdigest(), prompt_tokens=n,
            generated_tokens=output.shape[-1]-n, generation_seconds=time.perf_counter()-started)
        calls.append(call)
        emit(call)
        return call['raw']

    for index, case in enumerate(cases):
        for arm in (list(prompts) if index % 2 == 0 else list(reversed(prompts))):
            raw = generate(case['pack'], case_id=case['case_id'], arm=arm)
            result = process_selection(case['pack'], raw)['results'][0]
            row = dict(event='result', case_id=case['case_id'], group=case['group'], arm=arm,
                       selected=[case['labels'][m['id']] for m in result['memories']], selection=result)
            results.append(row)
            emit(row)
    assert len(results) == len(calls) == 42
    emit(dict(event='complete', calls=len(calls), results=len(results),
              peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved(),
              totals={arm: dict(calls=sum(c['arm'] == arm for c in calls),
                  prompt_tokens=sum(c['prompt_tokens'] for c in calls if c['arm'] == arm),
                  generated_tokens=sum(c['generated_tokens'] for c in calls if c['arm'] == arm),
                  generation_seconds=sum(c['generation_seconds'] for c in calls if c['arm'] == arm))
                  for arm in prompts}))


if __name__ == '__main__':
    main()
