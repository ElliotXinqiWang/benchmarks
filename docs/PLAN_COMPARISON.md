# Plan A vs Plan B: 验证策略对比

## 快速决策指南

**先运行 Plan A**:
- 实施简单 (只修改 prompt)
- 成本低 (无额外机制)
- 预期 2/4 成功

**如果 Plan A < 2/4，再尝试 Plan B**:
- 强制执行验证清单
- 可追踪 skill 调用
- 预期 2-3/4 成功

**如果 Plan B 仍不理想，升级到 Plan C**:
- 对抗性 subagent 验证
- 详见 `targeted_fix_strategy.md`

---

## 详细对比

| 维度 | Plan A (Prompt 注入) | Plan B (Skill 强制) | Plan C (Subagent 验证) |
|-----|---------------------|-------------------|---------------------|
| **实施难度** | ⭐ 简单 | ⭐⭐ 中等 | ⭐⭐⭐ 复杂 |
| **修改文件** | 1个 (prompt.j2) | 2个 (prompt + skill) | 5+ (tools + subagent) |
| **依赖** | 无 | OpenHands SDK skills | SDK + subagent 机制 |
| **强制执行** | ❌ 弱 (靠自觉) | ✅ 中 (显式调用) | ✅✅ 强 (独立验证) |
| **可追踪性** | ❌ 难 | ✅ 易 (skill 调用记录) | ✅✅ 完整 (验证报告) |
| **Token 消耗** | 低 | 中 (skill 展开) | 高 (subagent 对话) |
| **预期成功率** | 2/4 (50%) | 2-3/4 (50-75%) | 3-4/4 (75-100%) |
| **失败风险** | Agent 忽略 prompt | Agent 不调用 skill | Subagent 逻辑错误 |
| **调试难度** | 简单 | 中等 | 复杂 |
| **扩展性** | ❌ 难扩展 | ✅ 可复用 skill | ✅✅ 通用框架 |

---

## Plan A: Prompt 注入

### 实施方式

在 `prompts/verification_enhanced.j2` 中直接添加验证清单内容。

### 优点
- ✅ 实施简单，只需修改一个文件
- ✅ 无额外依赖，兼容所有环境
- ✅ Token 消耗低
- ✅ 适合 agent 已有验证意识的情况

### 缺点
- ❌ 缺乏强制执行，agent 可能跳过
- ❌ System prompt 太长时容易被忽略
- ❌ 难以追踪 agent 是否真正执行了验证
- ❌ 验证质量依赖 agent 的自觉性

### 适用场景
- Agent 通常会遵循 system prompt 指令
- 任务相对简单，验证步骤明确
- 预算有限，希望最小化 token 消耗

### 运行方式
```bash
./run_4_targets.sh
```

### 验证方法
```bash
# 检查 agent 在 conversation 中是否提到了验证
cd evaluation_results/eval_verification_4tasks/instances_target_4/
grep -ri "round.trip\|differential\|operator precedence" */conversation.jsonl
```

---

## Plan B: Skill 强制调用

### 实施方式

1. 创建 `.openhands/skills/verify-before-submit.md` skill
2. 在 prompt 中提示 agent 在 finish 前调用 `/verify-before-submit`
3. Skill 展开完整的验证清单

### 优点
- ✅ 结构化触发机制，更显式
- ✅ 可追踪 skill 调用记录
- ✅ Skill 内容独立维护，易于更新
- ✅ 可与 Plan A 并存，多层防护
- ✅ 调用 skill 是显式行为，难以被忽略

### 缺点
- ❌ 依赖 SDK 的 skill 机制
- ❌ Agent 仍可能选择不调用 skill
- ❌ Skill 展开会增加 token 消耗
- ❌ 需要额外的 skill 文件管理

### 适用场景
- Plan A 效果不理想 (agent 经常忽略 prompt)
- 希望有明确的验证调用记录
- 环境支持 OpenHands SDK skills
- 预算允许适度增加 token 消耗

### 运行方式
```bash
./run_4_targets_planb.sh
```

### 验证方法
```bash
# 检查 agent 是否调用了 skill
cd evaluation_results/eval_planb_4tasks/instances_target_4/
grep -ri "verify-before-submit" */conversation.jsonl

# 统计调用率
for d in */; do
    if grep -qi "verify-before-submit" "$d/conversation.jsonl" 2>/dev/null; then
        echo "✓ $d"
    else
        echo "✗ $d"
    fi
done
```

---

## Plan C: 对抗性 Subagent (未实施)

### 实施方式

详见 `docs/targeted_fix_strategy.md` Phase 3 (A3 方案)

1. 创建 `verify_patch` tool
2. Tool 接收 patch，调用独立 subagent
3. Subagent 使用 oracle 策略库验证
4. 返回 PASS/FAIL + 问题列表

### 优点
- ✅✅ 强制执行，agent 无法跳过
- ✅✅ 独立验证，避免 agent 自我欺骗
- ✅✅ 可积累 oracle 策略库
- ✅✅ 通用框架，可扩展到更多任务

### 缺点
- ❌❌ 实施复杂，需要开发 tool
- ❌❌ Token 消耗高 (subagent 对话)
- ❌❌ 延长执行时间
- ❌ Subagent 逻辑本身可能有 bug

### 适用场景
- Plan A + Plan B 均失败
- 高价值任务，值得投入更多成本
- 需要可复用的验证框架
- 预算充足

---

## 实验流程建议

### 阶段 1: 快速验证 Plan A

```bash
# 1. 运行 Plan A
./run_4_targets.sh

# 2. 查看结果
cd evaluation_results/eval_verification_4tasks/instances_target_4/
cat */output.jsonl | jq -r '.instance_id + ": " + (.model_patch | length | tostring)'

# 3. 分析 conversation (抽样)
cat astropy__astropy-14182/conversation.jsonl | jq -r '.content' | grep -i "round-trip"
```

**成功标准**: 2/4 或以上 resolved

**如果 < 2/4**: 进入阶段 2

---

### 阶段 2: 强化执行 Plan B

```bash
# 1. 确认 skill 文件存在
ls -la .openhands/skills/verify-before-submit.md

# 2. 运行 Plan B
./run_4_targets_planb.sh

# 3. 对比结果
diff <(ls evaluation_results/eval_verification_4tasks/instances_target_4/*/output.jsonl) \
     <(ls evaluation_results/eval_planb_4tasks/instances_target_4/*/output.jsonl)

# 4. 分析 skill 调用率
cd evaluation_results/eval_planb_4tasks/instances_target_4/
grep -r "verify-before-submit" . | wc -l
```

**成功标准**: 3/4 或以上 resolved，且 skill 调用率 > 75%

**如果仍 < 2/4**: 考虑 Plan C

---

### 阶段 3: (如需要) 实施 Plan C

详见 `docs/targeted_fix_strategy.md` Phase 3。

关键步骤：
1. 设计 oracle 策略库
2. 实现 verify_patch tool
3. 编写 subagent prompt
4. 测试验证逻辑
5. 集成到 inference pipeline

---

## 成本效益分析

### Plan A
- **开发成本**: 1 小时 (修改 prompt)
- **运行成本**: 基准 token 消耗
- **维护成本**: 低 (只有一个文件)
- **预期收益**: 2/4 题 (vs 0/4 baseline) = +50%

### Plan B
- **开发成本**: 2-3 小时 (创建 skill + 测试)
- **运行成本**: 基准 +10-20% token (skill 展开)
- **维护成本**: 中 (skill 文件 + prompt)
- **预期收益**: 2-3/4 题 = +50-75%

### Plan C
- **开发成本**: 1-2 天 (tool 开发 + subagent 设计)
- **运行成本**: 基准 +50-100% token (subagent 对话)
- **维护成本**: 高 (tool + oracle 库 + subagent)
- **预期收益**: 3-4/4 题 = +75-100%

---

## 决策树

```
开始
 │
 ├─ Agent 通常遵循 prompt? ──YES──> Plan A
 │                         └─NO─┐
 │                              │
 ├─ 预算充足，可以增加 20% token? ──YES──> Plan B
 │                                    └─NO─┐
 │                                         │
 ├─ 高价值任务，值得深度投入? ──YES──> Plan C
 │                             └─NO──> 优化 prompt 或接受现状
 │
 └─ 不确定? ──> 先试 Plan A，不满意再升级
```

---

## 文件清单

### Plan A
- ✅ `prompts/verification_enhanced.j2`
- ✅ `run_4_targets.sh`
- ✅ `instance_set/instances_target_4.txt`
- ✅ `docs/verification_checklist.md` (参考)

### Plan B (在 Plan A 基础上)
- ✅ `.openhands/skills/verify-before-submit.md`
- ✅ `run_4_targets_planb.sh`
- ✅ `docs/PLAN_B_SKILL_BASED.md`

### Plan C (未实施)
- ⬜ `tools/verify_patch.py`
- ⬜ `oracles/` (策略库目录)
- ⬜ `subagents/verification_agent.py`
- ⬜ 详见 `docs/targeted_fix_strategy.md`

---

## 常见问题

### Q: Plan A 和 Plan B 可以同时运行吗？
A: 可以！它们是互补的：
- Plan A: 在 prompt 中提醒
- Plan B: 提供显式 skill 调用机制
- 一起使用可以形成多层防护

### Q: 如何判断应该用哪个 Plan？
A: 先看 agent 的行为模式：
- Agent 通常遵循 prompt → Plan A
- Agent 经常忽略 prompt → Plan B
- Agent 完全不可控 → Plan C

### Q: Plan B 的 skill 会自动被调用吗？
A: 不会！Skill 需要：
1. Agent 看到 prompt 中的提示
2. Agent 主动调用 `/verify-before-submit`
3. Skill 展开后 agent 执行验证

如果 agent 连 skill 都不调用，需要 Plan C。

### Q: 三个 Plan 的 token 消耗差异有多大？
A: 粗略估计：
- Plan A: 基准 (100%)
- Plan B: 基准 +10-20% (skill 展开)
- Plan C: 基准 +50-100% (subagent 对话)

### Q: 如果 4 题全部失败怎么办？
A: 可能原因：
1. Prompt 设计有问题 → 优化 prompt
2. LLM 模型能力不足 → 换更强的模型
3. 验证清单不适用这些题 → 重新分析失败原因
4. 基础设施问题 → 检查 Docker/环境配置

---

## 总结

| Plan | 何时使用 | 一句话总结 |
|------|---------|-----------|
| **A** | 默认选择 | 在 prompt 中注入验证清单，依赖 agent 自觉执行 |
| **B** | A 失败时 | 创建 skill 显式触发验证，增强提示 |
| **C** | B 仍失败 | 独立 subagent 对抗性验证，强制执行 |

**建议路径**: A → (如不满意) → B → (如仍不满意) → C

这样可以在成本和效果之间找到最佳平衡点。
