"""Presentation qatlami: middleware'larni ro'yxatga olish."""
from __future__ import annotations

from aiogram import Dispatcher

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.application.services.user_service import UserService
from bot.core.config import Settings
from bot.presentation.middlewares.admin_middleware import AdminMiddleware
from bot.presentation.middlewares.dependency_middleware import DependencyMiddleware
from bot.presentation.middlewares.error_middleware import ErrorMiddleware


def register_middlewares(
    dp: Dispatcher,
    user_service: UserService,
    client_service: ClientService,
    debt_service: DebtService,
    settings: Settings,
) -> None:
    """Barcha middleware'larni ro'yxatga oladi."""
    error_mw = ErrorMiddleware()
    admin_mw = AdminMiddleware(settings)
    dependency_mw = DependencyMiddleware(
        user_service=user_service,
        client_service=client_service,
        debt_service=debt_service,
        settings=settings,
    )

    for observer in (dp.message, dp.callback_query):
        observer.middleware(error_mw)
        observer.middleware(admin_mw)
        observer.middleware(dependency_mw)
