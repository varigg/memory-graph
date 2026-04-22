import sqlite3
from contextlib import contextmanager

from flask import g


def get_db():
    from flask import current_app

    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db


@contextmanager
def write_transaction(db: sqlite3.Connection):
    """Context manager that commits on clean exit and rolls back on any exception.

    Usage::

        with write_transaction(db):
            insert_memory(db, ...)
            insert_memory(db, ...)   # both committed or neither
    """
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
