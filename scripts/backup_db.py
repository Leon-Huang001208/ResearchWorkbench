#!/usr/bin/env python3
"""PostgreSQL full backup script with retention support.

Supports both PostgreSQL and SQLite backups.
"""

import os
import sys
import subprocess
import argparse
import datetime
from pathlib import Path
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger()

def parse_args():
    parser = argparse.ArgumentParser(description="Backup database")
    parser.add_argument(
        "--output-dir", "-o",
        default="./backups",
        help="Directory to store backups (default: ./backups)"
    )
    parser.add_argument(
        "--retention", "-r",
        type=int,
        default=30,
        help="Number of daily backups to keep (default: 30)"
    )
    parser.add_argument(
        "--database-url", "-d",
        help="Database URL (overrides environment variable)"
    )
    parser.add_argument(
        "--sqlite-path",
        help="SQLite database path (for SQLite backups)"
    )
    return parser.parse_args()

def backup_postgres(database_url: str, output_path: Path) -> bool:
    """Create a PostgreSQL backup using pg_dump."""
    logger.info("Starting PostgreSQL backup", output_path=output_path)
    
    # Parse database URL to get connection parameters
    # URL format: postgresql://user:password@host:port/dbname
    from urllib.parse import urlparse
    parsed = urlparse(database_url)
    
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    
    cmd = [
        "pg_dump",
        f"--host={parsed.hostname or 'localhost'}",
        f"--port={parsed.port or 5432}",
        f"--username={parsed.username or 'postgres'}",
        f"--dbname={parsed.path.lstrip('/')}",
        "--no-owner",
        "--no-privileges",
        "-f", str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        logger.info("PostgreSQL backup completed successfully", output_path=output_path)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(
            "PostgreSQL backup failed",
            returncode=e.returncode,
            stderr=e.stderr
        )
        return False

def backup_sqlite(sqlite_path: Path, output_path: Path) -> bool:
    """Create a SQLite backup using SQLite's .backup command."""
    logger.info("Starting SQLite backup", sqlite_path=sqlite_path, output_path=output_path)
    
    cmd = [
        "sqlite3",
        str(sqlite_path),
        f".backup {output_path}"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info("SQLite backup completed successfully", output_path=output_path)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(
            "SQLite backup failed",
            returncode=e.returncode,
            stderr=e.stderr
        )
        return False

def cleanup_old_backups(backup_dir: Path, retention_days: int):
    """Remove backups older than retention_days."""
    logger.info("Cleaning up old backups", retention_days=retention_days)
    
    now = datetime.datetime.now()
    count = 0
    
    for backup_file in backup_dir.glob("*.sql"):
        try:
            # Parse timestamp from filename: backup_YYYYMMDD_HHMMSS.sql
            name_parts = backup_file.stem.split("_")
            if len(name_parts) < 3:
                continue
            
            date_str = name_parts[1]
            time_str = name_parts[2]
            backup_date = datetime.datetime.strptime(
                f"{date_str}_{time_str}",
                "%Y%m%d_%H%M%S"
            )
            
            age_days = (now - backup_date).days
            if age_days > retention_days:
                backup_file.unlink()
                # Also remove corresponding .gz if exists
                gz_file = backup_file.with_suffix(".sql.gz")
                if gz_file.exists():
                    gz_file.unlink()
                logger.info("Removed old backup", backup=backup_file.name, age_days=age_days)
                count += 1
        except Exception as e:
            logger.warning("Could not process backup file for cleanup", file=backup_file.name, error=str(e))
    
    logger.info("Cleanup completed", removed_count=count)

def main():
    load_dotenv()
    args = parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.sql"
    backup_path = output_dir / backup_filename
    
    database_url = args.database_url or os.getenv("DATABASE_URL")
    
    success = False
    if database_url and database_url.startswith("postgresql"):
        success = backup_postgres(database_url, backup_path)
    elif args.sqlite_path:
        success = backup_sqlite(Path(args.sqlite_path), backup_path)
    elif database_url and database_url.startswith("sqlite"):
        sqlite_path = Path(database_url.replace("sqlite:///", ""))
        success = backup_sqlite(sqlite_path, backup_path)
    else:
        logger.error("No valid database configuration found")
        sys.exit(1)
    
    if not success:
        sys.exit(1)
    
    # Compress the backup
    logger.info("Compressing backup", output_path=backup_path)
    try:
        subprocess.run(["gzip", str(backup_path)], check=True, capture_output=True, text=True)
        compressed_path = backup_path.with_suffix(".sql.gz")
        logger.info("Backup compressed successfully", compressed_path=compressed_path)
    except subprocess.CalledProcessError as e:
        logger.warning("Could not compress backup", error=str(e))
    
    # Cleanup old backups
    cleanup_old_backups(output_dir, args.retention)
    
    logger.info("Backup process completed")

if __name__ == "__main__":
    main()
