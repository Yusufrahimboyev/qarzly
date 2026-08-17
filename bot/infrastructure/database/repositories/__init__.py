"""Infrastructure database repositories paketi."""
from bot.infrastructure.database.repositories.client_repository import (
    PgClientRepository,
)
from bot.infrastructure.database.repositories.debt_repository import (
    PgDebtRepository,
)
from bot.infrastructure.database.repositories.payment_repository import (
    PgPaymentRepository,
)
from bot.infrastructure.database.repositories.user_repository import (
    PgUserRepository,
)

__all__ = [
    "PgClientRepository",
    "PgDebtRepository",
    "PgPaymentRepository",
    "PgUserRepository",
]
