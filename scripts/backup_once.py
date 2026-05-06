from app_logging import setup_logging
from backup import create_backup, cleanup_old_backups

logger = setup_logging()

if __name__ == '__main__':
    path = create_backup()
    deleted = cleanup_old_backups()
    logger.info('Backup created: %s; old deleted=%s', path, deleted)
    print(path)
