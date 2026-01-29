#!/usr/bin/env python3
"""
生成 SWE-bench 实例的详细报告

用法:
    python generate_instance_report.py --instances '[("eval_outputs_fuzz_hypo_100/instances_100_4", "matplotlib__matplotlib-23476")]'
    
或者使用配置文件:
    python generate_instance_report.py --config instances_to_report.json
    
配置文件格式:
    {
        "instances": [
            ["eval_outputs_fuzz_hypo_100/instances_100_4", "matplotlib__matplotlib-23476"],
            ["eval_outputs_100/instances_100_1", "django__django-11333"]
        ]
    }
"""

import argparse
import ast
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class InstanceResult:
    """单个实例在某个模型下的结果"""
    instance_id: str
    model_name: str
    resolved: bool = False
    patch: str = ""
    # 测试结果 (如果有 swebench 评估结果)
    tests_status: dict = field(default_factory=dict)
    # 统计数据
    token_usage: dict = field(default_factory=dict)
    agent_actions: int = 0
    tool_use_stats: dict = field(default_factory=dict)
    duration_seconds: float = 0.0
    max_iterations_reached: bool = False
    error_info: dict = field(default_factory=dict)


def find_model_dirs(base_path: Path) -> list[Path]:
    """
    从 base_path 开始搜索，找到所有包含 output.jsonl 的模型目录
    
    目录结构通常是:
    base_path/princeton-nlp__SWE-bench_Verified-test/openrouter/anthropic/model_name/
    """
    model_dirs = []
    
    # 遍历查找包含 output.jsonl 的目录
    for root, dirs, files in os.walk(base_path):
        if "output.jsonl" in files or "output.report.json" in files:
            model_dirs.append(Path(root))
    
    return model_dirs


def extract_model_name(model_dir: Path) -> str:
    """从目录路径提取模型名称"""
    # 目录名通常是: claude-sonnet-4_sdk_73769d5_maxiter_200_N_initial
    return model_dir.name


def load_output_jsonl(model_dir: Path, instance_id: str) -> dict | None:
    """从 output.jsonl 中加载指定实例的数据"""
    output_file = model_dir / "output.jsonl"
    if not output_file.exists():
        return None
    
    with open(output_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("instance_id") == instance_id:
                    return data
            except json.JSONDecodeError:
                continue
    
    return None


def load_report_json(model_dir: Path) -> dict | None:
    """加载 output.report.json"""
    report_file = model_dir / "output.report.json"
    if not report_file.exists():
        return None
    
    with open(report_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_instance_result(
    model_dir: Path,
    instance_id: str,
    model_name: str,
) -> InstanceResult | None:
    """获取某个实例在某个模型下的结果"""
    
    result = InstanceResult(
        instance_id=instance_id,
        model_name=model_name,
    )
    
    # 1. 从 output.jsonl 加载补丁
    output_data = load_output_jsonl(model_dir, instance_id)
    if output_data:
        test_result = output_data.get("test_result", {})
        result.patch = test_result.get("git_patch", "")
    
    # 2. 从 output.report.json 加载评估结果
    report = load_report_json(model_dir)
    if report:
        # 检查是否已解决
        resolved_ids = report.get("resolved_ids", [])
        result.resolved = instance_id in resolved_ids
        
        # 获取 per_instance 统计
        statistics = report.get("statistics", {})
        per_instance = statistics.get("per_instance", {})
        instance_stats = per_instance.get(instance_id, {})
        
        if instance_stats:
            result.token_usage = instance_stats.get("token_usage", {})
            result.agent_actions = instance_stats.get("agent_actions", 0)
            result.tool_use_stats = instance_stats.get("tool_use_stats", {})
            result.duration_seconds = instance_stats.get("duration_seconds", 0.0)
            result.max_iterations_reached = instance_stats.get("max_iterations_reached", False)
            result.error_info = instance_stats.get("error_info", {})
    
    # 3. 尝试从 swebench 评估日志加载详细测试结果
    # swebench 评估会生成 logs/run_evaluation/eval_results.swebench/... 结构
    swebench_report = find_swebench_eval_result(model_dir, instance_id)
    if swebench_report:
        result.tests_status = swebench_report.get("tests_status", {})
    
    return result


def find_swebench_eval_result(model_dir: Path, instance_id: str) -> dict | None:
    """
    尝试查找 swebench 官方评估产生的详细测试结果
    
    这些结果通常在 logs/run_evaluation/eval_results.swebench/MODEL_NAME/INSTANCE_ID/report.json
    """
    # 首先在 benchmarks 根目录下查找
    benchmarks_dir = model_dir
    while benchmarks_dir.name != "benchmarks" and benchmarks_dir.parent != benchmarks_dir:
        benchmarks_dir = benchmarks_dir.parent
    
    if benchmarks_dir.name != "benchmarks":
        return None
    
    # 尝试多个可能的路径
    possible_paths = [
        benchmarks_dir / "logs" / "run_evaluation" / "eval_results.swebench" / "openhands" / instance_id / "report.json",
        model_dir / "swebench_results" / instance_id / "report.json",
    ]
    
    for path in possible_paths:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 结果可能直接是 instance_id 的 key
                if instance_id in data:
                    return data[instance_id]
                return data
    
    return None


def generate_report(
    instances: list[tuple[str, str]],
    benchmarks_dir: Path,
) -> dict:
    """
    生成报告
    
    Args:
        instances: [(relative_path, instance_id), ...]
        benchmarks_dir: benchmarks 目录的绝对路径
    
    Returns:
        报告字典
    """
    report = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "instances": {},
    }
    
    for relative_path, instance_id in instances:
        base_path = benchmarks_dir / relative_path
        
        if not base_path.exists():
            print(f"警告: 路径不存在 {base_path}")
            continue
        
        # 查找该路径下的所有模型目录
        model_dirs = find_model_dirs(base_path)
        
        if not model_dirs:
            print(f"警告: 在 {base_path} 下未找到模型目录")
            continue
        
        instance_report = {
            "path": relative_path,
            "models": {},
        }
        
        for model_dir in model_dirs:
            model_name = extract_model_name(model_dir)
            result = get_instance_result(model_dir, instance_id, model_name)
            
            if result:
                instance_report["models"][model_name] = {
                    "resolved": result.resolved,
                    "patch": result.patch,
                    "tests_status": result.tests_status,
                    "token_usage": result.token_usage,
                    "agent_actions": result.agent_actions,
                    "tool_use_stats": result.tool_use_stats,
                    "duration_seconds": result.duration_seconds,
                    "max_iterations_reached": result.max_iterations_reached,
                    "error_info": result.error_info,
                }
        
        report["instances"][instance_id] = instance_report
    
    return report


def print_summary(report: dict) -> None:
    """打印报告摘要"""
    print("\n" + "=" * 80)
    print("报告摘要")
    print("=" * 80)
    
    for instance_id, instance_data in report["instances"].items():
        print(f"\n📋 实例: {instance_id}")
        print(f"   路径: {instance_data['path']}")
        print()
        
        for model_name, model_data in instance_data["models"].items():
            resolved_str = "✅ 已解决" if model_data["resolved"] else "❌ 未解决"
            print(f"   🤖 模型: {model_name}")
            print(f"      状态: {resolved_str}")
            
            if model_data["patch"]:
                patch_lines = model_data["patch"].count('\n') + 1
                print(f"      补丁: {patch_lines} 行")
            else:
                print(f"      补丁: 无")
            
            if model_data["token_usage"]:
                total_tokens = model_data["token_usage"].get("total_tokens", 0)
                print(f"      Token: {total_tokens:,}")
            
            if model_data["duration_seconds"]:
                print(f"      耗时: {model_data['duration_seconds']:.1f}s")
            
            if model_data["tests_status"]:
                f2p = model_data["tests_status"].get("FAIL_TO_PASS", {})
                p2p = model_data["tests_status"].get("PASS_TO_PASS", {})
                f2p_success = len(f2p.get("success", []))
                f2p_failure = len(f2p.get("failure", []))
                p2p_success = len(p2p.get("success", []))
                p2p_failure = len(p2p.get("failure", []))
                print(f"      测试: FAIL_TO_PASS({f2p_success}✓/{f2p_failure}✗) PASS_TO_PASS({p2p_success}✓/{p2p_failure}✗)")
            
            print()


def main():
    parser = argparse.ArgumentParser(
        description="生成 SWE-bench 实例的详细报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--instances",
        type=str,
        help='实例列表，格式: \'[("路径1", "实例ID1"), ("路径2", "实例ID2")]\'',
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径 (JSON 格式)",
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="instance_report.json",
        help="输出文件路径 (默认: instance_report.json)",
    )
    
    parser.add_argument(
        "--benchmarks-dir",
        type=str,
        default=None,
        help="benchmarks 目录路径 (默认: 脚本所在目录)",
    )
    
    args = parser.parse_args()
    
    # 确定 benchmarks 目录
    if args.benchmarks_dir:
        benchmarks_dir = Path(args.benchmarks_dir)
    else:
        benchmarks_dir = Path(__file__).parent
    
    benchmarks_dir = benchmarks_dir.resolve()
    print(f"Benchmarks 目录: {benchmarks_dir}")
    
    # 解析实例列表
    instances = []
    
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = benchmarks_dir / config_path
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            instances = [tuple(item) for item in config["instances"]]
    
    elif args.instances:
        # 解析字符串格式的列表
        try:
            parsed = ast.literal_eval(args.instances)
            instances = [(str(p), str(i)) for p, i in parsed]
        except Exception as e:
            print(f"错误: 无法解析 --instances 参数: {e}")
            print("格式示例: '[\"eval_outputs_100/instances_100_1\", \"django__django-11333\")]'")
            return 1
    
    else:
        print("错误: 请提供 --instances 或 --config 参数")
        return 1
    
    print(f"处理 {len(instances)} 个实例...")
    
    # 生成报告
    report = generate_report(instances, benchmarks_dir)
    
    # 保存报告
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = benchmarks_dir / output_path
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n报告已保存到: {output_path}")
    
    # 打印摘要
    print_summary(report)
    
    return 0


if __name__ == "__main__":
    exit(main())
