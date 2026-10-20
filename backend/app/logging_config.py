"""
COMPASS Logging Configuration
Structured logging to console and rotating log file with secret redaction (§14).
"""

import logging
import re
import sys

from backend.app.config import settings


class SecretRedactionFilter(logging.Filter):
    """
    Scrubs credentials, API keys, Bearer tokens, and passwords from log records (§14).
    Prevents leakage of sensitive runtime authentication artifacts into persistent logs.
    """

    PATTERNS = [  # noqa: RUF012
        re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
        re.compile(
            r'((?:api[_-]?key|access[_-]?token|secret)["\s:=]+)["\']?[A-Za-z0-9\-._~+/]{8,}["\']?',
            re.IGNORECASE,
        ),
        re.compile(
            r'((?:password|passwd)["\s:=]+)["\']?[^\s"\']{4,}["\']?', re.IGNORECASE
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self.redact(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: self.redact(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
        return True

    @classmethod
    def redact(cls, text: str) -> str:
        res = text
        for p in cls.PATTERNS:
            res = p.sub(r"\1[REDACTED]", res)
        return res


def setup_logging() -> logging.Logger:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("compass")
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s:%(module)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    redaction_filter = SecretRedactionFilter()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redaction_filter)
    logger.addHandler(console_handler)

    # Use basic FileHandler to avoid WinError 32 during high concurrency
    file_handler = logging.FileHandler(
        filename=str(settings.log_file),
        mode='a',
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redaction_filter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


logger = setup_logging()
