"""Compare selection prompts on identical recorded v2 applicability outputs."""
import hashlib
import json
import re
import time

from experiments.qwen4b_gpu_selection_first import (
    ROOT, torch, AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, emit)
from experiments.staged_selection_probe import run
from experiments.selection_response_probe import process_selection


def main(*, applicability_ablation=False, annotation_ablation=False):
    assert not (applicability_ablation and annotation_ablation)
    paths = {'v2': ROOT / 'results/qwen4b_staged_selection_v2.jsonl',
             'v3': ROOT / 'results/qwen4b_staged_selection_v3.jsonl',
             'cases': ROOT / 'results/qwen4b_prompt_selection_v2.md'}
    sources = {k: p.read_bytes() for k, p in paths.items()}
    records = {k: [json.loads(s) for s in sources[k].decode('utf-8-sig').splitlines()]
               for k in ('v2', 'v3')}
    prompts = {k: records[k][0]['prompts']['selection'] for k in records}
    if applicability_ablation:
        prompts = {k: prompts['v2'] for k in prompts}
    if annotation_ablation:
        prompts = {k: prompts['v2'] for k in ('annotated', 'unannotated')}
    cases = [json.loads(s) for s in re.findall(r'```json\n(.*?)\n```',
             sources['cases'].decode('utf-8'), re.S)]
    cases = [c for c in cases if c['event'] == 'input']
    assessments = {k: {r['case_id']: r for r in records[k]
                      if r['event'] == 'call' and r['phase'] == 'applicability'} for k in records}
    assert len(cases) == len(assessments['v2']) == len(assessments['v3']) == 15 and torch.cuda.is_available()
    emit(dict(event='frozen', source_hashes={k: hashlib.sha256(v).hexdigest() for k, v in sources.items()},
              prompts=prompts, prompt_hashes={k: hashlib.sha256(v.encode()).hexdigest() for k, v in prompts.items()},
              applicability_mode=('recorded_v2_vs_no_annotation_fixed_v2_selection' if annotation_ablation
                                  else 'recorded_v2_v3_raw_fixed_v2_selection' if applicability_ablation
                                  else 'recorded_v2_raw_no_new_inference')))
    for case in cases:
        assessment = assessments['v2'][case['case_id']]
        assert all(assessments[k][case['case_id']]['pack'] == case['pack'] for k in assessments)
        assert hashlib.sha256(json.dumps(case['pack'], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() == case['input_sha256']
        emit(dict(event='input', **{k: case[k] for k in ('case_id', 'group', 'pack', 'labels', 'input_sha256')},
                  applicability_raw=({k: assessments[k][case['case_id']]['raw'] for k in assessments}
                                     if applicability_ablation else assessment['raw'])))
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
            if arm == 'unannotated':
                raw = generate(case['pack'], case_id=case['case_id'], arm=arm)
                result = dict(applicability_status='not_used', applicability=None,
                              selection=process_selection(case['pack'], raw)['results'][0])
            else:
                result = run(case['pack'], assessor=lambda p: assessments[arm if applicability_ablation else 'v2'][case['case_id']]['raw'],
                             selector=lambda p: generate(p, case_id=case['case_id'], arm=arm))
            row = dict(event='result', case_id=case['case_id'], group=case['group'], arm=arm,
                       selected=[case['labels'][m['id']] for m in result['selection']['memories']], **result)
            results.append(row)
            emit(row)
    assert len(results) == 30 and len(calls) == 30
    emit(dict(event='complete', calls=len(calls), results=len(results),
              peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved(),
              totals={arm: dict(calls=sum(c['arm'] == arm for c in calls),
                  prompt_tokens=sum(c['prompt_tokens'] for c in calls if c['arm'] == arm),
                  generated_tokens=sum(c['generated_tokens'] for c in calls if c['arm'] == arm),
                  generation_seconds=sum(c['generation_seconds'] for c in calls if c['arm'] == arm))
                  for arm in prompts}))


if __name__ == '__main__':
    main()
