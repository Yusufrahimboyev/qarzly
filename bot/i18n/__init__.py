"""Bot interfeysi tillari: o'zbek (lotin), o'zbek (kirill), rus.

Matnlar kodda lotin o'zbekchada `_("...")` bilan yoziladi:
- kirill varianti `to_cyrillic` bilan avtomatik hosil qilinadi;
- ruscha tarjima `ru.RU` lug'atidan olinadi (kalit — lotin matnning o'zi).

Joriy til har bir Telegram update uchun middleware'da `set_language` bilan
o'rnatiladi (ContextVar) — handler, klaviatura va formatter'lar tilni
parametr sifatida olib yurmaydi.
"""
from __future__ import annotations

from contextvars import ContextVar

from bot.i18n.ru import RU
from bot.i18n.translit import to_cyrillic

LANGUAGES: dict[str, str] = {
    "uz": "🇺🇿 O'zbekcha (lotin)",
    "uz_cyrl": "🇺🇿 Ўзбекча (кирилл)",
    "ru": "🇷🇺 Русский",
}
DEFAULT_LANGUAGE = "uz"

_current: ContextVar[str] = ContextVar("language", default=DEFAULT_LANGUAGE)


def set_language(language: str | None) -> None:
    _current.set(language if language in LANGUAGES else DEFAULT_LANGUAGE)


def get_language() -> str:
    return _current.get()


def translate(text: str, language: str) -> str:
    if language == "ru":
        return RU.get(text, text)
    if language == "uz_cyrl":
        return to_cyrillic(text)
    return text


def _(text: str, /, **kwargs: object) -> str:
    """Matnni joriy tilga o'giradi; `kwargs` — `{nom}` o'rniga qo'yiladigan qiymatlar.

    Qiymatlar tarjimadan keyin qo'yiladi — mijoz ismi, tovar nomi kabi
    ma'lumotlar o'girilmaydi.
    """
    result = translate(text, _current.get())
    return result.format(**kwargs) if kwargs else result


def N_(text: str) -> str:
    """Matnni tarjima qilinadigan deb belgilaydi, lekin hozir o'girmaydi.

    Modul darajasidagi doimiylar uchun (masalan, tugma matnlari): ular
    ishlatilgan joyda `_(DOIMIY)` bilan o'giriladi.
    """
    return text


def all_variants(text: str) -> set[str]:
    """Matnning barcha tillardagi ko'rinishi (reply-tugma bosilishini tanish uchun)."""
    return {translate(text, language) for language in LANGUAGES}
