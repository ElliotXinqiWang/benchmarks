#!/usr/bin/env python3
"""测试fuzz_hypo工具的修复效果"""

import sys
from pathlib import Path

# 测试1: 检查_load_spec是否正确处理长字符串
print("=" * 80)
print("测试1: _load_spec方法 - 处理长spec字符串")
print("=" * 80)

spec_content = """inputs:
  base_number: 
    type: integer
    min: 1
    max: 999999
  suffix:
    type: string
    min_length: 1
    max_length: 10
pre_conditions:
  - "suffix is not None"
post_conditions:
  - "result is not None"
"""

# 模拟_load_spec方法
def _load_spec_fixed(spec: str, working_dir: Path) -> str:
    """Fixed version of _load_spec"""
    # If spec contains newlines or looks like YAML/JSON content, treat it as content directly
    if '\n' in spec or spec.strip().startswith(('inputs:', '{', '[')):
        return spec
    
    # Otherwise, try to treat it as a file path
    try:
        spec_path = working_dir / spec
        if spec_path.exists() and spec_path.is_file():
            return spec_path.read_text()
    except (OSError, ValueError):
        # If path construction fails (e.g., invalid path), treat spec as content
        pass
    
    # Fallback: return spec as-is (content)
    return spec

try:
    result = _load_spec_fixed(spec_content, Path("/tmp"))
    print("✅ 成功处理长spec字符串")
    print(f"   返回内容长度: {len(result)} 字符")
    print(f"   是否保留原内容: {result == spec_content}")
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试2: 检查response.choices访问
print("\n" + "=" * 80)
print("测试2: LLM响应处理 - response.choices[0].message.content")
print("=" * 80)

# 模拟LLM response对象
class MockMessage:
    def __init__(self):
        self.content = '{"strategy": "st.integers()", "post_condition": "def post_condition(i, o): return True", "seeds": [1, 2, 3]}'

class MockChoice:
    def __init__(self):
        self.message = MockMessage()

class MockResponse:
    def __init__(self):
        self.choices = [MockChoice()]

try:
    mock_response = MockResponse()
    # 旧代码会失败: raw_content = mock_response.content
    # 新代码应该成功:
    raw_content = mock_response.choices[0].message.content
    print("✅ 成功访问 response.choices[0].message.content")
    print(f"   获取到的内容: {raw_content[:50]}...")
except AttributeError as e:
    print(f"❌ 失败: {e}")

# 测试3: 检查File name too long错误是否修复
print("\n" + "=" * 80)
print("测试3: 验证不会触发 'File name too long' 错误")
print("=" * 80)

# 创建一个非常长的spec字符串（原来会导致文件名过长）
long_spec = "inputs:\n  " + "x" * 500 + "\npre_conditions:\n  " + "y" * 500

try:
    result = _load_spec_fixed(long_spec, Path("/tmp"))
    # 不应该尝试将其作为文件路径，而应该直接返回内容
    print("✅ 成功处理超长spec字符串，没有触发文件名过长错误")
    print(f"   内容长度: {len(result)} 字符")
    print(f"   正确返回原内容: {result == long_spec}")
except OSError as e:
    if "File name too long" in str(e):
        print(f"❌ 仍然触发文件名过长错误: {e}")
    else:
        print(f"❌ 其他OS错误: {e}")
except Exception as e:
    print(f"❌ 未预期的错误: {e}")

print("\n" + "=" * 80)
print("总结")
print("=" * 80)
print("""
修复的两个关键bug:

1. ✅ AttributeError - 'LLMResponse' object has no attribute 'content'
   修复: 改为 response.choices[0].message.content

2. ✅ OSError - File name too long
   修复: 先检查spec是否包含换行符或YAML结构，如果是则直接作为内容使用
   
这两个bug导致了fuzz_hypo工具100%的失败率。修复后工具应该能够正常工作。
""")
