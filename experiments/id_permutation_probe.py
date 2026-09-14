"""Only rename atom IDs in a frozen corpus; anonymize candidates and MCP ranks."""
import argparse
import json
import random
from pathlib import Path
from experiments.frozen_replay_probe import probe


def run(data):
    rows=[]
    for seed in range(12):
        order=list(range(len(data['atoms'])))
        random.Random(seed).shuffle(order)
        report=probe(data,id_order=order,repeats=2)
        rows.append({'permutation':seed,'candidates':report['candidates'], 'runs':report['runs']})
    return {'conditions':'Only atom IDs permuted (fixed random seeds 0-11); content, insertion order, creation times and manual edges unchanged. Each permutation has off/on fresh WAL clones with actual MCP session/precision/budget sequence. Candidate snapshot taken before reinforcement. Current clock not frozen; assistant labels/private corpus are not independent quality proof.', 'permutations':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus',type=Path)
    args=parser.parse_args()
    print(json.dumps(run(json.loads(args.corpus.read_text(encoding='utf-8-sig')))))
