# 针对4个最有希望题目的定向改进策略

## 背景

基于improvement_plan.md的分析,以下4题是最有希望通过prompt改进解决的:
- astropy-14182 (I/O round-trip)
- django-10999 (parse round-trip)
- xarray-6599 (差分测试)
- xarray-6992 (运算符优先级)

这4题的共同特征:**Agent做了验证但oracle太弱,只测了MVCE展示的一面**。

---

## 策略1: 增强Pre-submission验证清单 (推荐)

### 实施方式

在agent的system prompt中注入一个**Pre-submission Verification Skill**,在调用`finish`前强制自查。

### 验证清单内容

```markdown
## CRITICAL: Pre-submission Verification (Must Complete Before Calling finish)

在你调用 finish 工具提交patch之前,你**必须**完成以下验证,并在think action中逐项确认。

---

### ✓ 验证项1: I/O和序列化的Round-trip测试

**如果你的修改涉及:**
- 文件读写 (read/write)
- 序列化/反序列化 (serialize/deserialize, pickle/unpickle)
- 格式化/解析 (format/parse)

**则必须验证:**

```python
# Pattern: write → read → compare
original_data = create_test_data()
write_to_file(original_data, "test.file")
read_back = read_from_file("test.file")
assert read_back == original_data, "Round-trip data mismatch"

# Pattern: format → parse → compare
original = create_object()
formatted = format_function(original)
parsed = parse_function(formatted)
assert parsed == original, "Format-parse round-trip failed"
```

**具体到你的修改:**
- 如果你修改了**写入逻辑**,你是否也测试了**读取逻辑**能否正确读回?
- 如果你修改了**格式化逻辑**,你是否测试了**解析逻辑**能否正确解析?
- 只测试单向(write或read)是**不充分的**

**🎯 这直接覆盖: astropy-14182, django-10999**

---

### ✓ 验证项2: 数值计算的差分测试

**如果你的修改涉及数学计算、数值函数、算法:**

**则必须验证:**

```python
# 与参考实现对比
import numpy as np  # 或其他标准库

test_inputs = generate_test_cases()
for input_data in test_inputs:
    your_result = your_modified_function(input_data)
    reference_result = numpy_equivalent_function(input_data)

    np.testing.assert_allclose(
        your_result, reference_result,
        rtol=1e-10,
        err_msg=f"Mismatch for input {input_data}"
    )
```

**参考实现可以是:**
- NumPy/SciPy中的对应函数
- 数学公式的直接实现
- 修改前的原始实现(存为baseline)

**如果没有现成的参考实现,至少验证:**
- 已知输入的手算期望输出
- 数学性质(如f(f(x))=f(x)的幂等性)

**🎯 这直接覆盖: xarray-6599**

---

### ✓ 验证项3: 运算符和语法的正确性

**如果你的修改涉及:**
- 运算符重载 (`__add__`, `__sub__`, `__or__`, etc.)
- 表达式计算
- 正则表达式或语法解析

**则必须验证:**

```python
# 运算符优先级
# 错误示例: a - b | c  (实际是 a - (b | c))
# 正确示例: (a - b) | c

# 手动构造能区分优先级的测试用例
A = {1, 2, 3, 4}
B = {2, 3}
C = {3, 4, 5}

result = (A - B) | C  # 期望: {1, 4, 3, 5}
# 如果写成 A - B | C 则结果不同

assert result == expected, f"Operator precedence error: {result} != {expected}"
```

**关键:**
- 不要只用MVCE中的示例测试
- 构造**能区分正确和错误实现**的case
- 对运算符,选择**非空交集**的输入来触发优先级问题

**🎯 这直接覆盖: xarray-6992**

---

### ✓ 验证项4: 边界和特殊值测试

**对你修改的代码涉及的每个输入参数,测试:**

| 参数类型 | 必测边界值 |
|---------|-----------|
| 字符串 | `""` 空字符串, `" "` 空白, 极长字符串 |
| 数值 | `0`, `-1`, 负数, `NaN`, `Infinity` |
| 集合 | `[]` 空集, 单元素, 与其他参数的交集/差集 |
| 路径 | `path`, `./path`, `../x/path` |

---

### ✓ 验证项5: 运行已有测试(回归检测)

在提交前,运行你修改的模块的完整测试套件:

```bash
# 1. 在修改前记录baseline
python -m pytest tests/relevant_module/ -v --tb=no > /tmp/baseline.txt 2>&1

# 2. 应用你的修改

# 3. 重新运行相同测试
python -m pytest tests/relevant_module/ -v --tb=short > /tmp/modified.txt 2>&1

# 4. 检查是否有回归
diff <(grep PASSED /tmp/baseline.txt) <(grep PASSED /tmp/modified.txt)
```

**如果发现之前PASS现在FAIL的测试,你必须先修复再提交。**

---

## 执行要求

在调用`finish`之前:
1. 在think action中逐项确认每个验证项是否适用
2. 对适用的验证项,给出你的测试代码和结果
3. 对不适用的验证项,说明为什么不适用
4. **只有所有适用的验证项都PASS,才能调用finish**

如果任何验证失败,回到代码修改步骤,fix后重新验证。
```

---

## 策略2: 为这4题创建专门的验证Skill

### 实施方式

创建4个针对性的验证skill,在agent准备提交时调用:

#### Skill 1: roundtrip_io_verification

```python
"""
验证I/O round-trip一致性
适用于: 文件读写、序列化、格式化相关修改
"""

def verify_roundtrip(write_function, read_function, test_data):
    """
    验证 write → read round-trip

    Args:
        write_function: 写入函数(data, filepath)
        read_function: 读取函数(filepath) -> data
        test_data: 测试数据列表

    Returns:
        验证报告
    """
    for i, data in enumerate(test_data):
        filepath = f"/tmp/roundtrip_test_{i}"
        write_function(data, filepath)
        read_back = read_function(filepath)

        assert read_back == data, (
            f"Round-trip失败: 写入 {data}, 读回 {read_back}"
        )

    return "✓ Round-trip验证通过"
```

**使用时机**: Agent修改了astropy table的write方法后,调用此skill验证read也正确。

#### Skill 2: differential_testing

```python
"""
差分测试: 对比你的实现和参考实现
"""

def verify_against_reference(your_func, reference_func, test_inputs):
    """
    Args:
        your_func: 你修改后的函数
        reference_func: 参考实现(如numpy函数)
        test_inputs: 测试输入列表
    """
    for inp in test_inputs:
        your_result = your_func(inp)
        ref_result = reference_func(inp)

        np.testing.assert_allclose(
            your_result, ref_result,
            rtol=1e-10,
            err_msg=f"差分测试失败: input={inp}"
        )

    return "✓ 差分测试通过"
```

**使用时机**: Agent修改polyval后,与numpy.polyval对比。

#### Skill 3: operator_precedence_check

```python
"""
运算符优先级验证
"""

def verify_operator_precedence(operation_str, test_cases):
    """
    Args:
        operation_str: 运算表达式(如 "a - b | c")
        test_cases: [(a, b, c, expected_result), ...]
    """
    for a, b, c, expected in test_cases:
        # 评估表达式
        result = eval(operation_str, {'a': a, 'b': b, 'c': c})

        assert result == expected, (
            f"运算符优先级错误: {operation_str} = {result}, 期望 {expected}\n"
            f"输入: a={a}, b={b}, c={c}"
        )

    return "✓ 运算符优先级正确"
```

**使用时机**: Agent修改集合运算后,用非空交集的case验证。

---

## 策略3: 使用Subagent进行对抗性验证 (高阶)

### 触发时机

Agent完成patch后,调用subagent做独立验证:

```python
# In main agent
verify_patch(
    issue_description="[Issue原文]",
    patch_diff="[git diff输出]",
    modified_files=["path1", "path2"],
    verification_strategies=[
        "roundtrip_io" if "write" in patch_diff else None,
        "differential" if "polyval" in patch_diff else None,
        "operator_precedence" if any(op in patch_diff for op in ['-', '|', '&']) else None,
    ]
)
```

### Subagent System Prompt

```markdown
你是一个patch验证专家。你的目标是找到patch可能存在的问题。

你将收到:
- Issue描述
- Patch diff
- 推荐的验证策略

你的任务:
1. 分析patch修改了什么
2. 根据推荐策略编写验证脚本
3. 执行验证
4. 报告发现的问题

## 验证策略库

### Round-trip测试 (适用于I/O/序列化)
- 如果修改了write,必测read
- 如果修改了format,必测parse
- 验证: original → transform → inverse_transform → should equal original

### 差分测试 (适用于数值计算)
- 找到参考实现(numpy/scipy/stdlib)
- 对比多组输入的输出
- 使用assert_allclose而非简单==

### 运算符优先级 (适用于表达式)
- 构造能区分优先级的case
- 例: (A-B)|C vs A-(B|C), 选择B∩C非空的A,B,C

### 边界值测试
- 空值: "", [], None, 0
- 极值: -1, MAX, NaN
- 特殊值: 负数, 分数, 符号

## 输出格式

对每个策略,给出:
1. 测试代码
2. 执行结果
3. PASS/FAIL判定
4. 如果FAIL,说明patch的问题在哪
```

---

## 实施路径

### 最小成本方案 (推荐优先实施)

**Phase 1: 在system prompt中注入验证清单**

修改位置: `openhands/agent/system_prompt.py` 或类似配置

在agent的base system prompt中添加:

```
在你准备调用finish工具提交patch之前,你必须先完成Pre-submission Verification。
详见上面的验证清单。这是强制要求。
```

**优点:**
- 零代码开发成本(只改prompt)
- 立即生效
- 理论上可覆盖全部4题

**局限:**
- 依赖agent执行力(可能读了清单但不严格执行)

---

### 中等成本方案(如果Phase 1效果不够)

**Phase 2: 创建Pre-submission Skill**

注册一个skill,名为`/verify-before-submit`,展开为完整验证清单。

Agent在准备提交时,要求它先调用这个skill。

**优点:**
- 结构化的验证流程
- 可追踪agent是否执行了验证
- 可以在skill中集成自动化测试脚本

**实施:**
1. 在openhands skills目录添加verify_before_submit.py
2. Skill展开为上面的验证清单markdown
3. 在agent准备finish时,由system prompt或hook触发skill调用

---

### 高级方案(A3级别的改进)

**Phase 3: Subagent对抗性验证**

创建verify_patch tool,调用独立subagent来验证。

**优点:**
- 独立认知框架,不受主agent盲区影响
- 结构化的oracle策略库
- 理论覆盖率最高

**缺点:**
- 需要开发tool框架
- 额外token开销(每次+15-25K tokens)
- 实施复杂度高

**建议:** 先做Phase 1+2,如果仍有题目未覆盖,再考虑Phase 3。

---

## 针对4题的具体映射

| Task ID | 失败原因 | 验证清单中的覆盖项 | 预期效果 |
|---------|---------|----------------|---------|
| astropy-14182 | 只测了write,没测read | **验证项1: I/O Round-trip** | Agent会被强制测试write→read一致性 |
| django-10999 | parse返回非None就算通过,没测round-trip | **验证项1: Format-Parse Round-trip** | Agent会被强制测试str→parse→str一致性 |
| xarray-6599 | 只用MVCE测试,没与numpy对比 | **验证项2: 差分测试** | Agent会被引导与numpy.polyval对比 |
| xarray-6992 | MVCE恰好没触发优先级问题 | **验证项3: 运算符优先级** | Agent会被提示用非空交集测试 |

---

## 成功指标

### 短期验证(单题测试)

对这4题分别:
1. 注入验证清单后重新运行swebench-infer
2. 检查agent的conversation trace:
   - 是否在finish前执行了验证清单?
   - 是否发现了遗漏的测试?
   - 是否因验证失败而修改了patch?
3. 最终patch是否resolved?

### 中期验证(批量评测)

在instances_hard的全部100题上:
- 当前: 61/98 resolved (62%)
- 目标(保守): +4题 = 65/98 (66%)
- 目标(乐观): +4题全部resolved = 65/98 (66%)

### 评估方法

```bash
# 创建带验证清单的新配置
cp .llm_config/openrouter.json .llm_config/openrouter_with_verification.json

# 只跑这4题
echo "astropy__astropy-14182
django__django-10999
pydata__xarray-6599
pydata__xarray-6992" > instance_set/instances_target_4.txt

# 运行评测
uv run swebench-infer .llm_config/openrouter_with_verification.json \
    --select instance_set/instances_target_4.txt \
    --workspace docker \
    --output-dir "./evaluation_results/eval_verification_test" \
    --max-attempts 3 \
    --max-iterations 200 \
    --num-workers 4 \
    --n-limit 4

# 对比结果
# 期望: 4/4 resolved (vs 之前 0/4)
```

---

## Next Steps

1. **立即可做** (5分钟):
   - 创建验证清单markdown文件
   - 准备注入到system prompt的文本

2. **今天可完成** (1小时):
   - 找到openhands agent的system prompt注入点
   - 添加验证清单
   - 跑一题(如astropy-14182)验证效果

3. **本周可完成** (4小时):
   - 跑全部4题评测
   - 分析conversation trace确认agent行为
   - 如效果好,扩展到全部instances_hard

4. **可选进阶** (1-2天):
   - 实施Skill版本的验证框架
   - 实施Subagent对抗性验证(如果Phase 1-2不够)
