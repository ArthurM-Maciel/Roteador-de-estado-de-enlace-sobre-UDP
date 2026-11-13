#!/usr/bin/env bash
# Sobe os 5 roteadores da topologia de teste do relatorio, cada um num
# terminal separado do tmux. Logs em logs/t<N>.log.
#
#   ./scripts/subir_teste.sh          sobe
#   tmux attach -t roteadores         acompanha
#   tmux kill-session -t roteadores   derruba tudo
set -euo pipefail
cd "$(dirname "$0")/.."

command -v tmux >/dev/null || { echo "tmux nao encontrado: brew install tmux"; exit 1; }
tmux kill-session -t roteadores 2>/dev/null || true
tmux new-session -d -s roteadores -n t1 "python3 src/roteador.py config/teste/t1.conf; read"
for n in 2 3 4 5; do
  tmux new-window -t roteadores -n "t$n" "python3 src/roteador.py config/teste/t$n.conf; read"
done
echo "5 roteadores no tmux 'roteadores'.  tmux attach -t roteadores"
