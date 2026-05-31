#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Форматирование md-файлов Конституции под ширину строки 80 символов.

Источник истины — сами md-файлы. Этот скрипт НЕ хранит нормативный
текст и НЕ изменяет его содержание: он только переносит строки
(hard wrap) под лимит ширины, убирает хвостовые пробелы, нормализует
пустые строки между блоками и завершающий перевод строки. Слова,
знаки препинания, нумерация, буква «ё» и кавычки не затрагиваются.

Ширина считается в СИМВОЛАХ (кодовых точках Unicode), а не в байтах.
Кириллица в UTF-8 занимает два байта на символ, поэтому проверка вида
`awk 'length>80'` ложно завышает длину; здесь используется len(str).

Структура блока распознаётся по первой строке:
- нумерованный пункт:   «N. текст»          (отступ 0)
- буквенный подпункт:   «а) текст»          (отступ 0 или 3)
- обычный абзац:        текст без маркера    (отступ 0)
- сегмент с отступом:   ведущие пробелы без маркера (списки, присяга)

Блоки разделяются пустой строкой. Внутри блока все строки склеиваются
в один логический абзац и заново переносятся по ширине. Отсюда правило:
ПУСТАЯ СТРОКА — граница абзаца; перенос строки без пустой строки —
обычное продолжение того же абзаца (будет переформатирован).

Использование:
    python3 _scripts/format_md.py                # форматировать весь корпус
    python3 _scripts/format_md.py путь [путь...]  # только указанные файлы/каталоги
    python3 _scripts/format_md.py --check         # только проверка (CI), без записи
    python3 _scripts/format_md.py --width 72 ...   # иная ширина (по умолчанию 80)
"""

import argparse
import os
import re
import sys
import textwrap

# Корень проекта — родитель каталога _scripts, чтобы скрипт не зависел
# от абсолютного пути запуска.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_WIDTH = 80

# Маркеры начала блока: «N.» (нумерованный пункт) или «а)» (подпункт).
# За маркером обязателен пробел; текст после маркера попадает в group(2).
_NUM_RE = re.compile(r"^(\d+\.)\s+(.*)$")
# Буквенный подпункт: «а)» либо «а.1)» (формат составных подпунктов,
# введённый в практику поправками 2014 года для прокурорских норм).
_LET_RE = re.compile(r"^([а-яё](?:\.\d+)?\))\s+(.*)$")


def _wrap(text, indent, prefix, width):
    """Перенести логический абзац под ширину с заданным отступом.

    Продолжения выравниваются по началу текста (отступ + длина префикса).
    Длинные слова и дефисы не разрываются, чтобы не дробить термины и
    составные слова («санитарно-эпидемиологическому»).
    """
    pad = " " * indent
    return textwrap.fill(
        text,
        width=width,
        initial_indent=pad + prefix,
        subsequent_indent=pad + " " * len(prefix),
        break_long_words=False,
        break_on_hyphens=False,
    )


def split_blocks(text):
    """Разбить текст на блоки по пустым (в т. ч. пробельным) строкам."""
    blocks = []
    current = []
    for line in text.splitlines():
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def parse_block(lines):
    """Определить (отступ, префикс, логический текст) блока.

    Отступ — число ведущих пробелов первой строки. Префикс — маркер
    пункта/подпункта с одним завершающим пробелом либо пустая строка.
    Логический текст — все строки блока без ведущих/хвостовых пробелов,
    склеенные одиночными пробелами.
    """
    first = lines[0]
    stripped = first.lstrip(" ")
    indent = len(first) - len(stripped)

    match = _NUM_RE.match(stripped) or _LET_RE.match(stripped)
    if match:
        prefix = match.group(1) + " "
        head = match.group(2)
    else:
        prefix = ""
        head = stripped

    parts = [head] + [line.strip() for line in lines[1:]]
    text = " ".join(part for part in parts if part)
    text = re.sub(r"\s+", " ", text).strip()
    return indent, prefix, text


def format_text(src, width=DEFAULT_WIDTH):
    """Вернуть переформатированный текст файла под заданную ширину."""
    rendered = []
    for lines in split_blocks(src):
        # Заголовки markdown (на случай служебных файлов) — дословно,
        # без склейки и переноса. В нормативном корпусе их нет.
        if lines[0].lstrip().startswith("#"):
            rendered.append("\n".join(line.rstrip() for line in lines))
            continue
        indent, prefix, text = parse_block(lines)
        rendered.append(_wrap(text, indent, prefix, width))
    if not rendered:
        return ""
    return "\n\n".join(rendered) + "\n"


def iter_default_targets():
    """Файлы нормативного корпуса по умолчанию: статьи всех глав,
    Раздел 2 и преамбула.

    Мета-документы в корне (CLAUDE.md, PRD.md) и служебные каталоги
    (_scripts, _notes, _redteam и пр.) НЕ форматируются: первые — это
    инструкции и план, не нормативный текст; вторые лежат вне «Раздел*».
    """
    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        rel = os.path.relpath(dirpath, PROJECT_ROOT)
        if rel == ".":
            # В корне не трогаем мета-документы; спускаемся только в
            # каталоги нормативного корпуса «Раздел*».
            dirnames[:] = [d for d in dirnames if d.startswith("Раздел")]
            continue
        for name in filenames:
            if name.endswith(".md"):
                yield os.path.join(dirpath, name)
    preamble = os.path.join(PROJECT_ROOT, "Преамбула.md")
    if os.path.exists(preamble):
        yield preamble


def collect_targets(paths):
    """Развернуть переданные пути (файлы и каталоги) в список md-файлов."""
    targets = []
    for path in paths:
        if os.path.isdir(path):
            for dirpath, _dirnames, filenames in os.walk(path):
                for name in sorted(filenames):
                    if name.endswith(".md"):
                        targets.append(os.path.join(dirpath, name))
        elif path.endswith(".md"):
            targets.append(path)
        else:
            print(f"  пропуск (не .md): {path}", file=sys.stderr)
    return targets


def max_width(text):
    lines = text.splitlines()
    return max((len(line) for line in lines), default=0)


def process(paths, width, check):
    """Отформатировать или проверить файлы. Вернуть код выхода."""
    if paths:
        targets = collect_targets(paths)
    else:
        targets = sorted(iter_default_targets())

    changed = []
    overflow = []
    for path in targets:
        with open(path, encoding="utf-8") as handle:
            original = handle.read()
        formatted = format_text(original, width)
        rel = os.path.relpath(path, PROJECT_ROOT)
        will_change = formatted != original
        over = max_width(formatted)
        if over > width:
            overflow.append((rel, over))
        if check:
            status = "ИЗМЕНИТСЯ" if will_change else "ок"
            mark = f"  >{width}: {over}" if over > width else ""
            print(f"  [{status}] {rel}{mark}")
            if will_change:
                changed.append(rel)
        else:
            if will_change:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(formatted)
                changed.append(rel)
                print(f"  отформатирован: {rel}")

    print()
    print(f"Файлов обработано: {len(targets)}")
    if check:
        print(f"Требуют форматирования: {len(changed)}")
        print(f"Превышают {width} символов: {len(overflow)}")
        return 1 if (changed or overflow) else 0
    print(f"Изменено: {len(changed)}")
    if overflow:
        print(f"ВНИМАНИЕ, превышают {width} символов даже после переноса:")
        for rel, over in overflow:
            print(f"  {rel}: {over}")
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Перенос строк md-файлов Конституции под лимит ширины.",
    )
    parser.add_argument(
        "paths", nargs="*",
        help="файлы или каталоги (.md); по умолчанию — весь корпус",
    )
    parser.add_argument(
        "--width", type=int, default=DEFAULT_WIDTH,
        help=f"максимальная ширина строки (по умолчанию {DEFAULT_WIDTH})",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="только проверка без записи; код выхода 1 при нарушениях",
    )
    args = parser.parse_args(argv)
    return process(args.paths, args.width, args.check)


if __name__ == "__main__":
    sys.exit(main())
