#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

app_dir="${EVO_VLM_APP_DIR:-$HOME/.local/share/evo-vlm}"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

install -d -m 0755 "$app_dir" "$unit_dir"
install -m 0755 run-vllm.sh "$app_dir/run-vllm.sh"
install -m 0755 smoke-test.sh "$app_dir/smoke-test.sh"
install -m 0644 evo-vlm.service "$unit_dir/evo-vlm.service"

if [[ ! -f "$app_dir/evo-vlm.env" ]]; then
  install -m 0644 evo-vlm.env.example "$app_dir/evo-vlm.env"
  echo "created $app_dir/evo-vlm.env"
else
  echo "kept existing $app_dir/evo-vlm.env"
fi

systemctl --user daemon-reload
echo "installed evo-vlm.service"
echo "next: edit $app_dir/evo-vlm.env, then systemctl --user enable --now evo-vlm.service"
