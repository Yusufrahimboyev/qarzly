"""O'zbek lotin yozuvidan kirill yozuviga o'girish.

Bot va Mini App matnlari lotinda yoziladi, kirill varianti shu yerda
avtomatik hosil qilinadi. HTML teglar, `{placeholder}`lar, HTML entity'lar
va lotinda qolishi kerak bo'lgan so'zlar (Excel, Mini App ...) o'zgarmaydi.
"""
from __future__ import annotations

import re

# Lotinda qoladigan so'zlar/belgilar
_KEEP = (
    "Mini App", "Web UI", "Excel", "Exchange", "exchange", "Telegram ID",
    "DD.MM.YYYY", "UZS", "USD", "EFB", "Ah", "OK", "ID", "A → Z", "Z → A",
)

# O'zgarmaydigan bo'laklar: HTML teg, entity, {placeholder}, /buyruq, saqlanadigan so'zlar
_PROTECTED = re.compile(
    r"(<[^>]*>|&[a-zA-Z#0-9]+;|\{[^}]*\}|/[a-z_]+|"
    + "|".join(rf"\b{re.escape(w)}\b" for w in sorted(_KEEP, key=len, reverse=True))
    + ")"
)

_APOSTROPHES = "'’ʼ‘ʻ`"
_VOWELS = set("aeiouAEIOUаеиоуўэАЕИОУЎЭ")

_DIGRAPHS = {
    "sh": "ш", "ch": "ч", "yo": "ё", "yu": "ю", "ya": "я", "ye": "е",
}
_SINGLE = {
    "a": "а", "b": "б", "c": "ц", "d": "д", "f": "ф", "g": "г", "h": "ҳ",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "w": "в", "x": "х", "y": "й", "z": "з",
}


def _case(src: str, cyr: str) -> str:
    return cyr.upper() if src[:1].isupper() else cyr


def _translit_chunk(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        low = ch.lower()
        nxt = text[i + 1] if i + 1 < n else ""
        after = text[i + 2] if i + 2 < n else ""

        # o' → ў, g' → ғ (faqat keyin harf kelsa yoki so'z oxirida)
        if low in "og" and nxt and nxt in _APOSTROPHES and (after.isalpha() or not after
                                                            or not after.strip()):
            out.append(_case(ch, "ў" if low == "o" else "ғ"))
            i += 2
            continue
        pair = (ch + nxt).lower()
        # "yo'q" — bu "yo" emas, "y" + "o'"
        if pair in _DIGRAPHS and not (pair == "yo" and after and after in _APOSTROPHES):
            out.append(_case(ch, _DIGRAPHS[pair]))
            i += 2
            continue
        if low == "e":
            prev = text[i - 1] if i > 0 else ""
            initial = not prev.isalpha() or prev in _VOWELS
            out.append(_case(ch, "э" if initial else "е"))
        elif low in _SINGLE:
            out.append(_case(ch, _SINGLE[low]))
        elif ch in _APOSTROPHES:
            prev = text[i - 1] if i > 0 else ""
            # So'z ichidagi tutuq belgisi → ъ, qo'shtirnoq vazifasidagisi qoladi
            out.append("ъ" if prev.isalpha() and nxt.isalpha() else ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def to_cyrillic(text: str) -> str:
    """Lotin o'zbekcha matnni kirillga o'giradi (himoyalangan bo'laklardan tashqari)."""
    parts = _PROTECTED.split(text)
    # split natijasida toq indekslar — himoyalangan bo'laklar
    return "".join(p if i % 2 else _translit_chunk(p) for i, p in enumerate(parts))
