#!/usr/bin/env python3
"""
简单的OpenRouter API测试脚本

用法:
    python test_openrouter_api.py [config_path]

示例:
    python test_openrouter_api.py .llm_config/openrouter.json
"""

import json
import sys
from pathlib import Path

from openhands.sdk import LLM, Message, TextContent


def test_openrouter_api(config_path: str) -> None:
    """测试OpenRouter API配置"""
    
    # 1. 读取配置文件
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"❌ 错误: 配置文件不存在: {config_path}")
        sys.exit(1)
    
    print(f"📖 读取配置文件: {config_path}")
    with open(config_file, "r") as f:
        config_data = json.load(f)
    
    # 显示配置信息（隐藏API key）
    print("\n📋 配置信息:")
    for key, value in config_data.items():
        if key == "api_key":
            masked_key = value[:10] + "..." + value[-4:] if len(value) > 14 else "***"
            print(f"  {key}: {masked_key}")
        else:
            print(f"  {key}: {value}")
    
    # 2. 创建LLM实例
    print("\n🔧 创建LLM实例...")
    try:
        llm = LLM.model_validate_json(json.dumps(config_data))
        print(f"✅ LLM实例创建成功")
        print(f"   模型: {llm.model}")
        print(f"   Base URL: {llm.base_url}")
    except Exception as e:
        print(f"❌ 创建LLM实例失败: {e}")
        sys.exit(1)
    
    # 3. 发送测试消息
    print("\n📤 发送测试消息...")
    test_message = "请用一句话回复：你好"
    print(f"   测试消息: {test_message}")
    
    try:
        messages = [Message(role="user", content=[TextContent(text=test_message)])]
        response = llm.completion(messages=messages)
        
        # 4. 显示结果
        print("\n✅ API调用成功!")
        print("\n📥 响应内容:")
        for content in response.message.content:
            if isinstance(content, TextContent):
                print(f"   {content.text}")
        
        # 显示使用统计
        print("\n📊 使用统计:")
        metrics = response.metrics
        print(f"   模型名称: {metrics.model_name}")
        token_usage = response.raw_response.get("usage", {})
        if token_usage:
            print(f"   输入tokens: {token_usage.get('prompt_tokens', 'N/A')}")
            print(f"   输出tokens: {token_usage.get('completion_tokens', 'N/A')}")
            print(f"   总tokens: {token_usage.get('total_tokens', 'N/A')}")
        
        cost = llm.metrics.accumulated_cost
        if cost > 0:
            print(f"   累计成本: ${cost:.6f}")
        
        print("\n🎉 测试完成! API配置正常工作。")
        
    except Exception as e:
        print(f"\n❌ API调用失败: {type(e).__name__}")
        print(f"   错误信息: {e}")
        
        # 提供诊断建议
        print("\n🔍 诊断建议:")
        if "APIConnectionError" in str(type(e).__name__):
            print("   1. 检查网络连接是否正常")
            print("   2. 确认base_url是否正确: https://openrouter.ai/api/v1")
            print("   3. 检查防火墙或代理设置")
        elif "AuthenticationError" in str(type(e).__name__) or "401" in str(e):
            print("   1. 检查API key是否正确")
            print("   2. 确认API key是否已激活")
            print("   3. 检查OpenRouter账户余额")
        elif "ModelNotFound" in str(type(e).__name__) or "404" in str(e):
            print("   1. 检查模型名称是否正确")
            print("   2. 确认模型是否在OpenRouter上可用")
            print("   3. 尝试使用 'openrouter/anthropic/claude-sonnet-4' 格式")
        else:
            print("   1. 查看完整错误信息")
            print("   2. 检查配置文件格式")
            print("   3. 确认所有必需字段都已填写")
        
        sys.exit(1)


def main():
    """主函数"""
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        # 默认配置文件路径
        config_path = ".llm_config/openrouter.json"
    
    print("=" * 60)
    print("OpenRouter API 测试脚本")
    print("=" * 60)
    
    test_openrouter_api(config_path)


if __name__ == "__main__":
    main()
