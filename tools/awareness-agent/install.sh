#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user"

ln -sfn "$ROOT/bin/awareness" "$HOME/.local/bin/awareness"
"$HOME/.local/bin/awareness" init

cp "$ROOT/systemd/awareness-agent.service" "$HOME/.config/systemd/user/awareness-agent.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true

cat <<MSG
installed awareness-agent spike A0

CLI:
  ~/.local/bin/awareness status

Manual daemon:
  awareness start
  awareness stop

Optional systemd user service:
  systemctl --user enable --now awareness-agent
MSG
