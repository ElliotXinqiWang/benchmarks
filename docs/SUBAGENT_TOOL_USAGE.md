# Subagent (Delegation) Tool Usage in SWE-bench

## Overview

The `subagent` tool (internally called `DelegateTool`) has been successfully added to the extra tools options. This allows the main agent to delegate tasks to specialized sub-agents for parallel processing.

## What is the Subagent Tool?

The delegation tool enables:
- **Spawning sub-agents**: Create multiple sub-agents with specific identities
- **Task delegation**: Assign tasks to sub-agents for parallel execution
- **Result aggregation**: Collect and merge results from all sub-agents

## How to Use

### Basic Usage

Add `--extra-tools subagent` to your swebench-infer command:

```bash
uv run swebench-infer .llm_config/openrouter.json \
    --select instance_set/instances_hard.txt \
    --workspace docker \
    --output-dir "./evaluation_results/eval_outputs_with_subagent" \
    --max-attempts 3 \
    --max-iterations 200 \
    --num-workers 5 \
    --extra-tools subagent \
    --n-limit 10
```

### Combining Multiple Extra Tools

You can enable multiple extra tools at once:

```bash
uv run swebench-infer .llm_config/openrouter.json \
    --select instance_set/instances_hard.txt \
    --workspace docker \
    --output-dir "./evaluation_results/eval_outputs_multi" \
    --max-attempts 3 \
    --max-iterations 200 \
    --num-workers 5 \
    --extra-tools fuzz_hypo subagent \
    --n-limit 10
```

## Available Tools

The tool is registered as:
- **Command-line name**: `subagent` (use with `--extra-tools`)
- **Internal name**: `delegate` (tool name in Agent)
- **Implementation**: `DelegateTool` from `openhands.tools.delegate`

## Delegation Commands

When the agent has access to the delegation tool, it can use two commands:

### 1. Spawn Sub-agents

```python
# Example: Agent spawns sub-agents
{
    "command": "spawn",
    "ids": ["researcher", "coder"]
}
```

### 2. Delegate Tasks

```python
# Example: Agent delegates tasks to sub-agents
{
    "command": "delegate",
    "tasks": {
        "researcher": "Analyze the bug and identify root cause",
        "coder": "Write a test case to reproduce the issue"
    }
}
```

## All Available Extra Tools

Current extra tools that can be enabled:
- `fuzz_hypo` - Fuzzing and hypothesis testing tool
- `fuzz_hypo_agent` - Agent-based fuzzing tool
- `fuzz_hypo_v2` - Version 2 of fuzzing tool
- `subagent` - **NEW!** Delegation/sub-agent tool

## Implementation Details

Modified files:
- `vendor/software-agent-sdk/openhands-tools/openhands/tools/preset/default.py`
  - Added `"subagent"` to `EXTRA_TOOL_NAMES`
  - Added registration logic in `register_extra_tools()`
  - Added tool initialization in `get_default_tools()`

## Testing

The tool has been verified to work correctly:
```
✅ Tool is registered in EXTRA_TOOL_NAMES
✅ Tool is properly imported from openhands.tools.delegate
✅ Tool is added to agent's tool list when requested
✅ Tool name resolves to 'delegate' internally
```

## Example Use Cases

1. **Parallel Bug Investigation**: Spawn sub-agents to investigate different aspects of a bug
2. **Multi-file Refactoring**: Delegate different files to different sub-agents
3. **Test Generation**: One sub-agent writes tests while another analyzes code
4. **Research + Implementation**: Separate research phase from implementation phase

## Notes

- Sub-agents share the same workspace as the main agent
- Each sub-agent has its own conversation state
- Maximum number of concurrent sub-agents: 5 (configurable)
- Sub-agents have access to the same tools as the main agent (except delegation to prevent infinite recursion)
