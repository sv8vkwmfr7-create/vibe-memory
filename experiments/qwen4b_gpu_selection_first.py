"""Offline, fixed 12-case diagnostic; prints raw evidence, never changes defaults."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT.parent / "知识库"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(VAULT))

import torch
import bitsandbytes
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from prepare_retrieval_fact_probe import DISTRACTORS
from experiments.resolution_selection_probe import run
from vibe_memory import VibeMemory


def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--short-ids', action='store_true', help='Experiment-only per-question c1... IDs')
    short_ids = parser.parse_args().short_ids
    source = (VAULT / "zcode-glm实验/cases.json").read_bytes()
    assert hashlib.sha256(source).hexdigest() == "a2deb039a6b138058a600dfe1e8db1cf26cf51a97911b753836cfab132c0d398"
    data = json.loads(source)
    prompt = next(line for line in (ROOT / "results/dated_local_selection_12_first.md").read_text(encoding="utf-8").splitlines()
                  if line.startswith("只根据本题候选"))
    assert hashlib.sha256(prompt.encode()).hexdigest() == "6ee9da1028cd0a73a9b8acefd96af6286df7478d5de78ce10ff054175df91b7e"
    assert len(data["cases"]) == 12 and data["as_of"] == "2026-10-01"
    assert torch.cuda.is_available()
    torch.set_num_threads(4)
    model_path = ROOT / "models/Qwen3-4B-Instruct-2507"
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False, dtype=torch.float16,
        device_map={"": "cuda:0"}, low_cpu_mem_usage=True,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                             bnb_4bit_use_double_quant=True,
                                             bnb_4bit_compute_dtype=torch.float16))
    model.eval()
    assert all(p.device.type == "cuda" for p in model.parameters())
    quantized_layers = sum(isinstance(m, bitsandbytes.nn.Linear4bit) for m in model.modules())
    assert quantized_layers > 0
    torch.cuda.synchronize()
    emit(dict(event="loaded", seconds=time.perf_counter()-started,
              short_ids=short_ids,
              torch=torch.__version__, transformers=transformers.__version__,
              bitsandbytes=bitsandbytes.__version__, quantized_layers=quantized_layers,
              allocated_bytes=torch.cuda.memory_allocated()))
    torch.cuda.reset_peak_memory_stats()
    rows = []
    with tempfile.TemporaryDirectory(prefix="vibe-qwen4b-selection-") as temporary:
        for case in data["cases"]:
            memory = VibeMemory(agent_id="synthetic-probe", tenant_id="synthetic-probe",
                                db_path=str(Path(temporary) / (case["id"] + ".db")),
                                embedding_backend="tfidf")
            mapping, captured = {}, {}
            try:
                for label, text in [(f"d{i}", text) for i, text in enumerate(DISTRACTORS, 1)] + [
                        (m["id"], m["text"]) for m in case["memories"]]:
                    atom = memory.store(text, session_id="fixture", auto_build_edges=False, auto_episode=False)
                    mapping[atom.id] = label

                def selector(pack):
                    user = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
                    inputs = tokenizer.apply_chat_template(
                        [dict(role="system", content=prompt), dict(role="user", content=user)],
                        tokenize=True, add_generation_prompt=True, return_dict=True,
                        return_tensors="pt").to("cuda:0")
                    torch.cuda.synchronize()
                    started = time.perf_counter()
                    with torch.inference_mode():
                        output = model.generate(**inputs, do_sample=False, max_new_tokens=192)
                    torch.cuda.synchronize()
                    seconds = time.perf_counter()-started
                    n = inputs["input_ids"].shape[-1]
                    raw = tokenizer.decode(output[0][n:], skip_special_tokens=True)
                    captured.update(raw=raw, prompt_tokens=n, generated_tokens=output.shape[-1]-n,
                                    generation_seconds=seconds,
                                    wire_pack=pack,
                                    input_sha256=hashlib.sha256(user.encode()).hexdigest())
                    return raw

                result = run(memory, case["question"], selector=selector, as_of=data["as_of"],
                             short_candidate_ids=short_ids)
                assert captured, "Selector failed before raw output; do not report success"
                selection = result["selection"]
                row = dict(case_id=case["id"], candidates=[mapping[x["id"]] for x in result["candidates"]],
                           selected=[mapping[x["id"]] for x in selection["memories"]],
                           status=selection["status"], fallback_reason=selection.get("fallback_reason"),
                           recall_failures=result["recall_failures"], uuid_map=mapping, **captured)
                if short_ids:
                    row['short_to_uuid'] = {f'c{i}': item['id'] for i, item in enumerate(result['candidates'], 1)}
                rows.append(row)
                emit(row)
            finally:
                memory.storage.conn.close()
    assert len(rows) == 12
    emit(dict(event="complete", cases=len(rows), accepted=sum(r["status"] != "fallback" for r in rows),
              prompt_tokens=sum(r["prompt_tokens"] for r in rows),
              generated_tokens=sum(r["generated_tokens"] for r in rows),
              generation_seconds=sum(r["generation_seconds"] for r in rows),
              peak_allocated_bytes=torch.cuda.max_memory_allocated(),
              peak_reserved_bytes=torch.cuda.max_memory_reserved()))


if __name__ == "__main__":
    main()
