#!/bin/bash

# 检查参数
if [ "$#" -lt 1 ]; then
    echo "用法: $0 <output.jsonl_path> [额外参数...]"
    echo "示例: $0 eval_outputs_subfuzz/hard/output.jsonl --num-workers 5"
    exit 1
fi

JSONL_PATH=$1
shift # 移除第一个参数

# 默认 LLM 配置
LLM_CONFIG=".llm_config/openrouter.json"
REMAINING_ARGS=()

# 手动解析参数，提取 --llm-config 并过滤掉它
while [[ $# -gt 0 ]]; do
    case $1 in
        --llm-config)
            LLM_CONFIG="$2"
            shift 2
            ;;
        *)
            REMAINING_ARGS+=("$1")
            shift
            ;;
    esac
done

echo "开始批量盲测验证..."
echo "输入文件: $JSONL_PATH"
echo "使用模型配置: $LLM_CONFIG"

# 运行 Python 脚本，第一个参数必须是位置参数 llm_config_path
uv run python benchmarks/swebench/batch_verify_runner.py \
    "$LLM_CONFIG" \
    --input-jsonl "$JSONL_PATH" \
    --workspace docker \
    --output-dir "./eval_outputs_batch_verification" \
    --max-iterations 200 \
    "${REMAINING_ARGS[@]}"
