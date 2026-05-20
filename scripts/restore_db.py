#!/usr/bin/env python3
"""Database restore script from backup files.

Supports both PostgreSQL and SQLite restores.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import structlog
from dotenv import load_dotenv

logger = structlog.get_logger()


def parse_args():
    parser = argparse.ArgumentParser(description="Restore database from backup")
    parser.add_argument("backup_file", help="Path to the backup file (.sql or .sql.gz)")
    parser.add_argument(
        "--database-url", "-d", help="Database URL (overrides environment variable)"
    )
    parser.add_argument("--sqlite-path", help="SQLite database path (for SQLite restores)")
    parser.add_argument(
        "--drop-existing",
        "-f",
        action="store_true",
        help="Drop existing database before restore (PostgreSQL only)",
    )
    parser.add_argument(
        "--create-db",
        "-c",
        action="store_true",
        help="Create database if it doesn't exist (PostgreSQL only)",
    )
    return parser.parse_args()


def restore_postgres(
    database_url: str, backup_file: Path, drop_existing: bool, create_db: bool
) -> bool:
    """Restore a PostgreSQL backup using psql."""
    logger.info("Starting PostgreSQL restore", backup_file=backup_file)

    # Parse database URL to get connection parameters
    # URL format: postgresql://user:password@host:port/dbname
    from urllib.parse import urlparse

    parsed = urlparse(database_url)

    db_name = parsed.path.lstrip("/")
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    username = parsed.username or "postgres"
    password = parsed.password

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    # Handle compressed backups
    is_compressed = backup_file.suffix == ".gz"
    if is_compressed:
        decompress_cmd = ["gunzip", "-c", str(backup_file)]
        psql_cmd = [
            "psql",
            f"--host={host}",
            f"--port={port}",
            f"--username={username}",
            f"--dbname={db_name}",
        ]
    else:
        decompress_cmd = None
        psql_cmd = [
            "psql",
            f"--host={host}",
            f"--port={port}",
            f"--username={username}",
            f"--dbname={db_name}",
            "-f",
            str(backup_file),
        ]

    # Drop existing database if requested
    if drop_existing:
        logger.info("Dropping existing database", db_name=db_name)
        try:
            # Connect to postgres to drop the target database
            drop_cmd = [
                "dropdb",
                f"--host={host}",
                f"--port={port}",
                f"--username={username}",
                "--force",
                db_name,
            ]
            subprocess.run(drop_cmd, env=env, check=True, capture_output=True, text=True)
            logger.info("Dropped existing database", db_name=db_name)
        except subprocess.CalledProcessError as e:
            if create_db:
                # If we're creating it anyway, it's okay if it didn't exist
                logger.warning("Drop failed (probably database didn't exist)", db_name=db_name)
            else:
                logger.error(
                    "Failed to drop existing database", returncode=e.returncode, stderr=e.stderr
                )
                return False

    # Create database if requested
    if create_db:
        logger.info("Creating new database", db_name=db_name)
        try:
            create_cmd = [
                "createdb",
                f"--host={host}",
                f"--port={port}",
                f"--username={username}",
                f"--owner={username}",
                db_name,
            ]
            subprocess.run(create_cmd, env=env, check=True, capture_output=True, text=True)
            logger.info("Created new database", db_name=db_name)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to create database", returncode=e.returncode, stderr=e.stderr)
            return False

    try:
        if is_compressed:
            # Pipe decompressed output to psql
            p1 = subprocess.Popen(decompress_cmd, stdout=subprocess.PIPE)
            p2 = subprocess.Popen(
                psql_cmd,
                env=env,
                stdin=p1.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            p1.stdout.close()
            stdout, stderr = p2.communicate()

            if p2.returncode != 0:
                logger.error("PostgreSQL restore failed", returncode=p2.returncode, stderr=stderr)
                return False
        else:
            subprocess.run(psql_cmd, env=env, check=True, capture_output=True, text=True)

        logger.info("PostgreSQL restore completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("PostgreSQL restore failed", returncode=e.returncode, stderr=e.stderr)
        return False


def restore_sqlite(backup_file: Path, sqlite_path: Path) -> bool:
    """Restore a SQLite backup."""
    logger.info("Starting SQLite restore", sqlite_path=sqlite_path)

    # Remove existing database if it exists
    if sqlite_path.exists():
        sqlite_path.unlink()
        logger.info("Removed existing SQLite database")

    is_compressed = backup_file.suffix == ".gz"

    try:
        if is_compressed:
            # Decompress directly to the target file
            cmd = ["gunzip", "-c", str(backup_file)]
            with open(sqlite_path, "w") as f:
                subprocess.run(cmd, stdout=f, check=True, capture_output=True, text=True)
        else:
            # Just copy the backup
            cmd = ["cp", str(backup_file), str(sqlite_path)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)

        logger.info("SQLite restore completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("SQLite restore failed", returncode=e.returncode, stderr=e.stderr)
        return False


def main():
    load_dotenv()
    args = parse_args()

    backup_file = Path(args.backup_file)
    if not backup_file.exists():
        logger.error("Backup file not found", backup_file=args.backup_file)
        sys.exit(1)

    database_url = args.database_url or os.getenv("DATABASE_URL")

    success = False
    if database_url and database_url.startswith("postgresql"):
        success = restore_postgres(database_url, backup_file, args.drop_existing, args.create_db)
    elif args.sqlite_path:
        success = restore_sqlite(backup_file, Path(args.sqlite_path))
    elif database_url and database_url.startswith("sqlite"):
        sqlite_path = Path(database_url.replace("sqlite:///", ""))
        success = restore_sqlite(backup_file, sqlite_path)
    else:
        logger.error("No valid database configuration found")
        sys.exit(1)

    if not success:
        sys.exit(1)

    logger.info("Restore process completed")


if __name__ == "__main__":
    main()
