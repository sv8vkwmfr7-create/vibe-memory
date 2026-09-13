"""Dependency-free CJK character bigrams for lexical retrieval."""
import re


def cjk_bigrams(text: str) -> list[str]:
    return [run[i:i + 2] for run in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", text)
            for i in range(len(run) - 1)]
