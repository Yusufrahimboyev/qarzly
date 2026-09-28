"""Ovozli xabar transkripti parserining testlari."""
from __future__ import annotations

import pytest

from bot.application.common.voice_parser import (
    VoiceDebtDraft,
    VoiceParseError,
    parse_voice_debt,
)
from bot.domain.entities.currency import Currency


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Anvar Aliyevga ikkita shina besh yuz ming so'mdan",
            VoiceDebtDraft("Anvar Aliyev", "Shina", 2, 500_000, Currency.UZS),
        ),
        (
            "alisherga akkumulyator 120 dollar",
            VoiceDebtDraft("Alisher", "Akkumulyator", 1, 120, Currency.USD),
        ),
        (
            "qarz Bekzodga 3 ta disk 1 500 000 so'm",
            VoiceDebtDraft("Bekzod", "Disk", 3, 1_500_000, Currency.UZS),
        ),
        (
            "Sardorga bitta kamera bir yarim million",
            VoiceDebtDraft("Sardor", "Kamera", 1, 1_500_000, None),
        ),
        (
            "Oybekka to'rtta yozgi shina yigirma besh dollardan",
            VoiceDebtDraft("Oybek", "Yozgi shina", 4, 25, Currency.USD),
        ),
        (
            "Jasurga moy 2 dona 85 ming soʻm",
            VoiceDebtDraft("Jasur", "Moy", 2, 85_000, Currency.UZS),
        ),
        (
            "Ulug'bekka shina 1 million 200 ming",
            VoiceDebtDraft("Ulug'bek", "Shina", 1, 1_200_000, None),
        ),
        (
            "Rustamga disk $300",
            VoiceDebtDraft("Rustam", "Disk", 1, 300, Currency.USD),
        ),
    ],
)
def test_parses_debt_phrases(text: str, expected: VoiceDebtDraft) -> None:
    assert parse_voice_debt(text) == expected


@pytest.mark.parametrize(
    ("text", "missing"),
    [
        ("ikkita shina besh yuz ming", "mijoz ismi"),
        ("Anvarga besh yuz ming so'm", "tovar nomi"),
        ("Anvarga shina", "narx"),
        ("", "mijoz ismi"),
    ],
)
def test_reports_missing_fields(text: str, missing: str) -> None:
    with pytest.raises(VoiceParseError, match=missing):
        parse_voice_debt(text)
