"""Exact unique mapping of publisher snippets, not inferred relevance labels."""


def evidence_indices(history: list[dict], snippet: list[dict]) -> list[int]:
    if not snippet:
        raise ValueError("empty evidence snippet")
    for message in history + snippet:
        if message.get("role") not in ("system", "user", "assistant") or not isinstance(message.get("content"), str):
            raise ValueError("only text messages with supported roles are accepted")
    if any(message["role"] == "system" for message in snippet):
        raise ValueError("system persona is not dialogue evidence")
    sequence = [(message["role"], message["content"]) for message in history]
    target = [(message["role"], message["content"]) for message in snippet]
    matches = [index for index in range(len(sequence) - len(target) + 1)
               if sequence[index:index + len(target)] == target]
    if len(matches) != 1:
        raise ValueError(f"evidence mapping requires exactly one full match; found {len(matches)}")
    return list(range(matches[0], matches[0] + len(target)))
