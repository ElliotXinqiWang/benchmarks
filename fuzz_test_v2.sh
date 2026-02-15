#!/bin/bash
# /Users/xinqiwang/Openhands/benchmarks/fuzz_test_v2.sh

# 1. 构建镜像 (如果尚未构建)
uv run benchmarks/swebench/build_images.py \
  --dataset princeton-nlp/SWE-bench_Verified \
  --split test \
  --image ghcr.io/openhands/eval-agent-server \
  --target source-minimal \
  --num-workers 4 \
  --select instances_1.txt \
  --n-limit 10

# 2. 运行推理测试
# 强制指定使用 fuzz_hypo_v2 工具和对应的测试 Prompt
uv run swebench-infer .llm_config/openrouter.json \
    --select instances_1.txt \
    --workspace docker \
    --output-dir ./eval_outputs_fuzz_v2_test \
    --max-attempts 1 \
    --max-retries 1 \
    --max-iterations 30 \
    --extra-tools fuzz_hypo_v2 \
    --num-workers 5 \
    --prompt-path benchmarks/swebench/prompts/hypothesis_test_v2.j2 \
    --n-limit 10
