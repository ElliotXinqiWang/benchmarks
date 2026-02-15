#!/bin/bash

# 检查参数
if [ "$#" -lt 2 ]; then
    echo "用法: $0 <instance_id_or_file> <patch_file> [llm_config]"
    echo "示例: $0 django__django-11001 my_fix.patch .llm_config/openrouter.json"
    exit 1
fi

INPUT_TARGET=$1
PATCH_FILE=$2
LLM_CONFIG=${3:-".llm_config/openrouter.json"}

# 如果输入是一个 ID 而不是文件，创建一个临时文件
if [[ ! -f "$INPUT_TARGET" ]]; then
    echo "$INPUT_TARGET" > temp_instance.txt
    INSTANCES_FILE="temp_instance.txt"
else
    INSTANCES_FILE="$INPUT_TARGET"
fi

echo "正在验证 Patch: $PATCH_FILE 对实例: $INSTANCES_FILE (盲测模式)"

uv run python benchmarks/swebench/verify_patch_runner.py \
    "$LLM_CONFIG" \
    --select "$INSTANCES_FILE" \
    --patch-path "$PATCH_FILE" \
    --prompt-path "benchmarks/swebench/prompts/verify_patch_blind.j2" \
    --workspace docker \
    --output-dir "./eval_outputs_verification" \
    --max-iterations 200 \
    --num-workers 1 \
    --n-limit 1 \
    --extra-tools fuzz_hypo

# 清理临时文件
if [[ "$INSTANCES_FILE" == "temp_instance.txt" ]]; then
    rm temp_instance.txt
fi
