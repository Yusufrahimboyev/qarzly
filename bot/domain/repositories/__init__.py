"""Domain repositories paketi."""
from bot.domain.repositories.client_repository import ClientRepository
from bot.domain.repositories.debt_repository import DebtRepository
from bot.domain.repositories.payment_repository import PaymentRepository
from bot.domain.repositories.user_repository import UserRepository

__all__ = [
    "ClientRepository",
    "DebtRepository",
    "PaymentRepository",
    "UserRepository",
]
