import sqlite3

from flask import g


def get_db():
    from flask import current_app

    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db
