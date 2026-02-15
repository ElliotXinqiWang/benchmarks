import os
import argparse
from pathlib import Path
from benchmarks.swebench.run_infer import SWEBenchEvaluation, get_instruction
from benchmarks.utils.args_parser import get_parser
from benchmarks.utils.models import EvalMetadata, EvalInstance
from benchmarks.utils.evaluation_utils import construct_eval_output_dir, get_default_on_result_writer
from openhands.sdk import LLM, get_logger

logger = get_logger(__name__)

class VerifyPatchEvaluation(SWEBenchEvaluation):
    """
    专门用于验证 Patch 的评估类。
    """
    def __init__(self, *args, custom_patch=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_patch = custom_patch

    def evaluate_instance(self, instance, workspace):
        # 将 custom_patch 注入到 instance 数据中，以便 Prompt 模板可以访问
        instance.data['custom_patch'] = self.custom_patch
        return super().evaluate_instance(instance, workspace)

def main():
    parser = get_parser()
    parser.add_argument("--patch-path", type=str, required=True, help="Path to the patch file")
    parser.add_argument("--prompt-path", type=str, default="benchmarks/swebench/prompts/verify_patch.j2")
    args = parser.parse_args()

    # 读取 Patch 内容
    patch_path = Path(args.patch_path)
    if not patch_path.exists():
        raise FileNotFoundError(f"Patch file not found: {patch_path}")
    with open(patch_path, 'r') as f:
        custom_patch = f.read()

    # 加载 LLM 配置
    with open(args.llm_config_path, "r") as f:
        llm_config = f.read()
    llm = LLM.model_validate_json(llm_config)

    # 准备输出目录
    structured_output_dir = construct_eval_output_dir(
        base_dir=args.output_dir,
        dataset_name=args.dataset.replace("/", "__"),
        model_name=llm.model,
        max_iterations=args.max_iterations,
        eval_note="patch_verification"
    )

    metadata = EvalMetadata(
        llm=llm,
        dataset=args.dataset,
        dataset_split=args.split,
        max_iterations=args.max_iterations,
        eval_output_dir=structured_output_dir,
        details={},
        prompt_path=args.prompt_path,
        eval_limit=args.n_limit,
        env_setup_commands=["export PIP_CACHE_DIR=~/.cache/pip"],
        max_attempts=args.max_attempts,
        selected_instances_file=args.select,
        max_retries=args.max_retries,
        workspace_type=args.workspace,
        extra_tools=args.extra_tools,
    )

    evaluator = VerifyPatchEvaluation(
        metadata=metadata,
        num_workers=args.num_workers,
        custom_patch=custom_patch
    )

    evaluator.run(on_result=get_default_on_result_writer(evaluator.output_path))
    logger.info("Verification completed!")

if __name__ == "__main__":
    main()
