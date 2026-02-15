# 文档索引

这个目录包含了针对 4 个最有希望题目的改进方案文档。

## 快速开始

**新用户? 从这里开始:**

1. **[QUICK_START_4_TASKS.md](QUICK_START_4_TASKS.md)** - 5分钟快速上手指南
   - 背景介绍
   - 解决方案概述
   - 实施步骤

2. **[PLAN_COMPARISON.md](PLAN_COMPARISON.md)** - Plan A vs Plan B 对比
   - 决策指南
   - 详细对比表
   - 实验流程建议

---

## 核心文档

### 策略设计

- **[targeted_fix_strategy.md](targeted_fix_strategy.md)** - 完整的改进策略
  - 4个目标任务分析
  - A1/A2/A3 三层方案设计
  - 实施路线图和预期效果

- **[verification_checklist.md](verification_checklist.md)** - 验证清单内容
  - 6大验证检查项
  - 可直接注入到 prompt
  - 包含代码示例和最佳实践

### 实施方案

- **[PLAN_B_SKILL_BASED.md](PLAN_B_SKILL_BASED.md)** - Plan B 详细文档
  - Skill 创建指南
  - 与 Plan A 的对比
  - 实施步骤和验证方法

- **[PLAN_COMPARISON.md](PLAN_COMPARISON.md)** - 多方案对比
  - Plan A/B/C 完整对比
  - 决策树和建议路径
  - 成本效益分析

---

## 背景分析

- **[SUBAGENT_TOOL_USAGE.md](SUBAGENT_TOOL_USAGE.md)** - Subagent 使用指南
  - 何时使用 subagent
  - 最佳实践
  - 常见陷阱

- **[THREE_VERSION_COMPARISON_REPORT.md](THREE_VERSION_COMPARISON_REPORT.md)** - 版本对比报告
  - Claude-3.5 Sonnet vs Opus 4.5 vs Opus 4.6
  - 性能分析
  - 关键发现

---

## 文件结构树

```
docs/
├── README.md                              # 本文档
├── QUICK_START_4_TASKS.md                 # ⭐ 快速开始
├── PLAN_COMPARISON.md                     # ⭐ Plan 对比
├── targeted_fix_strategy.md               # 完整策略
├── verification_checklist.md              # 验证清单
├── PLAN_B_SKILL_BASED.md                 # Plan B 详解
├── SUBAGENT_TOOL_USAGE.md                # Subagent 指南
└── THREE_VERSION_COMPARISON_REPORT.md    # 版本对比

../
├── prompts/
│   └── verification_enhanced.j2           # Plan A prompt
├── .openhands/skills/
│   └── verify-before-submit.md            # Plan B skill
├── instance_set/
│   └── instances_target_4.txt             # 4个目标任务
├── run_4_targets.sh                       # Plan A 脚本
└── run_4_targets_planb.sh                 # Plan B 脚本
```

---

## 使用流程

### 第一次使用 (推荐 Plan A)

1. 阅读 [QUICK_START_4_TASKS.md](QUICK_START_4_TASKS.md)
2. 查看 [verification_checklist.md](verification_checklist.md) 了解验证内容
3. 运行 `../run_4_targets.sh`
4. 分析结果

### 如果 Plan A 效果不理想

1. 阅读 [PLAN_COMPARISON.md](PLAN_COMPARISON.md) 了解 Plan B
2. 阅读 [PLAN_B_SKILL_BASED.md](PLAN_B_SKILL_BASED.md) 了解实施细节
3. 确认 `.openhands/skills/verify-before-submit.md` 存在
4. 运行 `../run_4_targets_planb.sh`
5. 对比两次运行的结果

### 如果需要更深入的改进

1. 阅读 [targeted_fix_strategy.md](targeted_fix_strategy.md) 了解 A3 方案
2. 考虑实施对抗性 subagent 验证
3. 参考 [SUBAGENT_TOOL_USAGE.md](SUBAGENT_TOOL_USAGE.md)

---

## 常见问题

### Q: 我应该先看哪个文档？
A: 按顺序阅读：
1. QUICK_START_4_TASKS.md (了解背景)
2. PLAN_COMPARISON.md (选择方案)
3. 对应的实施文档 (Plan A 或 Plan B)

### Q: Plan A 和 Plan B 有什么区别？
A:
- **Plan A**: 在 prompt 中注入验证清单，依赖 agent 自觉执行
- **Plan B**: 创建 skill 强制触发验证，更结构化

详见 [PLAN_COMPARISON.md](PLAN_COMPARISON.md)

### Q: 4个目标任务是哪些？
A:
1. astropy__astropy-14182 (I/O round-trip)
2. django__django-10999 (parse round-trip)
3. pydata__xarray-6599 (differential testing)
4. pydata__xarray-6992 (operator precedence)

详见 [QUICK_START_4_TASKS.md](QUICK_START_4_TASKS.md)

### Q: 验证清单包含哪些检查？
A: 6大检查项：
1. I/O Round-trip Testing
2. Differential Testing
3. Operator Precedence
4. Boundary Values
5. Regression Testing
6. Semantic Correctness

详见 [verification_checklist.md](verification_checklist.md)

### Q: 预期能解决几个题？
A:
- **Baseline** (无验证): 0/4
- **Plan A**: 2/4 (保守预期)
- **Plan B**: 2-3/4
- **Plan C** (对抗性 subagent): 3-4/4

### Q: 如果 4 题都失败了怎么办？
A: 可能需要：
1. 检查 prompt 是否正确注入
2. 查看 conversation logs 分析 agent 行为
3. 确认 LLM 模型配置正确
4. 考虑升级到更强的 Plan (B → C)

---

## 贡献指南

如果你发现文档有误或需要补充：

1. 直接编辑对应的 .md 文件
2. 更新本 README.md 的索引 (如果添加了新文档)
3. 确保文档间的交叉引用正确

---

## 相关资源

### 项目根目录文档
- `../README.md` - Benchmarks 主文档
- `../prompts/verification_enhanced.j2` - Plan A 使用的 prompt
- `../.openhands/skills/verify-before-submit.md` - Plan B 使用的 skill

### 上游项目
- [OpenHands](https://github.com/OpenHands/OpenHands) - Agent 框架
- [SWE-bench](https://www.swebench.com/) - 评测数据集

---

## 文档版本

- **创建日期**: 2026-02-15
- **最后更新**: 2026-02-15
- **适用范围**: 4个最有希望题目的改进方案

---

## 许可证

这些文档与父项目使用相同的许可证。

---

**提示**: 如果你不确定从哪里开始，直接运行 `../run_4_targets.sh` 试试 Plan A！
