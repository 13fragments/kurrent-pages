# EVO VLM Endpoint

OpenAI-compatible VLM serving for the GMKtec EVO-X2 / Ryzen AI Max+ 395 box.

## Shape

- Server: vLLM OpenAI-compatible server on ROCm
- Default model: `Qwen/Qwen2.5-VL-3B-Instruct-AWQ`
- Served model name: `qwen2.5-vl-3b-awq`
- Context: `--max-model-len 16384`
- Benchmark role: silver stand-in only; the pre-registered §6 gold VLM remains
  `Qwen3-VL-4B`.
- API: `http://<tailscale-ip>:8080/v1`
- Main endpoint: `/v1/chat/completions`

vLLM is used because it exposes the OpenAI-compatible chat-completions API and
supports image inputs for Qwen2.5-VL/Qwen3-VL.

## Current EVO Deployment

The live EVO box does not currently have Docker or passwordless sudo. It is
running a user-level service from the Lemonade portable ROCm vLLM bundle:

```sh
ssh <user>@<evo-host> 'systemctl --user status evo-vlm.service'
ssh <user>@<evo-host> 'journalctl --user -u evo-vlm.service -f'
ssh <user>@<evo-host> '$HOME/.local/share/evo-vlm/smoke-test.sh'
```

Runtime config lives at:

```sh
~/.local/share/evo-vlm/evo-vlm.env
```

The Qwen AWQ target config is backed up on the EVO as:

```sh
~/.local/share/evo-vlm/evo-vlm.env.qwen2.5-vl-3b-awq
```

For gold reporting, treat the live Qwen2.5-VL-3B AWQ service as a silver
stand-in. A gold Qwen run needs the pre-registered §6 Qwen3-VL-4B model or a
protocol amendment.

## Install On EVO

Prerequisite: unpack the Lemonade ROCm vLLM bundle so
`$HOME/.local/share/evo-vlm/vllm-rocm/vllm-rocm.tmp/bin/vllm-server` exists.

From this directory on the EVO, install the user service:

```sh
./install.sh
$EDITOR ~/.local/share/evo-vlm/evo-vlm.env
systemctl --user enable --now evo-vlm.service
journalctl --user -u evo-vlm.service -f
```

Set `VLLM_HOST` to the EVO Tailscale IP for a tailnet-only bind, or leave
`0.0.0.0` if the host firewall already restricts access.

## Smoke Test

```sh
./smoke-test.sh http://127.0.0.1:8080/v1 qwen2.5-vl-3b-awq
```

From another tailnet machine:

```sh
./smoke-test.sh http://<evo-host>:8080/v1 qwen2.5-vl-3b-awq
```

## Swap Models

Edit `~/.local/share/evo-vlm/evo-vlm.env`:

```sh
VLLM_MODEL=Qwen/Qwen3-VL-4B-Instruct
VLLM_SERVED_MODEL=qwen3-vl-4b-instruct
VLLM_EXTRA_ARGS='--trust-remote-code --limit-mm-per-prompt {"image":1}'
```

Then:

```sh
systemctl --user restart evo-vlm.service
```
