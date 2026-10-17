#!/usr/bin/env bash
# ============================================================================
# Управление сервером neuro БЕЗ интерактивной сессии (для медленного интернета).
#
#   NEURO_HOST=1.2.3.4 scripts/run_neuro.sh start   # залить setup_neuro.sh и запустить в фоне
#   NEURO_HOST=1.2.3.4 scripts/run_neuro.sh status  # идёт ли установка
#   NEURO_HOST=1.2.3.4 scripts/run_neuro.sh log     # хвост лога
#   NEURO_HOST=1.2.3.4 scripts/run_neuro.sh report  # только блок REPORT (мелкий вывод)
#   NEURO_HOST=1.2.3.4 scripts/run_neuro.sh full    # весь лог
#
# Лаги ввода не важны: одна команда → отрываешься → смотришь лог позже.
# Скрипту на сервере всё равно, жива ли сессия (nohup).
# ============================================================================
set -euo pipefail
HOST=${NEURO_HOST:?передай адрес сервера: NEURO_HOST=ip scripts/run_neuro.sh start}
USER_S=${NEURO_USER:-sadmin}
TARGET="$USER_S@$HOST"
DIR=/home/zhus/datathon
HERE=$(cd "$(dirname "$0")" && pwd)

case "${1:-}" in
  start)
    ssh "$TARGET" "mkdir -p $DIR"
    cat "$HERE/setup_neuro.sh" | ssh "$TARGET" "cat > $DIR/setup_neuro.sh"
    echo "--- запускаю в фоне ---"
    ssh "$TARGET" "cd $DIR && (nohup bash setup_neuro.sh > neuro_setup.log 2>&1 &) && echo 'стартовано; лог: '$DIR'/neuro_setup.log'"
    echo "--- через несколько минут: $0 log / $0 report ---"
    ;;
  status)
    ssh "$TARGET" "pgrep -af 'setup_neuro' || echo 'процесс не запущен'"
    ssh "$TARGET" "ls -l $DIR/neuro_setup.log 2>/dev/null || echo 'лога ещё нет'"
    ;;
  log)
    ssh "$TARGET" "tail -60 $DIR/neuro_setup.log 2>/dev/null || echo 'лога ещё нет'"
    ;;
  report)
    ssh "$TARGET" "sed -n '/=== REPORT/,\$p' $DIR/neuro_setup.log 2>/dev/null | head -40"
    ;;
  full)
    ssh "$TARGET" "cat $DIR/neuro_setup.log 2>/dev/null || echo 'лога ещё нет'"
    ;;
  *)
    echo "usage: NEURO_HOST=<ip> $0 start|status|log|report|full"
    exit 2
    ;;
esac