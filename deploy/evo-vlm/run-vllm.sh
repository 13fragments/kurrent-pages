#!/usr/bin/env bash
set -euo pipefail

env_file="${EVO_VLM_ENV:-$HOME/.local/share/evo-vlm/evo-vlm.env}"
source "$env_file"

: "${BUNDLE_DIR:=$HOME/.local/share/evo-vlm/vllm-rocm/vllm-rocm.tmp}"
: "${HF_HOME:=$HOME/.cache/huggingface}"
: "${VLLM_MODEL:=Qwen/Qwen2.5-VL-3B-Instruct-AWQ}"
: "${VLLM_SERVED_MODEL:=qwen2.5-vl-3b-awq}"
: "${VLLM_HOST:=0.0.0.0}"
: "${VLLM_PORT:=8080}"
: "${VLLM_MAX_MODEL_LEN:=4096}"
: "${VLLM_GPU_MEMORY_UTILIZATION:=0.80}"
: "${VLLM_DTYPE:=float16}"

mkdir -p "$HF_HOME"

if [[ ! -x "$BUNDLE_DIR/bin/vllm-server" ]]; then
  echo "vllm-server not found at $BUNDLE_DIR/bin/vllm-server" >&2
  exit 1
fi

export HF_HOME
export HF_XET_HIGH_PERFORMANCE="${HF_XET_HIGH_PERFORMANCE:-1}"
export HF_XET_NUM_CONCURRENT_RANGE_GETS="${HF_XET_NUM_CONCURRENT_RANGE_GETS:-64}"
export HF_HUB_DOWNLOAD_TIMEOUT="${HF_HUB_DOWNLOAD_TIMEOUT:-60}"
export HIP_VISIBLE_DEVICES="${HIP_VISIBLE_DEVICES:-0}"
export PYTHONUNBUFFERED=1

args=(
  --model "$VLLM_MODEL"
  --served-model-name "$VLLM_SERVED_MODEL"
  --host "$VLLM_HOST"
  --port "$VLLM_PORT"
  --max-model-len "$VLLM_MAX_MODEL_LEN"
  --gpu-memory-utilization "$VLLM_GPU_MEMORY_UTILIZATION"
  --dtype "$VLLM_DTYPE"
)

if [[ -n "${HUGGING_FACE_HUB_TOKEN:-}" ]]; then
  export HUGGING_FACE_HUB_TOKEN
fi

if [[ -n "${HSA_OVERRIDE_GFX_VERSION:-}" ]]; then
  export HSA_OVERRIDE_GFX_VERSION
fi

if [[ -n "${VLLM_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_args=($VLLM_EXTRA_ARGS)
  args+=("${extra_args[@]}")
fi

exec "$BUNDLE_DIR/bin/vllm-server" "${args[@]}"
