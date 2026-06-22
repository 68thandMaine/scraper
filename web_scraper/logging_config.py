"""Shared logging configuration for the scraper and agent."""

import logging
import sys
import threading
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
    level = logging.DEBUG if verbose else logging.WARNING
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


_BRAILLE_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class Spinner:
    """Animates a tqdm bar's description with a rotating braille glyph."""

    def __init__(self, pbar: "tqdm.tqdm", interval: float = 0.1) -> None:
        self._pbar = pbar
        self._interval = interval
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self.message: str = ""
        self._thread: Optional[threading.Thread] = None

    def _run(self) -> None:
        frame_count = len(_BRAILLE_FRAMES)
        idx = 0
        while not self._stop_event.wait(self._interval):
            frame = _BRAILLE_FRAMES[idx % frame_count]
            idx += 1
            with self.lock:
                desc = frame + (" " + self.message if self.message else "")
                self._pbar.set_description_str(desc)

    def start(self) -> None:
        if not sys.stderr.isatty():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            if self._thread.is_alive():
                self._thread.join()
            with self.lock:
                self._pbar.set_description_str("")

    def update_message(self, message: str) -> None:
        with self.lock:
            self.message = message

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


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
