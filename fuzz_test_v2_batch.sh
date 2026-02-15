#!/bin/bash
# /Users/xinqiwang/Openhands/benchmarks/fuzz_test_v2_batch.sh

# 1. 定义输出目录
OUTPUT_DIR="./eval_outputs_fuzz_v2_batch"

# 2. 清理旧的输出目录，防止因为旧结果导致跳过测试
if [ -d "$OUTPUT_DIR" ]; then
    echo "Cleaning old output directory: $OUTPUT_DIR"
    rm -rf "$OUTPUT_DIR"
fi

# 3. 自动删除旧镜像并重新构建 (确保改动生效)
echo "Removing old images to force rebuild..."
# 使用 || true 防止在没有镜像时脚本报错退出
docker rmi -f $(docker images --format "{{.Repository}}:{{.Tag}}" | grep "openhands/eval-agent-server" | grep "source-minimal") 2>/dev/null || true

# 4. 创建统一的 select 文件包含所有 4 个案例
SELECT_FILE="select_batch_v2.txt"
echo "astropy__astropy-7671" > "$SELECT_FILE"
echo "astropy__astropy-13977" >> "$SELECT_FILE"
echo "django__django-10554" >> "$SELECT_FILE"
echo "django__django-11333" >> "$SELECT_FILE"

echo "Starting batch build and test for 4 instances..."

# 5. 统一构建镜像
uv run benchmarks/swebench/build_images.py \
  --dataset princeton-nlp/SWE-bench_Verified \
  --split test \
  --image ghcr.io/openhands/eval-agent-server \
  --target source-minimal \
  --num-workers 4 \
  --select "$SELECT_FILE"

# 6. 统一运行推理 (通过 --num-workers 实现并行)
# 所有结果将存放在同一个 OUTPUT_DIR 文件夹内
uv run swebench-infer .llm_config/openrouter.json \
    --select "$SELECT_FILE" \
    --workspace docker \
    --output-dir "$OUTPUT_DIR" \
    --max-attempts 1 \
    --max-retries 1 \
    --max-iterations 30 \
    --extra-tools fuzz_hypo_v2 \
    --num-workers 4 \
    --prompt-path benchmarks/swebench/prompts/hypothesis_test_v2.j2
