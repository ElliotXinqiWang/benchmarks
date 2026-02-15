#!/bin/bash
# Example: Using subagent (delegation tool) in SWE-bench inference
#
# This script demonstrates how to enable the subagent (delegation) tool
# in swebench-infer, allowing the main agent to delegate tasks to sub-agents.

# Basic usage with subagent enabled
uv run swebench-infer .llm_config/openrouter.json \
    --select instance_set/instances_1.txt \
    --workspace docker \
    --output-dir "./evaluation_results/eval_outputs_subagent_test" \
    --max-attempts 3 \
    --max-iterations 200 \
    --num-workers 1 \
    --extra-tools subagent \
    --n-limit 1

# You can also combine multiple extra tools
# uv run swebench-infer .llm_config/openrouter.json \
#     --select instance_set/instances_1.txt \
#     --workspace docker \
#     --output-dir "./evaluation_results/eval_outputs_multi_tools" \
#     --max-attempts 3 \
#     --max-iterations 200 \
#     --num-workers 1 \
#     --extra-tools fuzz_hypo subagent \
#     --n-limit 1
