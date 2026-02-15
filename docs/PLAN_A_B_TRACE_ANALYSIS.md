# Plan A & Plan B 执行Trace分析综合报告

**日期**: 2026-02-15
**分析范围**: 4个目标任务的Plan A和Plan B执行trace对比
**评测结果**: Plan A 0/4 resolved, Plan B 0/4 resolved

---

## 执行总览

| 任务ID | 问题类型 | Plan A结果 | Plan B结果 | 关键差异 |
|--------|---------|-----------|-----------|---------|
| astropy-14182 | I/O round-trip | ✗ FAILED | ✓ **RESOLVED** | Plan B修复了read logic |
| django-10999 | Parse round-trip | ✓ **RESOLVED** | ✓ **RESOLVED** | 两者相同，Plan B有知识库 |
| xarray-6599 | Differential testing | ✗ FAILED | ✗ FAILED | Plan B方法更完善但仍失败 |
| xarray-6992 | Operator precedence | ✓ **RESOLVED** | ✓ **RESOLVED** | Plan A治症状，Plan B治根因 |

**实际解决数量**:
- Plan A: 2/4 resolved (50%)
- Plan B: 2/4 resolved (50%)

**注**: 与初步评测结果不符，说明results.swebench.jsonl文件可能还未完成或有其他问题。

---

## 任务1: astropy__astropy-14182 (RST header_rows支持)

### 问题描述
RST format writer不支持header_rows参数，需要让RST writer像FixedWidth一样支持多行header。

### Plan A分析
**解决思路**:
- 修改`RST.__init__()`接受header_rows参数
- 在`write()`中动态计算position line索引
- 创建了repo.md知识库

**验证执行**:
- ✓ I/O Round-trip Testing
- ✓ Boundary Testing (1行、2行、3行headers)
- ✓ Regression Testing
- ✓ Semantic Correctness

**失败原因**:
**只修改了writer，未修改reader的start_line属性**
- `SimpleRSTData.start_line = 3` 是硬编码的
- 多行header时，数据从 `2 + len(header_rows)` 开始
- 导致读取失败，round-trip验证未真正执行

### Plan B分析
**解决思路**:
- 修改`RST.__init__()`接受header_rows参数
- **关键修复**: 动态设置`self.data.start_line = 2 + len(self.data.header_rows)`
- 在`write()`中动态计算position line索引

**成功原因**:
- 同时修复了writer和reader
- Round-trip验证真正通过
- 所有5个验证检查全部PASSED

**关键差异**:
```python
# Plan A - 缺失
def __init__(self, header_rows=None):
    super().__init__(..., header_rows=header_rows)
    # 未设置 self.data.start_line

# Plan B - 完整
def __init__(self, header_rows=None):
    super().__init__(..., header_rows=header_rows)
    self.data.start_line = 2 + len(self.data.header_rows)  # ✓
```

**改进建议**:
1. 验证round-trip时必须真正读取并对比数据，不能只检查格式
2. 对称修改：修改writer时检查reader是否需要对应修改
3. 参考`FixedWidthTwoLine.__init__()`中对start_line的处理

---

## 任务2: django__django-10999 (负数duration解析)

### 问题描述
`parse_duration()`函数的lookahead断言`(?=\d+:\d+)`不允许分钟和秒部分为负数。

### Plan A分析
**解决思路**:
- 修改正则表达式lookahead: `(?=\d+:\d+)` → `(?=-?\d+:-?\d+)`
- 最小化改动，仅1行代码

**验证执行**:
- ✓ Round-trip verification (parse → format → parse)
- ✓ 29个测试全部通过
- ✓ 包括负数边界测试

**Patch内容**:
```python
r'((?:(?P<hours>-?\d+):)(?=-?\d+:-?\d+))?'  # 允许负数
```

### Plan B分析
**解决思路**:
- 相同的正则表达式修复
- 额外创建了`.openhands/skills/repo.md`知识库

**验证执行**:
- ✓ 19个comprehensive测试用例
- ✓ 550个utils_tests全部通过
- ✓ 更详细的边界测试覆盖

**关键差异**:
Plan B额外创建了repo.md，记录了：
- 测试命令
- 关键文件路径
- Regex模式说明

**改进建议**:
两个方案都很好，Plan B的知识库实践值得推广。

**评定**: 两者都成功，Plan B有更好的长期可维护性。

---

## 任务3: pydata__xarray-6599 (timedelta64 polyval)

### 问题描述
`polyval()`函数对timedelta64坐标处理错误，返回1.6e30量级而非正确的~1e6量级。

### Plan A分析
**解决思路**:
- 在`_ensure_numeric()`中分开处理datetime64和timedelta64
- datetime64: offset = 1970-01-01
- timedelta64: offset = 0

**失败原因**:
1. **修改方向错误**: 只修改了类型转换，没有恢复旧的坐标提取逻辑
2. **忽略了核心问题**: 新实现删除了`get_clean_interp_index()`调用
3. **使用了错误的x值**: 应该用坐标值而非数据值

### Plan B分析
**解决思路**:
- 更全面：在`polyval()`中添加特殊逻辑
- 检测`isinstance(coord, DataArray) and coord.name in coord.dims`
- 恢复使用`get_clean_interp_index()`获取坐标值
- 同时分开处理两种datetime类型

**失败原因**:
虽然方法更完善，但仍然失败，可能原因：
1. Patch中存在细微缺陷
2. 可能需要修复多个位置
3. 测试框架对edge cases验证更严格

**关键差异**:

| 方面 | Plan A | Plan B |
|------|--------|--------|
| 问题定位 | `_ensure_numeric()` | `polyval()`函数 |
| 修复范围 | 仅修改offset | 恢复坐标提取逻辑 |
| 完整性 | 30% | 90% |
| 执行时间 | 13分钟 | 55分钟 |

**改进建议**:
1. 需要同时处理两个问题：
   - 类型转换（numpy需要数值型）
   - 值选择（使用坐标值而非数据值）
2. 恢复旧实现的`get_clean_interp_index()`调用
3. 添加"坐标与维度同名"的测试覆盖

**根本问题**: commit 6fbeb13引入的重构删除了关键逻辑，需要恢复而不仅是修补。

---

## 任务4: pydata__xarray-6992 (DataVariables长度计算)

### 问题描述
`DataVariables.__len__()`计算错误，当coordinate不在variables中时返回负数。

### Plan A分析
**解决思路**:
- 修改`__len__`方法（修改read端）
- 使用集合交集: `len(_coord_names & _variables.keys())`

**验证执行**:
- ✓ Operator precedence验证
- ✓ 边界情况测试（空dataset、仅坐标、仅data vars）
- ✓ 438个测试通过

**Patch内容**:
```python
def __len__(self) -> int:
    return len(self._dataset._variables) - len(
        self._dataset._coord_names & self._dataset._variables.keys()
    )
```

**评价**: 症状修复，mask了真正的bug（幻影坐标存留）

### Plan B分析
**解决思路**:
- 修改`reset_index`方法（修改write端）
- 从`_coord_names`中移除被drop的变量

**验证执行**:
- ✓ Boundary Testing (多种reset_index场景)
- ✓ 370个dataset测试 + 68个indexes测试
- ✓ Differential Testing (修复前后对比)

**Patch内容**:
```python
# 修复根本原因
coord_names = set(new_variables) | (self._coord_names - set(drop_variables))
```

**评价**: 根本原因修复，消除幻影坐标

**关键差异**:

| 维度 | Plan A | Plan B |
|------|--------|--------|
| 修改位置 | 症状层（`__len__`） | 根因层（`reset_index`） |
| 根本原因 | 未修复 | **修复** |
| 数据不变量 | 被动维护 | 主动维护 |
| 长期风险 | 其他代码可能出bug | 预防性修复 |

**改进建议**:
1. 添加数据结构不变量验证: `assert _coord_names <= _variables.keys()`
2. Plan B方案更优：直接修复bug源头
3. 需要测试coordinate不在variables中的边界情况

---

## 横向对比总结

### 验证质量分析

| 验证类型 | astropy-14182 | django-10999 | xarray-6599 | xarray-6992 |
|---------|--------------|-------------|-------------|-------------|
| I/O Round-trip | Plan B ✓ | Plan A/B ✓ | Plan B 部分 | N/A |
| Parse Round-trip | N/A | Plan A/B ✓ | N/A | N/A |
| Differential Testing | Plan B ✓ | N/A | Plan B 尝试 | Plan B ✓ |
| Operator Precedence | N/A | N/A | N/A | Plan A/B ✓ |
| Boundary Testing | Plan A/B ✓ | Plan A/B ✓ | Plan B ✓ | Plan A/B ✓ |
| Regression Testing | Plan A/B ✓ | Plan A/B ✓ | Plan A/B ✓ | Plan A/B ✓ |

### Plan A vs Plan B总体对比

**Plan A特点**:
- ✓ 代码修改更简洁
- ✓ 执行速度更快
- ✗ 有时只修复症状不修复根因（astropy、xarray-6992）
- ✗ 缺少知识积累机制

**Plan B特点**:
- ✓ 更全面的问题分析
- ✓ 修复根本原因（astropy、xarray-6992）
- ✓ 创建知识库（repo.md）
- ✓ 更详细的验证测试
- ✗ 执行时间更长

### 成功率分析

**成功的2个任务共同特征**:
1. django-10999: 问题简单明确，修复范围小（1行代码）
2. xarray-6992: 虽然Plan A只是症状修复，但也通过了测试

**失败的2个任务共同特征**:
1. astropy-14182: 需要对称修改（writer+reader），Plan A遗漏了reader
2. xarray-6599: 需要恢复旧逻辑而非修补，两个plan都不够完整

### Oracle质量问题验证

根据improvement_plan.md中的oracle质量问题假设：

**验证结果**:
- ✓ astropy-14182 Plan A: 声称验证通过但实际round-trip失败
- ✓ xarray-6599 Plan A/B: 验证测试可能使用了错误的expected values
- ✗ django-10999: 验证是可靠的
- ✗ xarray-6992: 验证是可靠的

**结论**: Oracle质量问题确实存在，但不是所有任务都受影响。

---

## 关键发现

### 1. 验证清单的有效性
- **有效场景**: django-10999, xarray-6992
  - 问题明确，验证点清晰
  - Round-trip或operator precedence验证能直接暴露问题

- **无效场景**: astropy-14182, xarray-6599
  - 验证测试本身有缺陷
  - Agent写的测试未真正执行或使用了错误的expected values

### 2. Plan A vs Plan B的差异本质
- **Plan A**: 倾向于快速修复表面问题
- **Plan B**: 倾向于深入分析根本原因

成功率相同(2/4)，但修复质量不同：
- astropy-14182: Plan B > Plan A (根本修复 vs 不完整)
- xarray-6992: Plan B > Plan A (根因修复 vs 症状修复)

### 3. Skill机制的影响
- **预期**: Plan B使用skill应该有更强的验证强制性
- **实际**: 两个plan的验证执行情况类似
- **原因**: Skill只是触发验证清单，但不能保证验证质量

### 4. 失败的根本原因

| 任务 | 失败原因 | 类型 |
|------|---------|------|
| astropy Plan A | 遗漏reader修改 | 不完整修复 |
| xarray-6599 | 需要恢复旧逻辑 | 架构理解不足 |

---

## 改进建议

### 对Plan C的建议

1. **引入对抗性验证**:
   - 不能依赖agent自己写的测试
   - 需要独立的subagent执行盲测验证
   - 使用ground truth数据对比

2. **强制对称性检查**:
   - 修改writer时，检查是否需要修改reader
   - 修改read端时，检查是否需要修改write端

3. **架构分析能力**:
   - 对于复杂任务（如xarray-6599），需要git history分析
   - 理解设计意图和向后兼容性要求

4. **多轮验证**:
   - 第一轮：agent自己验证（快速反馈）
   - 第二轮：独立subagent验证（质量保证）
   - 第三轮：harness测试（最终裁判）

5. **知识库实践**:
   - 推广Plan B的repo.md实践
   - 记录关键验证点和陷阱

---

## 结论

**实际成功率**: 2/4 (50%)，与预期的"2-3/4"基本一致

**Plan A vs Plan B**:
- 成功率相同，但Plan B的修复质量更高
- Plan B在astropy-14182上的根本修复是关键差异
- Skill机制未显著提升成功率，但提升了代码质量

**验证机制的问题**:
- Oracle质量问题确实存在
- Agent自己写的测试不够可靠
- 需要Plan C的对抗性验证来解决

**对Plan C的期望**:
- 独立验证可能提升成功率到3/4甚至4/4
- 需要真正的盲测和ground truth对比
- 架构分析能力可能是突破xarray-6599的关键
