# Plan A & Plan B 实施总结

## 已完成的工作

### 1. 文档整理
✅ 将所有策略文档移动到 `docs/` 目录，便于管理和查找

### 2. Plan A 实现 (Prompt 注入方式)

**核心思路**: 在 prompt 中注入验证清单，依赖 agent 自觉执行

#### 创建的文件:

```
prompts/verification_enhanced.j2
├── 基于 default_install.j2
├── 添加了完整的 6 点验证清单
└── 包含详细的执行要求和示例代码

run_4_targets.sh
├── Build + Infer 脚本
├── 使用 verification_enhanced.j2 作为 prompt
└── 输出到 evaluation_results/eval_verification_4tasks/

instance_set/instances_target_4.txt
└── 包含 4 个目标任务 ID
```

#### 运行方式:
```bash
./run_4_targets.sh
```

#### 预期效果:
- **保守**: 2/4 resolved (50%)
- **乐观**: 4/4 resolved (100%)

---

### 3. Plan B 实现 (Skill 强制调用方式)

**核心思路**: 创建 `/verify-before-submit` skill，通过显式调用强制执行验证

#### 创建的文件:

```
.openhands/skills/verify-before-submit.md
├── Frontmatter 定义触发关键词
├── 完整的 6 点验证清单
└── 强制执行要求

run_4_targets_planb.sh
├── Build + Infer 脚本 (Plan B 版本)
├── 检查 skill 文件是否存在
├── 分析 skill 调用情况
└── 输出到 evaluation_results/eval_planb_4tasks/
```

#### 运行方式:
```bash
./run_4_targets_planb.sh
```

#### 预期效果:
- **保守**: 2/4 resolved (50%)
- **乐观**: 3/4 resolved (75%)

---

### 4. 文档体系

#### docs/ 目录结构:

```
docs/
├── README.md                              # 📚 文档索引和使用指南
├── QUICK_START_4_TASKS.md                 # 🚀 5分钟快速上手
├── PLAN_COMPARISON.md                     # 📊 Plan A/B/C 详细对比
├── PLAN_B_SKILL_BASED.md                 # 📖 Plan B 完整文档
├── targeted_fix_strategy.md               # 🎯 完整改进策略
├── verification_checklist.md              # ✅ 验证清单内容
├── SUBAGENT_TOOL_USAGE.md                # 🤖 Subagent 使用指南
└── THREE_VERSION_COMPARISON_REPORT.md    # 📈 版本对比报告
```

#### 关键文档说明:

- **README.md**: 文档导航，新用户从这里开始
- **QUICK_START_4_TASKS.md**: 背景介绍 + 快速上手
- **PLAN_COMPARISON.md**: 三个 Plan 的详细对比和决策指南
- **PLAN_B_SKILL_BASED.md**: Plan B 的完整实施文档

---

## 文件清单

### 核心实现文件

| 文件 | Plan | 用途 |
|-----|------|-----|
| `prompts/verification_enhanced.j2` | A | 增强的 prompt 模板 |
| `.openhands/skills/verify-before-submit.md` | B | 验证 skill |
| `instance_set/instances_target_4.txt` | A/B | 4个目标任务列表 |
| `run_4_targets.sh` | A | Plan A 运行脚本 |
| `run_4_targets_planb.sh` | B | Plan B 运行脚本 |

### 文档文件

| 文件 | 类型 | 用途 |
|-----|------|-----|
| `docs/README.md` | 索引 | 文档导航 |
| `docs/QUICK_START_4_TASKS.md` | 指南 | 快速上手 |
| `docs/PLAN_COMPARISON.md` | 对比 | Plan 选择指南 |
| `docs/PLAN_B_SKILL_BASED.md` | 详解 | Plan B 文档 |
| `docs/targeted_fix_strategy.md` | 策略 | 完整改进方案 |
| `docs/verification_checklist.md` | 参考 | 验证清单详情 |
| `docs/SUBAGENT_TOOL_USAGE.md` | 指南 | Subagent 最佳实践 |
| `docs/THREE_VERSION_COMPARISON_REPORT.md` | 分析 | 版本对比 |

---

## 快速开始

### 新用户推荐路径

1. **阅读文档** (5-10分钟)
   ```bash
   # 打开文档索引
   cat docs/README.md

   # 快速上手指南
   cat docs/QUICK_START_4_TASKS.md

   # Plan 对比 (如果想了解选择哪个)
   cat docs/PLAN_COMPARISON.md
   ```

2. **运行 Plan A** (推荐先试这个)
   ```bash
   ./run_4_targets.sh
   ```

3. **查看结果**
   ```bash
   cd evaluation_results/eval_verification_4tasks/instances_target_4/
   ls -la
   ```

4. **如果效果不理想，运行 Plan B**
   ```bash
   ./run_4_targets_planb.sh
   ```

---

## 验证清单内容概览

两个 Plan 都使用相同的验证清单，包含 6 大检查项:

### ✓ CHECK 1: I/O Round-trip Testing
- **目标任务**: astropy-14182, django-10999
- **验证**: write → read 一致性，format → parse 一致性

### ✓ CHECK 2: Differential Testing
- **目标任务**: xarray-6599
- **验证**: 与 numpy 等参考实现对比

### ✓ CHECK 3: Operator Precedence
- **目标任务**: xarray-6992
- **验证**: 运算符优先级，使用非空交集测试

### ✓ CHECK 4: Boundary Values
- **所有任务**
- **验证**: 边界值和特殊值测试

### ✓ CHECK 5: Regression Testing
- **所有任务**
- **验证**: 运行已有测试，检查回归

### ✓ CHECK 6: Semantic Correctness
- **所有任务**
- **验证**: 输出值正确性，不只是"不崩溃"

---

## 实施难度对比

| Plan | 实施时间 | 文件数 | Token 消耗 | 强制执行 |
|------|---------|-------|-----------|---------|
| **A** | 30分钟 | 3 | 基准 | ❌ 弱 |
| **B** | 1小时 | 5 | +10-20% | ✅ 中 |
| **C** | 1-2天 | 10+ | +50-100% | ✅✅ 强 |

---

## 预期效果分析

### 4个目标任务的失败原因

| Task ID | 问题类型 | Agent 做了什么 | 为什么失败 | 对应检查 |
|---------|---------|--------------|-----------|---------|
| astropy-14182 | I/O round-trip | 测了158个write测试 | 只测写,没测读 | CHECK 1 |
| django-10999 | Parse round-trip | 测了550个utils测试 | 只检查非None,没验证round-trip | CHECK 1 |
| xarray-6599 | 差分测试 | 用MVCE数据测试 | 没与numpy对比 | CHECK 2 |
| xarray-6992 | 运算符优先级 | 用MVCE测试 | 恰好没触发优先级bug | CHECK 3 |

### 预期改进

| Baseline | Plan A | Plan B | Plan C (未实施) |
|----------|--------|--------|----------------|
| 0/4 (0%) | 2/4 (50%) | 2-3/4 (50-75%) | 3-4/4 (75-100%) |

---

## 验证方法

### Plan A 验证

```bash
# 检查 agent 是否在 conversation 中提到验证
cd evaluation_results/eval_verification_4tasks/instances_target_4/
grep -ri "round.trip\|differential\|precedence" */conversation.jsonl | head -20

# 查看某个实例的详细 conversation
cat astropy__astropy-14182/conversation.jsonl | jq -r '.content' | less
```

### Plan B 验证

```bash
# 检查 skill 调用情况
cd evaluation_results/eval_planb_4tasks/instances_target_4/
for d in */; do
    if grep -qi "verify-before-submit" "$d/conversation.jsonl" 2>/dev/null; then
        echo "✓ $d: Skill 已调用"
    else
        echo "✗ $d: Skill 未调用"
    fi
done

# 统计调用率
skill_called=$(grep -rl "verify-before-submit" */conversation.jsonl 2>/dev/null | wc -l)
total=$(ls -d */ | wc -l)
echo "Skill 调用率: $skill_called/$total"
```

---

## 下一步

### 如果 Plan A/B 成功 (2-4/4 resolved)

1. **扩展到更多任务**
   - 应用到全部 hard_instances (100题)
   - 预期: +7 到 +15 题

2. **集成到默认配置**
   - 让所有 SWE-bench 评测默认使用验证清单

3. **结合其他方案**
   - A1 (静态检查) + A2 (回归测试) + A3 (对抗验证)

### 如果 Plan A/B 失败 (< 2/4 resolved)

1. **分析失败原因**
   - Agent 是否看到了验证清单?
   - Agent 是否尝试执行验证?
   - 验证清单是否适用这些任务?

2. **考虑 Plan C**
   - 实施对抗性 subagent 验证
   - 详见 `docs/targeted_fix_strategy.md` Phase 3

3. **优化 Prompt**
   - 简化验证清单
   - 增强提示语
   - 添加示例

---

## 技术细节

### Skill 机制 (Plan B)

OpenHands SDK 的 Skill 系统支持三种触发方式:

1. **None (always active)** - 始终加载到 context
2. **KeywordTrigger** - 关键词触发
3. **TaskTrigger** - 任务触发，支持用户输入

Plan B 使用 **TaskTrigger**:
- 触发词: `/verify-before-submit`
- Agent 需要显式调用
- Skill 展开后注入到对话中

### Prompt 结构 (Plan A)

`verification_enhanced.j2` 结构:

1. Phase 1-8: 原始 `default_install.j2` 的内容
2. **新增部分**: Pre-submission Verification Checklist
   - 标记为 CRITICAL
   - 6 大检查项详细说明
   - 执行要求和示例代码

---

## 常见问题

### Q: Plan A 和 Plan B 可以同时使用吗?
**A**: 可以！它们是互补的。Plan A 在 prompt 中提醒，Plan B 提供显式调用机制。

### Q: 为什么不直接用 Plan C?
**A**: Plan C 实施复杂度高，成本高。先用低成本方案 (A/B) 验证思路，确认有效后再投入 Plan C。

### Q: 如果 4 题全失败怎么办?
**A**: 可能原因:
1. Prompt 注入位置不对
2. LLM 模型配置错误
3. 基础设施问题 (Docker/环境)
4. 验证清单不适用

先检查 conversation logs 分析 agent 行为。

### Q: Token 消耗会增加多少?
**A**:
- Plan A: 几乎无增加 (验证清单约 3-4K tokens)
- Plan B: +10-20% (skill 展开)

### Q: 需要修改代码吗?
**A**: 不需要！两个 Plan 都只修改配置文件:
- Plan A: prompt 文件
- Plan B: prompt + skill 文件

---

## 贡献

如果你有改进建议或发现问题:

1. 更新对应的文档
2. 运行测试验证
3. 提交改进

---

## 许可证

与父项目相同。

---

**最后更新**: 2026-02-15

**状态**: ✅ Plan A 和 Plan B 已完全实现，可以开始测试

**建议**: 先运行 Plan A (`./run_4_targets.sh`)，如果效果不理想再试 Plan B (`./run_4_targets_planb.sh`)
