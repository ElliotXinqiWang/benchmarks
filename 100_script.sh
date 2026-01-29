#!/bin/bash
# bash 100_script.sh -i instances_100_2.txt -l .llm_config/openrouter.json && bash 100_script.sh -i instances_100_1.txt -l .llm_config/openrouter.json && bash 100_script.sh -i instances_100_2.txt -l .llm_config/openrouter_opus.json && bash 100_script.sh -i instances_100_1.txt -l .llm_config/openrouter_opus.json 
# 默认值
INSTANCES_FILE="instances_100_2.txt"
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
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  -i, --instances <文件>    指定测试集文件 (默认: instances_100.txt)"
            echo "  -l, --llm-config <文件>   指定LLM配置文件 (默认: .llm_config/openrouter.json)"
            echo "  -h, --help                显示帮助信息"
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            echo "使用 -h 或 --help 查看帮助信息"
            exit 1
            ;;
    esac
done

# 从 LLM 配置文件中提取 model 字段
if ! command -v jq &> /dev/null; then
    echo "错误: 需要安装 jq 来解析 JSON 配置文件"
    exit 1
fi

if [[ ! -f "$LLM_CONFIG" ]]; then
    echo "错误: 找不到 LLM 配置文件: $LLM_CONFIG"
    exit 1
fi

MODEL=$(jq -r '.model' "$LLM_CONFIG")
if [[ -z "$MODEL" || "$MODEL" == "null" ]]; then
    echo "错误: 无法从配置文件中读取 model 字段"
    exit 1
fi

# 构建评估输出路径的基础部分
# 格式: {output_dir}/princeton-nlp__SWE-bench_Verified-test/{model}_sdk_73769d5_maxiter_200_N_initial/output.jsonl
MODEL_PATH_SUFFIX="${MODEL}_sdk_73769d5_maxiter_200_N_initial"
DATASET_PATH="princeton-nlp__SWE-bench_Verified-test"

# 为输出文件名创建安全的后缀（将斜杠替换为下划线）
MODEL_SAFE="${MODEL//\//_}"
MODEL_SAFE_SUFFIX="${MODEL_SAFE}_sdk_73769d5_maxiter_200_N_initial"

# 从 INSTANCES_FILE 提取文件名（不含扩展名）作为子目录名
INSTANCES_SUBDIR=$(basename "$INSTANCES_FILE" .txt)

echo "使用测试集: $INSTANCES_FILE"
echo "使用LLM配置: $LLM_CONFIG"
echo "模型: $MODEL"
echo "输出子目录: $INSTANCES_SUBDIR"

uv run benchmarks/swebench/build_images.py \
  --dataset princeton-nlp/SWE-bench_Verified \
  --split test \
  --image ghcr.io/openhands/eval-agent-server \
  --target source-minimal \
  --num-workers 5 \
  --select "$INSTANCES_FILE" \
  --n-limit 100
# Run with fuzz_hypo tool enabled
uv run swebench-infer "$LLM_CONFIG" \
    --select "$INSTANCES_FILE" \
    --workspace docker \
    --output-dir "./eval_outputs_fuzz_hypo_100/${INSTANCES_SUBDIR}" \
    --max-attempts 3 \
    --max-iterations 200 \
    --max-retries 1 \
    --num-workers 5 \
    --extra-tools fuzz_hypo \
    --prompt-path benchmarks/swebench/prompts/custom_fuzz_prompt.j2 \
    --n-limit 100

uv run swebench-eval "./eval_outputs_fuzz_hypo_100/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}/output.jsonl" \
  --dataset princeton-nlp/SWE-bench_Verified \
  --output-file results_fuzz_hypo_100_${INSTANCES_SUBDIR}_${MODEL_SAFE_SUFFIX}.swebench.jsonl \
  --workers 5


uv run swebench-infer "$LLM_CONFIG" \
    --select "$INSTANCES_FILE" \
    --workspace docker \
    --output-dir "./eval_outputs_fuzz_hypo_final/${INSTANCES_SUBDIR}" \
    --max-attempts 3 \
    --max-iterations 200 \
    --max-retries 1 \
    --num-workers 5 \
    --extra-tools fuzz_hypo \
    --prompt-path benchmarks/swebench/prompts/fuzz_final_only.j2 \
    --n-limit 100

uv run swebench-eval "./eval_outputs_fuzz_hypo_final/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}/output.jsonl" \
  --dataset princeton-nlp/SWE-bench_Verified \
  --output-file results_fuzz_hypo_final_${INSTANCES_SUBDIR}_${MODEL_SAFE_SUFFIX}.swebench.jsonl \
  --workers 5

# Run with hypothesis prompt (no extra tools)
uv run swebench-infer "$LLM_CONFIG" \
    --select "$INSTANCES_FILE" \
    --workspace docker \
    --output-dir "./eval_outputs_hypothesis_100/${INSTANCES_SUBDIR}" \
    --max-attempts 3 \
    --max-iterations 200 \
    --max-retries 1 \
    --num-workers 5 \
    --prompt-path benchmarks/swebench/prompts/hypothesis_default.j2 \
    --n-limit 100

uv run swebench-eval "./eval_outputs_hypothesis_100/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}/output.jsonl" \
  --dataset princeton-nlp/SWE-bench_Verified \
  --output-file results_hypothesis_100_${INSTANCES_SUBDIR}_${MODEL_SAFE_SUFFIX}.swebench.jsonl \
  --workers 5


# Run with default prompt (no extra tools - baseline)
uv run swebench-infer "$LLM_CONFIG" \
    --select "$INSTANCES_FILE" \
    --workspace docker \
    --output-dir "./eval_outputs_100/${INSTANCES_SUBDIR}" \
    --max-attempts 3 \
    --max-iterations 200 \
    --max-retries 1 \
    --num-workers 5 \
    --prompt-path benchmarks/swebench/prompts/default.j2 \
    --n-limit 100

uv run swebench-eval "./eval_outputs_100/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}/output.jsonl" \
  --dataset princeton-nlp/SWE-bench_Verified \
  --output-file results_100_${INSTANCES_SUBDIR}_${MODEL_SAFE_SUFFIX}.swebench.jsonl \
  --workers 5
