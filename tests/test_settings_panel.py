import subprocess
import sys

from test_mcp_enhancement import exchange, payload


def panel(tmp_path, answer):
    return subprocess.run(
        [sys.executable, "-m", "vibe_memory.settings", "--vibe-dir", str(tmp_path / "state")],
        input=answer, capture_output=True, text=True, encoding="utf-8", timeout=10,
    )


def test_first_use_panel_acknowledges_and_keeps_default_after_restart(tmp_path):
    result = panel(tmp_path, "\n")
    assert result.returncode == 0, result.stderr
    assert "模型服务商" in result.stdout
    assert "额度" in result.stdout
    settings = payload(exchange(tmp_path, [("vibe_settings", {})])[0])
    assert settings["enhanced"] is True
    assert settings["privacy_acknowledged"] is True
    assert settings["settings_file"] == str(tmp_path / "state" / "settings.json")


def test_panel_cancel_and_eof_do_not_acknowledge_or_change_preference(tmp_path):
    for answer in ("cancel\n", ""):
        assert panel(tmp_path, answer).returncode == 0
        settings = payload(exchange(tmp_path, [("vibe_settings", {})])[0])
        assert settings["enhanced"] is True
        assert settings["privacy_acknowledged"] is False
    assert panel(tmp_path, "off\n").returncode == 0
    assert panel(tmp_path, "cancel\n").returncode == 0
    settings = payload(exchange(tmp_path, [("vibe_settings", {})])[0])
    assert settings["enhanced"] is False
    assert settings["privacy_acknowledged"] is True
    assert panel(tmp_path, "on\n").returncode == 0
    assert payload(exchange(tmp_path, [("vibe_settings", {})])[0])["enhanced"] is True


def test_bad_configuration_is_visible_and_cannot_be_overwritten_by_panel(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "settings.json").write_text('{"enhanced": "false"}', encoding="utf-8")
    result = panel(tmp_path, "on\n")
    assert result.returncode == 1
    assert "设置错误" in result.stderr
    assert "error" in exchange(tmp_path, [("vibe_settings", {})])[0]


def test_mcp_cannot_assert_human_privacy_acknowledgement(tmp_path):
    replies = exchange(tmp_path, [("vibe_settings", {"privacy_acknowledged": True}),
                                  ("vibe_settings", {"enhanced": False}),
                                  ("vibe_settings", {})])
    assert "error" in replies[0]
    assert payload(replies[2])["privacy_acknowledged"] is False
