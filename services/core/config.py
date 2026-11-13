"""Aurora Core configuration."""

import os

API_KEY = os.environ.get("AURORA_API_KEY", "default-api-key")
DB_PASSWORD = os.environ.get("AURORA_DB_PASSWORD", "default-db-password")
JWT_SECRET = os.environ.get("AURORA_JWT_SECRET", "default-jwt-secret")

DB_URL = f"postgresql://aurora:{DB_PASSWORD}@db.internal.aurora-bank.example:5432/core"

ARCHIVE_DIR = "archives"
