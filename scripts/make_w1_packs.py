#!/usr/bin/env python3
"""Сборка W1-паков по людям → w1_pack/W1_<имя>.zip.

Вход: w1_frames/<ролик>/  (кадры, см. make_w1_frames.py)
      w1_preds/<ролик>/   (опционально: YOLO-предразметка <кадр>.txt — кладётся рядом с кадрами)
Выход: w1_pack/W1_<имя>.zip + README_W1.txt + СООБЩЕНИЕ.txt внутри.

Распределение см. W1_PROTOCOL.md; Х-43…Х-46 (нигде не были назначены) отдал
клорексу и Жусу — самым лёгким по загрузке. README для Жуса отличается:
он сам принимает паки у тимейтов, «отправить Жусу» в его пике нет.
Запуск: python3 scripts/make_w1_packs.py [имя]  (имя опционально: clorex/bogdag/kira/zhus)
"""
import glob
import os
import sys
import zipfile

ROOT = "/home/zhus/Desktop/datathon"
FRAMES = os.path.join(ROOT, "w1_frames")
PREDS = os.path.join(ROOT, "w1_preds")
PACK = os.path.join(ROOT, "w1_pack")

# латиница/кириллица в именах смешаны → перечисляем номерами, имя собираем по метке ролика
ASSIGN = {
    "clorex": [1, 2, 3, 4, 5, 8, 10, 43, 44],
    "bogdag": list(range(11, 23)),
    "kira": list(range(23, 35)),
    "zhus": [35, 37, 38, 39, 40, 45, 46],
}
HOLDOUT = {3, 11, 16, 26, 34, 40}
DNAMES = {"clorex": "клорекс", "bogdag": "Богдаг", "kira": "キラ", "zhus": "Жус"}

CLASSES = ["banknotes", "money_bag", "document", "safe", "stamp", "outerwear", "terminal"]

# фразы приёма: для всех — «сдать Жусу», для Жуса — свой пайплайн
HANDOFF = {
    "zhus": {
        "fallback": "Не заводится за 30 минут — сам переходишь на запасной путь (веб-редактор).",
        "export": "Складывай txt в w1_out/<ролик>/ у себя — общий датасет собираешь ты.",
        "question": "Сомнение в классе — не выдумывать: помечай вопросом, разрулишь при сборке.",
    },
    "default": {
        "fallback": "Не заводится за 30 минут — напиши Жусу, отдаст веб-редактор.",
        "export": "Архив папки роликов — Жусу в личку (личный чат / локалка / флешка).",
        "question": "Сомнение в классе — не выдумывать: помечай вопросом в общий чат, Жус разрулит.",
    },
}

README_TMPL = """W1 — РАЗМЕТКА КАДРОВ ПОД ДЕТЕКТОР (Forte Vision)

Тебе: {dname} — {n} роликов.
Дедлайн: к утру 18.10. Ролики HOLDOUT — в последний порядок, они для валидации.

== РОЛИКИ ==
{videos}

== ЧТО РАЗМЕЧАТЬ (классы и погранички) ==
{classes}

НЕ размечаем (COCO уже умеет): человек, кружка/бутылка, телефон, сумка/рюкзак,
экран/монитор, клавиатура.

== ИНСТРУМЕНТ ==
X-AnyLabeling (десктоп под винду/mac/linux): github.com/CVHub520/X-AnyLabeling → Releases → последняя
сборка под твою ОС. {fallback}

1. Открыть папку с кадрами ОДНОГО ролика (File → Open dir) — кадры вида <ролик>_t<сек>.jpg.
2. Если рядом с кадрами есть файлы *_t*.txt — это автопредразметка. File → Import
   ("Load custom annotations / YOLO txt"); классы — файл classes.txt в корне пака.
   Предразметка черновая: ПРОВЕРЯЙ каждый бокс, лишние удаляй, пропущенные рисуй.
3. Класс назначать из classes.txt: banknotes, money_bag, document, safe, stamp, outerwear, terminal.
4. Экспорт: File → Export → YOLO txt (или "Save YOLO annotations") — один txt на кадр,
   имена кадров не менять. {export}

== ПРАВИЛА БОКСОВ ==
— Плотный бокс: чуть меньше видимого объекта, а не «область вокруг».
— Перекрытие объекта ≥50% — размечаем; сильно перекрыт — лучше размечать, чем нет.
— Мелькнул на 1–2 кадрах — размечаем на каждом кадре, где различим.
— {question}

== ДВЕ ЖЁСТКИЕ ШТУКИ ==
— НЕ публиковать кадры/разметку нигде (облака третьих сторон — тоже нет), не заливать в тест.
— НЕ размечать человека и одежду на нём (outerwear = только снятая одежда-объект).
"""

CL_LINES = """- banknotes — банкноты/стопка/пачка (в т.ч. в руках, в сейфе, на столе); две разрозненные пачки = два бокса;
  картинки купюр на документе/экране НЕ размечать
- money_bag — инкассаторский мешок/плотный пакет с деньгами/конверт с пачками; личная сумка клиента НЕ это;
  содержимое не видно, но мешок крупный у стойки → money_bag
- document — документ, удостоверяющий личность (паспорт/удостоверение/карта), который подают или проверяют;
  чеки/квитанции/другая бумага — НЕ document; документ на столе во время операции — размечать
- safe — сейф/кассовый ящик/укладина целиком по корпусу, открытая крышка в том же боксе
- stamp — именной штамп/печать на столе; ручка-штамп = да; простая ручка = нет
- outerwear — снятая куртка/шапка как объект на столе/стуле/в руках; надетая на человеке = НЕ размечать
- terminal — счётный аппарат пересчёта денег (часто вне кадра; если виден — размечать)
"""


def find_video_dir(num):
    """Возвращает имя папки (с латиницей/кириллицей как в датасете) по номеру."""
    for p in glob.glob(os.path.join(FRAMES, "*")):
        base = os.path.basename(p)
        tail = base.rsplit("-", 1)[-1]
        if tail.isdigit() and int(tail) == num:
            return base
    return None


def build(who, nums):
    dirs = []
    missing = []
    for n in nums:
        d = find_video_dir(n)
        if d:
            dirs.append((d, n))
        else:
            missing.append(n)
    if missing:
        raise SystemExit(f"нет кадров для {who}: {missing} — сначала make_w1_frames.py")

    os.makedirs(PACK, exist_ok=True)
    zip_path = os.path.join(PACK, f"W1_{who}.zip")
    lines = []
    for d, n in dirs:
        mark = "  ← HOLDOUT (в последнюю очередь)" if n in HOLDOUT else ""
        lines.append(f"  {d}{mark}")
    h = HANDOFF.get(who, HANDOFF["default"])
    readme = README_TMPL.format(
        dname=DNAMES[who], n=len(dirs), videos="\n".join(lines), classes=CL_LINES,
        fallback=h["fallback"], export=h["export"], question=h["question"],
    )
    msg_path = os.path.join(PACK, "СООБЩЕНИЕ.txt")
    msg = open(msg_path, encoding="utf-8").read() if os.path.exists(msg_path) else ""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr(f"_W1_{who}/classes.txt", "\n".join(CLASSES) + "\n")
        z.writestr(f"_W1_{who}/README_W1.txt", readme)
        if msg:
            z.writestr(f"_W1_{who}/СООБЩЕНИЕ.txt", msg)
        for d, n in dirs:
            folder = os.path.join(FRAMES, d)
            for img in sorted(glob.glob(os.path.join(folder, "*.jpg"))):
                name = f"_W1_{who}/{d}/{os.path.basename(img)}"
                z.write(img, name)
                txt = os.path.join(PREDS, d, os.path.basename(img)[:-4] + ".txt")
                if os.path.exists(txt):
                    z.write(txt, name[:-4] + ".txt")
            # classes.txt рядом с кадрами — X-AnyLabeling её подхватывает с папкой
            z.writestr(f"_W1_{who}/{d}/classes.txt", "\n".join(CLASSES) + "\n")
    print(f"OK {zip_path}: {len(dirs)} роликов, {os.path.getsize(zip_path)/1e6:.0f} МБ")


def main():
    only = set(sys.argv[1:]) or set(ASSIGN)
    for who, nums in ASSIGN.items():
        if who in only:
            build(who, nums)


if __name__ == "__main__":
    main()