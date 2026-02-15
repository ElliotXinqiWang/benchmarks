import os
import json
import argparse
import glob
from pathlib import Path
from benchmarks.swebench.run_infer import SWEBenchEvaluation
from benchmarks.utils.args_parser import get_parser
from benchmarks.utils.models import EvalMetadata, EvalInstance
from benchmarks.utils.evaluation_utils import construct_eval_output_dir, get_default_on_result_writer
from benchmarks.utils.critics import create_critic
from openhands.sdk import LLM, get_logger

logger = get_logger(__name__)

class BatchVerifyEvaluation(SWEBenchEvaluation):
    patch_map: dict = {}

    def __init__(self, *args, patch_map=None, **kwargs):
        super().__init__(*args, **kwargs)
        object.__setattr__(self, 'patch_map', patch_map or {})

    def evaluate_instance(self, instance, workspace):
        instance_id = instance.id
        if instance_id in self.patch_map:
            logger.info(f"Injecting patch for {instance_id}")
            instance.data['custom_patch'] = self.patch_map[instance_id]
        else:
            logger.warning(f"No patch found for {instance_id}, skipping verification or using empty.")
            instance.data['custom_patch'] = ""
        
        # 物理隔离：删除原有的 tests 目录，防止 Agent 偷看
        repo_name = instance.data['repo'].split('/')[-1]
        repo_path = f"/workspace/{repo_name}"
        logger.info(f"Cleaning up official tests in {repo_path}/tests")
        workspace.execute_command(f"rm -rf {repo_path}/tests {repo_path}/testing")
        
        return super().evaluate_instance(instance, workspace)

def main():
    parser = get_parser()
    parser.add_argument("--input-jsonl", type=str, required=True, help="Path to the output.jsonl from swebench-infer")
    parser.add_argument("--prompt-path", type=str, default="benchmarks/swebench/prompts/verify_patch_blind.j2")
    args = parser.parse_args()

    # 1. 解析 JSONL，获取所有 patch
    patch_map = {}
    with open(args.input_jsonl, 'r') as f:
        for line in f:
            data = json.loads(line)
            inst_id = data['instance_id']
            patch = data.get('test_result', {}).get('git_patch', '')
            if patch:
                patch_map[inst_id] = patch

    # 2. 准备实例 ID 列表
    # 我们需要保持 --select 文件中的原始顺序
    to_verify_ids = []
    
    if args.select:
        with open(args.select, 'r') as f:
            for line in f:
                inst_id = line.strip()
                if inst_id and inst_id in patch_map:
                    to_verify_ids.append(inst_id)
    else:
        # 如果没有指定 select，则按 patch_map 的键排序（通常是 JSONL 中的顺序）
        to_verify_ids = list(patch_map.keys())
    
    # 限制数量（选择前 n 个）
    if args.n_limit > 0:
        to_verify_ids = to_verify_ids[:args.n_limit]

    if not to_verify_ids:
        logger.error("No instances found to verify based on selection and JSONL content.")
        return

    temp_instances = "temp_to_verify.txt"
    with open(temp_instances, "w") as f:
        for inst_id in to_verify_ids:
            f.write(f"{inst_id}\n")

    # 3. 配置 LLM
    with open(args.llm_config_path, "r") as f:
        llm_config = f.read()
    llm = LLM.model_validate_json(llm_config)

    # 4. 准备输出目录
    structured_output_dir = construct_eval_output_dir(
        base_dir=args.output_dir,
        dataset_name="swebench_verify",
        model_name=llm.model,
        max_iterations=args.max_iterations,
        eval_note="batch_blind_verify"
    )

    # --- 新增：清理之前的结果缓存 ---
    logger.info("Cleaning up previous results for selected instances...")
    for inst_id in to_verify_ids:
        # 删除日志文件
        log_pattern = os.path.join(structured_output_dir, "logs", f"instance_{inst_id}.*")
        for log_file in glob.glob(log_pattern):
            try:
                os.remove(log_file)
            except Exception as e:
                logger.warning(f"Failed to remove log file {log_file}: {e}")
        
        # 删除会话归档
        conv_file = os.path.join(structured_output_dir, "conversations", f"{inst_id}.tar.gz")
        if os.path.exists(conv_file):
            try:
                os.remove(conv_file)
            except Exception as e:
                logger.warning(f"Failed to remove conversation file {conv_file}: {e}")

    # 5. 运行
    critic = create_critic(args)
    logger.info(f"Using critic: {type(critic).__name__}")

    metadata = EvalMetadata(
        llm=llm,
        dataset=args.dataset,
        dataset_split=args.split,
        max_iterations=args.max_iterations,
        eval_output_dir=structured_output_dir,
        prompt_path=args.prompt_path,
        env_setup_commands=["export PIP_CACHE_DIR=~/.cache/pip"],
        selected_instances_file=temp_instances,
        workspace_type=args.workspace,
        extra_tools=args.extra_tools,
        critic=critic,
        details={},
    )

    evaluator = BatchVerifyEvaluation(
        metadata=metadata,
        num_workers=args.num_workers,
        patch_map=patch_map
    )

    evaluator.run(on_result=get_default_on_result_writer(evaluator.output_path))
    
    # --- 新增：自动解析结论并生成报告 ---
    logger.info("Generating agent_verification_report.jsonl...")
    report_path = Path(evaluator.output_path).parent / "agent_verification_report.jsonl"
    
    with open(evaluator.output_path, 'r') as f_in, open(report_path, 'w') as f_out:
        for line in f_in:
            data = json.loads(line)
            inst_id = data['instance_id']
            
            # 提取 Agent 的最后一条消息
            verdict = "UNKNOWN"
            # 优先从 FinishAction 中提取结论
            finish_msgs = [
                h.get('message', '') 
                for h in data.get('history', []) 
                if h.get('action') == 'finish' and h.get('message')
            ]
            
            # 如果没有明确的 FinishAction 消息，则扫描所有来自 Agent 的内容
            if finish_msgs:
                combined_text = "\n".join(finish_msgs).upper()
            else:
                agent_msgs = []
                for h in data.get('history', []) :
                    if h.get('source') == 'agent':
                        if h.get('message'):
                            agent_msgs.append(h['message'])
                        if h.get('llm_message') and isinstance(h['llm_message'], dict):
                            content = h['llm_message'].get('content')
                            if content:
                                if isinstance(content, list):
                                    # 处理多模态或列表格式的消息内容
                                    content_text = ""
                                    for item in content:
                                        if isinstance(item, dict) and 'text' in item:
                                            content_text += item['text']
                                        elif isinstance(item, str):
                                            content_text += item
                                    agent_msgs.append(content_text)
                                else:
                                    agent_msgs.append(str(content))
                combined_text = "\n".join(agent_msgs).upper()
            
            if "[VERDICT]: FIXED" in combined_text:
                verdict = "FIXED"
            elif "[VERDICT]: FAILED" in combined_text:
                verdict = "FAILED"
            
            report_entry = {
                "instance_id": inst_id,
                "verdict": verdict
            }
            f_out.write(json.dumps(report_entry) + "\n")

    logger.info(f"Report generated at: {report_path}")
    
    if os.path.exists(temp_instances):
        os.remove(temp_instances)

if __name__ == "__main__":
    main()
