#!/bin/bash
# Smoke test for test_generator tool
# Tests that the tool works correctly, NOT that it solves issues

set -e

# ============================================
# Configuration
# ============================================

INSTANCES_FILE="instance_set/instances_target_4.txt"
LLM_CONFIG=".llm_config/openrouter_opus.json"
DATASET_NAME="princeton-nlp/SWE-bench_Verified"
SPLIT="test"
NUM_WORKERS=4
N_LIMIT=4
OUTPUT_NAME="smoke_test_generator"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -w|--workers) NUM_WORKERS="$2"; shift 2 ;;
        -n|--n-limit) N_LIMIT="$2"; shift 2 ;;
        -l|--llm-config) LLM_CONFIG="$2"; shift 2 ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo "  -w, --workers <数量>      并行worker数 (默认: 4)"
            echo "  -n, --n-limit <数量>      实例数量限制 (默认: 4)"
            echo "  -l, --llm-config <文件>   LLM配置 (默认: .llm_config/openrouter_opus.json)"
            exit 0 ;;
        *) echo "未知选项: $1"; exit 1 ;;
    esac
done

# ============================================
# Validate
# ============================================

if ! command -v jq &> /dev/null; then
    echo "❌ 需要安装 jq"
    exit 1
fi

if [[ ! -f "$LLM_CONFIG" ]]; then
    echo "❌ 找不到 LLM 配置文件: $LLM_CONFIG"
    exit 1
fi

# ============================================
# Extract Configuration
# ============================================

MODEL=$(jq -r '.model' "$LLM_CONFIG")
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
echo "Smoke Test: test_generator Tool"
echo "=========================================="
echo ""
echo "配置信息:"
echo "  测试集文件:    $INSTANCES_FILE"
echo "  LLM配置:       $LLM_CONFIG"
echo "  模型:          $MODEL"
echo "  并行workers:   $NUM_WORKERS"
echo "  实例数量:      $N_LIMIT"
echo ""
echo "目的: 验证 test_generator 工具正常工作"
echo "  - generate 命令能生成测试脚本"
echo "  - run 命令能执行测试脚本"
echo "  - F2P/P2P 分类正确"
echo ""
echo "=========================================="

if [[ "${SKIP_CONFIRM:-0}" != "1" ]]; then
    read -p "继续执行? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消。"
        exit 0
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
echo "Phase 2: Running Smoke Test (test_generator)"
echo "=========================================="
echo ""
echo "Prompt: prompts/test_generator_smoke.j2"
echo "Extra tools: test_generator"
echo "Output: evaluation_results/${OUTPUT_NAME}/$INSTANCES_SUBDIR"
echo ""

uv run swebench-infer "$LLM_CONFIG" \
    --select "$INSTANCES_FILE" \
    --workspace docker \
    --output-dir "./evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}" \
    --max-attempts 1 \
    --max-iterations 100 \
    --max-retries 1 \
    --num-workers "$NUM_WORKERS" \
    --prompt-path benchmarks/swebench/prompts/test_generator_smoke.j2 \
    --extra-tools test_generator \
    --n-limit "$N_LIMIT"

echo "✓ Smoke test 执行完成"

# ============================================
# Phase 3: Check Results
# ============================================

echo ""
echo "=========================================="
echo "Phase 3: Results Check"
echo "=========================================="
echo ""

OUTPUT_DIR="./evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}"

if [[ -f "${OUTPUT_DIR}/output.jsonl" ]]; then
    echo "✓ output.jsonl 已生成"
    echo ""
    echo "每个instance的状态:"
    python3 << 'PYEOF'
import json, sys

output_file = "./evaluation_results/smoke_test_generator/instances_target_4/princeton-nlp__SWE-bench_Verified-test/"
import glob
files = glob.glob("./evaluation_results/smoke_test_generator/*/princeton-nlp__SWE-bench_Verified-test/*/output.jsonl")
if not files:
    print("  ❌ 找不到output.jsonl")
    sys.exit(0)

for output_file in files:
    with open(output_file) as f:
        for line in f:
            data = json.loads(line)
            iid = data.get("instance_id", "unknown")
            history = data.get("history", [])

            # Check if test_generator was called
            tg_calls = [h for h in history if "test_generator" in str(h.get("action", ""))]
            patch = data.get("model_patch", "")

            print(f"  {iid}:")
            print(f"    history events: {len(history)}")
            print(f"    test_generator calls: {len(tg_calls)}")
            print(f"    has patch: {'Yes' if patch and patch.strip() else 'No'}")
PYEOF
else
    echo "❌ output.jsonl 未生成"
fi

echo ""
echo "=========================================="
echo "Smoke Test 完成"
echo "=========================================="
echo ""
echo "下一步:"
echo "  1. 解压 conversations/*.tar.gz 查看 agent 对话历史"
echo "  2. 检查 test_generator 工具是否被正确调用"
echo "  3. 检查生成的测试脚本质量"
echo ""
echo "查看conversation的命令:"
echo "  cd ${OUTPUT_DIR}"
echo "  tar -xzf conversations/<instance_id>.tar.gz -C /tmp/smoke/"
echo "  ls /tmp/smoke/workspace/conversations/*/events/"
echo ""
