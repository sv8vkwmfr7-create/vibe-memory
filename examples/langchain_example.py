"""
VibeMemory + LangChain Agent Example

Shows how to use VibeMemoryLC as a drop-in memory for LangChain.
Run: python examples/langchain_example.py
"""

from vibe_memory.langchain import VibeMemoryLC

# Initialize memory
memory = VibeMemoryLC(agent_id="langchain-demo", db_path=":memory:")

# Simulate conversation
print("=== Simulating Conversations ===\n")

memory.save_context(
    {"input": "What's the API timeout setting?"},
    {"output": "Currently set to 30 seconds, but we may need to increase it."},
)

memory.save_context(
    {"input": "I'm seeing connection pool errors after the timeout change"},
    {"output": "That makes sense — longer timeouts mean connections hold the pool longer. Let's increase pool size to 20."},
)

memory.save_context(
    {"input": "60 seconds is still causing timeouts for large queries"},
    {"output": "Let's try 120 seconds. The large analytics queries need more time."},
)

# Recall: what does the agent remember about timeout?
print("--- Recall: timeout ---")
result = memory.load_memory_variables({"input": "timeout"})
print(result["history"])
print()

# Recall: what about pool?
print("--- Recall: pool ---")
result = memory.load_memory_variables({"input": "pool"})
print(result["history"])
print()

# Session management
print("--- Session Lifecycle ---")
start = memory.start_session("API timeout debugging")
print(f"Started: {start['session_id']}, recalled {start['memories_recalled']} memories")

end = memory.end_session("Fixed timeout cascade: 30→60→120s, pool 10→20", ["cascade pattern identified"])
print(f"Ended: {end['stored']} memories stored")

print("\nDone!")