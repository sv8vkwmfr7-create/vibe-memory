"""Replay fixed, deliberately false cause-to-symptom edges; no production changes."""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from experiments.directional_holdout_probe import evaluate


WRONG_CAUSES = ("proxy-cause", "poller-cause", "console-cause")
EFFECTS = (
    ("console-effect-0", "console-effect-1"),
    ("proxy-effect-0", "proxy-effect-1"),
    ("poller-effect-0", "poller-effect-1"),
)


def run(path: Path) -> dict:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    if len(data["queries"]) != len(WRONG_CAUSES):
        raise ValueError("Unexpected source fixture shape")
    clean = evaluate(data)
    variants = []
    for index, (wrong, effects) in enumerate(zip(WRONG_CAUSES, EFFECTS)):
        if wrong not in data["queries"][index]["negative_ids"]:
            raise ValueError("Injected cause must be labeled negative")
        poisoned = deepcopy(data)
        poisoned["edges"].extend([[wrong, effect] for effect in effects])
        altered = evaluate(poisoned)
        variants.append(
            {
                "query_id": f"query-{index}",
                "added_false_edges": 2,
                "clean": {key: clean["rows"][index][key] for key in clean["aggregates"]},
                "poisoned": {key: altered["rows"][index][key] for key in clean["aggregates"]},
                "directional_diagnostic": altered["rows"][index]["directional_diagnostic"],
            }
        )
    return {
        "dataset_id": "causal-wrong-anchor-v1",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "evaluation_is_independent": False,
        "evidence_boundary": "Three variants with two assistant-injected false cross-case edges each, tested separately. Source cases and labels are assistant-authored; not independent evidence or observed graph errors. Returned IDs are anonymous aliases.",
        "conditions": clean["conditions"] | {"variants": len(variants)},
        "variants": variants,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(run(args.corpus), ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
