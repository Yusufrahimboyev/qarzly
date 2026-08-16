"""Domain entities paketi."""
from bot.domain.entities.client import Client
from bot.domain.entities.debt import Debt, DebtStatus
from bot.domain.entities.payment import Payment, PaymentType
from bot.domain.entities.report import ClientDebtSummary, ClientReport
from bot.domain.entities.user import User

__all__ = [
    "Client",
    "ClientDebtSummary",
    "ClientReport",
    "Debt",
    "DebtStatus",
    "Payment",
    "PaymentType",
    "User",
]
