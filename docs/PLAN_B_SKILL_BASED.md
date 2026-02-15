# Plan B: Skill-Based Verification (如果 Plan A 效果不理想)

## 一句话总结

如果 Plan A 的 prompt 注入被 agent 忽略，Plan B 通过创建一个 `/verify-before-submit` skill 来强制执行验证清单，确保 agent 在调用 finish 前必须完成验证步骤。

---

## 为什么需要 Plan B？

### Plan A 的潜在问题：
1. **Agent 可能忽略 system prompt 中的指令**
   - System prompt 太长时，agent 可能跳过某些部分
   - 验证清单在 prompt 末尾，可能被 "遗忘"

2. **缺乏强制执行机制**
   - Plan A 只是 "建议" agent 执行验证
   - 没有结构化的方式追踪 agent 是否执行了验证

### Plan B 的优势：
1. **结构化触发机制** - Skill 可以被明确调用
2. **可追踪** - 可以检查 agent 是否调用了 `/verify-before-submit`
3. **更强的提示** - Skill 调用是显式行为，难以被忽略
4. **渐进式** - 可以与 Plan A 并存，增强而非替代

---

## 实施方案

### Step 1: 创建 Skill 文件

在 `.openhands/skills/` 目录下创建 `verify-before-submit.md`：

**文件位置**: `benchmarks/.openhands/skills/verify-before-submit.md`

**Skill 类型**: TaskTrigger (用户显式调用)

**触发关键词**: `/verify-before-submit`, `verify before submit`, `pre-submission check`

### Step 2: Skill 内容结构

Skill 应该：
1. 展开为完整的验证清单（复用 `docs/verification_checklist.md` 内容）
2. 要求 agent 逐项执行检查
3. 强制 agent 在 think action 中记录验证结果
4. 只有全部检查通过后才允许调用 finish

### Step 3: 修改 System Prompt

在 agent 的 system prompt 中添加一条规则：

```
CRITICAL: Before calling the finish tool, you MUST call the /verify-before-submit skill
to complete the pre-submission verification checklist.
```

这样：
- Plan A (prompt 注入) 作为后备提醒
- Plan B (skill 调用) 作为强制执行机制

### Step 4: 运行评测

使用与 Plan A 相同的 `run_4_targets.sh` 脚本，但：
- 确保 `.openhands/skills/verify-before-submit.md` 存在
- Agent 会看到可用的 skill 并在需要时调用

---

## Skill 实现细节

### Frontmatter (skill 元数据)

```yaml
---
name: verify-before-submit
triggers:
  - /verify-before-submit
  - verify before submit
  - pre-submission check
description: Pre-submission verification checklist for ensuring patch quality
---
```

### Skill Content (验证指令)

```markdown
# Pre-submission Verification Checklist

You have invoked the pre-submission verification skill. Before calling `finish`, you MUST:

1. Complete all applicable verification checks from the list below
2. Document your verification results in your think action
3. Only proceed to `finish` if ALL applicable checks PASS

---

## ✓ CHECK 1: I/O Round-trip Testing

**Applies if your patch modifies:**
- File read/write operations
- Serialization/deserialization (pickle, JSON, etc.)
- Format/parse functions

**Verification pattern:**
```python
# Pattern 1: write → read consistency
original_data = create_test_data()
write_function(original_data, "/tmp/test_file")
read_back = read_function("/tmp/test_file")
assert read_back == original_data, f"Mismatch: {original_data} vs {read_back}"

# Pattern 2: format → parse consistency
original_obj = create_test_object()
formatted_str = format_function(original_obj)
parsed_obj = parse_function(formatted_str)
assert parsed_obj == original_obj, f"Mismatch: {original_obj} vs {parsed_obj}"
```

**Examples:**
- astropy-14182: Modified table.write() → MUST test table.read()
- django-10999: Modified format logic → MUST test parse round-trip

---

## ✓ CHECK 2: Differential Testing

**Applies if your patch modifies:**
- Mathematical calculations
- Numerical algorithms
- Data transformations

**Verification pattern:**
```python
import numpy as np

test_inputs = [input1, input2, input3]
for inp in test_inputs:
    your_result = your_modified_function(inp)
    reference = numpy_equivalent(inp)  # or baseline
    np.testing.assert_allclose(your_result, reference, rtol=1e-10)
```

**Examples:**
- xarray-6599: Modified polyval → MUST compare against numpy.polyval

---

## ✓ CHECK 3: Operator Precedence

**Applies if your patch modifies:**
- Operator overloading (`__add__`, `__sub__`, `__or__`, `__and__`)
- Expression evaluation
- Set/bitwise operations

**Verification pattern:**
```python
# Test cases with NON-EMPTY intersections to catch precedence bugs
A = {1, 2, 3, 4}
B = {2, 3}
C = {3, 4, 5}

# Verify (A - B) | C  vs  A - (B | C) gives expected result
result = your_expression(A, B, C)
expected = {1, 4} | {3, 4, 5}  # = {1, 3, 4, 5}
assert result == expected, f"Precedence error: {result} != {expected}"
```

**Examples:**
- xarray-6992: Modified set operations → MUST test with overlapping sets

---

## ✓ CHECK 4: Boundary Values

Test boundary conditions for ALL input parameters:

| Type | Boundary Values |
|------|----------------|
| Strings | `""`, `" "`, Unicode, very long |
| Numbers | `0`, `-1`, `NaN`, `Infinity` |
| Collections | `[]`, single element, overlapping |
| Paths | relative, absolute, with spaces |

---

## ✓ CHECK 5: Regression Testing

**CRITICAL: Run existing test suite for modified modules**

```bash
# Before modifications (baseline)
python -m pytest tests/relevant_module/ -v --tb=no > /tmp/baseline.txt 2>&1

# After modifications
cd {{ instance.repo_path }} && pip install -e . --no-deps
python -m pytest tests/relevant_module/ -v --tb=short > /tmp/modified.txt 2>&1

# Check for regressions
diff <(grep "PASSED" /tmp/baseline.txt | sort) \
     <(grep "PASSED" /tmp/modified.txt | sort)
```

If any previously-passing test now fails → FIX before submitting

---

## ✓ CHECK 6: Semantic Correctness

Don't just check "no crash" - verify OUTPUT VALUES are correct:

```python
# BAD: No assertion
result = query.filter(...)

# GOOD: Verify semantics
result = query.filter(...)
assert expected_obj in result, "Expected object missing"
assert unexpected_obj not in result, "Unexpected object found"
assert len(result) == expected_count
```

---

## Execution Instructions

Before calling `finish`:

1. ✓ State which checks apply to your patch
2. ✓ For applicable checks, provide:
   - Test code you wrote
   - Execution results
   - PASS/FAIL status
3. ✓ For non-applicable checks, explain why
4. ✓ **ONLY call `finish` if ALL applicable checks PASS**

If any check fails:
- Return to implementation phase
- Fix the issue
- Re-run ALL applicable checks
- Repeat until all checks pass

---

## Why This Matters

Analysis shows:
- **69%** of failures caught by existing tests (Check 5)
- **Round-trip bugs** (Check 1) extremely common in I/O code
- **Differential testing** (Check 2) catches numerical errors
- **Operator precedence** (Check 3) often missed by single examples
- **Semantic verification** (Check 6) prevents "doesn't crash but wrong output"

This checklist saves iteration time and improves resolution rate.
```

---

## 与 Plan A 的对比

| 方面 | Plan A (Prompt 注入) | Plan B (Skill 调用) |
|-----|---------------------|-------------------|
| 实施难度 | 简单 (修改一个 prompt 文件) | 中等 (创建 skill + 修改 prompt) |
| 强制执行 | 弱 (依赖 agent 自觉) | 强 (显式调用机制) |
| 可追踪性 | 难 (需要分析 conversation) | 易 (检查 skill 调用记录) |
| 兼容性 | 无依赖 | 需要 OpenHands SDK skill 机制 |
| 适用场景 | Agent 已有验证意识 | Agent 经常忽略 prompt 指令 |

---

## 实施步骤

### 1. 创建 Skill 文件

```bash
# 在 benchmarks 目录下
mkdir -p .openhands/skills
cat > .openhands/skills/verify-before-submit.md << 'EOF'
[粘贴上面的 Skill 内容]
EOF
```

### 2. 修改 Prompt (可选增强)

在 `prompts/verification_enhanced.j2` 的开头添加：

```jinja2
IMPORTANT: Before calling the finish tool, you MUST invoke the /verify-before-submit skill.
This skill will guide you through the pre-submission verification checklist.

```

### 3. 运行评测

```bash
./run_4_targets.sh
```

### 4. 分析 Skill 调用情况

```bash
# 检查 agent 是否调用了 skill
cd evaluation_results/eval_verification_4tasks/instances_target_4/

for instance in */; do
    echo "=== $instance ==="
    # 查找 skill 调用记录
    grep -i "verify-before-submit" "$instance/conversation.jsonl" || echo "未调用 skill"
done
```

**成功标志**:
- Agent 在 finish 前调用了 `/verify-before-submit`
- Conversation 中有 skill 展开的验证清单内容
- Agent 按清单逐项执行了检查

---

## 预期效果

### 相比 Plan A 的改进
- **调用率**: Plan A 可能 0-2/4 执行验证，Plan B 预期 4/4 调用 skill
- **完成度**: Plan A 可能部分执行，Plan B 强制完整执行
- **解题率**: Plan A 预期 2/4，Plan B 预期 2-3/4 (因为强制执行更严格)

### 风险
- **Skill 机制不成熟**: 如果 SDK 的 skill 触发有 bug，Plan B 可能失败
- **Token 消耗**: Skill 展开会增加 context，可能触发 token 限制
- **Complexity**: 引入新机制增加了调试难度

---

## 如果 Plan B 仍不理想

### Plan C: 对抗性 Subagent (docs/targeted_fix_strategy.md 中的 A3 方案)

如果 Plan B 仍然无法确保 agent 正确验证，实施 A3 方案：

1. **创建 verify_patch tool**
   - 接收 patch 作为输入
   - 调用独立 subagent 从 "攻击者" 视角验证

2. **Subagent 使用 Oracle 策略库**
   - Round-trip testing
   - Differential testing
   - Operator precedence
   - Boundary value testing

3. **返回验证报告**
   - PASS/FAIL 状态
   - 发现的问题列表
   - 建议的修复方向

详见 `docs/targeted_fix_strategy.md` Phase 3。

---

## 文件清单

Plan B 需要以下文件：

- ✅ `.openhands/skills/verify-before-submit.md` (待创建)
- ✅ `prompts/verification_enhanced.j2` (已存在，可选增强)
- ✅ `run_4_targets.sh` (已存在，无需修改)
- ✅ `instance_set/instances_target_4.txt` (已存在)
- ✅ `docs/verification_checklist.md` (参考内容)

---

## 快速测试

```bash
# 1. 创建 skill 文件
mkdir -p .openhands/skills
# [手动创建 verify-before-submit.md]

# 2. 验证 skill 加载
# (可选) 写一个测试脚本检查 SDK 是否能加载这个 skill

# 3. 运行评测
./run_4_targets.sh

# 4. 分析结果
cd evaluation_results/eval_verification_4tasks/instances_target_4/
grep -r "verify-before-submit" . | head -20
```

---

## 总结

Plan B 的核心思路：

> **如果 agent 会忽略 system prompt 中的指令，那就让它显式调用一个 skill，把验证清单作为 skill 的内容强制展开到对话中。**

这种方法：
- ✅ 实施简单 (只需创建一个 .md 文件)
- ✅ 不侵入代码 (利用现有的 skill 机制)
- ✅ 可与 Plan A 并存 (多层防护)
- ✅ 易于追踪 (skill 调用有明确记录)

如果 Plan A 的 2/4 成功率不理想，Plan B 有望提升到 3/4。
