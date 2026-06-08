#!/usr/bin/env bash
set -euo pipefail

systemctl --user disable --now awareness-agent >/dev/null 2>&1 || true

rm -f "$HOME/.local/bin/awareness"
rm -f "$HOME/.config/systemd/user/awareness-agent.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true

if [ "${1:-}" = "--purge" ]; then
  rm -rf \
    "$HOME/.config/awareness-agent" \
    "$HOME/.local/share/awareness-agent" \
    "$HOME/.local/state/awareness-agent"
  echo "uninstalled awareness-agent and purged local data"
else
  echo "uninstalled awareness-agent launcher/service; local data preserved"
fi
