"""Tillar: kirillga o'girish, tarjima va har bir matnning ruscha tarjimasi borligi."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from bot.i18n import _, all_variants, set_language
from bot.i18n.ru import RU
from bot.i18n.translit import to_cyrillic

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("latin", "cyrillic"),
    [
        ("Qarz to'lovi", "Қарз тўлови"),
        ("Yo'q", "Йўқ"),
        ("so'm", "сўм"),
        ("Ma'lumotlar", "Маълумотлар"),
        ("Sozlamalar", "Созламалар"),
        ("Yangi qarz yaratish", "Янги қарз яратиш"),
        ("Bekor qilish", "Бекор қилиш"),
        ("O'chirish", "Ўчириш"),
        ("G'alla", "Ғалла"),
        ("Eski shina", "Эски шина"),
        ("Tovar turini tanlang", "Товар турини танланг"),
        ("Yoki", "Ёки"),
        ("Ortga", "Ортга"),
        ("Jami: {total}", "Жами: {total}"),
        ("<b>Sana:</b> bugun", "<b>Сана:</b> бугун"),
        ("'Bugun' tugmasini bosing", "'Бугун' тугмасини босинг"),
        ("Excel hisobot", "Excel ҳисобот"),
        ("/start — menyu", "/start — меню"),
    ],
)
def test_to_cyrillic(latin: str, cyrillic: str) -> None:
    assert to_cyrillic(latin) == cyrillic


def test_translate_uses_current_language() -> None:
    RU.setdefault("Sinov {name}", "Тест {name}")
    try:
        set_language("ru")
        assert _("Sinov {name}", name="Anvar") == "Тест Anvar"
        set_language("uz_cyrl")
        assert _("Sinov {name}", name="Anvar") == "Синов Anvar"  # qiymat o'girilmaydi
        set_language("xx")  # noma'lum til — lotin
        assert _("Sinov {name}", name="Anvar") == "Sinov Anvar"
        assert all_variants("Sinov {name}") == {"Sinov {name}", "Синов {name}", "Тест {name}"}
    finally:
        set_language("uz")
        RU.pop("Sinov {name}", None)


def _translatable_literals() -> dict[str, str]:
    """bot/ ichidagi barcha `_("...")`/`N_("...")` matnlari: {matn: fayl:qator}."""
    found: dict[str, str] = {}
    for path in (ROOT / "bot").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("_", "N_")
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.setdefault(node.args[0].value, f"{path.relative_to(ROOT)}:{node.lineno}")
    return found


def test_every_bot_text_has_russian_translation() -> None:
    missing = {text: where for text, where in _translatable_literals().items() if text not in RU}
    assert not missing, "Ruscha tarjimasi yo'q matnlar:\n" + "\n".join(
        f"{where}: {text!r}" for text, where in sorted(missing.items(), key=lambda x: x[1])
    )


def test_russian_placeholders_match() -> None:
    import string

    def fields(s: str) -> set[str]:
        return {f for _, f, _, _ in string.Formatter().parse(s) if f}

    wrong = [k for k, v in RU.items() if fields(k) != fields(v)]
    assert not wrong, f"Placeholder'lar mos emas: {wrong}"


def test_no_unused_russian_entries() -> None:
    unused = set(RU) - set(_translatable_literals())
    assert not unused, f"Ishlatilmaydigan tarjimalar: {sorted(unused)}"
