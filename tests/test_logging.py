import logging

from dome_core.logging import configure_logging, get_logger


def test_configure_logging_development():
    configure_logging(environment="development")
    logger = get_logger("test")
    assert logger is not None
    logger.info("test_event", key="value")


def test_configure_logging_production():
    configure_logging(environment="production")
    logger = get_logger("test")
    assert logger is not None
    logger.info("test_event", key="value")


def test_httpx_suppressed():
    configure_logging(environment="production")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
