"""Mini App tillari: har bir matnning ruscha tarjimasi va JS/Python kirillcha mosligi."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from bot.i18n.translit import to_cyrillic

WEB = Path(__file__).resolve().parents[1] / "web"
APP_JS = WEB / "static" / "js" / "app.js"
I18N_JS = WEB / "static" / "js" / "i18n.js"
RU_JS = WEB / "static" / "js" / "i18n-ru.js"
INDEX_HTML = WEB / "templates" / "index.html"

_T_CALL = re.compile(r"""\b(?:t|N_)\(\s*(['"])((?:\\.|(?!\1).)*)\1""")
_TRANSLATABLE_ATTRS = ("placeholder", "aria-label", "title")


def _unescape_js(text: str) -> str:
    return re.sub(r"\\(.)", r"\1", text)


def js_texts() -> set[str]:
    return {_unescape_js(m.group(2)) for m in _T_CALL.finditer(APP_JS.read_text(encoding="utf-8"))}


class _HtmlTexts(HTMLParser):
    """`translateDom` o'giradigan matnlar: text node va atributlar."""

    _VOID = {"input", "br", "img", "meta", "link", "use", "path", "circle", "rect", "symbol"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.texts: set[str] = set()
        self._stack: list[tuple[str, bool]] = []  # (teg, o'girilmaydimi)

    @property
    def _skip(self) -> bool:
        return any(skip for _, skip in self._stack)

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        skip = tag in ("script", "style") or "data-no-i18n" in attrs_d
        if not (self._skip or skip):
            for name in _TRANSLATABLE_ATTRS:
                value = attrs_d.get(name)
                if value and re.search("[a-zA-Z]", value):
                    self.texts.add(value)
        if tag not in self._VOID:
            self._stack.append((tag, skip))

    def handle_endtag(self, tag):
        while self._stack:
            if self._stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        text = data.strip()
        if text and not self._skip and re.search("[a-zA-Z]", text):
            self.texts.add(text)


def html_texts() -> set[str]:
    parser = _HtmlTexts()
    parser.feed(INDEX_HTML.read_text(encoding="utf-8"))
    return parser.texts


def ru_dict() -> dict[str, str]:
    raw = RU_JS.read_text(encoding="utf-8")
    start = raw.index("window.I18N_RU =") + len("window.I18N_RU =")
    body = raw[start: raw.rindex("}") + 1]
    return json.loads(body)


# Lotin yozuvida qoladigan matnlar (brend, valyuta, misol qiymatlar)
_NOT_TRANSLATED = {"Qarz Daftar", "Mini App"}


def test_every_webapp_text_has_russian_translation() -> None:
    ru = ru_dict()
    needed = (js_texts() | html_texts()) - _NOT_TRANSLATED
    missing = sorted(t for t in needed if t not in ru)
    assert not missing, "Ruscha tarjimasi yo'q Mini App matnlari:\n" + "\n".join(map(repr, missing))


def test_no_unused_webapp_russian_entries() -> None:
    unused = set(ru_dict()) - js_texts() - html_texts()
    assert not unused, f"Ishlatilmaydigan tarjimalar: {sorted(unused)}"


def test_webapp_placeholders_match() -> None:
    def fields(s: str) -> set[str]:
        return set(re.findall(r"\{(\w+)\}", s))

    wrong = [k for k, v in ru_dict().items() if fields(k) != fields(v)]
    assert not wrong, f"Placeholder'lar mos emas: {wrong}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node o'rnatilmagan")
def test_js_and_python_cyrillic_match() -> None:
    texts = sorted(js_texts() | html_texts() | {"Yo'q", "yo'q", "G'alla", "Eski", "'Bugun'"})
    script = (
        I18N_JS.read_text(encoding="utf-8")
        + "\nconst input = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        + "\nprocess.stdout.write(JSON.stringify(input.map(toCyrillic)));"
    )
    # i18n.js brauzer uchun: localStorage/document Node'da yo'q — stub qilinadi
    prelude = "const localStorage = { getItem() { return null; } };\n"
    result = subprocess.run(
        ["node", "-e", prelude + script],
        input=json.dumps(texts),
        capture_output=True,
        text=True,
        check=True,
    )
    js = json.loads(result.stdout)
    diffs = [(t, j, to_cyrillic(t)) for t, j in zip(texts, js, strict=True) if j != to_cyrillic(t)]
    assert not diffs, f"JS va Python kirillchasi farq qiladi: {diffs[:10]}"
