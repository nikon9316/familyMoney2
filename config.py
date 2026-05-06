import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

BASE_PUBLIC_URL = os.getenv("BASE_PUBLIC_URL", "http://localhost:8080").rstrip("/")
WEBAPP_URL = f"{BASE_PUBLIC_URL}/webapp/index.html"

WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "8080")))

# Local: sqlite:///family_finance.db
# Railway PostgreSQL: postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME
DATABASE_URL = os.getenv("DATABASE_URL", os.getenv("DB_URL", "sqlite:///family_finance.db"))
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "UZS")

REMINDER_ENABLED = os.getenv("REMINDER_ENABLED", "true").lower() == "true"
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "21"))
REMINDER_MINUTE = int(os.getenv("REMINDER_MINUTE", "0"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "logs")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "true").lower() == "true"
BACKUP_HOUR = int(os.getenv("BACKUP_HOUR", "3"))
BACKUP_KEEP_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "14"))

# Admin panel. Keep this secret. Change it on Railway.
ADMIN_PANEL_TOKEN = os.getenv("ADMIN_PANEL_TOKEN", "change-me")


# Level 4.0 admin hardening
SUPERADMIN_TOKEN = os.getenv("SUPERADMIN_TOKEN", "change-me-superadmin")
ADMIN_IP_ALLOWLIST = [ip.strip() for ip in os.getenv("ADMIN_IP_ALLOWLIST", "").split(",") if ip.strip()]
ADMIN_RATE_LIMIT_COUNT = int(os.getenv("ADMIN_RATE_LIMIT_COUNT", "5"))
ADMIN_RATE_LIMIT_WINDOW = int(os.getenv("ADMIN_RATE_LIMIT_WINDOW", "10"))
RESTORE_OTP_TTL_SECONDS = int(os.getenv("RESTORE_OTP_TTL_SECONDS", "300"))

# Level 4.0.1 admin session/restore hardening
SUPERADMIN_TELEGRAM_ID = int(os.getenv("SUPERADMIN_TELEGRAM_ID", str(ADMIN_ID or 0)))
ADMIN_SESSION_TTL_SECONDS = int(os.getenv("ADMIN_SESSION_TTL_SECONDS", "86400"))
ADMIN_CSRF_HEADER = os.getenv("ADMIN_CSRF_HEADER", "X-CSRF-Token")


# Level 4.2 production settings
APP_ENV = os.getenv("APP_ENV", os.getenv("ENV", "development")).lower()
# In production/Railway, database schema should be managed by Alembic only.
DB_AUTO_CREATE = os.getenv("DB_AUTO_CREATE", "false" if APP_ENV == "production" else "true").lower() == "true"
# Cookie must be secure behind HTTPS in production/Railway.
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true" if APP_ENV == "production" or BASE_PUBLIC_URL.startswith("https://") else "false").lower() == "true"

# Level 4.3
BUDGET_NOTIFY_COOLDOWN_HOURS = int(os.getenv('BUDGET_NOTIFY_COOLDOWN_HOURS', '12'))
PDF_REPORT_FONT = os.getenv('PDF_REPORT_FONT', 'DejaVuSans')
PDF_REPORT_FONT_PATH = os.getenv('PDF_REPORT_FONT_PATH', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
PDF_REPORT_FONT_BOLD_PATH = os.getenv('PDF_REPORT_FONT_BOLD_PATH', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')

# Level 5.5.4 production/monitoring settings
SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05"))
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", APP_ENV)
ERROR_NOTIFY_TELEGRAM = os.getenv("ERROR_NOTIFY_TELEGRAM", "true").lower() == "true"
APP_VERSION = os.getenv("APP_VERSION", "5.5.4")
HEALTHCHECK_SECRET = os.getenv("HEALTHCHECK_SECRET", "").strip()
BACKUP_AT_STARTUP = os.getenv("BACKUP_AT_STARTUP", "false").lower() == "true"
BACKUP_EVERY_HOURS = int(os.getenv("BACKUP_EVERY_HOURS", "24"))

# Level 5.5.4 external backup storage. Provider can be: local, s3.
BACKUP_STORAGE_PROVIDER = os.getenv("BACKUP_STORAGE_PROVIDER", "local").lower().strip()
BACKUP_S3_BUCKET = os.getenv("BACKUP_S3_BUCKET", "").strip()
BACKUP_S3_PREFIX = os.getenv("BACKUP_S3_PREFIX", "family-finance/backups").strip().strip("/")
BACKUP_S3_ENDPOINT_URL = os.getenv("BACKUP_S3_ENDPOINT_URL", "").strip()
BACKUP_S3_REGION = os.getenv("BACKUP_S3_REGION", "auto").strip()
