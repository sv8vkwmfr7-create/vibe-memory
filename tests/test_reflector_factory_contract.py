import pytest

from vibe_memory.reflect import create_reflector
from vibe_memory.llm.provider import OpenAIProvider, AnthropicProvider


@pytest.mark.parametrize('provider_type,provider_class', [('openai', OpenAIProvider), ('anthropic', AnthropicProvider)])
def test_hosted_factory_uses_explicit_credentials_and_reflector_options(provider_type, provider_class):
    reflector = create_reflector(None, provider_type=provider_type, api_key='synthetic-test-key',
                                 model='synthetic-model', base_url='http://127.0.0.1:1', auto_store=False)
    assert isinstance(reflector.provider, provider_class)
    assert reflector.provider.model == 'synthetic-model'
    assert reflector.provider.base_url == 'http://127.0.0.1:1'
    assert reflector.auto_store is False


def test_unknown_provider_alias_is_rejected_not_silently_replaced():
    with pytest.raises(ValueError, match='Unknown LLM provider: deepseek'):
        create_reflector(None, provider_type='deepseek', api_key='synthetic-test-key')
