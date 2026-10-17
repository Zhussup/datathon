#!/usr/bin/env bash
# ============================================================================
# W2-подготовка сервера neuro (без sudo, в venv, докачиваемо, ПРОВЕРЯЙ-ПОТОМ-СТАВЬ).
#
# Логика: сначала инвентаризация (GPU, диск, llama-server, python, venv, torch,
# веса). Ставим/качаем ТОЛЬКО недостающее; сеть проверяем лишь если что-то
# реально нужно скачать. Повторный запуск безопасен.
#
# Запуск на сервере:
#   cd /home/zhus/datathon && bash setup_neuro.sh 2>&1 | tee neuro_setup.log
# Затем прислать neuro_setup.log (или блок === REPORT ... REPORT ===).
# ============================================================================
set -u
cd /home/zhus/datathon || { echo "нет папки /home/zhus/datathon"; exit 1; }
ROOT=/home/zhus/datathon
VENV=$ROOT/venv
WEIGHTS=$ROOT/weights
WORLD_PT=$WEIGHTS/yolov8x-worldv2.pt
mkdir -p "$WEIGHTS"

FAILURES=()
fail() { echo "[FAIL] $1"; FAILURES+=("$1"); }
ok()   { echo "[OK]   $1"; }

echo "===================== 1. ДИАГНОСТИКА ЖЕЛЕЗА ====================="
cat /etc/os-release 2>/dev/null | head -1 || true
date -u
echo; echo "--- GPU ---"
nvidia-smi --query-gpu=index,name,memory.used,memory.total,driver_version,compute_cap --format=csv \
  || fail "nvidia-smi не отвечает"
echo; echo "--- llama-server (только смотрим, не трогаем) ---"
pgrep -a llama-server 2>/dev/null | head -3 || echo "не запущен"
echo; echo "--- диск ---"
df -h "$ROOT" | tail -1
AVAIL_KB=$(df -k --output=avail "$ROOT" 2>/dev/null | tail -1 | tr -d ' ')
if [ -n "$AVAIL_KB" ] && [ "$AVAIL_KB" -lt 25165824 ]; then
  fail "на диске < 25 ГБ свободно — cu128-torch + кэш HF могут не влезть"
fi
echo; echo "--- системный python ---"
python3 -V || fail "python3 не найден"

echo; echo "===================== 2. ИНВЕНТАРИЗАЦИЯ ОКРУЖЕНИЯ ====================="
# --- venv есть? torch в нём подходит (>=2.7, сборка cu*, CUDA живой)? ---
NEED_VENV=1; NEED_TORCH=1; TORCH_FOUND=""
if [ -x "$VENV/bin/python3" ]; then
  if check=$("$VENV/bin/python3" - <<'PY' 2>&1
try:
    import torch
except Exception as e:
    print(f"torch: нет ({type(e).__name__})"); raise SystemExit
ver = torch.__version__
base = ver.split("+")[0]
parts = base.split(".")
minor = (int(parts[0]), int(parts[1])) if len(parts) >= 2 else (0, 0)
why = []
if minor < (2, 7): why.append(f"версия {ver} < 2.7 (Blackwell sm_120 требует 2.7+)")
elif "+cu" not in ver: why.append("сборка без CUDA")
elif not torch.cuda.is_available(): why.append("cuda.is_available()==False")
else: print(f"torch: {ver}, GPU: {torch.cuda.device_count()}, ok"); raise SystemExit
print("torch: " + "; ".join(why))
PY
) ; then
    TORCH_FOUND="$check"
    NEED_VENV=0
    case "$check" in *", ok") NEED_TORCH=0 ;; esac
    echo "venv есть: $check"
  else
    echo "venv есть, но torch не поднялся: $check"
  fi
else
  echo "venv нет — будет создан ($VENV)"
fi
echo "NEED_VENV=$NEED_VENV NEED_TORCH=$NEED_TORCH"

NEED_RFDETR=1; NEED_YOLO=1
if [ "$NEED_TORCH" = 0 ] || [ -x "$VENV/bin/python3" ]; then
  "$VENV/bin/python3" -c "import rfdetr" >/dev/null 2>&1 && NEED_RFDETR=0
  "$VENV/bin/python3" -c "import ultralytics" >/dev/null 2>&1 && NEED_YOLO=0
fi
echo "NEED_RFDETR=$NEED_RFDETR NEED_YOLO=$NEED_YOLO"

NEED_WGET=0
if [ -s "$WORLD_PT" ]; then NEED_WGET=0; echo "вес YOLO-World уже: $(ls -lh "$WORLD_PT" | awk '{print $5}')"
else NEED_WGET=1; fi

RFDETR_PT=$(find "$ROOT" -maxdepth 1 -name "*.pth" -size +10M 2>/dev/null | head -1)
if [ -n "$RFDETR_PT" ]; then echo "веса RF-DETR похоже уже лежат: $RFDETR_PT"; fi

NEED_NET=0
[ "$NEED_TORCH" = 1 ] || [ "$NEED_RFDETR" = 1 ] || [ "$NEED_YOLO" = 1 ] || [ "$NEED_WGET" = 1 ] && NEED_NET=1
echo "NEED_NET=$NEED_NET"

echo; echo "===================== 3. СТАВИМ ТОЛЬКО НЕДОСТАЮЩЕЕ ====================="
if [ "$NEED_NET" = 1 ]; then
  echo "--- доступность сети (нужна: есть что ставить) ---"
  curl -sS -m 10 -o /dev/null -w "pypi.org: HTTP %{http_code}\n" https://pypi.org/simple/ || fail "нет доступа к pypi.org"
  if [ "$NEED_WGET" = 1 ]; then
    curl -sS -m 10 -o /dev/null -w "github.com: HTTP %{http_code}\n" https://github.com || fail "нет доступа к github.com"
  fi
  if [ "$NEED_TORCH" = 1 ]; then
    curl -sS -m 10 -o /dev/null -w "download.pytorch.org: HTTP %{http_code}\n" https://download.pytorch.org/whl/cu128 || fail "нет доступа к download.pytorch.org"
  fi
else
  echo "--- сеть не понадобилась: всё уже на месте ---"
fi

if [ "$NEED_VENV" = 1 ] || [ "$NEED_NET" = 1 ]; then
  echo "--- venv ---"
  if [ -x "$VENV/bin/pip3" ]; then
    ok "venv уже есть"
  else
    if python3 -m venv "$VENV" 2>/dev/null; then ok "venv создан"
    else fail "venv создать (пакет python3-venv установлен?)"; fi
  fi
  if [ -x "$VENV/bin/pip3" ]; then
    "$VENV/bin/pip3" install --quiet --upgrade pip || fail "pip upgrade"
  fi
fi

if [ "$NEED_TORCH" = 1 ]; then
  echo "--- torch+torchvision cu128 (долго: ~2-6 ГБ) ---"
  if "$VENV/bin/pip3" install "torch>=2.7,<3" torchvision --index-url https://download.pytorch.org/whl/cu128; then
    ok "torch cu128"
  else
    fail "torch cu128 install"
  fi
else
  ok "torch уже в порядке"
fi

if [ "$NEED_RFDETR" = 1 ]; then
  echo "--- rfdetr (Apache-2.0) + supervision ---"
  if "$VENV/bin/pip3" install --quiet rfdetr; then ok "rfdetr install"; else fail "rfdetr install"; fi
else
  ok "rfdetr уже есть"
fi
if [ "$NEED_YOLO" = 1 ]; then
  echo "--- ultralytics (AGPL — инструмент предразметки, вне поставки) ---"
  if "$VENV/bin/pip3" install --quiet ultralytics; then ok "ultralytics install"; else fail "ultralytics install"; fi
else
  ok "ultralytics уже есть"
fi

if [ "$NEED_WGET" = 1 ]; then
  echo "--- веса YOLO-World v2 ---"
  if wget -c -q --show-progress -O "$WORLD_PT" \
      https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8x-worldv2.pt; then
    ok "yolov8x-worldv2.pt скачан"
  else
    fail "скачать yolov8x-worldv2.pt (github.com доступен?)"
  fi
fi

# Смоуки — дешёвые локальные проверки, выполняем всегда (это и есть «проверка»).
echo; echo "--- CUDA-смоук из venv (GPU реально считает) ---"
if [ -x "$VENV/bin/python3" ]; then
  if "$VENV/bin/python3" - <<'PY'
import torch
print("torch:", torch.__version__, "| cuda:", torch.version.cuda)
print("available:", torch.cuda.is_available(), "| devices:", torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    print(f"  [{i}] {torch.cuda.get_device_name(i)} sm={torch.cuda.get_device_capability(i)}")
x = torch.randn(8, 8, device="cuda")
print("matmul on cuda ok:", bool((x @ x).sum().item() != 0.0))
PY
  then ok "CUDA-смоук"; else fail "CUDA-смоук"; fi
else
  fail "CUDA-смоук: venv не собрался"
fi

echo; echo "--- init весов rfdetr (локально, если кэш есть — без сети) ---"
if [ -x "$VENV/bin/python3" ]; then
  if "$VENV/bin/python3" - <<'PY'
from rfdetr import RFDETRBase
m = RFDETRBase(pretrain_weights="coco")
print("rfdetr загружен, ок")
PY
  then ok "rfdetr init"; else fail "rfdetr init (весов нет/сеть?)"; fi
fi

echo; echo "--- смоук YOLO-World (open-vocab) ---"
if [ -x "$VENV/bin/python3" ] && [ -s "$WORLD_PT" ]; then
  if "$VENV/bin/python3" - <<PY
from ultralytics import YOLO
m = YOLO("$WORLD_PT")
m.set_classes(["banknotes", "money bag", "safe"])
print("yolo-world загружен, ок")
PY
  then ok "yolo-world смоук"; else fail "yolo-world смоук"; fi
else
  echo "пропущено: весов нет"
fi

echo; echo "===================== REPORT (прислать Жусу) ====================="
echo "--- python venv ---"
"$VENV/bin/python3" -V 2>/dev/null || echo "venv python не поднялся"
echo "--- установленные ключевые пакеты ---"
"$VENV/bin/pip3" list 2>/dev/null | grep -Ei "torch|ultralytics|supervision|rfdetr|numpy|opencv" || true
echo "--- веса ---"
ls -lh "$WEIGHTS" 2>/dev/null | tail -n +2 || echo "весов нет"
ls -lh "$ROOT" | grep -E "\.pth|\.pt|\.onnx" || true
echo "--- диски ---"
df -h "$ROOT" | tail -1
echo "--- GPU (конечное состояние) ---"
nvidia-smi --query-gpu=index,name,memory.used,memory.total,compute_cap --format=csv 2>/dev/null || true
echo "--- неудачи этапов: ${#FAILURES[@]} ---"
for f in "${FAILURES[@]:-}"; do echo "  FAIL: $f"; done
echo "=================================================================="
echo "Конец. Лог лежит в $ROOT/neuro_setup.log"