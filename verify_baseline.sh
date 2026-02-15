#!/bin/bash

# 默认值 (保持与 hard_script.sh 一致)
INSTANCES_FILE="instances_hard.txt"
LLM_CONFIG=".llm_config/openrouter.json"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--instances)
            INSTANCES_FILE="$2"
            shift 2
            ;;
        -l|--llm-config)
            LLM_CONFIG="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -i, --instances <file>    Specify instances file (default: instances_hard.txt)"
            echo "  -l, --llm-config <file>   Specify LLM config file (default: .llm_config/openrouter.json)"
            echo "  -h, --help                Show help info"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for info"
            exit 1
            ;;
    esac
done

# 从 LLM 配置文件中提取 model 字段
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required"
    exit 1
fi

if [[ ! -f "$LLM_CONFIG" ]]; then
    echo "Error: LLM config not found: $LLM_CONFIG"
    exit 1
fi

MODEL=$(jq -r '.model' "$LLM_CONFIG")
SDK_SHA=$(git submodule status vendor/software-agent-sdk | awk '{print $1}' | sed 's/^[+-]*//')
SDK_SHORT_SHA="${SDK_SHA:0:7}"

# 路径匹配 (与 hard_script.sh 的 Baseline 路径一致)
MODEL_PATH_SUFFIX="${MODEL}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial"
DATASET_PATH="princeton-nlp__SWE-bench_Verified-test"
INSTANCES_SUBDIR=$(basename "$INSTANCES_FILE" .txt)

# 定位 Baseline 的输出文件
OUTPUT_JSONL="./eval_outputs/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}/output.jsonl"

echo ">>> Starting blind verification for Baseline results..."
echo "Target JSONL: $OUTPUT_JSONL"

if [[ -f "$OUTPUT_JSONL" ]]; then
    # 注意：这里改为传递具体的参数，batch_verify.sh 现在能更好地处理 --llm-config
    ./batch_verify.sh "$OUTPUT_JSONL" \
        --llm-config "$LLM_CONFIG" \
        --num-workers 4 \
        --select "$INSTANCES_FILE" \
        --n-limit 50
else
    echo "Error: Could not find output file $OUTPUT_JSONL"
    echo "Please make sure the baseline inference in hard_script.sh has completed."
    exit 1
fi
