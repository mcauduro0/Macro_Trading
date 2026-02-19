"""Structured logging configuration for the Macro Trading system.

Uses structlog with context variables, ISO timestamps, and console rendering
for development. Provides get_logger() for named loggers and configure_logging()
for one-time setup.
"""

import structlog

_configured = False


def configure_logging() -> None:
    """Configure structlog processors once.

    Safe to call multiple times -- only the first invocation takes effect.
    """
    global _configured
    if _configured:
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a bound logger with the given name.

    Ensures logging is configured before returning.

    Args:
        name: Logger name, typically the module or connector name.

    Returns:
        A structlog BoundLogger instance bound with the given name.
    """
    configure_logging()
    return structlog.get_logger(logger_name=name)
