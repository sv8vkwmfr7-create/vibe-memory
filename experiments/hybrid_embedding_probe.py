"""Experiment-only TF-IDF + semantic embedding comparison."""

import argparse
import ctypes
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.precision_guard_probe import evaluate
from vibe_memory.embedding import EmbeddingProvider, SentenceTransformerProvider, TfidfProvider


class HybridEmbeddingProvider(EmbeddingProvider):
    """Combine lexical and semantic cosine scores with a fixed weight."""

    def __init__(self, semantic_provider, lexical_provider=None, lexical_weight=0.5):
        if not 0 <= lexical_weight <= 1:
            raise ValueError('lexical_weight must be between 0 and 1')
        self.semantic = semantic_provider
        self.lexical = lexical_provider or TfidfProvider()
        self.lexical_weight = lexical_weight
        self._fitted = False

    def fit(self, documents):
        fit = getattr(self.lexical, 'fit', None)
        if fit is not None:
            fit(documents)
        self._fitted = True
        return self

    def encode(self, texts):
        if not self._fitted:
            self.fit(texts)
        lexical = self.lexical.encode(texts)
        semantic = self.semantic.encode(texts)
        return self._combine(lexical, semantic)

    def encode_query(self, query):
        if not self._fitted:
            raise RuntimeError('fit documents before encoding a hybrid query')
        return self._combine(
            self.lexical.encode_query(query)[None, :],
            self.semantic.encode_query(query)[None, :],
        )[0]

    def _combine(self, lexical, semantic):
        lexical_scale = np.sqrt(self.lexical_weight)
        semantic_scale = np.sqrt(1 - self.lexical_weight)
        return np.concatenate((lexical * lexical_scale, semantic * semantic_scale), axis=1)

    @property
    def dim(self):
        return self.lexical.dim + self.semantic.dim

    @property
    def name(self):
        return f'hybrid-{self.lexical_weight:g}-lexical+semantic'


def compare_corpus(data, semantic_provider, lexical_weight=0.5):
    providers = {
        'tfidf': TfidfProvider(),
        'semantic': semantic_provider,
        'hybrid': HybridEmbeddingProvider(semantic_provider,
            lexical_weight=lexical_weight),
    }
    return {name: evaluate(data, embedding_provider=provider,
        include_timing=True)['aggregates']
        for name, provider in providers.items()}


def working_set_bytes():
    if os.name != 'nt':
        return None

    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ('cb', wintypes.DWORD),
            ('PageFaultCount', wintypes.DWORD),
            ('PeakWorkingSetSize', ctypes.c_size_t),
            ('WorkingSetSize', ctypes.c_size_t),
            ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
            ('QuotaPagedPoolUsage', ctypes.c_size_t),
            ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
            ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
            ('PagefileUsage', ctypes.c_size_t),
            ('PeakPagefileUsage', ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    get_memory = kernel32.K32GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD]
    get_memory.restype = wintypes.BOOL
    if not get_memory(kernel32.GetCurrentProcess(),
            ctypes.byref(counters), counters.cb):
        return None
    return int(counters.WorkingSetSize)


def run(model_dir, corpora, lexical_weight=0.5):
    before = working_set_bytes()
    started = time.perf_counter()
    semantic = SentenceTransformerProvider(model_name=str(model_dir), device='cpu')
    semantic.encode(['model warmup'])
    model_load_ms = (time.perf_counter() - started) * 1000
    after = working_set_bytes()

    datasets = []
    for corpus in corpora:
        raw = corpus.read_bytes()
        data = json.loads(raw.decode('utf-8-sig'))
        if 'cases' in data:
            cases = [{'case_id': case['case_id'],
                'methods': compare_corpus(case, semantic, lexical_weight)}
                for case in data['cases']]
            datasets.append({'name': corpus.name,
                'sha256': hashlib.sha256(raw).hexdigest(), 'cases': cases})
        else:
            datasets.append({'name': corpus.name,
                'sha256': hashlib.sha256(raw).hexdigest(),
                'methods': compare_corpus(data, semantic, lexical_weight)})

    return {
        'model': 'BAAI/bge-small-zh-v1.5',
        'model_dir': str(model_dir),
        'device': 'cpu',
        'lexical_weight': lexical_weight,
        'model_load_ms': model_load_ms,
        'working_set_before_bytes': before,
        'working_set_after_load_bytes': after,
        'working_set_load_delta_bytes': None if before is None or after is None else after - before,
        'model_files_bytes': sum(path.stat().st_size for path in model_dir.rglob('*') if path.is_file()),
        'conditions': 'Fixed-weight vector concatenation makes cosine score equal to lexical_weight * TF-IDF cosine + (1 - lexical_weight) * BGE cosine when both branches are normalized. One process, CPU, model warmup once; recall p95 includes production core recall but excludes corpus/model setup and experimental post-filter cost. Assistant labels/manual edges; not independent evaluation. No SDK/MCP or default change.',
        'datasets': datasets,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path,
        default=Path('models/bge-small-zh-v1.5'))
    parser.add_argument('--lexical-weight', type=float, default=0.5)
    parser.add_argument('--output', type=Path)
    parser.add_argument('corpus', type=Path, nargs='+')
    args = parser.parse_args()
    report = json.dumps(run(args.model_dir, args.corpus, args.lexical_weight),
        indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.write_text(report, encoding='utf-8')
    else:
        print(report, end='')
