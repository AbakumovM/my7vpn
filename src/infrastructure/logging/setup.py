import logging
import logging.handlers
import sys

import structlog

from src.infrastructure.config import LoggingSettings


def configure_logging(settings: LoggingSettings) -> None:
    level = logging.getLevelName(settings.log_level.upper())

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    stdout_renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer()
    )
    stdout_formatter = structlog.stdlib.ProcessorFormatter(
        processor=stdout_renderer,
        foreign_pre_chain=shared_processors,
    )
    json_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(stdout_formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(stdout_handler)

    if settings.log_to_file:
        settings.log_dir.mkdir(parents=True, exist_ok=True)

        app_handler = logging.handlers.RotatingFileHandler(
            settings.log_dir / "app.jsonl",
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        app_handler.setFormatter(json_formatter)
        root.addHandler(app_handler)

        error_handler = logging.handlers.RotatingFileHandler(
            settings.log_dir / "error.jsonl",
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(json_formatter)
        root.addHandler(error_handler)
