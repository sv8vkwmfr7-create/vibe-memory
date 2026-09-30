import json
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from vibe_memory.init import AgentDetector


@pytest.fixture
def detector(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    instance = AgentDetector(db_path=r'C:\Users\测试用户\memory.db')
    instance.cwd = tmp_path
    return instance


@pytest.mark.parametrize('name', ['.mcp.json', '.claude/mcp.json'])
@pytest.mark.parametrize('content', ['{broken', '[]', '{"mcpServers": []}'])
def test_invalid_claude_config_is_untouched(detector, name, content):
    target = detector.cwd / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError):
        detector.configure('claude-code')
    assert target.read_text(encoding='utf-8') == content
    assert not (detector.cwd / 'CLAUDE.md').exists()


def test_claude_merges_project_config_and_preserves_backup(detector):
    target = detector.cwd / '.mcp.json'
    original = b'{"mcpServers":{"other":{"command":"keep"}},"extra":true}'
    target.write_bytes(original)
    detector.configure('claude-code')
    config = json.loads(target.read_text(encoding='utf-8'))
    assert config['mcpServers']['other'] == {'command': 'keep'}
    assert config['extra'] is True
    assert config['mcpServers']['vibe-memory']['args'][0] == '-m'
    assert any(p.read_bytes() == original for p in target.parent.glob('.mcp.json.*.bak'))
    detector.configure('claude-code')
    assert len(list(target.parent.glob('.mcp.json.*.bak'))) == 1


def test_legacy_claude_config_is_copied_not_deleted(detector):
    legacy = detector.cwd / '.claude/mcp.json'
    legacy.parent.mkdir()
    original = '{"mcpServers":{"other":{"command":"keep"}}}'
    legacy.write_text(original, encoding='utf-8')
    result = detector.configure('claude-code')
    config = json.loads((detector.cwd / '.mcp.json').read_text(encoding='utf-8'))
    assert 'other' in config['mcpServers']
    assert legacy.read_text(encoding='utf-8') == original
    assert any('legacy' in action.lower() for action in result['actions'])


@pytest.mark.parametrize('existing', [False, True])
def test_codex_windows_paths_round_trip_and_existing_config_survives(detector, monkeypatch, existing):
    import vibe_memory.init as init
    monkeypatch.setattr(init.sys, 'executable', r'C:\Program Files\Python\python.exe')
    monkeypatch.setenv('VIBE_AGENT_ID', 'agent-"quoted"')
    target = Path.home() / '.codex/config.toml'
    target.parent.mkdir()
    original = '# vibe-memory mentioned in a comment\nmodel = "keep"\n'
    if existing:
        target.write_text(original, encoding='utf-8')
    detector.configure('codex')
    parsed = tomllib.loads(target.read_text(encoding='utf-8'))
    if existing:
        assert parsed['model'] == 'keep'
    server = parsed['mcp_servers']['vibe-memory']
    assert server['command'] == init.sys.executable
    assert server['args'][3] == detector.db_path
    assert server['args'][5] == 'agent-"quoted"'
    before = target.read_bytes()
    detector.configure('codex')
    assert target.read_bytes() == before


def test_config_backup_failure_does_not_replace_file(detector, monkeypatch):
    import vibe_memory.init as init
    target = detector.cwd / '.mcp.json'
    original = b'{"mcpServers":{}}'
    target.write_bytes(original)

    def fail_backup(*args):
        raise OSError('synthetic backup failure')

    monkeypatch.setattr(init.shutil, 'copy2', fail_backup)
    with pytest.raises(OSError, match='synthetic'):
        detector.configure('claude-code')
    assert target.read_bytes() == original


@pytest.mark.parametrize('agent, name', [
    ('cursor', '.cursorrules'),
    ('github-copilot', '.github/copilot-instructions.md'),
])
def test_instruction_files_preserve_original_backup(detector, agent, name):
    target = detector.cwd / name
    target.parent.mkdir(parents=True, exist_ok=True)
    original = '原有规则\n'.encode('utf-8')
    target.write_bytes(original)
    detector.configure(agent)
    assert target.read_bytes().startswith(original)
    assert any(p.read_bytes() == original for p in target.parent.glob(target.name + '.*.bak'))
    before = target.read_bytes()
    detector.configure(agent)
    assert target.read_bytes() == before


def test_invalid_codex_config_is_untouched(detector):
    target = Path.home() / '.codex/config.toml'
    target.parent.mkdir()
    original = 'broken = [\n'
    target.write_text(original, encoding='utf-8')
    with pytest.raises(ValueError):
        detector.configure('codex')
    assert target.read_text(encoding='utf-8') == original
    assert not (detector.cwd / 'AGENTS.md').exists()


def test_atomic_replace_failure_preserves_original(detector, monkeypatch):
    import vibe_memory.init as init
    target = detector.cwd / '.mcp.json'
    original = b'{"mcpServers":{}}'
    target.write_bytes(original)

    def fail_replace(*args):
        raise OSError('synthetic replace failure')

    monkeypatch.setattr(init.os, 'replace', fail_replace)
    with pytest.raises(OSError, match='synthetic'):
        detector.configure('claude-code')
    assert target.read_bytes() == original
    assert any(p.read_bytes() == original for p in target.parent.glob('.mcp.json.*.bak'))
    assert not list(target.parent.glob('*.tmp'))


@pytest.mark.parametrize('agent', ['claude-code', 'codex', 'cursor', 'github-copilot'])
def test_dry_run_does_not_create_files(detector, agent):
    before = set(detector.cwd.rglob('*'))
    assert detector.configure(agent, dry_run=True)['status'] == 'would_configure'
    assert set(detector.cwd.rglob('*')) == before
