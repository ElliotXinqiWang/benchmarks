#!/bin/bash
# Build + Infer script for 4 target tasks with Plan B (Skill-based verification)
# This version uses the /verify-before-submit skill for mandatory verification

set -e  # Exit on error

# ============================================
# Configuration
# ============================================

# Default values
INSTANCES_FILE="instance_set/instances_target_4.txt"
LLM_CONFIG=".llm_config/openrouter.json"
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

# Validate skill file exists
SKILL_FILE=".openhands/skills/verify-before-submit.md"
if [[ ! -f "$SKILL_FILE" ]]; then
    echo "❌ 错误: 找不到 skill 文件: $SKILL_FILE"
    echo "   请先创建这个文件 (参见 docs/PLAN_B_SKILL_BASED.md)"
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
DATASET_SANITIZED=${DATASET_NAME//\\//__}
DATASET_PATH="${DATASET_SANITIZED}-${SPLIT}"
MODEL_PATH_SUFFIX="${MODEL}_sdk_${SDK_SHORT_SHA}_maxiter_200_N_initial"

# Extract subdirectory name from instances file
INSTANCES_SUBDIR=$(basename "$INSTANCES_FILE" .txt)

# ============================================
# Display Configuration
# ============================================

echo "=========================================="
echo "Plan B: Skill-Based Verification"
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
echo "  Skill文件:     $SKILL_FILE ✓"
echo ""
echo "目标任务:"
echo "  1. astropy__astropy-14182  (I/O round-trip)"
echo "  2. django__django-10999    (parse round-trip)"
echo "  3. pydata__xarray-6599     (differential testing)"
echo "  4. pydata__xarray-6992     (operator precedence)"
echo ""
echo "Plan B 机制:"
echo "  ✓ Agent 会看到 /verify-before-submit skill"
echo "  ✓ Prompt 提示 agent 在 finish 前调用该 skill"
echo "  ✓ Skill 展开完整的验证清单"
echo "  ✓ 强制 agent 逐项执行并记录验证结果"
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
# Phase 2: Run Inference with Plan B
# ============================================

echo ""
echo "=========================================="
echo "Phase 2: Running Inference (Plan B - Skill-Based)"
echo "=========================================="
echo ""
echo "Prompt: benchmarks/swebench/prompts/verification_skill_trigger.j2 (强制调用 skill)"
echo "Skill:  .openhands/skills/verify-before-submit.md"
echo "Output: evaluation_results/eval_planb_4tasks/$INSTANCES_SUBDIR"
echo ""

uv run swebench-infer "$LLM_CONFIG" \
    --select "$INSTANCES_FILE" \
    --workspace docker \
    --output-dir "./evaluation_results/eval_planb_4tasks/${INSTANCES_SUBDIR}" \
    --max-attempts 3 \
    --max-iterations 200 \
    --max-retries 1 \
    --num-workers "$NUM_WORKERS" \
    --prompt-path benchmarks/swebench/prompts/verification_skill_trigger.j2 \
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

OUTPUT_JSONL="./evaluation_results/eval_planb_4tasks/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}/output.jsonl"
RESULTS_JSONL="./evaluation_results/eval_planb_4tasks/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}/results.swebench.jsonl"

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
# Phase 4: Results Summary & Skill Analysis
# ============================================

echo ""
echo "=========================================="
echo "Phase 4: Results Summary & Skill Analysis"
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
    echo "=========================================="
    echo "Skill 调用分析:"
    echo "=========================================="
    echo ""

    # Check for skill invocation in conversation logs
    RESULT_DIR="./evaluation_results/eval_planb_4tasks/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}"

    if [[ -d "$RESULT_DIR" ]]; then
        echo "检查各实例是否调用了 /verify-before-submit skill:"
        echo ""

        for instance_dir in "$RESULT_DIR"/*/; do
            if [[ -d "$instance_dir" ]]; then
                instance_name=$(basename "$instance_dir")
                conv_file="$instance_dir/conversation.jsonl"

                if [[ -f "$conv_file" ]]; then
                    # Check if skill was invoked
                    if grep -qi "verify-before-submit\|verify before submit" "$conv_file"; then
                        echo "  ✓ $instance_name: Skill 已调用"
                    else
                        echo "  ✗ $instance_name: Skill 未调用 (可能被忽略)"
                    fi
                else
                    echo "  ? $instance_name: 无 conversation 文件"
                fi
            fi
        done
    else
        echo "未找到结果目录: $RESULT_DIR"
    fi

    echo ""
    echo "下一步:"
    echo "  1. 对比 Plan B 与 Plan A 的 resolved 数量"
    echo "  2. 检查 Skill 调用率与 resolved 率的相关性"
    echo "  3. 查看调用了 skill 的实例是否验证完整"
    echo "  4. 分析未调用 skill 的原因"
    echo ""
    echo "查看 conversation trace 示例:"
    echo "  cd evaluation_results/eval_planb_4tasks/${INSTANCES_SUBDIR}/${DATASET_PATH}/${MODEL_PATH_SUFFIX}"
    echo "  cat astropy__astropy-14182/conversation.jsonl | jq -r '.content' | grep -A50 'verify-before-submit'"
else
    echo "❌ 未找到评测结果文件: $RESULTS_JSONL"
    exit 1
fi

# ============================================
# Completion
# ============================================

echo ""
echo "=========================================="
echo "✓ Plan B 脚本执行完成 (包含评测)"
echo "=========================================="
echo ""
echo "输出目录: evaluation_results/eval_planb_4tasks/${INSTANCES_SUBDIR}"
echo "结果文件: $RESULTS_JSONL"
echo ""
echo "预期效果对比:"
echo "  Baseline (无验证):  0/4 resolved"
echo "  Plan A (prompt注入): 2/4 resolved (预期)"
echo "  Plan B (skill强制):  2-3/4 resolved (预期)"
echo ""
echo "分析重点:"
echo "  1. Skill 调用率: 有多少实例调用了 /verify-before-submit?"
echo "  2. 验证完整性: 调用 skill 的实例是否完整执行了所有检查?"
echo "  3. 效果提升: Plan B 是否比 Plan A 有更高的解题率?"
echo ""
echo "如果 Plan B 效果仍不理想,考虑实施 Tool 版本或 Plan C (对抗性 subagent)"
echo "详见: docs/PLAN_COMPARISON.md 和 docs/targeted_fix_strategy.md"
echo ""
