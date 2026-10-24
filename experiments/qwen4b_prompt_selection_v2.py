"""Paired offline prompt diagnostic on frozen short-ID inputs, not production."""
import hashlib
import json
import re
import time

from experiments.qwen4b_gpu_selection_first import (
    ROOT, torch, AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, emit)
from experiments.selection_response_probe import process_selection


def main():
    prior = ROOT / 'results/qwen4b_short_selection_12_v1.md'
    records = [json.loads(text) for text in re.findall(r'```json\n(.*?)\n```', prior.read_text(encoding='utf-8'), re.S)]
    cases = []
    for row in records:
        if 'case_id' not in row:
            continue
        wire = json.dumps(row['wire_pack'], ensure_ascii=False, separators=(',', ':'))
        assert hashlib.sha256(wire.encode()).hexdigest() == row['input_sha256']
        labels = {key: row['uuid_map'][value] for key, value in row['short_to_uuid'].items()}
        cases.append(dict(case_id=row['case_id'], group='original12', pack=row['wire_pack'], labels=labels))
    assert len(cases) == 12
    holdout_path = ROOT / 'experiments/prompt_holdout_cases.json'
    holdout_bytes = holdout_path.read_bytes()
    for case in json.loads(holdout_bytes):
        candidates = [dict(id=f'c{i}', text=text, scope=scope, context_before='', context_after='', source_session='')
                      for i, (text, scope) in enumerate(case['writes'], 1)]
        pack = dict(dataset_id='resolution-selection-probe', cases=[dict(
            case_id='q', question=case['question'], scope=case['scope'], candidates=candidates,
            as_of='2026-10-01')])
        cases.append(dict(case_id=case['id'], group='development_holdout3', pack=pack,
                          labels={f'c{i}': f'write{i}' for i in range(1, len(candidates)+1)}))
    old_prompt = next(line for line in (ROOT / 'results/dated_local_selection_12_first.md').read_text(encoding='utf-8').splitlines()
                      if line.startswith('只根据本题候选'))
    assert hashlib.sha256(old_prompt.encode()).hexdigest() == '6ee9da1028cd0a73a9b8acefd96af6286df7478d5de78ce10ff054175df91b7e'
    extension = (ROOT / 'experiments/qwen4b_evidence_prompt_v2.txt').read_text(encoding='utf-8').strip()
    prompts = dict(v1=old_prompt, v2=extension + '\n' + old_prompt)
    emit(dict(event='frozen', prior_sha256=hashlib.sha256(prior.read_bytes()).hexdigest(),
              holdout_sha256=hashlib.sha256(holdout_bytes).hexdigest(),
              prompts=prompts, prompt_hashes={k: hashlib.sha256(v.encode()).hexdigest() for k, v in prompts.items()}))
    assert torch.cuda.is_available()
    torch.set_num_threads(4)
    started = time.perf_counter()
    model_path = ROOT / 'models/Qwen3-4B-Instruct-2507'
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False, dtype=torch.float16,
        device_map={'': 'cuda:0'}, low_cpu_mem_usage=True,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                             bnb_4bit_use_double_quant=True,
                                             bnb_4bit_compute_dtype=torch.float16))
    model.eval()
    assert all(p.device.type == 'cuda' for p in model.parameters())
    torch.cuda.synchronize()
    emit(dict(event='loaded', seconds=time.perf_counter()-started))
    torch.cuda.reset_peak_memory_stats()
    rows = []
    for index, case in enumerate(cases):
        user = json.dumps(case['pack'], ensure_ascii=False, separators=(',', ':'))
        emit(dict(event='input', **case, input_sha256=hashlib.sha256(user.encode()).hexdigest()))
        for arm in (('v1', 'v2') if index % 2 == 0 else ('v2', 'v1')):
            inputs = tokenizer.apply_chat_template(
                [dict(role='system', content=prompts[arm]), dict(role='user', content=user)],
                tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors='pt').to('cuda:0')
            torch.cuda.synchronize()
            started = time.perf_counter()
            with torch.inference_mode():
                output = model.generate(**inputs, do_sample=False, max_new_tokens=192)
            torch.cuda.synchronize()
            seconds = time.perf_counter()-started
            n = inputs['input_ids'].shape[-1]
            raw = tokenizer.decode(output[0][n:], skip_special_tokens=True)
            result = process_selection(case['pack'], raw)['results'][0]
            row = dict(event='response', case_id=case['case_id'], group=case['group'], arm=arm, raw=raw,
                       status=result['status'], fallback_reason=result['fallback_reason'],
                       selected=[case['labels'][item['id']] for item in result['memories']],
                       prompt_tokens=n, generated_tokens=output.shape[-1]-n, generation_seconds=seconds)
            rows.append(row)
            emit(row)
    assert len(rows) == 30 and len({(r['case_id'], r['arm']) for r in rows}) == 30
    emit(dict(event='complete', calls=len(rows),
              peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved(),
              totals={arm: dict(accepted=sum(r['status']=='selected' for r in rows if r['arm']==arm),
                                prompt_tokens=sum(r['prompt_tokens'] for r in rows if r['arm']==arm),
                                generated_tokens=sum(r['generated_tokens'] for r in rows if r['arm']==arm),
                                generation_seconds=sum(r['generation_seconds'] for r in rows if r['arm']==arm))
                      for arm in prompts}))


if __name__ == '__main__':
    main()
