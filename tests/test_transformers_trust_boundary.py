import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibe_memory.llm.provider import TransformersProvider, create_provider


MODEL_SHA = "a" * 40
CODE_SHA = "b" * 40


@pytest.fixture
def loaders(monkeypatch):
    calls = []
    model = SimpleNamespace(eval=lambda: calls.append(("eval",)),
                            to=lambda device: calls.append(("device", device)))
    def load_tokenizer(name, **kwargs):
        calls.append(("tokenizer", name, kwargs))
        return object()
    def load_model(name, **kwargs):
        calls.append(("model", name, kwargs))
        return model
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        float32="float32", cuda=SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=load_tokenizer),
        AutoModelForCausalLM=SimpleNamespace(from_pretrained=load_model)))
    return calls


def test_default_never_opts_in_to_remote_code(loaders):
    provider = TransformersProvider()
    provider._load()
    assert loaders[0][2]["trust_remote_code"] is False
    assert loaders[1][2]["trust_remote_code"] is False
    assert provider._device == "cpu"
    provider._load()
    assert len(loaders) == 3  # tokenizer/model/eval, still lazy once loaded


def test_explicit_trust_pins_model_and_code_in_both_loaders(loaders):
    provider = create_provider("transformers", trust_remote_code=True,
                               revision=MODEL_SHA, code_revision=CODE_SHA)
    provider._load()
    for call in loaders[:2]:
        assert call[2]["trust_remote_code"] is True
        assert call[2]["revision"] == MODEL_SHA
        assert call[2]["code_revision"] == CODE_SHA


def test_same_repo_code_defaults_to_model_commit(loaders):
    provider = TransformersProvider(trust_remote_code=True, revision=MODEL_SHA)
    provider._load()
    for call in loaders[:2]:
        assert call[2]["code_revision"] == MODEL_SHA


@pytest.mark.parametrize("trust", [None, 0, 1, "false", "true"])
def test_trust_requires_real_boolean(trust):
    with pytest.raises(ValueError, match="trust_remote_code"):
        TransformersProvider(trust_remote_code=trust)


@pytest.mark.parametrize("revision", [None, "", "main", "v1", "a" * 39,
                                       "a" * 41, "g" * 40, 1])
def test_trusted_loading_requires_full_model_commit(revision):
    with pytest.raises(ValueError, match="revision"):
        TransformersProvider(trust_remote_code=True, revision=revision)


@pytest.mark.parametrize("revision", ["", "main", "a" * 39, "g" * 40, 1])
def test_trusted_code_revision_cannot_float(revision):
    with pytest.raises(ValueError, match="code_revision"):
        TransformersProvider(trust_remote_code=True, revision=MODEL_SHA, code_revision=revision)


def test_untrusted_builtin_model_can_use_named_revision(loaders):
    provider = TransformersProvider(revision="v1")
    provider._load()
    for call in loaders[:2]:
        assert call[2]["trust_remote_code"] is False
        assert call[2]["revision"] == "v1"


def test_mutated_trust_is_checked_before_loading(loaders):
    provider = TransformersProvider()
    provider.trust_remote_code = True
    with pytest.raises(ValueError, match="revision"):
        provider._load()
    assert loaders == []


def test_denied_custom_code_is_not_retried_with_trust(loaders, monkeypatch):
    def denied(name, **kwargs):
        loaders.append(("denied", kwargs))
        raise ValueError("synthetic custom code requires explicit trust")
    monkeypatch.setattr(sys.modules["transformers"].AutoTokenizer, "from_pretrained", denied)
    with pytest.raises(ValueError, match="explicit trust"):
        TransformersProvider()._load()
    assert loaders == [("denied", {"trust_remote_code": False})]


@pytest.mark.parametrize("trust", [False, True])
def test_real_tokenizer_import_gate_with_local_sentinel(tmp_path, monkeypatch, trust):
    pytest.importorskip("transformers")
    from transformers import dynamic_module_utils
    monkeypatch.setattr(dynamic_module_utils, "HF_MODULES_CACHE", str(tmp_path / "modules"))
    model_path = Path(__file__).parent / "fixtures" / "custom_transformers_trust"
    provider = TransformersProvider(model_name=str(model_path), trust_remote_code=trust,
                                    revision=MODEL_SHA if trust else None)
    if trust:
        with pytest.raises(RuntimeError, match="synthetic custom tokenizer module executed"):
            provider._load()
    else:
        with pytest.raises(ValueError, match="trust_remote_code"):
            provider._load()
    assert provider._model is None
