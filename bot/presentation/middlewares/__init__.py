"""Presentation qatlami: middleware'larni ro'yxatga olish."""
from __future__ import annotations

from aiogram import Dispatcher

from bot.core.config import Settings
from bot.infrastructure.branches import BranchRegistry
from bot.infrastructure.database.repositories.branch_preference_repository import (
    BranchPreferenceStore,
)
from bot.infrastructure.database.repositories.language_repository import LanguageStore
from bot.presentation.middlewares.admin_middleware import AdminMiddleware
from bot.presentation.middlewares.dependency_middleware import DependencyMiddleware
from bot.presentation.middlewares.error_middleware import ErrorMiddleware
from bot.presentation.middlewares.language_middleware import LanguageMiddleware


def register_middlewares(
    dp: Dispatcher,
    registry: BranchRegistry,
    preferences: BranchPreferenceStore,
    settings: Settings,
    language_store: LanguageStore,
) -> None:
    """Barcha middleware'larni ro'yxatga oladi."""
    language_mw = LanguageMiddleware(language_store)
    error_mw = ErrorMiddleware()
    admin_mw = AdminMiddleware(settings)
    dependency_mw = DependencyMiddleware(
        registry=registry,
        preferences=preferences,
        settings=settings,
    )

    for observer in (dp.message, dp.callback_query, dp.inline_query):
        observer.middleware(language_mw)
        observer.middleware(error_mw)
        observer.middleware(admin_mw)
        observer.middleware(dependency_mw)
