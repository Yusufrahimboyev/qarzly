from __future__ import annotations

from aiogram import Dispatcher

from bot.application.services.user_service import UserService
from bot.presentation.middlewares.dependency_middleware import DependencyMiddleware
from bot.presentation.middlewares.error_middleware import ErrorMiddleware


def register_middlewares(dp: Dispatcher, user_service: UserService) -> None:
    error_mw = ErrorMiddleware()
    dependency_mw = DependencyMiddleware(user_service)

    for observer in (dp.message, dp.callback_query):
        observer.middleware(error_mw)
        observer.middleware(dependency_mw)
