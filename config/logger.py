import logging
from time import perf_counter
from typing import Any

from .manager import get_logging_config


logging_configured = False


def configure_logging(force: bool = False) -> None:
    global logging_configured

    if logging_configured and not force:
        return

    logging_config = get_logging_config()
    if not logging_config.get('enabled', True):
        logging.disable(logging.CRITICAL)
        logging_configured = True
        return

    logging.disable(logging.NOTSET)

    log_level_name = str(logging_config.get('level', 'INFO')).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_format = logging_config.get(
        'format',
        '%(asctime)s %(levelname)s [%(name)s] %(message)s',
    )
    date_format = logging_config.get('date_format', '%Y-%m-%d %H:%M:%S')

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    logging.basicConfig(level=log_level, format=log_format, datefmt=date_format)
    logging_configured = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def is_timing_logging_enabled() -> bool:
    logging_config = get_logging_config()
    return logging_config.get('enabled', True) and logging_config.get('timing_enabled', True)


def start_timer() -> float:
    return perf_counter()


def log_stage_timing(logger: logging.Logger, stage_name: str, started_at: float, **context: Any) -> None:
    if not is_timing_logging_enabled():
        return

    elapsed_ms = (perf_counter() - started_at) * 1000
    context_message = ' '.join(f'{key}={value}' for key, value in context.items())
    suffix = f' {context_message}' if context_message else ''
    logger.info('Timing stage=%s elapsed_ms=%.2f%s', stage_name, elapsed_ms, suffix)
