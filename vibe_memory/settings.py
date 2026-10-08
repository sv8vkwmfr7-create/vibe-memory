"""Local enhancement preference and human-facing terminal panel (no network)."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


PRIVACY_NOTICE = (
    "记忆保存在本地，但返回给宿主的原文可能发送到模型服务商并消耗对话额度。\n"
    "增强默认开启，由当前对话模型解释候选；不新增独立云请求。\n"
    "关闭增强仅减少返回条数，不保证不联网。完整原文可能增加上下文用量。"
)


def load_settings(vibe_dir):
    path = Path(vibe_dir) / "settings.json" if vibe_dir else None
    settings = {"enhanced": True, "privacy_acknowledged": False}
    if path and path.exists():
        with path.open(encoding="utf-8") as handle:
            saved = json.load(handle)
        if (not isinstance(saved, dict) or type(saved.get("enhanced")) is not bool
                or type(saved.get("privacy_acknowledged", False)) is not bool):
            raise ValueError("Invalid enhancement settings")
        settings.update(saved)
    return settings


def save_settings(vibe_dir, settings):
    if not vibe_dir:
        raise ValueError("A vibe directory is required to persist settings")
    directory = Path(vibe_dir)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as handle:
            temporary = handle.name
            json.dump(settings, handle)
        os.replace(temporary, directory / "settings.json")
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def settings_status(vibe_dir):
    return {**load_settings(vibe_dir),
            "settings_file": str((Path(vibe_dir) / "settings.json").resolve()) if vibe_dir else None,
            "configuration_scope": "vibe_dir_shared_by_all_agents",
            "privacy_notice": PRIVACY_NOTICE}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="VibeMemory 本地设置面板")
    parser.add_argument("--vibe-dir", default=".vibe")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.vibe_dir)
        print("VibeMemory 设置面板")
        print(f"配置位置：{(Path(args.vibe_dir) / 'settings.json').resolve()}")
        print("配置范围：共享此目录的所有 agent；需要独立偏好请使用不同目录。")
        print(f"增强：{'开启' if settings['enhanced'] else '关闭'}")
        print(f"首次说明：{'已确认' if settings['privacy_acknowledged'] else '待确认'}")
        print(PRIVACY_NOTICE)
        print("自动建边/摘要开关：本面板尚不支持；安全保护不可关闭。")
        answer = input("回车=确认说明并保留当前设置；on=开启；off=关闭；cancel=取消：").strip().lower()
        if answer == "cancel":
            print("已取消，设置未修改。")
            return 0
        if answer not in ("", "on", "off"):
            raise ValueError("无效选择，设置未修改")
        if answer:
            settings["enhanced"] = answer == "on"
        settings["privacy_acknowledged"] = True
        save_settings(args.vibe_dir, settings)
        print("已保存。后续不需要重复选择对话模型。")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("已取消，设置未修改。")
        return 0
    except (OSError, ValueError) as exc:
        print(f"设置错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
