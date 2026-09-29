"""Ovozli xabar transkriptidan qarz qoralamasini ajratib olish.

Qoidaga asoslangan (LLM'siz) parser. Kutilgan gap shakli:

    "<Ism>ga <miqdor> ta <tovar> <narx> <valyuta>"
    "Anvar Aliyevga ikkita shina besh yuz ming so'mdan"
    "Alisherga akkumulyator 120 dollar"

- Mijoz — jo'nalish kelishigidagi (-ga/-ka/-qa) so'z (+ undan oldingi bitta so'z);
- miqdor — "ta"/"dona" dan oldingi son (bo'lmasa 1);
- narx — bitta tovar narxi, valyutadan oldingi son (bo'lmasa oxirgi son);
- valyuta — "so'm"/"dollar" so'zlari (bo'lmasa None — servis hal qiladi).

Son so'zlar ("besh yuz ming", "bir yarim million") raqamga aylantiriladi.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bot.domain.entities.currency import Currency

_UNITS = {
    "nol": 0, "bir": 1, "ikki": 2, "uch": 3, "to'rt": 4, "tort": 4, "besh": 5,
    "olti": 6, "yetti": 7, "sakkiz": 8, "to'qqiz": 9, "toqqiz": 9,
}
_TENS = {
    "o'n": 10, "on": 10, "yigirma": 20, "o'ttiz": 30, "ottiz": 30, "qirq": 40,
    "ellik": 50, "oltmish": 60, "yetmish": 70, "sakson": 80, "to'qson": 90,
    "toqson": 90,
}
_SCALES = {"ming": 1_000, "million": 1_000_000, "mln": 1_000_000, "milliard": 1_000_000_000}
_NUMBER_WORDS = {*_UNITS, *_TENS, *_SCALES, "yuz", "yarim", "bitta"}

_USD_WORDS = {"dollar", "dollor", "usd"}
_UZS_WORDS = {"so'm", "som", "sum", "uzs"}

_STOP_WORDS = {
    "dona", "qarz", "qarzga", "nasiya", "nasiyaga", "berildi", "berdim", "berdik",
    "oldi", "olib", "ketdi", "narxi", "narx", "har", "biri", "bittasi", "jami",
    "uchun", "yoz", "yozing", "yozib", "qo'y", "qo'sh", "qo'shing", "yangi", "va",
}
_DATIVE_SUFFIXES = ("ga", "ka", "qa")
_APOSTROPHES = str.maketrans({"ʻ": "'", "’": "'", "‘": "'", "`": "'", "ʼ": "'"})


class VoiceParseError(ValueError):
    """Transkriptdan majburiy maydonlar ajratib olinmadi."""


@dataclass(frozen=True, slots=True)
class VoiceDebtDraft:
    client_name: str
    product_name: str
    quantity: int
    price_per_unit: int
    currency: Currency | None


# Token: ("num", float) | ("ta", None) | ("word", str)
_Token = tuple[str, Any]


def parse_voice_debt(text: str) -> VoiceDebtDraft:
    """Transkriptni qarz qoralamasiga aylantiradi.

    Raises:
        VoiceParseError: ism, tovar yoki narx topilmasa.
    """
    tokens = _merge_numbers(_tokenize(text))

    currency = None
    for kind, value in tokens:
        if kind == "word" and value in _USD_WORDS:
            currency = Currency.USD
            break
        if kind == "word" and value in _UZS_WORDS:
            currency = Currency.UZS
            break

    quantity_idx = None
    for i, (kind, _) in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        if kind == "num" and (nxt[0] == "ta" or nxt == ("word", "dona")):
            quantity_idx = i
            break
    quantity = int(tokens[quantity_idx][1]) if quantity_idx is not None else 1

    price_candidates = [
        i for i, (kind, _) in enumerate(tokens) if kind == "num" and i != quantity_idx
    ]
    price_idx = next(
        (
            i for i in price_candidates
            if i + 1 < len(tokens) and tokens[i + 1][1] in _USD_WORDS | _UZS_WORDS
        ),
        price_candidates[-1] if price_candidates else None,
    )
    price = int(tokens[price_idx][1]) if price_idx is not None else 0

    words = [(i, str(v)) for i, (k, v) in enumerate(tokens) if k == "word"]
    name_parts: list[str] = []
    name_end = -1
    for pos, (i, word) in enumerate(words):
        if len(word) > 3 and word.endswith(_DATIVE_SUFFIXES) and word not in _STOP_WORDS:
            name_parts = [word[:-2]]
            prev = words[pos - 1] if pos > 0 else None
            if prev and prev[0] == i - 1 and prev[1] not in _STOP_WORDS:
                name_parts.insert(0, prev[1])
            name_end = i
            break

    product_words = [
        word for i, word in words
        if i > name_end
        and word not in _STOP_WORDS
        and word not in _USD_WORDS | _UZS_WORDS
    ]

    missing = []
    if not name_parts:
        missing.append("mijoz ismi (masalan: «Anvarga»)")
    if not product_words:
        missing.append("tovar nomi")
    if price <= 0:
        missing.append("narx")
    if missing:
        raise VoiceParseError("Aniqlanmadi: " + ", ".join(missing))

    return VoiceDebtDraft(
        client_name=" ".join(w.capitalize() for w in name_parts),
        product_name=" ".join(product_words).capitalize(),
        quantity=max(quantity, 1),
        price_per_unit=price,
        currency=currency,
    )


def _tokenize(text: str) -> list[_Token]:
    normalized = text.lower().translate(_APOSTROPHES).replace("$", " dollar ")
    # "1 500 000" / "1.500.000" -> "1500000"; "1,5" o'nlik kasr bo'lib qoladi
    prev = None
    while prev != normalized:
        prev = normalized
        normalized = re.sub(r"(?<=\d)[ .,](?=\d{3}\b)", "", normalized)

    tokens: list[_Token] = []
    for raw in re.findall(r"\d+(?:[.,]\d+)?|[a-z']+", normalized):
        if raw[0].isdigit():
            tokens.append(("num", float(raw.replace(",", "."))))
            continue
        word = raw.strip("'")
        if not word:
            continue
        tokens.extend(_split_word(word))
    return tokens


def _split_word(word: str) -> list[_Token]:
    """"ikkitadan" -> [ikki, ta]; "so'mdan" -> [so'm]; "shina" -> [shina]."""
    if word in ("bitta", "bittadan"):
        return [("word", "bir"), ("ta", None)]
    if word == "ta":
        return [("ta", None)]
    # ASR qo'shimchalarni buzishi mumkin: "so'mda", "so'ma", "dollarga"
    for stem in ("so'm", "dollar", "dollor"):
        if word.startswith(stem):
            return [("word", stem)]
    for suffix, marker in (("tadan", True), ("ta", True), ("dan", False), ("lik", False)):
        stem = word[: -len(suffix)]
        if word.endswith(suffix) and (
            stem in _NUMBER_WORDS or (not marker and stem in _USD_WORDS | _UZS_WORDS)
        ):
            return [("word", stem), ("ta", None)] if marker else [("word", stem)]
    return [("word", word)]


def _merge_numbers(tokens: list[_Token]) -> list[_Token]:
    """Ketma-ket son so'zlari va raqamlarni bitta ("num", qiymat) ga yig'adi."""
    result: list[_Token] = []
    total = current = 0.0
    last: str | None = None  # oxirgi qo'shilgan son bo'lagi turi

    def flush() -> None:
        nonlocal total, current, last
        if last is not None:
            result.append(("num", total + current))
        total = current = 0.0
        last = None

    for kind, value in tokens:
        part: str | None = None
        if kind == "num":
            part = "digit"
        elif kind == "word" and value in _UNITS:
            part = "unit"
        elif kind == "word" and value in _TENS:
            part = "tens"
        elif kind == "word" and (value in ("yuz", "yarim") or value in _SCALES):
            part = str(value)

        if part is None:
            flush()
            result.append((kind, value))
            continue

        # "ikki uch", "2 500 ming", "besh o'n" — alohida sonlar
        if (part in ("unit", "digit") and last in ("unit", "digit")) or (
            part == "tens" and last in ("unit", "tens", "digit")
        ):
            flush()

        if part == "digit":
            current += float(value)
        elif part == "unit":
            current += _UNITS[str(value)]
        elif part == "tens":
            current += _TENS[str(value)]
        elif part == "yuz":
            current = (current or 1) * 100
        elif part == "yarim":
            current += 0.5
        else:
            total += (current or 1) * _SCALES[part]
            current = 0.0
        last = part

    flush()
    return result
