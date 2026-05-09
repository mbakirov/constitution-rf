#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize formatting of amendment law texts in Поправки/.

For each .md file in the directory:
- Convert straight `"..."` to «...» (outer) / „...“ (inner) using a
  depth-aware pass over the whole file (quotes can span paragraphs).
- Convert ` - ` (space-hyphen-space) and ` – ` (en-dash) to ` — ` (em-dash).
- Apply ё-normalization to common word patterns.
- Re-wrap each paragraph to 80 characters, preserving blank-line
  paragraph boundaries.

The script is idempotent: re-running it does not regress already-normalized
text.
"""

import os
import re
import textwrap

BASE = "/Users/mbakirov/Projects/constitution/Поправки"

# Russian inner closing quote: U+201C (LEFT DOUBLE QUOTATION MARK,
# used as closing in Russian/German typography pair „...“).
INNER_OPEN = "„"   # „
INNER_CLOSE = "“"  # "

# Word-boundary ё-normalizations. Cover only stable cases —
# don't touch ambiguous forms.
YO_PATTERNS = [
    # Pronouns
    (r"\bее\b", "её"), (r"\bЕе\b", "Её"),
    # Verbs (3rd person singular)
    (r"\bведет\b", "ведёт"), (r"\bВедет\b", "Ведёт"),
    (r"\bиздает\b", "издаёт"), (r"\bИздает\b", "Издаёт"),
    (r"\bнесет\b", "несёт"), (r"\bНесет\b", "Несёт"),
    (r"\bвлечет\b", "влечёт"), (r"\bВлечет\b", "Влечёт"),
    (r"\bберет\b", "берёт"), (r"\bБерет\b", "Берёт"),
    (r"\bдает\b", "даёт"), (r"\bДает\b", "Даёт"),
    # Past passive participles
    (r"\bлишен\b", "лишён"), (r"\bЛишен\b", "Лишён"),
    (r"\bотрешен\b", "отрешён"), (r"\bОтрешен\b", "Отрешён"),
    (r"\bпривлечен\b", "привлечён"), (r"\bПривлечен\b", "Привлечён"),
    (r"\bпринужден\b", "принуждён"), (r"\bПринужден\b", "Принуждён"),
    (r"\bотклонен\b", "отклонён"), (r"\bОтклонен\b", "Отклонён"),
    (r"\bподтверждена?ого\b", "подтверждённого"),
    (r"\bпримененного\b", "применённого"),
    (r"\bотнесенным\b", "отнесённым"),
    (r"\bотнесенных\b", "отнесённых"),
    # Nouns
    (r"\bучет\b", "учёт"), (r"\bУчет\b", "Учёт"),
    (r"\bучетом\b", "учётом"), (r"\bУчетом\b", "Учётом"),
    (r"\bсчет\b", "счёт"),
    (r"\bотчет\b", "отчёт"), (r"\bОтчет\b", "Отчёт"),
    (r"\bотчетов\b", "отчётов"),
    (r"\bотчеты\b", "отчёты"),
    (r"\bпутем\b", "путём"), (r"\bПутем\b", "Путём"),
    (r"\bСчетная\b", "Счётная"),
    (r"\bСчетной\b", "Счётной"),
    (r"\bСчетную\b", "Счётную"),
    # Numerals (genitive forms)
    (r"\bтрех\b", "трёх"), (r"\bТрех\b", "Трёх"),
    (r"\bчетырех\b", "четырёх"),
    (r"\bчетвертой\b", "четвёртой"),
    (r"\bтрехкратного\b", "трёхкратного"),
    (r"\bтрехмесячный\b", "трёхмесячный"),
    (r"\bтрехмесячный\b", "трёхмесячный"),
    # Adjectives
    (r"\bвооруженных\b", "вооружённых"),
    (r"\bВооруженных\b", "Вооружённых"),
    (r"\bвооруженные\b", "вооружённые"),
    (r"\bпочетные\b", "почётные"),
    (r"\bпочетных\b", "почётных"),
    (r"\bпочетных\b", "почётных"),
    # Specific grammatical forms
    (r"\bкраев\b", "краёв"),
    (r"\bземлей\b", "землёй"), (r"\bЗемлей\b", "Землёй"),
    (r"\bстатьей\b", "статьёй"), (r"\bСтатьей\b", "Статьёй"),
    (r"\bпризнается\b", "признаётся"),
    (r"\bПризнается\b", "Признаётся"),
    (r"\bберетесь?\b", "берёшь"),  # rare, kept for safety
]

# Set of preceding chars that mark `"` as opening quote.
QUOTE_OPENS_AFTER = set(" \t\n\r([{«„")


def normalize_quotes(text):
    """Convert straight `"` to «...» / „...“ with depth tracking."""
    out = []
    depth = 0
    for i, c in enumerate(text):
        if c != '"':
            out.append(c)
            continue
        prev = text[i - 1] if i > 0 else "\n"
        is_opening = prev in QUOTE_OPENS_AFTER
        if is_opening:
            out.append("«" if depth == 0 else INNER_OPEN)
            depth += 1
        else:
            out.append("»" if depth <= 1 else INNER_CLOSE)
            depth = max(0, depth - 1)
    return "".join(out)


def normalize_dashes(text):
    return text.replace(" - ", " — ").replace(" – ", " — ")


def normalize_yo(text):
    for pattern, replacement in YO_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def wrap_paragraphs(text, width=80):
    """Re-wrap each blank-line-separated paragraph to width."""
    paragraphs = re.split(r"\n\s*\n", text)
    wrapped = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Collapse internal whitespace inside paragraph
        flat = re.sub(r"\s+", " ", p)
        wrapped.append(textwrap.fill(
            flat, width=width,
            break_long_words=False,
            break_on_hyphens=False,
        ))
    return "\n\n".join(wrapped) + "\n"


def normalize_file(path, width=80):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Whole-file passes (quote depth must span paragraphs).
    content = normalize_quotes(content)
    content = normalize_dashes(content)
    content = normalize_yo(content)
    # Per-paragraph wrap.
    content = wrap_paragraphs(content, width=width)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    max_len = max((len(line) for line in content.splitlines()), default=0)
    return max_len


def main():
    files = sorted(f for f in os.listdir(BASE) if f.endswith(".md"))
    for fname in files:
        path = os.path.join(BASE, fname)
        max_len = normalize_file(path)
        status = "OK" if max_len <= 80 else f"OVERFLOW ({max_len})"
        print(f"{fname}: {status}")


if __name__ == "__main__":
    main()
