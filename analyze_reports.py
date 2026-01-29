#!/usr/bin/env python3
"""
分析三个SWE-bench评估报告，比较baseline与hypothesis/fuzz_hypo的差异
"""

import json
from pathlib import Path
from collections import defaultdict

# 文件路径
baseline_path = Path("/Users/xinqiwang/Openhands/benchmarks/eval_outputs_100/princeton-nlp__SWE-bench_Verified-test/openrouter/anthropic/claude-sonnet-4_sdk_73769d5_maxiter_200_N_initial/output.report.json")
hypothesis_path = Path("/Users/xinqiwang/Openhands/benchmarks/eval_outputs_hypothesis_100_fixed/princeton-nlp__SWE-bench_Verified-test/openrouter/anthropic/claude-sonnet-4_sdk_73769d5_maxiter_200_N_initial/output.report.json")
fuzz_hypo_path = Path("/Users/xinqiwang/Openhands/benchmarks/eval_outputs_fuzz_hypo_100/princeton-nlp__SWE-bench_Verified-test/openrouter/anthropic/claude-sonnet-4_sdk_73769d5_maxiter_200_N_initial/output.report.json")

# 加载数据
with open(baseline_path) as f:
    baseline = json.load(f)
with open(hypothesis_path) as f:
    hypothesis = json.load(f)
with open(fuzz_hypo_path) as f:
    fuzz_hypo = json.load(f)

print("=" * 80)
print("SWE-bench 评估报告分析")
print("=" * 80)

# 1. 总体统计
print("\n" + "=" * 80)
print("1. 总体统计对比")
print("=" * 80)

print("\n{:<25} {:>15} {:>15} {:>15}".format("指标", "Baseline", "Hypothesis", "Fuzz+Hypo"))
print("-" * 70)
for key in ["submitted_instances", "completed_instances", "resolved_instances", "unresolved_instances", "empty_patch_instances", "error_instances"]:
    print("{:<25} {:>15} {:>15} {:>15}".format(
        key, 
        baseline.get(key, "N/A"),
        hypothesis.get(key, "N/A"),
        fuzz_hypo.get(key, "N/A")
    ))

# 计算解决率
baseline_rate = baseline["resolved_instances"] / baseline["completed_instances"] * 100 if baseline["completed_instances"] > 0 else 0
hypothesis_rate = hypothesis["resolved_instances"] / hypothesis["completed_instances"] * 100 if hypothesis["completed_instances"] > 0 else 0
fuzz_hypo_rate = fuzz_hypo["resolved_instances"] / fuzz_hypo["completed_instances"] * 100 if fuzz_hypo["completed_instances"] > 0 else 0

print("-" * 70)
print("{:<25} {:>14.1f}% {:>14.1f}% {:>14.1f}%".format(
    "解决率 (resolved/completed)",
    baseline_rate,
    hypothesis_rate,
    fuzz_hypo_rate
))

# 2. Resolved IDs 差异分析
print("\n" + "=" * 80)
print("2. Resolved IDs 差异分析")
print("=" * 80)

baseline_resolved = set(baseline["resolved_ids"])
hypothesis_resolved = set(hypothesis["resolved_ids"])
fuzz_hypo_resolved = set(fuzz_hypo["resolved_ids"])

# Baseline有但Hypothesis没有
baseline_only_vs_hypo = baseline_resolved - hypothesis_resolved
# Hypothesis有但Baseline没有
hypo_only_vs_baseline = hypothesis_resolved - baseline_resolved
# Baseline有但Fuzz+Hypo没有
baseline_only_vs_fuzz = baseline_resolved - fuzz_hypo_resolved
# Fuzz+Hypo有但Baseline没有
fuzz_only_vs_baseline = fuzz_hypo_resolved - baseline_resolved

print("\n2.1 Baseline vs Hypothesis:")
print(f"   Baseline独有解决: {len(baseline_only_vs_hypo)} 个")
if baseline_only_vs_hypo:
    for id_ in sorted(baseline_only_vs_hypo):
        print(f"      - {id_}")
print(f"   Hypothesis独有解决: {len(hypo_only_vs_baseline)} 个")
if hypo_only_vs_baseline:
    for id_ in sorted(hypo_only_vs_baseline):
        print(f"      + {id_}")

print("\n2.2 Baseline vs Fuzz+Hypo:")
print(f"   Baseline独有解决: {len(baseline_only_vs_fuzz)} 个")
if baseline_only_vs_fuzz:
    for id_ in sorted(baseline_only_vs_fuzz):
        print(f"      - {id_}")
print(f"   Fuzz+Hypo独有解决: {len(fuzz_only_vs_baseline)} 个")
if fuzz_only_vs_baseline:
    for id_ in sorted(fuzz_only_vs_baseline):
        print(f"      + {id_}")

# 三者共同解决
common_all = baseline_resolved & hypothesis_resolved & fuzz_hypo_resolved
print(f"\n2.3 三者共同解决: {len(common_all)} 个")

# 3. Completed IDs 差异分析  
print("\n" + "=" * 80)
print("3. Completed IDs 差异分析 (提交实例)")
print("=" * 80)

baseline_completed = set(baseline["completed_ids"])
hypothesis_completed = set(hypothesis["completed_ids"])
fuzz_hypo_completed = set(fuzz_hypo["completed_ids"])

print(f"\nBaseline完成: {len(baseline_completed)}")
print(f"Hypothesis完成: {len(hypothesis_completed)}")
print(f"Fuzz+Hypo完成: {len(fuzz_hypo_completed)}")

# 差异
baseline_only_completed = baseline_completed - hypothesis_completed
hypo_only_completed = hypothesis_completed - baseline_completed
fuzz_only_completed = fuzz_hypo_completed - baseline_completed
baseline_only_vs_fuzz_completed = baseline_completed - fuzz_hypo_completed

if baseline_only_completed:
    print(f"\n只在Baseline完成 (不在Hypothesis): {len(baseline_only_completed)}")
    for id_ in sorted(baseline_only_completed):
        print(f"   - {id_}")

if hypo_only_completed:
    print(f"\n只在Hypothesis完成 (不在Baseline): {len(hypo_only_completed)}")
    for id_ in sorted(hypo_only_completed):
        print(f"   + {id_}")

if baseline_only_vs_fuzz_completed:
    print(f"\n只在Baseline完成 (不在Fuzz+Hypo): {len(baseline_only_vs_fuzz_completed)}")
    for id_ in sorted(baseline_only_vs_fuzz_completed):
        print(f"   - {id_}")

if fuzz_only_completed:
    print(f"\n只在Fuzz+Hypo完成 (不在Baseline): {len(fuzz_only_completed)}")
    for id_ in sorted(fuzz_only_completed):
        print(f"   + {id_}")

# 4. Per-Instance 详细分析
print("\n" + "=" * 80)
print("4. Per-Instance 详细分析")
print("=" * 80)

baseline_per_instance = baseline.get("statistics", {}).get("per_instance", {})
hypothesis_per_instance = hypothesis.get("statistics", {}).get("per_instance", {})
fuzz_hypo_per_instance = fuzz_hypo.get("statistics", {}).get("per_instance", {})

# 获取共同的instance
common_instances = set(baseline_per_instance.keys()) & set(hypothesis_per_instance.keys()) & set(fuzz_hypo_per_instance.keys())
print(f"\n共同完成的实例数: {len(common_instances)}")

# 计算token使用统计
print("\n4.1 Token 使用统计 (仅共同实例):")

def get_token_stats(per_instance, instances):
    prompt_tokens = []
    completion_tokens = []
    cache_read_tokens = []
    total_tokens = []
    for inst in instances:
        if inst in per_instance:
            token_usage = per_instance[inst].get("token_usage", {})
            prompt_tokens.append(token_usage.get("prompt_tokens", 0))
            completion_tokens.append(token_usage.get("completion_tokens", 0))
            cache_read_tokens.append(token_usage.get("cache_read_tokens", 0))
            total_tokens.append(token_usage.get("total_tokens", 0))
    return {
        "prompt_tokens_avg": sum(prompt_tokens) / len(prompt_tokens) if prompt_tokens else 0,
        "prompt_tokens_total": sum(prompt_tokens),
        "completion_tokens_avg": sum(completion_tokens) / len(completion_tokens) if completion_tokens else 0,
        "completion_tokens_total": sum(completion_tokens),
        "cache_read_tokens_avg": sum(cache_read_tokens) / len(cache_read_tokens) if cache_read_tokens else 0,
        "cache_read_tokens_total": sum(cache_read_tokens),
        "total_tokens_avg": sum(total_tokens) / len(total_tokens) if total_tokens else 0,
        "total_tokens_total": sum(total_tokens),
    }

baseline_token_stats = get_token_stats(baseline_per_instance, common_instances)
hypothesis_token_stats = get_token_stats(hypothesis_per_instance, common_instances)
fuzz_hypo_token_stats = get_token_stats(fuzz_hypo_per_instance, common_instances)

print("\n{:<30} {:>20} {:>20} {:>20}".format("指标", "Baseline", "Hypothesis", "Fuzz+Hypo"))
print("-" * 90)
print("{:<30} {:>20,.0f} {:>20,.0f} {:>20,.0f}".format(
    "Prompt Tokens (平均)",
    baseline_token_stats["prompt_tokens_avg"],
    hypothesis_token_stats["prompt_tokens_avg"],
    fuzz_hypo_token_stats["prompt_tokens_avg"]
))
print("{:<30} {:>20,.0f} {:>20,.0f} {:>20,.0f}".format(
    "Completion Tokens (平均)",
    baseline_token_stats["completion_tokens_avg"],
    hypothesis_token_stats["completion_tokens_avg"],
    fuzz_hypo_token_stats["completion_tokens_avg"]
))
print("{:<30} {:>20,.0f} {:>20,.0f} {:>20,.0f}".format(
    "Cache Read Tokens (平均)",
    baseline_token_stats["cache_read_tokens_avg"],
    hypothesis_token_stats["cache_read_tokens_avg"],
    fuzz_hypo_token_stats["cache_read_tokens_avg"]
))
print("{:<30} {:>20,.0f} {:>20,.0f} {:>20,.0f}".format(
    "Total Tokens (平均)",
    baseline_token_stats["total_tokens_avg"],
    hypothesis_token_stats["total_tokens_avg"],
    fuzz_hypo_token_stats["total_tokens_avg"]
))

# 计算token差异百分比
prompt_diff_hypo = (hypothesis_token_stats["prompt_tokens_avg"] - baseline_token_stats["prompt_tokens_avg"]) / baseline_token_stats["prompt_tokens_avg"] * 100 if baseline_token_stats["prompt_tokens_avg"] else 0
prompt_diff_fuzz = (fuzz_hypo_token_stats["prompt_tokens_avg"] - baseline_token_stats["prompt_tokens_avg"]) / baseline_token_stats["prompt_tokens_avg"] * 100 if baseline_token_stats["prompt_tokens_avg"] else 0
completion_diff_hypo = (hypothesis_token_stats["completion_tokens_avg"] - baseline_token_stats["completion_tokens_avg"]) / baseline_token_stats["completion_tokens_avg"] * 100 if baseline_token_stats["completion_tokens_avg"] else 0
completion_diff_fuzz = (fuzz_hypo_token_stats["completion_tokens_avg"] - baseline_token_stats["completion_tokens_avg"]) / baseline_token_stats["completion_tokens_avg"] * 100 if baseline_token_stats["completion_tokens_avg"] else 0

print("\n相较于Baseline的Token变化:")
print(f"   Hypothesis: Prompt {prompt_diff_hypo:+.1f}%, Completion {completion_diff_hypo:+.1f}%")
print(f"   Fuzz+Hypo:  Prompt {prompt_diff_fuzz:+.1f}%, Completion {completion_diff_fuzz:+.1f}%")

# 5. Duration 和 Agent Actions 分析
print("\n" + "=" * 80)
print("5. 运行时间 & Agent Actions 分析")
print("=" * 80)

def get_performance_stats(per_instance, instances):
    durations = []
    agent_actions = []
    tool_success_rates = []
    for inst in instances:
        if inst in per_instance:
            durations.append(per_instance[inst].get("duration_seconds", 0))
            agent_actions.append(per_instance[inst].get("agent_actions", 0))
            tool_success_rates.append(per_instance[inst].get("tool_success_rate", 0))
    return {
        "duration_avg": sum(durations) / len(durations) if durations else 0,
        "duration_total": sum(durations),
        "agent_actions_avg": sum(agent_actions) / len(agent_actions) if agent_actions else 0,
        "agent_actions_total": sum(agent_actions),
        "tool_success_rate_avg": sum(tool_success_rates) / len(tool_success_rates) if tool_success_rates else 0,
    }

baseline_perf = get_performance_stats(baseline_per_instance, common_instances)
hypothesis_perf = get_performance_stats(hypothesis_per_instance, common_instances)
fuzz_hypo_perf = get_performance_stats(fuzz_hypo_per_instance, common_instances)

print("\n{:<30} {:>18} {:>18} {:>18}".format("指标", "Baseline", "Hypothesis", "Fuzz+Hypo"))
print("-" * 85)
print("{:<30} {:>18.1f} {:>18.1f} {:>18.1f}".format(
    "平均运行时间 (秒)",
    baseline_perf["duration_avg"],
    hypothesis_perf["duration_avg"],
    fuzz_hypo_perf["duration_avg"]
))
print("{:<30} {:>18.1f} {:>18.1f} {:>18.1f}".format(
    "总运行时间 (秒)",
    baseline_perf["duration_total"],
    hypothesis_perf["duration_total"],
    fuzz_hypo_perf["duration_total"]
))
print("{:<30} {:>18.1f} {:>18.1f} {:>18.1f}".format(
    "平均 Agent Actions",
    baseline_perf["agent_actions_avg"],
    hypothesis_perf["agent_actions_avg"],
    fuzz_hypo_perf["agent_actions_avg"]
))
print("{:<30} {:>18,.0f} {:>18,.0f} {:>18,.0f}".format(
    "总 Agent Actions",
    baseline_perf["agent_actions_total"],
    hypothesis_perf["agent_actions_total"],
    fuzz_hypo_perf["agent_actions_total"]
))
print("{:<30} {:>17.1f}% {:>17.1f}% {:>17.1f}%".format(
    "工具成功率",
    baseline_perf["tool_success_rate_avg"],
    hypothesis_perf["tool_success_rate_avg"],
    fuzz_hypo_perf["tool_success_rate_avg"]
))

# 计算差异
duration_diff_hypo = (hypothesis_perf["duration_avg"] - baseline_perf["duration_avg"]) / baseline_perf["duration_avg"] * 100 if baseline_perf["duration_avg"] else 0
duration_diff_fuzz = (fuzz_hypo_perf["duration_avg"] - baseline_perf["duration_avg"]) / baseline_perf["duration_avg"] * 100 if baseline_perf["duration_avg"] else 0
actions_diff_hypo = (hypothesis_perf["agent_actions_avg"] - baseline_perf["agent_actions_avg"]) / baseline_perf["agent_actions_avg"] * 100 if baseline_perf["agent_actions_avg"] else 0
actions_diff_fuzz = (fuzz_hypo_perf["agent_actions_avg"] - baseline_perf["agent_actions_avg"]) / baseline_perf["agent_actions_avg"] * 100 if baseline_perf["agent_actions_avg"] else 0

print("\n相较于Baseline的变化:")
print(f"   Hypothesis: 运行时间 {duration_diff_hypo:+.1f}%, Agent Actions {actions_diff_hypo:+.1f}%")
print(f"   Fuzz+Hypo:  运行时间 {duration_diff_fuzz:+.1f}%, Agent Actions {actions_diff_fuzz:+.1f}%")

# 6. 工具使用统计
print("\n" + "=" * 80)
print("6. 工具使用统计 (共同实例)")
print("=" * 80)

def get_tool_stats(per_instance, instances):
    tool_counts = defaultdict(int)
    for inst in instances:
        if inst in per_instance:
            tool_use_stats = per_instance[inst].get("tool_use_stats", {})
            for tool, stats in tool_use_stats.items():
                tool_counts[tool] += stats.get("count", 0)
    return dict(tool_counts)

baseline_tools = get_tool_stats(baseline_per_instance, common_instances)
hypothesis_tools = get_tool_stats(hypothesis_per_instance, common_instances)
fuzz_hypo_tools = get_tool_stats(fuzz_hypo_per_instance, common_instances)

all_tools = sorted(set(baseline_tools.keys()) | set(hypothesis_tools.keys()) | set(fuzz_hypo_tools.keys()))

print("\n{:<20} {:>15} {:>15} {:>15}".format("工具", "Baseline", "Hypothesis", "Fuzz+Hypo"))
print("-" * 65)
for tool in all_tools:
    print("{:<20} {:>15} {:>15} {:>15}".format(
        tool,
        baseline_tools.get(tool, 0),
        hypothesis_tools.get(tool, 0),
        fuzz_hypo_tools.get(tool, 0)
    ))

# 7. 按项目分组的解决率
print("\n" + "=" * 80)
print("7. 按项目分组的解决率")
print("=" * 80)

def group_by_project(ids):
    groups = defaultdict(list)
    for id_ in ids:
        # 从 "astropy__astropy-14096" 提取 "astropy__astropy"
        parts = id_.rsplit("-", 1)
        if len(parts) == 2:
            project = parts[0]
        else:
            project = id_
        groups[project].append(id_)
    return groups

baseline_resolved_groups = group_by_project(baseline_resolved)
hypothesis_resolved_groups = group_by_project(hypothesis_resolved)
fuzz_hypo_resolved_groups = group_by_project(fuzz_hypo_resolved)

baseline_completed_groups = group_by_project(baseline_completed)
hypothesis_completed_groups = group_by_project(hypothesis_completed)
fuzz_hypo_completed_groups = group_by_project(fuzz_hypo_completed)

all_projects = sorted(set(baseline_completed_groups.keys()) | set(hypothesis_completed_groups.keys()) | set(fuzz_hypo_completed_groups.keys()))

print("\n{:<35} {:>12} {:>12} {:>12}".format("项目", "Baseline", "Hypothesis", "Fuzz+Hypo"))
print("-" * 75)

for project in all_projects:
    b_resolved = len(baseline_resolved_groups.get(project, []))
    b_completed = len(baseline_completed_groups.get(project, []))
    h_resolved = len(hypothesis_resolved_groups.get(project, []))
    h_completed = len(hypothesis_completed_groups.get(project, []))
    f_resolved = len(fuzz_hypo_resolved_groups.get(project, []))
    f_completed = len(fuzz_hypo_completed_groups.get(project, []))
    
    b_str = f"{b_resolved}/{b_completed}" if b_completed > 0 else "N/A"
    h_str = f"{h_resolved}/{h_completed}" if h_completed > 0 else "N/A"
    f_str = f"{f_resolved}/{f_completed}" if f_completed > 0 else "N/A"
    
    print("{:<35} {:>12} {:>12} {:>12}".format(project, b_str, h_str, f_str))

# 8. 详细实例对比表
print("\n" + "=" * 80)
print("8. 详细实例对比表 (Baseline vs Hypothesis vs Fuzz+Hypo)")
print("=" * 80)

all_instances = sorted(baseline_completed | hypothesis_completed | fuzz_hypo_completed)

print("\n{:<40} {:>10} {:>10} {:>10}".format("Instance ID", "Baseline", "Hypothesis", "Fuzz+Hypo"))
print("-" * 75)

# 只显示有差异的
diff_instances = []
for inst in all_instances:
    b_status = "✅" if inst in baseline_resolved else ("❌" if inst in baseline_completed else "—")
    h_status = "✅" if inst in hypothesis_resolved else ("❌" if inst in hypothesis_completed else "—")
    f_status = "✅" if inst in fuzz_hypo_resolved else ("❌" if inst in fuzz_hypo_completed else "—")
    
    # 检查是否有差异
    if not (b_status == h_status == f_status):
        diff_instances.append((inst, b_status, h_status, f_status))

print(f"\n有差异的实例数: {len(diff_instances)}")
if diff_instances:
    print("\n{:<45} {:>10} {:>12} {:>12}".format("Instance ID", "Baseline", "Hypothesis", "Fuzz+Hypo"))
    print("-" * 80)
    for inst, b, h, f in diff_instances:
        print("{:<45} {:>10} {:>12} {:>12}".format(inst, b, h, f))

# 9. Fuzz+Hypo 相较于 Hypothesis 的改进
print("\n" + "=" * 80)
print("9. Fuzz+Hypo 相较于 Hypothesis 的改进分析")
print("=" * 80)

# 找出Hypothesis没有完成但Fuzz+Hypo完成的
fuzz_added_completed = fuzz_hypo_completed - hypothesis_completed
fuzz_added_resolved = fuzz_hypo_resolved - hypothesis_resolved

print(f"\nFuzz+Hypo 新增完成的实例 (相较于Hypothesis): {len(fuzz_added_completed)}")
if fuzz_added_completed:
    for inst in sorted(fuzz_added_completed):
        resolved_status = "✅ 已解决" if inst in fuzz_hypo_resolved else "❌ 未解决"
        print(f"   + {inst} ({resolved_status})")

print(f"\nFuzz+Hypo 新增解决的实例 (相较于Hypothesis): {len(fuzz_added_resolved)}")
if fuzz_added_resolved:
    for inst in sorted(fuzz_added_resolved):
        print(f"   + {inst}")

# 计算同时在Hypothesis和Fuzz+Hypo中完成的实例的性能对比
common_h_f = hypothesis_completed & fuzz_hypo_completed
print(f"\n同时在Hypothesis和Fuzz+Hypo中完成的实例: {len(common_h_f)}")

if common_h_f:
    h_perf_common = get_performance_stats(hypothesis_per_instance, common_h_f)
    f_perf_common = get_performance_stats(fuzz_hypo_per_instance, common_h_f)
    
    print(f"   Hypothesis 平均运行时间: {h_perf_common['duration_avg']:.1f}秒")
    print(f"   Fuzz+Hypo 平均运行时间: {f_perf_common['duration_avg']:.1f}秒")
    duration_diff = (f_perf_common['duration_avg'] - h_perf_common['duration_avg']) / h_perf_common['duration_avg'] * 100 if h_perf_common['duration_avg'] else 0
    print(f"   差异: {duration_diff:+.1f}%")

# 10. 总结
print("\n" + "=" * 80)
print("10. 总结")
print("=" * 80)

print("\n📊 整体表现:")
print(f"   Baseline:    解决 {baseline['resolved_instances']}/{baseline['completed_instances']} ({baseline_rate:.1f}%)")
print(f"   Hypothesis:  解决 {hypothesis['resolved_instances']}/{hypothesis['completed_instances']} ({hypothesis_rate:.1f}%)")
print(f"   Fuzz+Hypo:   解决 {fuzz_hypo['resolved_instances']}/{fuzz_hypo['completed_instances']} ({fuzz_hypo_rate:.1f}%)")

rate_diff_hypo = hypothesis_rate - baseline_rate
rate_diff_fuzz = fuzz_hypo_rate - baseline_rate

print("\n📈 相较于Baseline的变化:")
print(f"   Hypothesis: 解决率 {rate_diff_hypo:+.1f}%, Token使用 {prompt_diff_hypo:+.1f}%, 运行时间 {duration_diff_hypo:+.1f}%")
print(f"   Fuzz+Hypo:  解决率 {rate_diff_fuzz:+.1f}%, Token使用 {prompt_diff_fuzz:+.1f}%, 运行时间 {duration_diff_fuzz:+.1f}%")

print("\n🔍 关键发现:")
print(f"   1. Baseline完成 {len(baseline_completed)} 个实例, 解决 {len(baseline_resolved)} 个")
print(f"   2. Hypothesis完成 {len(hypothesis_completed)} 个实例, 解决 {len(hypothesis_resolved)} 个")
print(f"   3. Fuzz+Hypo完成 {len(fuzz_hypo_completed)} 个实例, 解决 {len(fuzz_hypo_resolved)} 个")

print(f"\n   • Hypothesis 相较于Baseline:")
if hypo_only_vs_baseline:
    print(f"     - 新解决: {sorted(hypo_only_vs_baseline)}")
if baseline_only_vs_hypo:
    print(f"     - 丢失解决: {sorted(baseline_only_vs_hypo)}")

print(f"\n   • Fuzz+Hypo 相较于Baseline:")
if fuzz_only_vs_baseline:
    print(f"     - 新解决: {sorted(fuzz_only_vs_baseline)}")
if baseline_only_vs_fuzz:
    print(f"     - 丢失解决: {sorted(baseline_only_vs_fuzz)}")

print(f"\n   • Fuzz+Hypo 相较于Hypothesis:")
fuzz_vs_hypo_new = fuzz_hypo_resolved - hypothesis_resolved
hypo_vs_fuzz_lost = hypothesis_resolved - fuzz_hypo_resolved
if fuzz_vs_hypo_new:
    print(f"     - 新解决: {sorted(fuzz_vs_hypo_new)}")
if hypo_vs_fuzz_lost:
    print(f"     - 丢失解决: {sorted(hypo_vs_fuzz_lost)}")

print("\n" + "=" * 80)
print("分析完成")
print("=" * 80)
