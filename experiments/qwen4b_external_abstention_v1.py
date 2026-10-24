"""First six official-order excluded LongMemEval abstentions; diagnostic only."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time

from vibe_memory.retrieval.strategies import BM25Strategy
from experiments.selection_response_probe import process_selection

ROOT = Path(__file__).resolve().parents[1]
DATA = Path('C:/Users/ASYS/.cache/vibe-memory-eval/longmemeval_s_cleaned.json')
SOURCE_HASH = 'd6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442'


def emit(row):
    print(json.dumps(row, ensure_ascii=True), flush=True)


def main(*, include_positive_pairs=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    data = DATA.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCE_HASH
    cases = json.loads(data)
    negatives = [c for c in cases if c['question_id'].endswith('_abs')]
    assert len(cases) == 500 and len(negatives) == 30
    selected_cases = negatives[:6]
    if include_positive_pairs:
        by_id = {c['question_id']: c for c in cases}
        selected_cases = [c for negative in negatives[:6]
                          for c in (by_id[negative['question_id'][:-4]], negative)]
        assert len(selected_cases) == 12
    scope = json.loads((ROOT / 'results/qwen4b_scope_rule_ablation_v1.jsonl').read_text(encoding='utf-8-sig').splitlines()[0])
    confirmation = json.loads((ROOT / 'results/qwen4b_confirmation_rule_ablation_v1.jsonl').read_text(encoding='utf-8-sig').splitlines()[0])
    answer = json.loads((ROOT / 'results/qwen4b_grounded_answer_ablation_v1.jsonl').read_text(encoding='utf-8-sig').splitlines()[0])
    prompts = {'baseline': scope['prompts']['baseline'], 'scope': scope['prompts']['minimal'],
               'confirmation': confirmation['prompts']['minimal'], 'answer': answer['prompt']}
    assert hashlib.sha256(prompts['baseline'].encode()).hexdigest() == 'e112f1bbe249c435e45ec2e987a3ce0e8bde7dbbf6a24a78029d674f8d86db41'
    assert hashlib.sha256(prompts['answer'].encode()).hexdigest() == 'a9b2e35a62bf4183e3686935bbcfba7a0836896cd7766c017c9b545437b8c62f'
    frozen = []
    for case in selected_cases:
        assert len(case['haystack_sessions']) == len(case['haystack_dates']) == len(case['haystack_session_ids'])
        turns = []
        for si, session in enumerate(case['haystack_sessions']):
            for ti, turn in enumerate(session):
                assert turn['role'] in ('user', 'assistant') and isinstance(turn['content'], str)
                turns.append(dict(source_id=f'{si}:{ti}', source_session=case['haystack_session_ids'][si],
                    text=case['haystack_dates'][si] + '\n' + turn['role'] + ': ' + turn['content']))
        bm25 = BM25Strategy()
        bm25.fit([t['text'] for t in turns])
        ranked = bm25.search(case['question'], top_k=5)
        candidates = [dict(id=f'c{i+1}', text=turns[index]['text'], scope={},
            context_before='', context_after='', source_session=turns[index]['source_session'])
            for i, (index, _) in enumerate(ranked)]
        assert len(candidates) == 5
        as_of = datetime.strptime(case['question_date'], '%Y/%m/%d (%a) %H:%M').date().isoformat()
        pack = dict(dataset_id='resolution-selection-probe', cases=[dict(case_id='q',
            question=case['question'], scope={}, as_of=as_of, candidates=candidates)])
        frozen.append(dict(event='input', case_id=case['question_id'], pack=pack,
            official_answer=case['answer'], question_type=case['question_type'],
            source_turns=[turns[index]['source_id'] for index, _ in ranked], total_turns=len(turns),
            input_sha256=hashlib.sha256(json.dumps(pack, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()))
    emit(dict(event='frozen', source_sha256=SOURCE_HASH, prompts=prompts,
        prompt_hashes={k: hashlib.sha256(v.encode()).hexdigest() for k,v in prompts.items()},
        rule=('first six official-order _abs cases paired with original positive IDs; original haystacks differ; positives reused in retrieval scoring; BM25-only top5 dated turns'
              if include_positive_pairs else 'first six official-order _abs cases; unmodified question/gold; BM25-only top5 dated turns'),
        rubric=('Positive: requested fact matches external reference semantically; abstention on an answerable case is not success. Negative: explicitly cannot determine requested fact, no invented value. Pair passes only if both pass. Ancillary precision and truncation recorded separately.'
                if include_positive_pairs else 'Correct abstention: explicitly cannot determine requested fact from supplied memory; no invented value. Correctly qualified related facts allowed. Full explanation checked separately. Truncation unresolved.'),
        independent_limit='External authored labels; previously excluded retrieval cases, not a new dataset or independent human grading. English questions; frozen Chinese prompts.'))
    for row in frozen:
        emit(row)
    if args.prepare_only:
        return
    from experiments.qwen4b_gpu_selection_first import torch, AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    assert torch.cuda.is_available()
    torch.set_num_threads(4)
    started = time.perf_counter()
    path = ROOT / 'models/Qwen3-4B-Instruct-2507'
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
    calls, selections, answer_groups = [], [], {}

    def generate(pack, stage, conditions):
        user = json.dumps(pack, ensure_ascii=False, separators=(',', ':'))
        tokens = tokenizer.apply_chat_template([dict(role='system', content=prompts[stage]),
            dict(role='user', content=user)], tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors='pt').to('cuda:0')
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(**tokens, do_sample=False, max_new_tokens=192 if stage != 'answer' else 160)
        torch.cuda.synchronize()
        n = tokens['input_ids'].shape[-1]
        row = dict(event='call', stage=stage, conditions=conditions, pack=pack,
            input_sha256=hashlib.sha256(user.encode()).hexdigest(),
            raw=tokenizer.decode(output[0][n:], skip_special_tokens=True), prompt_tokens=n,
            generated_tokens=output.shape[-1]-n, ended_with_eos=int(output[0][-1])==tokenizer.eos_token_id,
            generation_seconds=time.perf_counter()-started)
        calls.append(row)
        emit(row)
        return row['raw']

    for index, case in enumerate(frozen):
        for arm in (['baseline','scope','confirmation'] if index % 2 == 0 else ['confirmation','scope','baseline']):
            condition = dict(case_id=case['case_id'], arm=arm)
            raw = generate(case['pack'], arm, [condition])
            result = process_selection(case['pack'], raw)['results'][0]
            selections.append(dict(event='selection', **condition, selection=result))
            emit(selections[-1])
            q = case['pack']['cases'][0]
            answer_pack = {k: q[k] for k in ['question','scope','as_of']}
            answer_pack['memories'] = result['memories']
            key = json.dumps(answer_pack, ensure_ascii=False, separators=(',', ':'))
            group = answer_groups.setdefault(key, dict(pack=answer_pack, conditions=[]))
            group['conditions'].append(condition)
    assert len(selections) == len(frozen) * 3
    for group in answer_groups.values():
        generate(group['pack'], 'answer', group['conditions'])
    emit(dict(event='complete', selections=len(selections), answer_calls=len(answer_groups), actual_calls=len(calls),
        totals={stage:dict(calls=sum(c['stage']==stage for c in calls),
            prompt_tokens=sum(c['prompt_tokens'] for c in calls if c['stage']==stage),
            generated_tokens=sum(c['generated_tokens'] for c in calls if c['stage']==stage),
            generation_seconds=sum(c['generation_seconds'] for c in calls if c['stage']==stage))
            for stage in prompts}, peak_allocated_bytes=torch.cuda.max_memory_allocated(),
        peak_reserved_bytes=torch.cuda.max_memory_reserved()))


if __name__ == '__main__':
    main()
