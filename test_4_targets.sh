#!/bin/bash
# Quick test script for the 4 most promising tasks with verification checklist

set -e

echo "=========================================="
echo "Testing 4 Target Tasks with Verification"
echo "=========================================="

# Create instances file with the 4 target tasks
cat > instance_set/instances_target_4.txt << 'EOF'
astropy__astropy-14182
django__django-10999
pydata__xarray-6599
pydata__xarray-6992
EOF

echo "✓ Created instance_set/instances_target_4.txt with 4 target tasks"

# Check if verification checklist exists
if [ ! -f "verification_checklist.md" ]; then
    echo "ERROR: verification_checklist.md not found in current directory"
    exit 1
fi

echo "✓ Found verification_checklist.md"

# Display what will be tested
echo ""
echo "Will test the following tasks:"
echo "  1. astropy__astropy-14182 - RST I/O round-trip issue"
echo "  2. django__django-10999 - duration parse round-trip issue"
echo "  3. pydata__xarray-6599 - polyval differential testing issue"
echo "  4. pydata__xarray-6992 - operator precedence issue"
echo ""

# Show verification strategies that apply
echo "Verification strategies:"
echo "  ✓ Check 1 (I/O Round-trip): astropy-14182, django-10999"
echo "  ✓ Check 2 (Differential): xarray-6599"
echo "  ✓ Check 3 (Operator Precedence): xarray-6992"
echo "  ✓ Check 5 (Regression Testing): ALL"
echo ""

# Recommend next steps
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Inject verification checklist into agent system prompt:"
echo "   → Locate: vendor/software-agent-sdk/openhands-agent/openhands/agent/system_prompt.py"
echo "   → Or: openhands/runtime/prompt/system_prompt.py (depending on structure)"
echo "   → Add: Content from verification_checklist.md to agent's base prompt"
echo ""
echo "2. Run the evaluation:"
echo "   uv run swebench-infer .llm_config/openrouter.json \\"
echo "       --select instance_set/instances_target_4.txt \\"
echo "       --workspace docker \\"
echo "       --output-dir ./evaluation_results/eval_verification_test \\"
echo "       --max-attempts 3 \\"
echo "       --max-iterations 200 \\"
echo "       --num-workers 4 \\"
echo "       --n-limit 4"
echo ""
echo "3. Compare results:"
echo "   → Baseline: 0/4 resolved (from improvement_plan.md)"
echo "   → Target (conservative): 2-3/4 resolved"
echo "   → Target (optimistic): 4/4 resolved"
echo ""
echo "4. Analyze conversation traces:"
echo "   → Check if agent executed verification checklist before calling finish"
echo "   → Check if agent discovered missing tests (round-trip, differential, etc.)"
echo "   → Check if agent modified patch based on verification failures"
echo ""
echo "=========================================="
echo "File Locations:"
echo "=========================================="
echo "  • Instances list: instance_set/instances_target_4.txt"
echo "  • Verification checklist: verification_checklist.md"
echo "  • Detailed strategy: targeted_fix_strategy.md"
echo "  • Output directory: evaluation_results/eval_verification_test/"
echo ""
echo "=========================================="
echo "Key Implementation Notes:"
echo "=========================================="
echo ""
echo "CRITICAL: The verification checklist must be injected into the agent's"
echo "system prompt BEFORE running the evaluation. This requires modifying"
echo "the OpenHands agent code."
echo ""
echo "Suggested injection point:"
echo "  In the agent's base system prompt, add:"
echo "  \"Before calling the finish tool, you MUST complete the"
echo "   Pre-submission Verification Checklist. See details below.\""
echo ""
echo "Then append the full verification_checklist.md content."
echo ""
echo "Alternative (if direct prompt injection is complex):"
echo "  Create a skill /verify-before-submit that expands to the checklist"
echo "  Require agent to call this skill before finish"
echo ""
echo "=========================================="

# Optional: Show the tasks in detail
echo ""
read -p "Show detailed task information? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "=========================================="
    echo "Task Details from improvement_plan.md:"
    echo "=========================================="
    echo ""
    echo "1. astropy-14182:"
    echo "   - Error: 只修了 RST 写入逻辑，没修读取逻辑"
    echo "   - Agent验证: 做了MVCE(写入) + 158个write测试，全pass"
    echo "   - 问题: 只测了写入，从未测读取"
    echo "   - 解决: Check 1 强制round-trip测试"
    echo ""
    echo "2. django-10999:"
    echo "   - Error: 只改了duration正则允许负号，没改解析逻辑传播负值"
    echo "   - Agent验证: 自建复现脚本 + 550个utils测试，全pass"
    echo "   - 问题: 只检查parse返回非None，没验证round-trip"
    echo "   - 解决: Check 1 强制format→parse→format一致性"
    echo ""
    echo "3. xarray-6599:"
    echo "   - Error: timedelta数据用最小值作offset导致polyval参考点偏移"
    echo "   - Agent验证: MVCE + 263个computation测试，全pass"
    echo "   - 问题: 只用MVCE数据，没做差分测试"
    echo "   - 解决: Check 2 强制与numpy.polyval对比"
    echo ""
    echo "4. xarray-6992:"
    echo "   - Error: `a - b | c` 运算符优先级bug，缺少 `(a - b) | c` 的括号"
    echo "   - Agent验证: MVCE + 370+442个dataset/array测试，全pass"
    echo "   - 问题: MVCE恰好没触发运算符优先级问题"
    echo "   - 解决: Check 3 强制用非空交集测试优先级"
    echo ""
fi

echo ""
echo "=========================================="
echo "Ready to implement!"
echo "=========================================="
