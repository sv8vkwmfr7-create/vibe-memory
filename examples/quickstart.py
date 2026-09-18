"""Minimal, offline VibeMemory store/reopen/recall example."""

from pathlib import Path
from tempfile import TemporaryDirectory

from vibe_memory import VibeMemory


def main() -> None:
    with TemporaryDirectory(prefix="vibe-memory-quickstart-") as temp_dir:
        db_path = Path(temp_dir) / "memory.db"

        memory = VibeMemory(
            agent_id="quickstart-agent",
            db_path=str(db_path),
            embedding_backend="tfidf",
        )
        memory.store(
            "request hangs request hangs Catalog",
            session_id="quickstart-1",
            tags=["catalog", "incident"],
            scope={"service": "catalog"},
            auto_build_edges=False,
            auto_episode=False,
        )
        target = memory.store(
            "request hangs Orders pool exhausted",
            session_id="quickstart-1",
            tags=["orders", "incident"],
            scope={"service": "orders"},
            auto_build_edges=False,
            auto_episode=False,
        )
        memory.storage.conn.close()

        reopened = VibeMemory(
            agent_id="quickstart-agent",
            db_path=str(db_path),
            embedding_backend="tfidf",
        )
        result = reopened.recall(
            "request hangs",
            mode="precision",
            top_k=5,
            scope={"service": "orders"},
        )
        recalled_ids = {atom.id for atom in result["atoms"]}
        if target.id not in recalled_ids:
            raise RuntimeError("Stored memory was not recalled after reopening the database")
        if result["atoms"][0].id != target.id or not result["scope_boosted"]:
            raise RuntimeError("Explicit scope did not boost the matching memory")

        print(f"Stored atom: {target.id}")
        for atom in result["atoms"]:
            print(f"Recalled: {atom.content}")
        print(f"Scope changed ordering: {result['scope_boosted']}")
        print("VibeMemory quickstart succeeded.")
        reopened.storage.conn.close()


if __name__ == "__main__":
    main()
