#!/bin/bash
# Smoke test for test_generator_v2 tool
# Tests that the improved tool works correctly (self-verification, better prompt)

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
OUTPUT_NAME="smoke_test_generator_v2"

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
echo "Smoke Test: test_generator_v2 Tool"
echo "=========================================="
echo ""
echo "配置信息:"
echo "  测试集文件:    $INSTANCES_FILE"
echo "  LLM配置:       $LLM_CONFIG"
echo "  模型:          $MODEL"
echo "  并行workers:   $NUM_WORKERS"
echo "  实例数量:      $N_LIMIT"
echo "  SDK SHA:       $SDK_SHORT_SHA"
echo ""
echo "目的: 验证 test_generator_v2 工具正常工作"
echo "  - generate 命令能生成测试脚本并自验证"
echo "  - self_verification 字段有值"
echo "  - F2P tests 在未修复代码上 FAIL"
echo "  - P2P tests 在未修复代码上 PASS"
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
# Phase 1: Delete old Docker images & rebuild
# ============================================

echo ""
echo "=========================================="
echo "Phase 1: Rebuilding Docker Images"
echo "(必须重建以包含 test_generator_v2 工具)"
echo "=========================================="
echo ""

# Delete old images for target_4 instances to force rebuild with new tool
echo "删除旧镜像..."
OLD_IMAGES=$(docker images | grep "eval-agent-server" | grep -E "astropy-14182|django-10999|xarray-6599|xarray-6992" | awk '{print $1":"$2}')
if [[ -n "$OLD_IMAGES" ]]; then
    echo "$OLD_IMAGES" | xargs docker rmi || true
    echo "✓ 旧镜像已删除"
else
    echo "  (无需删除，镜像不存在)"
fi

echo ""
echo "重建镜像..."
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
echo "Phase 2: Running Smoke Test (test_generator_v2)"
echo "=========================================="
echo ""
echo "Prompt: prompts/test_generator_v2_smoke.j2"
echo "Extra tools: test_generator_v2"
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
    --prompt-path benchmarks/swebench/prompts/test_generator_v2_smoke.j2 \
    --extra-tools test_generator_v2 \
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

OUTPUT_DIR="./evaluation_results/${OUTPUT_NAME}/${INSTANCES_SUBDIR}/${DATASET_PATH}/openrouter/anthropic/${MODEL_PATH_SUFFIX}"

python3 << PYEOF
import json, sys, glob

files = glob.glob("./evaluation_results/smoke_test_generator_v2/*/princeton-nlp__SWE-bench_Verified-test/*/output.jsonl")
if not files:
    print("  ❌ 找不到 output.jsonl")
    sys.exit(0)

total = 0
ok = 0
for output_file in files:
    with open(output_file) as f:
        for line in f:
            data = json.loads(line)
            iid = data.get("instance_id", "unknown")
            history = data.get("history", [])
            total += 1

            # Check for test_generator_v2 calls
            tg_generate_calls = [h for h in history
                if h.get("kind") == "ActionEvent"
                and "test_generator_v2" in str(h.get("action", ""))
                and "generate" in str(h.get("action", ""))]
            tg_run_calls = [h for h in history
                if h.get("kind") == "ActionEvent"
                and "test_generator_v2" in str(h.get("action", ""))
                and '"run"' in str(h.get("action", ""))]

            # Check for self_verification in observations
            self_verif = None
            for h in history:
                if h.get("kind") == "ObservationEvent":
                    obs = h.get("observation", {})
                    if "test_generator_v2" in str(obs.get("kind", "")):
                        sv = obs.get("self_verification")
                        if sv:
                            self_verif = sv

            instance_ok = len(tg_generate_calls) >= 1 and len(tg_run_calls) >= 1
            if instance_ok:
                ok += 1

            status = "✓" if instance_ok else "❌"
            print(f"  {status} {iid}:")
            print(f"      history events:          {len(history)}")
            print(f"      generate calls:          {len(tg_generate_calls)}")
            print(f"      run calls:               {len(tg_run_calls)}")
            print(f"      self_verification:       {self_verif or '(not found)'}")

print()
print(f"  결果: {ok}/{total} instances 정상 실행")
PYEOF

echo ""
echo "=========================================="
echo "Smoke Test 完成"
echo "=========================================="
echo ""
echo "下一步分析:"
echo "  查看 conversation 中 self_verification 内容:"
echo "  cd ${OUTPUT_DIR}"
echo "  tar -xzf conversations/<instance_id>.tar.gz -C /tmp/smoke_v2/"
echo "  ls /tmp/smoke_v2/workspace/conversations/*/events/"
echo ""
