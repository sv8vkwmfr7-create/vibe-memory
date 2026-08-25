"""
VibeMemory — 5 分钟快速上手

安装：pip install vibe-memory
"""

from vibe_memory import VibeMemory

# 1. 初始化（SQLite 零依赖）
mem = VibeMemory(agent_id="my-agent")

# 2. 写入记忆
mem.store("修好了 API timeout，从 30s 改成 60s", session_id="chat-1")
mem.store("timeout 改完后连接池耗尽，pool 从 10 扩到 20", session_id="chat-2")

# 3. 检索记忆（precision 模式，噪声 0%）
result = mem.recall("API timeout", mode="precision")
for atom in result["atoms"]:
    print(f"[{atom.summary}]")

# 4. 查看统计
print(mem.stats())