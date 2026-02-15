# Quick Start: 针对4个最有希望题目的改进方案

## 一句话总结

通过在agent的system prompt中注入**验证清单**,强制agent在提交前执行round-trip、差分测试和运算符优先级检查,预期可将这4题的解题率从0/4提升到2-4/4。

---

## 背景

根据`improvement_plan.md`的分析,以下4题是最有希望通过prompt改进解决的:

| Task ID | 问题类型 | Agent当前做了什么 | 为什么失败 | 需要什么验证 |
|---------|---------|----------------|-----------|------------|
| astropy-14182 | I/O round-trip | 测了158个write测试 | **只测写,没测读** | Round-trip: write→read |
| django-10999 | Parse round-trip | 测了550个utils测试 | **只检查非None,没验证round-trip** | Round-trip: format→parse |
| xarray-6599 | 差分测试 | 用MVCE数据测试 | **没与numpy对比** | Differential: vs numpy.polyval |
| xarray-6992 | 运算符优先级 | 用MVCE测试 | **恰好没触发优先级bug** | Precedence: 非空交集case |

**共同模式**: Agent用issue的MVCE作为唯一oracle,只验证了问题的一面。

**根本原因**: Agent缺乏结构化的验证思维,不知道应该测什么。

---

## 解决方案: 验证清单注入

### 核心思路

在agent的system prompt中注入一个**Pre-submission Verification Checklist**,包含6大检查项:

1. ✓ **I/O Round-trip测试** (覆盖astropy-14182, django-10999)
2. ✓ **差分测试** (覆盖xarray-6599)
3. ✓ **运算符优先级** (覆盖xarray-6992)
4. ✓ **边界值测试** (通用)
5. ✓ **回归测试** (运行已有测试)
6. ✓ **语义正确性** (不只检查"不崩溃")

Agent在调用`finish`前,**必须**在think action中逐项确认这些检查。

---

## 实施步骤

### Step 1: 注入验证清单到agent系统prompt

**位置查找** (按可能性排序):
```bash
# Option 1: Agent SDK中的system prompt
find vendor/software-agent-sdk -name "*system*prompt*.py" -type f

# Option 2: OpenHands runtime中的prompt
find vendor/software-agent-sdk -name "prompt*.py" -type f

# Option 3: LLM配置中的system_message
grep -r "system.*prompt\|system.*message" .llm_config/
```

**注入内容**:

将`verification_checklist.md`的内容添加到agent的base system prompt末尾,或在调用finish之前的位置注入:

```python
# Pseudocode示例
agent_system_prompt = f"""
{base_system_prompt}

...

## CRITICAL: Pre-submission Verification

Before you call the finish tool, you MUST complete the verification checklist below.

{open('verification_checklist.md').read()}
"""
```

### Step 2: 运行4题评测

```bash
# 创建instances文件 (已由test_4_targets.sh创建)
# instance_set/instances_target_4.txt 包含:
#   astropy__astropy-14182
#   django__django-10999
#   pydata__xarray-6599
#   pydata__xarray-6992

# 运行评测
uv run swebench-infer .llm_config/openrouter.json \
    --select instance_set/instances_target_4.txt \
    --workspace docker \
    --output-dir ./evaluation_results/eval_verification_test \
    --max-attempts 3 \
    --max-iterations 200 \
    --num-workers 4 \
    --n-limit 4
```

### Step 3: 分析结果

```bash
# 查看结果汇总
cat evaluation_results/eval_verification_test/*/report.json | \
    python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    print(f\"{r['instance_id']}: {r.get('resolved', 'N/A')}\")
"

# 期望: 2-4个resolved (vs 当前 0/4)
```

### Step 4: 分析conversation traces (验证agent行为)

```bash
# 解压并查看agent是否执行了验证
cd evaluation_results/eval_verification_test/astropy__astropy-14182/

# 检查agent在finish前是否做了round-trip测试
grep -i "round.trip\|write.*read\|read.*write" conversation.json

# 检查agent是否发现了遗漏的测试
grep -i "verify\|check.*read\|test.*read" conversation.json
```

**成功标志**:
- Agent在finish前的think action中提到了验证清单
- Agent编写并执行了之前遗漏的测试(如read测试)
- Agent因验证失败而修改了patch
- 最终patch resolved

---

## 预期效果

### 保守估计
- **2/4 题 resolved** (50% 成功率)
- 覆盖: astropy-14182 (round-trip最明显) + xarray-6599 (differential有numpy参考)

### 乐观估计
- **4/4 题 resolved** (100% 成功率)
- 全部覆盖,因为验证清单直接对应每题的缺失验证

### 风险
- Agent执行力: Agent可能读了清单但不严格执行
- Token限制: 额外验证可能消耗更多iterations
- 复杂环境: 某些测试可能需要特殊环境设置

---

## 如果效果不理想

### Plan B: 创建Skill而非直接注入

如果发现agent忽略了system prompt中的验证清单,可以:

1. 创建一个`/verify-before-submit` skill
2. 在agent准备调用finish时,要求它先调用这个skill
3. Skill展开为验证清单 + 强制执行

**优势**: 更结构化,可追踪是否调用

### Plan C: 使用Subagent对抗性验证 (A3方案)

如果A1验证清单仍不够,实施A3方案:
- 创建verify_patch tool
- 调用独立subagent从"攻击者"视角验证
- Subagent使用结构化的oracle策略库

详见`targeted_fix_strategy.md`的Phase 3。

---

## 文件索引

- **验证清单** (可直接注入): `verification_checklist.md`
- **详细策略文档**: `targeted_fix_strategy.md`
- **测试脚本**: `test_4_targets.sh`
- **Instance列表**: `instance_set/instances_target_4.txt`
- **错误分析报告**: `improvement_plan.md`
- **Subagent使用指南**: `subagent_methodology.md`

---

## 快速测试

```bash
# 1. 查看测试脚本会做什么
./test_4_targets.sh

# 2. (手动) 注入验证清单到agent system prompt
#    → 找到system prompt文件
#    → 添加verification_checklist.md内容

# 3. 运行评测 (上面的uv run命令)

# 4. 查看结果
ls -la evaluation_results/eval_verification_test/*/report.json
```

---

## 成功后的扩展

如果4/4成功,可以将验证清单应用到更大范围:

1. **扩展到全部instances_hard** (100题)
   - 预期: 从61/98提升到68-76/98 (+7到+15题)

2. **添加到默认agent配置**
   - 让所有SWE-bench评测都默认使用验证清单

3. **结合A2 (差分测试) 和 A3 (对抗性subagent)**
   - 形成分层防御: A1静态检查 + A2回归检测 + A3对抗验证
   - 预期: 可覆盖14个"中等"task中的10-12个

---

## 理论基础

根据`improvement_plan.md`的深度分析:

- **4个"高"可解决的task**: 存在无需领域知识的通用oracle
- **Agent行为模式**: 4/4都属于"agent做了验证但oracle太弱"
- **验证清单的价值**: 告诉agent去测什么,而非让agent自己决定
- **不需要fuzz工具**: 这4题只需结构化的思维框架,不需要额外工具

**关键洞察**:
> Agent不是不会写测试,而是不知道应该写什么测试。
> 验证清单弥合了"agent自然会做的"和"应该做的"之间的gap。

---

## 联系人 & 反馈

如有问题或发现改进空间,请记录在:
- 项目issue tracker
- 或更新本文档的"已知问题"部分

预祝成功! 🎯
