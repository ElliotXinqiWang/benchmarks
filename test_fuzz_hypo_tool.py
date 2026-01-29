#!/usr/bin/env python3
"""测试脚本：验证 fuzz_hypo 工具在容器内是否能被正确调用

用法:
    python test_fuzz_hypo_tool.py [--llm-config LLM_CONFIG_PATH] [--server-image IMAGE_NAME]

示例:
    python test_fuzz_hypo_tool.py
    python test_fuzz_hypo_tool.py --llm-config .llm_config/openrouter.json
"""

import argparse
import json
import sys
from pathlib import Path

from openhands.sdk import Agent, Conversation, LLM, get_logger
from openhands.sdk.workspace import RemoteWorkspace
from openhands.tools.preset.default import get_default_tools
from openhands.workspace import DockerWorkspace

logger = get_logger(__name__)


def load_llm_config(config_path: str) -> dict:
    """加载 LLM 配置文件"""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"LLM config file not found: {config_path}")
    
    with open(config_file) as f:
        return json.load(f)


def test_tool_with_workspace(
    workspace: RemoteWorkspace,
    llm: LLM,
):
    """测试工具在给定 workspace 中是否能被调用
    
    Args:
        workspace: 远程工作区
        llm: LLM 实例
    """
    logger.info("=" * 60)
    logger.info("开始测试 fuzz_hypo 工具")
    logger.info("=" * 60)
    
    # 1. 创建 Agent（包含 fuzz_hypo 工具）
    try:
        tools = get_default_tools(enable_browser=False)
        agent = Agent(llm=llm, tools=tools)
        logger.info("✓ 成功创建 Agent")
        logger.info(f"  可用工具: {[tool.name for tool in agent.tools_map.values()]}")
        
        # 检查 fuzz_hypo 工具是否存在
        if "fuzz_hypo" in agent.tools_map:
            logger.info("✓ fuzz_hypo 工具已注册")
        else:
            logger.warning("⚠ fuzz_hypo 工具未在工具列表中")
            logger.info("  这可能是因为工具未正确注册，但可能仍然可用")
    except Exception as e:
        logger.error(f"✗ 创建 Agent 失败: {e}")
        return False
    
    # 2. 创建 Conversation 并测试工具调用
    try:
        logger.info("\n" + "=" * 60)
        logger.info("创建 Conversation 并测试工具调用")
        logger.info("=" * 60)
        
        conversation = Conversation(
            agent=agent,
            workspace=workspace,
            max_iteration_per_run=5,
        )
        
        logger.info(f"✓ Conversation 创建成功 (ID: {conversation.state.id})")
        
        # 发送测试消息，要求使用 fuzz_hypo 工具
        test_message = """请使用 fuzz_hypo 工具测试一个简单的函数。

目标函数: math.sqrt (Python 标准库的平方根函数)
请使用 fuzz_hypo 工具，mode 设置为 "quick"，测试 math.sqrt 函数。

如果工具调用成功，请告诉我结果。如果失败，请告诉我错误信息。"""
        
        logger.info("\n发送测试消息...")
        conversation.send_message(test_message)
        
        logger.info("运行 conversation...")
        conversation.run()
        
        logger.info("✓ Conversation 运行完成")
        
        # 检查事件，查找工具调用
        events = list(conversation.state.events)
        logger.info(f"\n检查事件 (共 {len(events)} 个事件)...")
        
        fuzz_hypo_called = False
        fuzz_hypo_success = False
        
        for event in events:
            event_str = str(event)
            if "fuzz_hypo" in event_str.lower() or "FuzzHypo" in event_str:
                logger.info(f"\n找到 fuzz_hypo 相关事件:")
                logger.info(f"  类型: {type(event).__name__}")
                fuzz_hypo_called = True
                
                # 检查是否是 ObservationEvent
                from openhands.sdk.event import ObservationEvent
                if isinstance(event, ObservationEvent):
                    content_preview = event.content[:500] if len(event.content) > 500 else event.content
                    logger.info(f"  观察结果: {content_preview}...")
                    if "error" not in event.content.lower() and "失败" not in event.content:
                        fuzz_hypo_success = True
        
        # 总结结果
        logger.info("\n" + "=" * 60)
        logger.info("测试结果总结")
        logger.info("=" * 60)
        
        if fuzz_hypo_called:
            logger.info("✓ fuzz_hypo 工具被调用")
            if fuzz_hypo_success:
                logger.info("✓ 工具执行成功（未发现错误）")
                return True
            else:
                logger.warning("⚠ 工具被调用，但执行可能失败")
                logger.info("  请查看上方的事件详情")
                return False
        else:
            logger.warning("⚠ fuzz_hypo 工具未被调用")
            logger.info("  这可能是因为:")
            logger.info("  1. Agent 选择不使用该工具")
            logger.info("  2. 工具未正确注册")
            logger.info("  3. Conversation 在调用工具前就结束了")
            return False
            
    except Exception as e:
        logger.error(f"\n✗ Conversation 运行失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_with_dockerworkspace(
    llm_config_path: str = ".llm_config/openrouter.json",
    server_image: str = "ghcr.io/openhands/eval-agent-server",
):
    """使用 DockerWorkspace 测试工具（完整的可运行示例）
    
    Args:
        llm_config_path: LLM 配置文件路径
        server_image: Docker 镜像名称
    """
    # 加载 LLM 配置
    try:
        llm_config = load_llm_config(llm_config_path)
        logger.info(f"✓ 成功加载 LLM 配置: {llm_config_path}")
        logger.info(f"  Model: {llm_config.get('model', 'N/A')}")
    except Exception as e:
        logger.error(f"✗ 加载 LLM 配置失败: {e}")
        return False
    
    # 创建 LLM 实例
    try:
        llm = LLM(**llm_config)
        logger.info("✓ 成功创建 LLM 实例")
    except Exception as e:
        logger.error(f"✗ 创建 LLM 实例失败: {e}")
        return False
    
    # 使用 DockerWorkspace 创建容器并测试
    try:
        logger.info(f"\n使用 Docker 镜像: {server_image}")
        logger.info("正在启动容器...")
        with DockerWorkspace(
            server_image=server_image,
            host_port=8000,
        ) as workspace:
            logger.info("✓ 容器启动成功")
            return test_tool_with_workspace(workspace, llm)
    except Exception as e:
        logger.error(f"✗ Docker 容器操作失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    parser = argparse.ArgumentParser(
        description="测试 fuzz_hypo 工具在容器内是否能被正确调用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置测试
  python test_fuzz_hypo_tool.py
  
  # 使用自定义 LLM 配置
  python test_fuzz_hypo_tool.py --llm-config .llm_config/openrouter.json
  
  # 使用自定义 Docker 镜像
  python test_fuzz_hypo_tool.py --server-image ghcr.io/openhands/eval-agent-server:latest
        """
    )
    parser.add_argument(
        "--llm-config",
        type=str,
        default=".llm_config/openrouter.json",
        help="LLM 配置文件路径（默认: .llm_config/openrouter.json）",
    )
    parser.add_argument(
        "--server-image",
        type=str,
        default="ghcr.io/openhands/eval-agent-server",
        help="Docker 镜像名称（默认: ghcr.io/openhands/eval-agent-server）",
    )
    
    args = parser.parse_args()
    
    try:
        success = test_with_dockerworkspace(
            llm_config_path=args.llm_config,
            server_image=args.server_image,
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
