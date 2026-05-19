"""
Logging utilities — structlog helpers and request context injection.
"""
import logging
import sys
import uuid
from typing import Any, Dict

import structlog

from app.core.config import settings


def configure_logging():
    """Configure structlog for the application."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            (
                structlog.processors.JSONRenderer()
                if settings.is_production
                else structlog.dev.ConsoleRenderer(colors=True)
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_request_id() -> str:
    """Generate a unique request ID for tracing."""
    return str(uuid.uuid4())[:8]


def bind_request_context(request_id: str, **kwargs: Any):
    """Bind values to the current structlog context."""
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        **kwargs,
    )


def clear_request_context():
    """Clear the structlog request context."""
    structlog.contextvars.clear_contextvars()
