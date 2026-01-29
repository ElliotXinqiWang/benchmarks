#!/usr/bin/env python3
"""
SWE-Bench Evaluation Script

This script converts OpenHands output.jsonl format to SWE-Bench prediction format
and runs the SWE-Bench evaluation.

Usage:
    uv run swebench-eval <path_to_output.jsonl>
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.utils.patch_utils import remove_files_from_patch
from benchmarks.utils.report_costs import generate_cost_report
from openhands.sdk import get_logger

# 抑制 litellm 的 DeprecationWarning
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message="There is no current event loop",
    module="litellm",
)

logger = get_logger(__name__)


def extract_error_info(history: List[Dict]) -> Dict[str, Any]:
    """
    Extract error information from conversation history.
    
    Returns a dict with:
    - error_type: Type of error (e.g., "API_ERROR", "MAX_ITERATIONS", "UNKNOWN")
    - error_message: Human-readable error message
    - error_details: Additional details
    """
    error_info = {
        "error_type": None,
        "error_message": None,
        "error_details": None,
    }
    
    # Check for ConversationErrorEvent
    for event in reversed(history):  # Check from latest first
        if event.get("kind") == "ConversationErrorEvent":
            error_code = event.get("code", "")
            error_detail = event.get("detail", "")
            
            # Detect API errors
            if "BadGateway" in error_code or "502" in error_detail:
                error_info["error_type"] = "API_ERROR"
                error_info["error_message"] = "API服务错误 (502 Bad Gateway)"
                error_info["error_details"] = f"错误代码: {error_code}, 详情: {error_detail[:200]}"
                break
            elif "Timeout" in error_code or "timeout" in error_detail.lower():
                error_info["error_type"] = "API_TIMEOUT"
                error_info["error_message"] = "API请求超时"
                error_info["error_details"] = f"错误代码: {error_code}, 详情: {error_detail[:200]}"
                break
            elif "RateLimit" in error_code or "rate limit" in error_detail.lower():
                error_info["error_type"] = "RATE_LIMIT"
                error_info["error_message"] = "API速率限制"
                error_info["error_details"] = f"错误代码: {error_code}, 详情: {error_detail[:200]}"
                break
            else:
                error_info["error_type"] = "CONVERSATION_ERROR"
                error_info["error_message"] = "对话执行错误"
                error_info["error_details"] = f"错误代码: {error_code}, 详情: {error_detail[:200]}"
                break
    
    return error_info


def check_max_iterations_reached(history: List[Dict], max_iterations: Optional[int]) -> bool:
    """Check if max iterations limit was reached."""
    if max_iterations is None:
        return False
    
    # Count agent actions (approximation for iterations)
    agent_action_count = sum(
        1 for event in history 
        if "Action" in event.get("kind", "") and event.get("source") == "agent"
    )
    
    # Check if conversation finished normally (has AgentFinishAction)
    has_finish_action = any(
        event.get("kind") == "AgentFinishAction" 
        for event in history
    )
    
    # Check for explicit iteration limit reached messages
    # Look for error messages or state changes indicating limit reached
    for event in history:
        event_str = str(event).lower()
        # Only check error events or state events that explicitly indicate limit reached
        if event.get("kind") in ["ConversationErrorEvent", "AgentErrorEvent"]:
            if ("iteration" in event_str and "limit" in event_str) or \
               ("max" in event_str and "iteration" in event_str and "reached" in event_str):
                return True
    
    # Check conversation state for execution status indicating limit
    for event in history:
        if event.get("kind") == "ConversationStateUpdateEvent":
            value = event.get("value", {})
            if isinstance(value, dict):
                state = value.get("value", value) if "value" in value else value
                if isinstance(state, dict):
                    execution_status = state.get("execution_status")
                    # Check if status indicates iteration limit (not just that max_iterations config exists)
                    # The actual iteration count would be in the state, but we approximate with actions
                    pass  # Keep checking actions count below
    
    # If conversation didn't finish normally AND we're very close to max_iterations,
    # likely hit the limit (but only if no explicit finish action)
    # Use a stricter threshold (0.95 instead of 0.9) and require no finish action
    if not has_finish_action and agent_action_count >= max_iterations * 0.95:
        return True
    
    # Also check if we're very close (>= 0.98) regardless of finish action
    # This catches cases where the limit was reached right before finishing
    if agent_action_count >= max_iterations * 0.98:
        return True
    
    return False


def extract_metrics(entry: Dict, metadata: Optional[Dict] = None) -> Dict[str, Any]:
    """Extract comprehensive metrics from an entry."""
    metrics_data = entry.get("metrics", {})
    history = entry.get("history", [])
    
    # Extract token usage
    token_usage = {}
    if metrics_data:
        accumulated = metrics_data.get("accumulated_token_usage")
        if accumulated:
            token_usage = {
                "prompt_tokens": accumulated.get("prompt_tokens", 0),
                "completion_tokens": accumulated.get("completion_tokens", 0),
                "cache_read_tokens": accumulated.get("cache_read_tokens", 0),
                "cache_write_tokens": accumulated.get("cache_write_tokens", 0),
                "total_tokens": accumulated.get("prompt_tokens", 0) + accumulated.get("completion_tokens", 0),
            }
    
    # Count LLM calls and conversation rounds
    llm_start_events = sum(1 for event in history if event.get("kind") == "LLMCallStartEvent")
    llm_complete_events = sum(1 for event in history if event.get("kind") == "LLMCallCompleteEvent")
    llm_calls = min(llm_start_events, llm_complete_events)  # Use minimum to avoid overcounting
    conversation_rounds = llm_calls
    
    # Count agent actions (tool calls) and categorize by tool type
    agent_actions = []
    tool_use_stats = {}  # {tool_name: {"count": int, "successful": int, "failed": int}}
    action_events = []
    
    for event in history:
        kind = event.get("kind", "")
        source = event.get("source", "")
        
        # Count ActionEvent (tool calls)
        if "Action" in kind and source == "agent":
            tool_name = event.get("tool_name", "unknown")
            agent_actions.append({
                "tool_name": tool_name,
                "event_id": event.get("id"),
                "tool_call_id": event.get("tool_call_id"),
            })
            
            # Initialize tool stats if not exists
            if tool_name not in tool_use_stats:
                tool_use_stats[tool_name] = {"count": 0, "successful": 0, "failed": 0}
            tool_use_stats[tool_name]["count"] += 1
            action_events.append(event)
    
    # Count successful/failed tool calls by checking for corresponding observations/errors
    action_ids = {action["event_id"] for action in agent_actions if action.get("event_id")}
    tool_call_ids = {action["tool_call_id"] for action in agent_actions if action.get("tool_call_id")}
    
    successful_tool_calls = set()
    failed_tool_calls = set()
    
    for event in history:
        kind = event.get("kind", "")
        
        # Check for successful observations
        if kind == "ObservationEvent":
            action_id = event.get("action_id")
            tool_call_id = event.get("tool_call_id")
            tool_name = event.get("tool_name", "unknown")
            if action_id in action_ids or tool_call_id in tool_call_ids:
                successful_tool_calls.add((action_id, tool_call_id))
                if tool_name in tool_use_stats:
                    tool_use_stats[tool_name]["successful"] += 1
        
        # Check for failed tool calls (errors)
        if kind in ["AgentErrorEvent", "ConversationErrorEvent"]:
            action_id = event.get("action_id")
            tool_call_id = event.get("tool_call_id")
            tool_name = event.get("tool_name", "unknown")
            if action_id in action_ids or tool_call_id in tool_call_ids:
                failed_tool_calls.add((action_id, tool_call_id))
                if tool_name in tool_use_stats:
                    tool_use_stats[tool_name]["failed"] += 1
    
    # Calculate tool use statistics
    total_tool_uses = len(agent_actions)
    successful_tool_uses = len(successful_tool_calls)
    failed_tool_uses = len(failed_tool_calls)
    
    # Count event types
    event_type_counts = {}
    for event in history:
        kind = event.get("kind", "unknown")
        event_type_counts[kind] = event_type_counts.get(kind, 0) + 1
    
    # Calculate duration from timestamps
    duration_seconds = None
    timestamps = []
    for event in history:
        timestamp_str = event.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                timestamps.append(timestamp)
            except (ValueError, AttributeError):
                continue
    
    if len(timestamps) >= 2:
        oldest = min(timestamps)
        newest = max(timestamps)
        duration_seconds = (newest - oldest).total_seconds()
    
    # Get max_iterations from metadata if available
    max_iterations = None
    if metadata:
        max_iterations = metadata.get("max_iterations")
    
    # Check if max iterations reached
    max_iterations_reached = check_max_iterations_reached(history, max_iterations)
    
    # Extract error info
    error_info = extract_error_info(history)
    
    return {
        "token_usage": token_usage,
        "conversation_rounds": conversation_rounds,
        "llm_calls": llm_calls,
        "agent_actions": total_tool_uses,
        "tool_use_stats": tool_use_stats,
        "successful_tool_uses": successful_tool_uses,
        "failed_tool_uses": failed_tool_uses,
        "tool_success_rate": (successful_tool_uses / total_tool_uses * 100) if total_tool_uses > 0 else 0.0,
        "total_events": len(history),
        "event_type_counts": event_type_counts,
        "duration_seconds": duration_seconds,
        "max_iterations": max_iterations,
        "max_iterations_reached": max_iterations_reached,
        "error_info": error_info,
    }


def convert_to_swebench_format(
    input_file: str, output_file: str, model_name: str = "OpenHands"
) -> None:
    """
    Convert OpenHands output.jsonl to SWE-Bench prediction format.

    OpenHands format:
    {
        "instance_id": "django__django-11333",
        "test_result": {
            "git_patch": "diff --git a/file.py b/file.py\n..."
        },
        "instruction": "...",
        "error": null,
        "history": [...]
    }

    SWE-Bench format:
    {
        "instance_id": "django__django-11333",
        "model_patch": "diff --git a/file.py b/file.py\n...",
        "model_name_or_path": "OpenHands"
    }
    """
    logger.info(f"Converting {input_file} to SWE-Bench format: {output_file}")

    converted_count = 0
    error_count = 0
    empty_line_count = 0
    missing_instance_id_count = 0
    json_error_count = 0
    other_error_count = 0
    total_lines = 0

    with open(input_file, "r") as infile, open(output_file, "w") as outfile:
        for line_num, line in enumerate(infile, 1):
            total_lines += 1
            try:
                line = line.strip()
                if not line:
                    empty_line_count += 1
                    continue

                data = json.loads(line)

                # Extract required fields
                instance_id = data.get("instance_id")
                if not instance_id:
                    logger.warning(f"Line {line_num}: Missing instance_id")
                    missing_instance_id_count += 1
                    error_count += 1
                    continue

                # Extract git_patch from test_result
                test_result = data.get("test_result", {})
                git_patch = test_result.get("git_patch", "")

                if not git_patch:
                    logger.warning(
                        f"Line {line_num}: Missing or empty git_patch for {instance_id}"
                    )
                    # Still create entry with empty patch
                    git_patch = ""

                # postprocess git_patch
                setup_files = ["pyproject.toml", "tox.ini", "setup.py"]
                git_patch = remove_files_from_patch(git_patch, setup_files)

                # Create SWE-Bench format entry
                swebench_entry = {
                    "instance_id": instance_id,
                    "model_patch": git_patch,
                    "model_name_or_path": model_name,
                }

                # Write to output file
                outfile.write(json.dumps(swebench_entry) + "\n")
                converted_count += 1

            except json.JSONDecodeError as e:
                logger.error(f"Line {line_num}: Invalid JSON - {e}")
                json_error_count += 1
                error_count += 1
            except Exception as e:
                logger.error(f"Line {line_num}: Unexpected error - {e}")
                other_error_count += 1
                error_count += 1

    logger.info(
        f"Conversion complete: {converted_count} entries converted, "
        f"{error_count} errors"
    )

    if converted_count == 0:
        error_details = []
        if total_lines == 0:
            error_details.append("Input file is empty or could not be read")
        else:
            error_details.append(f"Total lines processed: {total_lines}")
            if empty_line_count > 0:
                error_details.append(f"Empty lines: {empty_line_count}")
            if missing_instance_id_count > 0:
                error_details.append(f"Missing instance_id: {missing_instance_id_count}")
            if json_error_count > 0:
                error_details.append(f"JSON decode errors: {json_error_count}")
            if other_error_count > 0:
                error_details.append(f"Other errors: {other_error_count}")
        
        error_msg = "No valid entries were converted. " + "; ".join(error_details)
        raise ValueError(error_msg)


def enhance_report_with_statistics(
    report_file: str,
    input_file: str,
) -> None:
    """
    Enhance the SWE-Bench report with statistics from OpenHands output.
    
    Adds:
    - Error analysis for failed instances
    - Token usage statistics
    - Conversation round statistics
    - Max iterations reached detection
    """
    logger.info(f"Enhancing report with statistics: {report_file}")
    
    # Load SWE-Bench report
    with open(report_file, "r", encoding="utf-8") as f:
        report = json.load(f)
    
    # Load metadata to get max_iterations
    metadata_file = Path(input_file).parent / "metadata.json"
    metadata = None
    if metadata_file.exists():
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    
    # Load OpenHands output to extract statistics
    instance_stats = {}
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                instance_id = entry.get("instance_id")
                if instance_id:
                    stats = extract_metrics(entry, metadata)
                    instance_stats[instance_id] = stats
            except Exception as e:
                logger.warning(f"Failed to parse entry for statistics: {e}")
    
    # Aggregate statistics
    total_token_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "total_tokens": 0,
    }
    total_rounds = 0
    total_llm_calls = 0
    total_actions = 0
    total_successful_tool_uses = 0
    total_failed_tool_uses = 0
    total_duration_seconds = 0.0
    durations_with_data = 0
    max_iterations_reached_count = 0
    
    # Aggregate tool use statistics by tool type
    aggregated_tool_stats = {}  # {tool_name: {"count": int, "successful": int, "failed": int}}
    
    # Aggregate event type counts
    aggregated_event_types = {}
    
    error_summary = {
        "api_errors": [],
        "max_iterations": [],
        "other_errors": [],
        "successful": [],
    }
    
    for instance_id, stats in instance_stats.items():
        # Aggregate token usage
        token_usage = stats.get("token_usage", {})
        total_token_usage["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
        total_token_usage["completion_tokens"] += token_usage.get("completion_tokens", 0)
        total_token_usage["cache_read_tokens"] += token_usage.get("cache_read_tokens", 0)
        total_token_usage["cache_write_tokens"] += token_usage.get("cache_write_tokens", 0)
        total_token_usage["total_tokens"] += token_usage.get("total_tokens", 0)
        
        total_rounds += stats.get("conversation_rounds", 0)
        total_llm_calls += stats.get("llm_calls", 0)
        total_actions += stats.get("agent_actions", 0)
        total_successful_tool_uses += stats.get("successful_tool_uses", 0)
        total_failed_tool_uses += stats.get("failed_tool_uses", 0)
        
        # Aggregate duration
        duration = stats.get("duration_seconds")
        if duration is not None:
            total_duration_seconds += duration
            durations_with_data += 1
        
        # Aggregate tool use statistics by tool type
        tool_use_stats = stats.get("tool_use_stats", {})
        for tool_name, tool_stat in tool_use_stats.items():
            if tool_name not in aggregated_tool_stats:
                aggregated_tool_stats[tool_name] = {"count": 0, "successful": 0, "failed": 0}
            aggregated_tool_stats[tool_name]["count"] += tool_stat.get("count", 0)
            aggregated_tool_stats[tool_name]["successful"] += tool_stat.get("successful", 0)
            aggregated_tool_stats[tool_name]["failed"] += tool_stat.get("failed", 0)
        
        # Aggregate event type counts
        event_type_counts = stats.get("event_type_counts", {})
        for event_type, count in event_type_counts.items():
            aggregated_event_types[event_type] = aggregated_event_types.get(event_type, 0) + count
        
        if stats.get("max_iterations_reached", False):
            max_iterations_reached_count += 1
            error_summary["max_iterations"].append(instance_id)
        
        error_info = stats.get("error_info", {})
        error_type = error_info.get("error_type")
        
        if error_type:
            if error_type == "API_ERROR" or error_type == "API_TIMEOUT" or error_type == "RATE_LIMIT":
                error_summary["api_errors"].append({
                    "instance_id": instance_id,
                    "error_type": error_type,
                    "error_message": error_info.get("error_message"),
                    "error_details": error_info.get("error_details"),
                })
            elif error_type == "CONVERSATION_ERROR":
                error_summary["other_errors"].append({
                    "instance_id": instance_id,
                    "error_type": error_type,
                    "error_message": error_info.get("error_message"),
                    "error_details": error_info.get("error_details"),
                })
        elif instance_id in report.get("resolved_ids", []):
            error_summary["successful"].append(instance_id)
    
    # Calculate averages
    num_instances = len(instance_stats)
    avg_stats = {}
    if num_instances > 0:
        avg_stats = {
            "avg_prompt_tokens": total_token_usage["prompt_tokens"] // num_instances,
            "avg_completion_tokens": total_token_usage["completion_tokens"] // num_instances,
            "avg_total_tokens": total_token_usage["total_tokens"] // num_instances,
            "avg_conversation_rounds": total_rounds / num_instances,
            "avg_llm_calls": total_llm_calls / num_instances,
            "avg_agent_actions": total_actions / num_instances,
            "avg_successful_tool_uses": total_successful_tool_uses / num_instances,
            "avg_failed_tool_uses": total_failed_tool_uses / num_instances,
        }
    
    # Calculate tool success rate
    overall_tool_success_rate = (
        (total_successful_tool_uses / total_actions * 100) if total_actions > 0 else 0.0
    )
    
    # Calculate average duration
    avg_duration_seconds = (
        total_duration_seconds / durations_with_data if durations_with_data > 0 else None
    )
    
    # Calculate per-tool success rates
    tool_stats_with_rates = {}
    for tool_name, tool_stat in aggregated_tool_stats.items():
        count = tool_stat["count"]
        successful = tool_stat["successful"]
        failed = tool_stat["failed"]
        success_rate = (successful / count * 100) if count > 0 else 0.0
        tool_stats_with_rates[tool_name] = {
            **tool_stat,
            "success_rate": success_rate,
        }
    
    # Add enhanced statistics to report
    report["statistics"] = {
        "token_usage": {
            "total": total_token_usage,
            "average": {
                "avg_prompt_tokens": avg_stats.get("avg_prompt_tokens", 0),
                "avg_completion_tokens": avg_stats.get("avg_completion_tokens", 0),
                "avg_total_tokens": avg_stats.get("avg_total_tokens", 0),
                "avg_cache_read_tokens": total_token_usage["cache_read_tokens"] / num_instances if num_instances > 0 else 0,
                "avg_cache_write_tokens": total_token_usage["cache_write_tokens"] / num_instances if num_instances > 0 else 0,
            },
        },
        "conversation": {
            "total_rounds": total_rounds,
            "total_llm_calls": total_llm_calls,
            "total_agent_actions": total_actions,
            "average_rounds": round(avg_stats.get("avg_conversation_rounds", 0), 2),
            "average_llm_calls": round(avg_stats.get("avg_llm_calls", 0), 2),
            "average_actions": round(avg_stats.get("avg_agent_actions", 0), 2),
        },
        "tool_usage": {
            "total_tool_uses": total_actions,
            "total_successful": total_successful_tool_uses,
            "total_failed": total_failed_tool_uses,
            "overall_success_rate": round(overall_tool_success_rate, 2),
            "average_successful_per_instance": round(avg_stats.get("avg_successful_tool_uses", 0), 2),
            "average_failed_per_instance": round(avg_stats.get("avg_failed_tool_uses", 0), 2),
            "by_tool_type": tool_stats_with_rates,
        },
        "duration": {
            "total_seconds": total_duration_seconds,
            "average_seconds": round(avg_duration_seconds, 2) if avg_duration_seconds is not None else None,
            "instances_with_duration": durations_with_data,
            "total_instances": num_instances,
        },
        "event_types": {
            "total_events": sum(aggregated_event_types.values()),
            "by_type": dict(sorted(aggregated_event_types.items(), key=lambda x: x[1], reverse=True)),
        },
        "errors": {
            "max_iterations_reached_count": max_iterations_reached_count,
            "max_iterations_reached_ids": error_summary["max_iterations"],
            "api_errors_count": len(error_summary["api_errors"]),
            "api_errors": error_summary["api_errors"],
            "other_errors_count": len(error_summary["other_errors"]),
            "other_errors": error_summary["other_errors"],
            "successful_count": len(error_summary["successful"]),
        },
        "per_instance": {
            instance_id: {
                "token_usage": stats.get("token_usage", {}),
                "conversation_rounds": stats.get("conversation_rounds", 0),
                "llm_calls": stats.get("llm_calls", 0),
                "agent_actions": stats.get("agent_actions", 0),
                "successful_tool_uses": stats.get("successful_tool_uses", 0),
                "failed_tool_uses": stats.get("failed_tool_uses", 0),
                "tool_success_rate": round(stats.get("tool_success_rate", 0), 2),
                "tool_use_stats": stats.get("tool_use_stats", {}),
                "duration_seconds": stats.get("duration_seconds"),
                "max_iterations_reached": stats.get("max_iterations_reached", False),
                "error_info": stats.get("error_info", {}),
            }
            for instance_id, stats in instance_stats.items()
        },
    }
    
    # Add error summary message
    error_messages = []
    if error_summary["api_errors"]:
        error_messages.append(
            f"API错误: {len(error_summary['api_errors'])} 个实例 "
            f"(实例ID: {', '.join(e['instance_id'] for e in error_summary['api_errors'][:5])}"
            f"{'...' if len(error_summary['api_errors']) > 5 else ''})"
        )
    if error_summary["max_iterations"]:
        error_messages.append(
            f"达到迭代上限: {len(error_summary['max_iterations'])} 个实例 "
            f"(实例ID: {', '.join(error_summary['max_iterations'][:5])}"
            f"{'...' if len(error_summary['max_iterations']) > 5 else ''})"
        )
    if error_summary["other_errors"]:
        error_messages.append(
            f"其他错误: {len(error_summary['other_errors'])} 个实例 "
            f"(实例ID: {', '.join(e['instance_id'] for e in error_summary['other_errors'][:5])}"
            f"{'...' if len(error_summary['other_errors']) > 5 else ''})"
        )
    
    if error_messages:
        report["error_summary"] = "; ".join(error_messages)
    else:
        report["error_summary"] = "无错误"
    
    # Write enhanced report back
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
    
    logger.info("Report enhanced with statistics successfully")
    logger.info(f"  Total tokens: {total_token_usage['total_tokens']:,}")
    logger.info(f"    - Prompt tokens: {total_token_usage['prompt_tokens']:,}")
    logger.info(f"    - Completion tokens: {total_token_usage['completion_tokens']:,}")
    logger.info(f"    - Cache read tokens: {total_token_usage['cache_read_tokens']:,}")
    logger.info(f"    - Cache write tokens: {total_token_usage['cache_write_tokens']:,}")
    logger.info(f"  Total conversation rounds: {total_rounds}")
    logger.info(f"  Total LLM calls: {total_llm_calls}")
    logger.info(f"  Total tool uses: {total_actions}")
    logger.info(f"    - Successful: {total_successful_tool_uses} ({overall_tool_success_rate:.1f}%)")
    logger.info(f"    - Failed: {total_failed_tool_uses}")
    if tool_stats_with_rates:
        logger.info(f"  Tool usage by type:")
        for tool_name, tool_stat in sorted(tool_stats_with_rates.items(), key=lambda x: x[1]["count"], reverse=True)[:5]:
            logger.info(f"    - {tool_name}: {tool_stat['count']} uses, {tool_stat['success_rate']:.1f}% success rate")
    if avg_duration_seconds is not None:
        logger.info(f"  Average duration: {avg_duration_seconds:.1f} seconds")
    logger.info(f"  API errors: {len(error_summary['api_errors'])}")
    logger.info(f"  Max iterations reached: {max_iterations_reached_count}")


def run_swebench_evaluation(
    predictions_file: str,
    dataset: str = "princeton-nlp/SWE-bench_Verified",
    workers: str = "12",
) -> None:
    """
    Run SWE-Bench evaluation on the predictions file.

    Args:
        predictions_file: Path to the SWE-Bench format predictions file
        dataset: SWE-Bench dataset to evaluate against
        workers: Number of workers to use for evaluation
    """
    logger.info(f"Running SWE-Bench evaluation on {predictions_file}")

    try:
        # Get the directory of the predictions file
        predictions_path = Path(predictions_file)
        predictions_dir = predictions_path.parent
        predictions_filename = predictions_path.name

        # Run SWE-Bench evaluation using global python (not UV environment)
        # since swebench is installed globally
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "swebench.harness.run_evaluation",
            "--dataset_name",
            dataset,
            "--predictions_path",
            predictions_filename,
            "--max_workers",
            str(workers),
            "--run_id",
            f"eval_{predictions_path.stem}",
        ]

        logger.info(f"Running command: {' '.join(cmd)}")
        logger.info(f"Working directory: {predictions_dir}")
        logger.info("SWE-Bench evaluation output:")
        print("-" * 80)

        # Stream output directly to console, running from predictions file directory
        result = subprocess.run(cmd, text=True, cwd=predictions_dir)

        print("-" * 80)
        if result.returncode == 0:
            logger.info("SWE-Bench evaluation completed successfully")
        else:
            logger.error(
                f"SWE-Bench evaluation failed with return code {result.returncode}"
            )
            raise subprocess.CalledProcessError(result.returncode, cmd)

    except FileNotFoundError:
        logger.error(
            "SWE-Bench evaluation command not found. "
            "Make sure SWE-Bench is properly installed."
        )
        raise
    except Exception as e:
        logger.error(f"Error running SWE-Bench evaluation: {e}")
        raise


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Convert OpenHands output to SWE-Bench format and run evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    uv run swebench-eval output.jsonl
    uv run swebench-eval /path/to/output.jsonl --dataset princeton-nlp/SWE-bench_Lite
    uv run swebench-eval output.jsonl --model-name "MyModel-v1.0"
        """,
    )

    parser.add_argument("input_file", help="Path to the OpenHands output.jsonl file")

    parser.add_argument(
        "--dataset",
        default="princeton-nlp/SWE-bench_Verified",
        help="SWE-Bench dataset to evaluate against "
        "(default: princeton-nlp/SWE-bench_Verified)",
    )

    parser.add_argument(
        "--output-file",
        help="Output file for SWE-Bench format "
        "(default: input_file with .swebench.jsonl extension)",
    )

    parser.add_argument(
        "--skip-evaluation",
        action="store_true",
        help="Only convert format, skip running evaluation",
    )

    parser.add_argument(
        "--model-name",
        default="openhands",
        help="Model name to use in the model_name_or_path field (default: openhands)",
    )

    parser.add_argument(
        "--workers",
        default="12",
        help="Number of workers to use when evaluating",
    )

    args = parser.parse_args()

    # Validate input file
    input_file = Path(args.input_file)
    if not input_file.exists():
        logger.error(f"Input file does not exist: {input_file}")
        sys.exit(1)

    if not input_file.suffix == ".jsonl":
        logger.warning(f"Input file does not have .jsonl extension: {input_file}")

    # Check if input file is empty, and if so, look for attempt files
    if input_file.stat().st_size == 0:
        logger.warning(f"Input file {input_file} is empty, looking for attempt files...")
        input_dir = input_file.parent
        attempt_files = sorted(
            input_dir.glob("output.critic_attempt_*.jsonl"),
            key=lambda x: int(x.stem.split("_")[-1]) if x.stem.split("_")[-1].isdigit() else 0,
            reverse=True,
        )
        
        if attempt_files:
            # Use the most recent attempt file
            input_file = attempt_files[0]
            logger.info(f"Using attempt file: {input_file}")
        else:
            logger.error(
                f"Input file is empty and no attempt files found in {input_dir}. "
                f"Please check if evaluation completed successfully."
            )
            sys.exit(1)

    # Determine output file
    if args.output_file:
        output_file = Path(args.output_file)
    else:
        output_file = input_file.with_suffix(".swebench.jsonl")

    logger.info(f"Input file: {input_file}")
    logger.info(f"Output file: {output_file}")
    logger.info(f"Dataset: {args.dataset}")
    logger.info(f"Model name: {args.model_name}")

    try:
        # Convert format
        convert_to_swebench_format(str(input_file), str(output_file), args.model_name)

        if not args.skip_evaluation:
            # Run evaluation
            run_swebench_evaluation(str(output_file), args.dataset, args.workers)

            # Move report file to input file directory with .report.json extension
            # SWE-Bench creates: {model_name.replace("/", "__")}.eval_{output_file.stem}.json
            report_filename = (
                f"{args.model_name.replace('/', '__')}.eval_{output_file.stem}.json"
            )
            report_path = output_file.parent / report_filename
            dest_report_path = input_file.with_suffix(".report.json")

            shutil.move(str(report_path), str(dest_report_path))
            logger.info(f"Moved report file to: {dest_report_path}")
            
            # Enhance report with statistics
            enhance_report_with_statistics(str(dest_report_path), str(input_file))

        # Generate cost report as final step
        generate_cost_report(str(input_file))

        logger.info("Script completed successfully!")

    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
