#!/bin/bash
# Run test_generator on instances_hard_fixed (167 tasks, excluding 2 env-broken)
set -e

# ============================================
# Configuration
# ============================================
INSTANCES_FILE="instance_set/instances_hard_fixed.txt"
# INSTANCES_FILE="instance_set/instances_hard_fixed.txt"
LLM_CONFIG=".llm_config/openrouter_opus.json"
DATASET_NAME="princeton-nlp/SWE-bench_Verified"
SPLIT="test"
NUM_WORKERS=5
N_LIMIT=167

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -w|--workers) NUM_WORKERS="$2"; shift 2 ;;
        -n|--n-limit) N_LIMIT="$2"; shift 2 ;;
        -l|--llm-config) LLM_CONFIG="$2"; shift 2 ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo "  -w, --workers <数量>      并行worker数 (默认: 4)"
            echo "  -n, --n-limit <数量>      实例数量限制 (默认: 167)"
            echo "  -l, --llm-config <文件>   LLM配置 (默认: .llm_config/openrouter_opus.json)"
            exit 0 ;;
        *) echo "未知选项: $1"; exit 1 ;;
    esac
done

# ============================================
# Validate
# ============================================
if ! command -v jq &> /dev/null; then
    echo "❌ 需要安装 jq"; exit 1
fi
if [[ ! -f "$LLM_CONFIG" ]]; then
    echo "❌ 找不到 LLM 配置文件: $LLM_CONFIG"; exit 1
fi
if [[ ! -f "$INSTANCES_FILE" ]]; then
    echo "❌ 找不到实例文件: $INSTANCES_FILE"; exit 1
fi

# ============================================
# Extract Configuration
# ============================================
MODEL=$(jq -r '.model' "$LLM_CONFIG")
if [[ -z "$MODEL" || "$MODEL" == "null" ]]; then
    echo "❌ 无法从配置文件中读取 model 字段"; exit 1
fi

SDK_SHA=$(git submodule status vendor/software-agent-sdk | awk '{print $1}' | sed 's/^[+-]*//')
SDK_SHORT_SHA="${SDK_SHA:0:7}"
DATASET_SANITIZED=${DATASET_NAME//\//__}
DATASET_PATH="${DATASET_SANITIZED}-${SPLIT}"
MODEL_SANITIZED=${MODEL//\//__}
MODEL_PATH_SUFFIX="${MODEL_SANITIZED}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial"
INSTANCES_SUBDIR=$(basename "$INSTANCES_FILE" .txt)

# ============================================
# Display Configuration
# ============================================
echo "=========================================="
echo "Plan C: test_generator Tool (hard_fixed, 167 tasks)"
echo "=========================================="
echo ""
echo "配置信息:"
echo "  测试集:        $INSTANCES_FILE ($N_LIMIT tasks)"
echo "  LLM配置:       $LLM_CONFIG"
echo "  模型:          $MODEL"
echo "  并行workers:   $NUM_WORKERS"
echo "  SDK版本:       $SDK_SHORT_SHA"
echo ""
echo "Prompt: test_generator_solve.j2"
echo "Extra tools: test_generator"
echo ""
echo "=========================================="

if [[ "${SKIP_CONFIRM:-0}" != "1" ]]; then
    read -p "继续执行? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消。"; exit 0
    fi
fi

# ============================================
# Phase 1: Build Docker Images
# ============================================
echo ""
echo "=========================================="
echo "Phase 1: Building Docker Images"
echo "=========================================="
echo ""

uv run benchmarks/swebench/build_images.py \
  --dataset "$DATASET_NAME" \
  --split "$SPLIT" \
  --image ghcr.io/openhands/eval-agent-server \
  --target source-minimal \
  --num-workers "$NUM_WORKERS" \
  --select "$INSTANCES_FILE" \
  --n-limit "$N_LIMIT"

echo "✓ Docker镜像构建完成"

# ============================================
# Phase 2: Run Inference with test_generator
# ============================================
echo ""
echo "=========================================="
echo "Phase 2: Running Inference (test_generator)"
echo "=========================================="
echo ""
echo "Output: evaluation_results/eval_hard_fixed/${INSTANCES_SUBDIR}"
echo ""

uv run swebench-infer "$LLM_CONFIG" \
    --select "$INSTANCES_FILE" \
    --workspace docker \
    --output-dir "./evaluation_results/eval_hard_fixed/${INSTANCES_SUBDIR}" \
    --max-attempts 3 \
    --max-iterations 200 \
    --max-retries 1 \
    --num-workers "$NUM_WORKERS" \
    --prompt-path benchmarks/swebench/prompts/test_generator_solve.j2 \
    --extra-tools test_generator \
    --n-limit "$N_LIMIT"

echo "✓ 推理执行完成"

# ============================================
# Phase 3: Evaluation
# ============================================
echo ""
echo "=========================================="
echo "Phase 3: Running SWE-bench Evaluation"
echo "=========================================="
echo ""

OUTPUT_JSONL="./evaluation_results/eval_hard_fixed/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial/output.jsonl"
RESULTS_JSONL="./evaluation_results/eval_hard_fixed/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial/results.swebench.jsonl"

# Try main output first, fallback to critic attempt
if [[ ! -f "$OUTPUT_JSONL" ]] || [[ ! -s "$OUTPUT_JSONL" ]]; then
    ATTEMPT_JSONL="./evaluation_results/eval_hard_fixed/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial/output.critic_attempt_1.jsonl"
    if [[ -f "$ATTEMPT_JSONL" ]]; then
        echo "⚠️  output.jsonl为空，使用 output.critic_attempt_1.jsonl"
        OUTPUT_JSONL="$ATTEMPT_JSONL"
    else
        echo "❌ 找不到输出文件"; exit 1
    fi
fi

echo "输入文件: $OUTPUT_JSONL"
echo ""

uv run swebench-eval "$OUTPUT_JSONL" \
    --dataset "$DATASET_NAME" \
    --output-file "$RESULTS_JSONL" \
    --workers "$NUM_WORKERS"

echo "✓ 评测执行完成"

# ============================================
# Phase 4: Results Summary
# ============================================
echo ""
echo "=========================================="
echo "Phase 4: Results Summary"
echo "=========================================="
echo ""

if [[ -f "$RESULTS_JSONL" ]]; then
    python3 << 'EOF'
import json, sys, glob

# Find results file
files = glob.glob("./evaluation_results/eval_hard_fixed/*/princeton-nlp__SWE-bench_Verified-test/*/results.swebench.jsonl")
if not files:
    print("❌ 找不到结果文件")
    sys.exit(0)

for results_file in files:
    resolved_count = 0
    total_count = 0
    resolved_ids = []

    with open(results_file) as f:
        for line in f:
            data = json.loads(line)
            iid = data.get("instance_id", "?")
            resolved = data.get("resolved", False)
            total_count += 1
            if resolved:
                resolved_count += 1
                resolved_ids.append(iid)

    print(f"总计: {resolved_count}/{total_count} resolved ({resolved_count*100//total_count if total_count else 0}%)")
    print(f"\nResolved ({resolved_count}):")
    for rid in sorted(resolved_ids):
        print(f"  ✓ {rid}")
EOF
fi

echo ""
echo "=========================================="
echo "✓ 完成"
echo "=========================================="
