import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import LOG_DIR, LOG_LEVEL, SENTRY_DSN, SENTRY_ENVIRONMENT, SENTRY_TRACES_SAMPLE_RATE, APP_VERSION


def setup_sentry() -> bool:
    """Initialize Sentry if SENTRY_DSN is configured.

    The app must also work without Sentry, so missing package/DSN is never fatal.
    """
    if not SENTRY_DSN:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.aiohttp import AioHttpIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            release=f"family-finance@{APP_VERSION}",
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            integrations=[
                AioHttpIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            send_default_pii=False,
        )
        return True
    except Exception:
        logging.getLogger(__name__).exception('Sentry init failed')
        return False


def setup_logging() -> logging.Logger:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    fmt = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)

    file_handler = RotatingFileHandler(
        Path(LOG_DIR) / 'app.log',
        maxBytes=1_000_000,
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(fmt)

    if not logger.handlers:
        logger.addHandler(console)
        logger.addHandler(file_handler)

    if setup_sentry():
        logger.info('Sentry monitoring enabled')
    else:
        logger.info('Sentry monitoring disabled')

    return logging.getLogger('family_finance')
