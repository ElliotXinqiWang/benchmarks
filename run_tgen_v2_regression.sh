#!/bin/bash
# Regression test for test_generator_v2 improved prompt
# Tests the 8 instances that regressed in 03ee02f vs cdfd13b
# Goal: verify that the improved prompt generates better tests for these cases

set -e

# ============================================
# Configuration
# ============================================

INSTANCES_FILE="instance_set/instances_tgen_v2_regression.txt"
LLM_CONFIG=".llm_config/openrouter_opus.json"
DATASET_NAME="princeton-nlp/SWE-bench_Verified"
SPLIT="test"
NUM_WORKERS=4
N_LIMIT=8
OUTPUT_NAME="eval_tgen_v2_regression"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -w|--workers) NUM_WORKERS="$2"; shift 2 ;;
        -n|--n-limit) N_LIMIT="$2"; shift 2 ;;
        -l|--llm-config) LLM_CONFIG="$2"; shift 2 ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo "  -w, --workers <数量>      并行worker数 (默认: 4)"
            echo "  -n, --n-limit <数量>      实例数量限制 (默认: 8)"
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
echo "Regression Test: test_generator_v2 Improved Prompt"
echo "=========================================="
echo ""
echo "配置信息:"
echo "  测试集:        $INSTANCES_FILE ($N_LIMIT tasks)"
echo "  LLM配置:       $LLM_CONFIG"
echo "  模型:          $MODEL"
echo "  并行workers:   $NUM_WORKERS"
echo "  SDK版本:       $SDK_SHORT_SHA"
echo ""
echo "背景: 以下8题在 cdfd13b → 03ee02f 中出现退化"
echo "  所有退化与 test_generator 生成的测试精度不足有关"
echo "  本次测试验证改进后的 test_generator_v2 prompt 是否能修复这些问题"
echo ""
echo "测试实例 (8个退化案例):"
cat "$INSTANCES_FILE" | sed 's/^/  - /'
echo ""
echo "Prompt: test_generator_solve.j2"
echo "Extra tools: test_generator_v2"
echo "Output: evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}"
echo ""
echo "对比基准:"
echo "  cdfd13b (无test_generator): 8/8 resolved"
echo "  03ee02f (旧test_generator):  0/8 resolved (全部退化)"
echo "  本次目标: 验证改进后的 test_generator_v2 能恢复更多解题"
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
# Phase 2: Run Inference with test_generator_v2
# ============================================

echo ""
echo "=========================================="
echo "Phase 2: Running Inference (test_generator_v2)"
echo "=========================================="
echo ""
echo "Output: evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}"
echo ""

uv run swebench-infer "$LLM_CONFIG" \
    --select "$INSTANCES_FILE" \
    --workspace docker \
    --output-dir "./evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}" \
    --max-attempts 3 \
    --max-iterations 200 \
    --max-retries 1 \
    --num-workers "$NUM_WORKERS" \
    --prompt-path benchmarks/swebench/prompts/test_generator_solve.j2 \
    --extra-tools test_generator_v2 \
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

OUTPUT_JSONL="./evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial/output.jsonl"
RESULTS_JSONL="./evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial/results.swebench.jsonl"

if [[ ! -f "$OUTPUT_JSONL" ]] || [[ ! -s "$OUTPUT_JSONL" ]]; then
    ATTEMPT_JSONL="./evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial/output.critic_attempt_1.jsonl"
    if [[ -f "$ATTEMPT_JSONL" ]]; then
        echo "⚠️  output.jsonl 为空，使用 output.critic_attempt_1.jsonl"
        OUTPUT_JSONL="$ATTEMPT_JSONL"
    else
        echo "❌ 找不到输出文件: $OUTPUT_JSONL"; exit 1
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
# Phase 4: Results Summary (与基准对比)
# ============================================

echo ""
echo "=========================================="
echo "Phase 4: Results Summary"
echo "=========================================="
echo ""

python3 << PYEOF
import json, sys

REGRESSION_INSTANCES = [
    "django__django-10973",
    "django__django-11141",
    "django__django-11276",
    "django__django-11790",
    "django__django-11885",
    "django__django-12273",
    "django__django-12406",
    "django__django-15022",
]

results_file = "./evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial/results.swebench.jsonl"
try:
    results = {}
    with open(results_file) as f:
        for line in f:
            data = json.loads(line)
            iid = data.get("instance_id", "?")
            results[iid] = data.get("resolved", False)
except FileNotFoundError:
    print(f"❌ 找不到结果文件: {results_file}")
    sys.exit(0)

# Baselines from previous analysis
baseline_cdfd13b = {iid: True for iid in REGRESSION_INSTANCES}   # 8/8 resolved
baseline_03ee02f = {iid: False for iid in REGRESSION_INSTANCES}  # 0/8 resolved (all regressed)

print("实例对比 (cdfd13b vs 03ee02f_旧 vs 本次_v2改进):")
print(f"{'实例':<35} {'cdfd13b':>10} {'03ee02f旧':>10} {'v2改进':>10}")
print("-" * 70)

resolved_count = 0
for iid in REGRESSION_INSTANCES:
    cdfd = "✓" if baseline_cdfd13b.get(iid) else "✗"
    old  = "✓" if baseline_03ee02f.get(iid) else "✗"
    new  = "✓" if results.get(iid, False) else "✗"
    if results.get(iid, False):
        resolved_count += 1
    print(f"  {iid:<33} {cdfd:>10} {old:>10} {new:>10}")

print("-" * 70)
print(f"  {'合计':<33} {'8/8':>10} {'0/8':>10} {f'{resolved_count}/8':>10}")
print()

if resolved_count == 8:
    print("🎉 完全恢复！改进后的 test_generator_v2 修复了所有退化")
elif resolved_count > 0:
    print(f"✅ 部分恢复：{resolved_count}/8 个退化案例得到修复")
    still_failing = [iid for iid in REGRESSION_INSTANCES if not results.get(iid, False)]
    print(f"   仍然失败 ({8 - resolved_count}):")
    for iid in still_failing:
        print(f"     - {iid}")
else:
    print("❌ 未能恢复：改进后的 prompt 对这些案例仍无效")
PYEOF

echo ""
echo "=========================================="
echo "✓ 完成"
echo "=========================================="
echo ""
echo "结果目录: ./evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}"
echo ""
echo "详细分析请参考:"
echo "  benchmarks/docs/HOW_TO_ANALYZE_SWEBENCH_RESULTS.md"
