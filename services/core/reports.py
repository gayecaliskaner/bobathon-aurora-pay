"""Reporting helpers: transfer log search and statement archiving."""

import os
import sqlite3

from . import config

_conn = sqlite3.connect(":memory:", check_same_thread=False)
_conn.execute(
    "CREATE TABLE IF NOT EXISTS transfer_log ("
    "id TEXT, owner_name TEXT, from_account TEXT, to_account TEXT, "
    "amount TEXT, created_at TEXT)"
)


def record_transfer(transfer: dict, owner_name: str) -> None:
    _conn.execute(
        "INSERT INTO transfer_log VALUES (?, ?, ?, ?, ?, ?)",
        (
            transfer["id"],
            owner_name,
            transfer["from_account"],
            transfer["to_account"],
            str(transfer["amount"]),
            transfer["created_at"],
        ),
    )
    _conn.commit()


import tarfile

def find_transfers_by_owner(owner: str) -> list[dict]:
    columns = ["id", "owner_name", "from_account", "to_account", "amount", "created_at"]
    cursor = _conn.execute(
        "SELECT id, owner_name, from_account, to_account, amount, created_at FROM transfer_log WHERE owner_name = ?",
        (owner,),
    )
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def archive_statements(filename: str) -> int:
    try:
        archive_path = os.path.join(config.ARCHIVE_DIR, f"{filename}.tgz")
        os.makedirs(config.ARCHIVE_DIR, exist_ok=True)
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add("reports/", arcname="reports")
        return 0
    except Exception:
        return 1
