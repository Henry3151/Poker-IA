#!/usr/bin/env bash
# Poker AI Tournament Lab - abre a interface local no navegador (servidor só em 127.0.0.1).
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .venv/bin/activate ]; then
  echo "Primeiro uso: crie o ambiente (veja docs/COMO_USAR.md, seção 1)." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
exec python -m poker_lab.api.launch "$@"
