uv run benchmarks/swebench/build_images.py \
  --dataset princeton-nlp/SWE-bench_Verified \
  --split test \
  --image ghcr.io/openhands/eval-agent-server \
  --target source-minimal \
  --num-workers 4 \
  --select instances_test.txt

uv run swebench-infer .llm_config/openrouter.json \
    --select instances.txt \
    --workspace docker \
    --output-dir ./eval_outputs \
    --max-attempts 3 \
    --max-retries 1 \
    --num-workers 5 \
    --prompt-path benchmarks/swebench/prompts/default.j2

uv run swebench-eval ./eval_outputs/princeton-nlp__SWE-bench_Verified-test/openrouter/anthropic/claude-sonnet-4_sdk_73769d5_maxiter_100_N_initial/output.jsonl \
  --dataset princeton-nlp/SWE-bench_Verified \
  --output-file results.swebench.jsonl \
  --workers 5

uv run swebench-infer .llm_config/openrouter.json \
    --select instances.txt \
    --workspace docker \
    --output-dir ./eval_outputs_hypothesis \
    --max-attempts 3 \
    --max-retries 1 \
    --num-workers 5 \
    --prompt-path benchmarks/swebench/prompts/hypothesis_default.j2

uv run swebench-eval ./eval_outputs_hypothesis/princeton-nlp__SWE-bench_Verified-test/openrouter/anthropic/claude-sonnet-4_sdk_73769d5_maxiter_100_N_initial/output.jsonl \
  --dataset princeton-nlp/SWE-bench_Verified \
  --output-file results.swebench.jsonl \
  --workers 5