"""Application logging.

The backend previously had no logging configuration at all — only `print` in
main.py — so uvicorn's access log was the only signal available. That log shows
that a request was rejected but never *why*: a screen full of
``POST /matches/swipe 400 Bad Request`` is indistinguishable between a species
mismatch, a duplicate swipe, an inactive pet and a missing target, which is
exactly the situation this module exists to end.

Every deliberate rejection is logged with the reason and the ids involved, and
every unexpected failure is logged with a traceback, so a line in the console is
enough to say what happened and where.
"""

import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """Install a single stdout handler on the root logger.

    Called once at import time from main.py. Uses ``force=True`` so it wins over
    any handler uvicorn or a library installed first — without it the app's own
    records were silently dropped in some run configurations.
    """
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,
        force=True,
    )

    # Loud by default, but not so loud the useful lines scroll away.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
