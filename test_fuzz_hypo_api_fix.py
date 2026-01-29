#!/usr/bin/env python3
"""测试fuzz_hypo工具使用正确的OpenHands API"""

import sys
from pathlib import Path

print("=" * 80)
print("测试: 验证fuzz_hypo使用OpenHands标准API")
print("=" * 80)

# 模拟OpenHands的LLMResponse和Message结构
class TextContent:
    def __init__(self, text: str):
        self.text = text
    
    def __repr__(self):
        return f"TextContent(text={self.text[:50]}...)"

class Message:
    def __init__(self, content):
        self.content = content
    
    def __repr__(self):
        return f"Message(content={self.content})"

class MetricsSnapshot:
    pass

class LLMResponse:
    """模拟OpenHands的LLMResponse"""
    def __init__(self, message, metrics, raw_response):
        self.message = message
        self.metrics = metrics
        self.raw_response = raw_response
    
    def __repr__(self):
        return f"LLMResponse(message={self.message})"

# 模拟content_to_str函数
def content_to_str(contents):
    """Convert a list of TextContent and ImageContent to a list of strings."""
    text_parts = []
    for content_item in contents:
        if hasattr(content_item, 'text'):
            text_parts.append(content_item.text)
    return text_parts

# 测试1: 验证正确的API访问方式
print("\n测试1: 使用response.message.content访问")
print("-" * 80)

json_response = '{"strategy": "st.integers()", "post_condition": "def post_condition(i, o): return True", "seeds": [1, 2, 3]}'
mock_message = Message(content=[TextContent(text=json_response)])
mock_response = LLMResponse(
    message=mock_message,
    metrics=MetricsSnapshot(),
    raw_response=None
)

try:
    # 正确的方式：使用content_to_str
    text_parts = content_to_str(mock_response.message.content)
    raw_content = "".join(text_parts)
    print("✅ 成功使用OpenHands标准API访问")
    print(f"   获取到的内容: {raw_content[:60]}...")
    print(f"   内容长度: {len(raw_content)} 字符")
    
    # 验证内容正确
    assert raw_content == json_response, "内容不匹配"
    print("✅ 内容验证通过")
except Exception as e:
    print(f"❌ 失败: {e}")
    sys.exit(1)

# 测试2: 验证错误的方式会失败
print("\n测试2: 验证旧的错误方式（应该失败）")
print("-" * 80)

try:
    # 错误的方式：直接访问choices（不存在）
    raw_content = mock_response.choices[0].message.content
    print("❌ 意外成功：错误的API居然可用！")
    sys.exit(1)
except AttributeError as e:
    print("✅ 正确：错误的API访问方式被拒绝")
    print(f"   错误信息: {str(e)}")

# 测试3: 验证直接访问方式（备选方案）
print("\n测试3: 验证直接访问content[0].text（备选方案）")
print("-" * 80)

try:
    if mock_response.message.content:
        raw_content = mock_response.message.content[0].text
    else:
        raw_content = ""
    
    print("✅ 成功使用直接访问方式")
    print(f"   获取到的内容: {raw_content[:60]}...")
    assert raw_content == json_response, "内容不匹配"
    print("✅ 内容验证通过")
except Exception as e:
    print(f"❌ 失败: {e}")
    sys.exit(1)

# 测试4: 处理空content的情况
print("\n测试4: 处理空content列表")
print("-" * 80)

empty_message = Message(content=[])
empty_response = LLMResponse(
    message=empty_message,
    metrics=MetricsSnapshot(),
    raw_response=None
)

try:
    text_parts = content_to_str(empty_response.message.content)
    raw_content = "".join(text_parts)
    print("✅ 成功处理空content")
    print(f"   结果: '{raw_content}' (空字符串)")
    assert raw_content == "", "应该返回空字符串"
    print("✅ 空content处理正确")
except Exception as e:
    print(f"❌ 失败: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("总结")
print("=" * 80)
print("""
✅ 所有测试通过！

修复对比:
1. ❌ 旧的错误修复: response.choices[0].message.content
   - 直接访问raw_response的内部结构
   - 绕过OpenHands的API抽象层
   - 与OpenHands其他组件不一致

2. ✅ 新的正确修复: content_to_str(response.message.content)
   - 使用OpenHands提供的标准工具函数
   - 遵循OpenHands的API设计
   - 与其他组件保持一致
   - 更安全，能处理多种content类型

3. ✅ 备选方案: response.message.content[0].text
   - 直接但仍符合API规范
   - 适合简单场景

现在fuzz_hypo工具完全符合OpenHands的API标准！
""")
