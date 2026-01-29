uv run benchmarks/swebench/build_images.py \
  --dataset princeton-nlp/SWE-bench_Verified \
  --split test \
  --image ghcr.io/openhands/eval-agent-server \
  --target source-minimal \
  --num-workers 4 \
  --select instances_1.txt \
  --n-limit 100

uv run swebench-infer .llm_config/openrouter.json \
    --select instances_1.txt \
    --workspace docker \
    --output-dir ./eval_outputs_fuzz_test \
    --max-attempts 3 \
    --max-retries 1 \
    --max-iterations 50 \
    --extra-tools fuzz_hypo \
    --num-workers 5 \
    --prompt-path benchmarks/swebench/prompts/hypothesis_test_prompt.j2\
    --n-limit 100

# uv run swebench-eval ./eval_outputs_fuzz_test/princeton-nlp__SWE-bench_Verified-test/openrouter/anthropic/claude-sonnet-4_sdk_73769d5_maxiter_100_N_initial/output.jsonl \
#   --dataset princeton-nlp/SWE-bench_Verified \
#   --output-file results.swebench.jsonl \
#   --workers 5
