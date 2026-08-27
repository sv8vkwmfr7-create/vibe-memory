"""
VibeMemory + OpenAI Agents SDK Example

Shows how to use create_vibe_tools() with an OpenAI Agent.
Run: python examples/openai_agents_example.py
"""

from vibe_memory.openai_agents import create_vibe_tools

# Create tools (no OpenAI SDK needed for this demo — just the tools)
tools = create_vibe_tools(agent_id="openai-demo", db_path=":memory:")
name_map = {t.__name__: t for t in tools}

print("=== VibeMemory Tools for OpenAI Agents ===\n")
print(f"Available tools: {list(name_map.keys())}\n")

# Simulate an agent using the tools
print("--- Agent: start session ---")
result = name_map["vibe_session_start"](context="API timeout debugging")
print(result)

print("\n--- Agent: store memory ---")
result = name_map["vibe_store"](
    content="Fixed API timeout, changed from 30s to 60s",
    tags=["bug", "api", "fix"],
)
print(result)

print("\n--- Agent: store another memory ---")
result = name_map["vibe_store"](
    content="After timeout increase, connection pool exhausted. Pool size increased to 20.",
    tags=["bug", "db", "fix"],
)
print(result)

print("\n--- Agent: recall ---")
result = name_map["vibe_recall"](query="API timeout")
print(result)

print("\n--- Agent: link causally ---")
import json
r1 = json.loads(name_map["vibe_store"](content="Root cause: timeout 30s", tags=["bug"]))
r2 = json.loads(name_map["vibe_store"](content="Effect: pool exhausted", tags=["db"]))
result = name_map["vibe_link"](from_id=r1["id"], to_id=r2["id"], label="causal")
print(result)

print("\n--- Agent: stats ---")
result = name_map["vibe_stats"]()
print(result)

print("\n--- Agent: end session ---")
result = name_map["vibe_session_end"](
    summary="Fixed timeout cascade: 30→60→120s",
    highlights=["timeout 30→60s caused pool exhaustion", "pool size increased to 20"],
)
print(result)

print("\n--- Agent: forget test memory ---")
result = name_map["vibe_forget"](atom_id=r1["id"])
print(result)

print("\nDone! Use these tools with OpenAI Agents SDK:")
print("  from openai import Agent")
print("  agent = Agent(name='Assistant', tools=tools, ...)")