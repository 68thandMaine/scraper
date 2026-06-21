"""Shared logging configuration for the scraper and agent."""

import logging
import sys
import time
from contextlib import contextmanager
from typing import Iterator, Optional

import tqdm


class TqdmLoggingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            tqdm.tqdm.write(msg, file=sys.stderr)
            self.flush()
        except Exception:
            self.handleError(record)


def configure_logging(verbose: bool = False) -> None:
    """Configure root logging once (avoids duplicate handlers)."""
    level = logging.DEBUG if verbose else logging.INFO
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    handler = TqdmLoggingHandler()
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.setLevel(level)
    root.addHandler(handler)


@contextmanager
def log_step(
    step: str,
    logger: Optional[logging.Logger] = None,
    **context: object,
) -> Iterator[None]:
    """Log start/end of a pipeline step with elapsed time."""
    log = logger or logging.getLogger(__name__)
    context_str = " ".join(f"{k}={v}" for k, v in context.items() if v is not None)
    log.info("[START] %s%s", step, f" ({context_str})" if context_str else "")
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        log.info("[DONE] %s (%.1fs)", step, elapsed)
