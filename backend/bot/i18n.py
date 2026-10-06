"""Настройка gettext (Babel) для aiogram."""

from pathlib import Path

from aiogram.utils.i18n import I18n

LOCALES_DIR = Path(__file__).resolve().parents[2] / "locales"

i18n = I18n(path=LOCALES_DIR, default_locale="ru", domain="messages")

SUPPORTED_LOCALES = ("ru", "uz", "en")
