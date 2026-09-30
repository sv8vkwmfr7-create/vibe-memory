import numpy as np

from vibe_memory import VibeMemory
from vibe_memory.embedding import TfidfProvider


def test_direct_encode_contract_documents_first_batch_fit():
    assert "first batch" in TfidfProvider.encode.__doc__
    assert "does not refit" in TfidfProvider.encode.__doc__


def test_query_before_fit_does_not_learn_query_vocabulary():
    provider = TfidfProvider()
    assert provider.encode_query("betaterm").shape == (0,)
    assert not provider._fitted
    assert provider.vectorizer.vocabulary == {}


def test_direct_encode_keeps_first_vocabulary_until_explicit_refit():
    provider = TfidfProvider()
    provider.encode(["alphaterm"])
    first_vocabulary = dict(provider.vectorizer.vocabulary)
    unseen = provider.encode(["betaterm"])
    assert provider.vectorizer.vocabulary == first_vocabulary
    assert np.count_nonzero(unseen) == 0
    provider.fit(["alphaterm", "betaterm"])
    assert "betaterm" in provider.vectorizer.vocabulary
    assert np.count_nonzero(provider.encode_query("betaterm")) > 0


def test_sdk_refits_changed_corpus_instead_of_freezing_first_batch():
    memory = VibeMemory("tfidf-contract", embedding_backend="tfidf")
    try:
        memory.store("alphaterm", auto_build_edges=False, auto_episode=False)
        memory.recall("alphaterm")
        second = memory.store("betaterm", auto_build_edges=False, auto_episode=False)
        assert "betaterm" not in memory.embedding.vectorizer.vocabulary
        result = memory.recall("betaterm")
        assert "betaterm" in memory.embedding.vectorizer.vocabulary
        assert any(atom.id == second.id for atom in result["atoms"])
    finally:
        memory.storage.conn.close()
