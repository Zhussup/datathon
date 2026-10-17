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
  pulse)
    ssh "$TARGET" "echo '--- процессы ---'; pgrep -af 'setup_neuro|pip3 install' | head -5 || true; echo '--- размеры ---'; du -sh /tmp/pip-* 2>/dev/null | head -5; du -sh /home/sadmin/.cache/pip ~/.cache/pip 2>/dev/null; du -sh $DIR/venv 2>/dev/null; echo '--- хвост лога ---'; tail -3 $DIR/neuro_setup.log 2>/dev/null"
    ;;
  frames)
    echo "--- заливка w1_frames (rsync, докачиваемо; ~сотни МБ) ---"
    rsync -az --partial --info=progress2 "$HERE/../w1_frames" "$TARGET:$DIR/"
    ;;
  preds)
    ssh "$TARGET" "mkdir -p $DIR/scripts"
    cat "$HERE/predlabel_w1.py" | ssh "$TARGET" "cat > $DIR/scripts/predlabel_w1.py"
    cat "$HERE/make_w1_frames.py" | ssh "$TARGET" "cat > $DIR/scripts/make_w1_frames.py" 2>/dev/null
    ssh "$TARGET" "cd $DIR && (nohup $DIR/venv/bin/python scripts/predlabel_w1.py > predlabel.log 2>&1 &) && echo 'предразметка запущена'"
    echo "--- прогресс: $0 plog ---"
    ;;
  plog)
    ssh "$TARGET" "tail -40 $DIR/predlabel.log 2>/dev/null || echo 'лога ещё нет'"
    ;;
  full)
    ssh "$TARGET" "cat $DIR/neuro_setup.log 2>/dev/null || echo 'лога ещё нет'"
    ;;
  *)
    echo "usage: NEURO_HOST=<ip> $0 start|status|log|report|full"
    exit 2
    ;;
esac