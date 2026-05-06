import gzip
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from config import (
    BACKUP_DIR,
    BACKUP_KEEP_DAYS,
    DATABASE_URL,
    BACKUP_STORAGE_PROVIDER,
    BACKUP_S3_BUCKET,
    BACKUP_S3_PREFIX,
    BACKUP_S3_ENDPOINT_URL,
    BACKUP_S3_REGION,
)


def _timestamp() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _public_backup_meta(path: Path, external_url: str | None = None) -> dict:
    return {
        'name': path.name,
        'path': str(path),
        'size': path.stat().st_size if path.exists() else 0,
        'created_at': datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds') if path.exists() else datetime.now().isoformat(timespec='seconds'),
        'storage': BACKUP_STORAGE_PROVIDER or 'local',
        'external_url': external_url or '',
    }


def upload_backup_to_external_storage(path: str) -> str | None:
    """Upload backup to an external object storage if configured.

    BACKUP_STORAGE_PROVIDER=local keeps only local backups.
    BACKUP_STORAGE_PROVIDER=s3 uploads to any S3-compatible storage: AWS S3,
    Cloudflare R2, Backblaze B2 S3, Yandex Object Storage, etc.

    Required env for s3: BACKUP_S3_BUCKET. Credentials use standard boto3 env:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN if needed.
    """
    provider = (BACKUP_STORAGE_PROVIDER or 'local').lower().strip()
    if provider in ('', 'local', 'none', 'disabled'):
        return None
    file_path = Path(path)
    if provider == 's3':
        if not BACKUP_S3_BUCKET:
            raise RuntimeError('BACKUP_STORAGE_PROVIDER=s3, но BACKUP_S3_BUCKET не задан')
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError('Для внешнего backup storage установите boto3: python -m pip install boto3') from exc
        kwargs = {'region_name': BACKUP_S3_REGION or 'auto'}
        if BACKUP_S3_ENDPOINT_URL:
            kwargs['endpoint_url'] = BACKUP_S3_ENDPOINT_URL
        client = boto3.client('s3', **kwargs)
        key_prefix = (BACKUP_S3_PREFIX or 'family-finance/backups').strip('/')
        key = f'{key_prefix}/{file_path.name}' if key_prefix else file_path.name
        client.upload_file(str(file_path), BACKUP_S3_BUCKET, key)
        return f's3://{BACKUP_S3_BUCKET}/{key}'
    raise RuntimeError(f'Неподдерживаемый BACKUP_STORAGE_PROVIDER: {provider}')


def create_backup() -> str:
    """Creates a DB backup. SQLite is copied. PostgreSQL uses pg_dump if available.

    Level 5.1: after local backup is created, it is optionally uploaded to external
    object storage. The function still returns the local path for compatibility.
    """
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    ts = _timestamp()

    if DATABASE_URL.startswith('sqlite'):
        db_path = DATABASE_URL.replace('sqlite:///', '', 1)
        if db_path == ':memory:' or not os.path.exists(db_path):
            raise RuntimeError(f'SQLite database file not found: {db_path}')
        out_path = Path(BACKUP_DIR) / f'family_finance_sqlite_{ts}.db.gz'
        with open(db_path, 'rb') as src, gzip.open(out_path, 'wb') as dst:
            shutil.copyfileobj(src, dst)
        upload_backup_to_external_storage(str(out_path))
        return str(out_path)

    if DATABASE_URL.startswith('postgresql'):
        out_path = Path(BACKUP_DIR) / f'family_finance_postgres_{ts}.sql.gz'
        dump_url = DATABASE_URL.replace('postgresql+psycopg://', 'postgresql://')
        proc = subprocess.run(['pg_dump', dump_url], capture_output=True, text=False)
        if proc.returncode != 0:
            err = proc.stderr.decode('utf-8', errors='ignore')
            raise RuntimeError('pg_dump failed. Install PostgreSQL client on server. ' + err[:500])
        with gzip.open(out_path, 'wb') as f:
            f.write(proc.stdout)
        upload_backup_to_external_storage(str(out_path))
        return str(out_path)

    raise RuntimeError('Unsupported DATABASE_URL for backup')


def cleanup_old_backups() -> int:
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now() - timedelta(days=BACKUP_KEEP_DAYS)
    deleted = 0
    for file in Path(BACKUP_DIR).glob('*'):
        if file.is_file() and datetime.fromtimestamp(file.stat().st_mtime) < cutoff:
            file.unlink(missing_ok=True)
            deleted += 1
    return deleted


def list_backups() -> list[dict]:
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    items = []
    for file in sorted(Path(BACKUP_DIR).glob('*'), key=lambda p: p.stat().st_mtime, reverse=True):
        if file.is_file():
            items.append(_public_backup_meta(file))
    return items


def get_backup_path(name: str) -> Path:
    """Return a safe backup path inside BACKUP_DIR only."""
    safe_name = Path(str(name or '')).name
    path = (Path(BACKUP_DIR) / safe_name).resolve()
    base = Path(BACKUP_DIR).resolve()
    if base not in path.parents and path != base:
        raise RuntimeError('Invalid backup filename')
    if not path.exists() or not path.is_file():
        raise RuntimeError('Backup not found')
    return path


def restore_backup_from_file(src_path: str) -> str:
    """Restore DB from a backup file.

    SQLite: accepts .db or .db.gz and replaces the current sqlite file.
    PostgreSQL: accepts .sql/.sql.gz and pipes it to psql. This requires PostgreSQL client.
    """
    source = Path(src_path)
    if not source.exists():
        raise RuntimeError('Restore file not found')

    if DATABASE_URL.startswith('sqlite'):
        db_path = Path(DATABASE_URL.replace('sqlite:///', '', 1))
        if db_path.name == ':memory:':
            raise RuntimeError('Cannot restore in-memory SQLite database')
        db_path.parent.mkdir(parents=True, exist_ok=True)
        before = create_backup()
        if source.suffix == '.gz':
            with gzip.open(source, 'rb') as src, open(db_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
        else:
            shutil.copy2(source, db_path)
        return f'SQLite restored. Safety backup before restore: {before}'

    if DATABASE_URL.startswith('postgresql'):
        restore_url = DATABASE_URL.replace('postgresql+psycopg://', 'postgresql://')
        if source.suffix == '.gz':
            proc_gzip = subprocess.Popen(['gzip', '-dc', str(source)], stdout=subprocess.PIPE)
            proc = subprocess.run(['psql', restore_url], stdin=proc_gzip.stdout, capture_output=True, text=True)
        else:
            proc = subprocess.run(['psql', restore_url, '-f', str(source)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError('psql restore failed: ' + (proc.stderr or '')[:500])
        return 'PostgreSQL restored via psql'

    raise RuntimeError('Unsupported DATABASE_URL for restore')
