"""Markazlashtirilgan logging sozlamasi."""
import logging


def setup_logging(level: str = "INFO") -> None:
    """Ilova bo'ylab yagona log formatini o'rnatadi."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Kutubxonalarning ortiqcha "shovqin"ini kamaytiramiz.
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
