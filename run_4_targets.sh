#!/bin/bash
# Build + Infer script for 4 target tasks with verification checklist
# Based on hard_script.sh structure

set -e  # Exit on error

# ============================================
# Configuration
# ============================================

# Default values
INSTANCES_FILE="instance_set/instances_target_4.txt"
# INSTANCES_FILE="instance_set/instances_hard.txt"
LLM_CONFIG=".llm_config/openrouter_opus.json"
DATASET_NAME="princeton-nlp/SWE-bench_Verified"
SPLIT="test"
NUM_WORKERS=4
N_LIMIT=4

# Parse command line arguments
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
        -d|--dataset)
            DATASET_NAME="$2"
            shift 2
            ;;
        -w|--workers)
            NUM_WORKERS="$2"
            shift 2
            ;;
        -n|--n-limit)
            N_LIMIT="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  -i, --instances <文件>    指定测试集文件 (默认: instance_set/instances_target_4.txt)"
            echo "  -l, --llm-config <文件>   指定LLM配置文件 (默认: .llm_config/openrouter.json)"
            echo "  -d, --dataset <名称>      指定数据集名称 (默认: princeton-nlp/SWE-bench_Verified)"
            echo "  -w, --workers <数量>      并行worker数 (默认: 4)"
            echo "  -n, --n-limit <数量>      处理的实例数量限制 (默认: 4)"
            echo "  -h, --help                显示帮助信息"
            echo ""
            echo "示例:"
            echo "  $0                                    # 使用默认配置"
            echo "  $0 -w 2 -n 2                          # 只跑2个worker,处理2个实例"
            echo "  $0 -l .llm_config/openrouter_opus.json  # 使用不同的LLM配置"
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            echo "使用 -h 或 --help 查看帮助信息"
            exit 1
            ;;
    esac
done

# ============================================
# Validate Dependencies
# ============================================

if ! command -v jq &> /dev/null; then
    echo "❌ 错误: 需要安装 jq 来解析 JSON 配置文件"
    echo "   安装: brew install jq  (macOS) 或 apt-get install jq (Linux)"
    exit 1
fi

if [[ ! -f "$LLM_CONFIG" ]]; then
    echo "❌ 错误: 找不到 LLM 配置文件: $LLM_CONFIG"
    exit 1
fi

if [[ ! -f "$INSTANCES_FILE" ]]; then
    echo "❌ 错误: 找不到实例文件: $INSTANCES_FILE"
    exit 1
fi

# ============================================
# Extract Configuration
# ============================================

MODEL=$(jq -r '.model' "$LLM_CONFIG")
if [[ -z "$MODEL" || "$MODEL" == "null" ]]; then
    echo "❌ 错误: 无法从配置文件中读取 model 字段"
    exit 1
fi

# Get SDK submodule short SHA
SDK_SHA=$(git submodule status vendor/software-agent-sdk | awk '{print $1}' | sed 's/^[+-]*//')
SDK_SHORT_SHA="${SDK_SHA:0:7}"

# Build output path components
DATASET_SANITIZED=${DATASET_NAME//\//__}
DATASET_PATH="${DATASET_SANITIZED}-${SPLIT}"
# Extract model provider and name (e.g., openrouter/anthropic/claude-sonnet-4)
MODEL_SANITIZED=${MODEL//\//__}
MODEL_PATH_SUFFIX="${MODEL_SANITIZED}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial"

# Extract subdirectory name from instances file
INSTANCES_SUBDIR=$(basename "$INSTANCES_FILE" .txt)

# ============================================
# Display Configuration
# ============================================

echo "=========================================="
echo "4 Target Tasks - Verification Enhanced"
echo "=========================================="
echo ""
echo "配置信息:"
echo "  测试集文件:    $INSTANCES_FILE"
echo "  LLM配置:       $LLM_CONFIG"
echo "  模型:          $MODEL"
echo "  数据集:        $DATASET_NAME"
echo "  并行workers:   $NUM_WORKERS"
echo "  实例数量限制:  $N_LIMIT"
echo "  SDK版本:       $SDK_SHORT_SHA"
echo "  输出子目录:    $INSTANCES_SUBDIR"
echo ""
echo "目标任务:"
echo "  1. astropy__astropy-14182  (I/O round-trip)"
echo "  2. django__django-10999    (parse round-trip)"
echo "  3. pydata__xarray-6599     (differential testing)"
echo "  4. pydata__xarray-6992     (operator precedence)"
echo ""
echo "增强验证清单:"
echo "  ✓ Check 1: I/O Round-trip Testing"
echo "  ✓ Check 2: Differential Testing"
echo "  ✓ Check 3: Operator Precedence"
echo "  ✓ Check 4: Boundary Values"
echo "  ✓ Check 5: Regression Testing"
echo "  ✓ Check 6: Semantic Correctness"
echo ""
echo "=========================================="

# Confirm before proceeding
read -p "继续执行? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消。"
    exit 0
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

if [[ $? -ne 0 ]]; then
    echo "❌ Docker镜像构建失败"
    exit 1
fi

echo "✓ Docker镜像构建完成"

# ============================================
# Phase 2: Run Inference with Verification
# ============================================

echo ""
echo "=========================================="
echo "Phase 2: Running Inference (Verification Enhanced)"
echo "=========================================="
echo ""
echo "Prompt: prompts/verification_enhanced.j2"
echo "Output: evaluation_results/eval_verification_4tasks/$INSTANCES_SUBDIR"
echo ""

uv run swebench-infer "$LLM_CONFIG" \
    --select "$INSTANCES_FILE" \
    --workspace docker \
    --output-dir "./evaluation_results/eval_verification_4tasks/${INSTANCES_SUBDIR}" \
    --max-attempts 3 \
    --max-iterations 200 \
    --max-retries 1 \
    --num-workers "$NUM_WORKERS" \
    --prompt-path benchmarks/swebench/prompts/verification_enhanced.j2 \
    --n-limit "$N_LIMIT"

if [[ $? -ne 0 ]]; then
    echo "❌ 推理执行失败"
    exit 1
fi

echo "✓ 推理执行完成"

# ============================================
# Phase 3: Evaluation
# ============================================

echo ""
echo "=========================================="
echo "Phase 3: Running SWE-bench Evaluation"
echo "=========================================="
echo ""

OUTPUT_JSONL="./evaluation_results/eval_verification_4tasks/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}/output.jsonl"
RESULTS_JSONL="./evaluation_results/eval_verification_4tasks/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}/results.swebench.jsonl"

if [[ ! -f "$OUTPUT_JSONL" ]]; then
    echo "❌ 错误: 找不到输出文件: $OUTPUT_JSONL"
    exit 1
fi

echo "输入文件: $OUTPUT_JSONL"
echo "输出文件: $RESULTS_JSONL"
echo ""

uv run swebench-eval "$OUTPUT_JSONL" \
    --dataset "$DATASET_NAME" \
    --output-file "$RESULTS_JSONL" \
    --workers "$NUM_WORKERS"

if [[ $? -ne 0 ]]; then
    echo "❌ 评测执行失败"
    exit 1
fi

echo "✓ 评测执行完成"

# ============================================
# Phase 4: Results Summary
# ============================================

echo ""
echo "=========================================="
echo "Phase 4: Results Summary"
echo "=========================================="
echo ""

# Display patch generation results
echo "Patch 生成情况:"
python3 << 'EOF'
import json
import sys

output_file = sys.argv[1] if len(sys.argv) > 1 else None
if not output_file:
    sys.exit(0)

try:
    with open(output_file, 'r') as f:
        for line in f:
            data = json.loads(line)
            instance_id = data.get('instance_id', 'unknown')
            model_patch = data.get('model_patch', '')
            has_patch = 'Yes' if model_patch and model_patch.strip() else 'No'
            patch_size = len(model_patch) if model_patch else 0
            print(f"  {instance_id}: Patch={has_patch} ({patch_size} bytes)")
except Exception as e:
    print(f"Error reading output: {e}", file=sys.stderr)
EOF
python3 -c "import sys; sys.exit(0)" "$OUTPUT_JSONL"

echo ""

# Display evaluation results
if [[ -f "$RESULTS_JSONL" ]]; then
    echo "=========================================="
    echo "评测结果 (SWE-bench):"
    echo "=========================================="
    echo ""

    # Parse and display results
    python3 << 'EOF'
import json
import sys

results_file = sys.argv[1] if len(sys.argv) > 1 else None
if not results_file:
    sys.exit(0)

try:
    resolved_count = 0
    total_count = 0
    results_list = []

    with open(results_file, 'r') as f:
        for line in f:
            data = json.loads(line)
            instance_id = data.get('instance_id', 'unknown')
            resolved = data.get('resolved', False)
            total_count += 1
            if resolved:
                resolved_count += 1
            results_list.append((instance_id, resolved))

    for instance_id, resolved in results_list:
        status = '✓ RESOLVED' if resolved else '✗ FAILED'
        print(f"  {instance_id}: {status}")

    print("")
    print(f"总结: {resolved_count}/{total_count} resolved ({resolved_count*100//total_count if total_count > 0 else 0}%)")
except Exception as e:
    print(f"Error reading results: {e}", file=sys.stderr)
EOF
python3 -c "import sys; sys.exit(0)" "$RESULTS_JSONL"

    echo ""
    echo "下一步:"
    echo "  1. 分析 resolved 的题目是否符合预期 (目标: 2-4/4)"
    echo "  2. 查看 conversation traces 确认 agent 是否执行了验证清单"
    echo "  3. 如果 < 2/4，运行 Plan B: ./run_4_targets_planb.sh"
    echo ""
    echo "查看 conversation trace 示例:"
    echo "  cd evaluation_results/eval_verification_4tasks/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}"
    echo "  cat astropy__astropy-14182/conversation.jsonl | jq -r '.content' | grep -i 'round-trip'"
else
    echo "❌ 未找到评测结果文件: $RESULTS_JSONL"
    exit 1
fi

# ============================================
# Completion
# ============================================

echo ""
echo "=========================================="
echo "✓ Plan A 脚本执行完成 (包含评测)"
echo "=========================================="
echo ""
echo "输出目录: evaluation_results/eval_verification_4tasks/${INSTANCES_SUBDIR}"
echo "结果文件: $RESULTS_JSONL"
echo ""
echo "预期效果对比:"
echo "  Baseline (无验证):  0/4 resolved"
echo "  Plan A (保守预期):  2/4 resolved (50%)"
echo "  Plan A (乐观预期):  4/4 resolved (100%)"
echo ""
echo "如果结果 < 2/4，建议运行 Plan B: ./run_4_targets_planb.sh"
echo ""
