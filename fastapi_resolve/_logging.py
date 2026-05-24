import logging
import os


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"fastapi_resolve.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s: %(message)s"))
        logger.addHandler(handler)
    level = os.environ.get("FASTAPI_RESOLVE_LOG_LEVEL")
    if level:
        logger.setLevel(level)
    return logger
