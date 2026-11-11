import sqlite3
from flask import current_app, g
from pathlib import Path


def get_db():
    if "db" not in g:
        db_path = Path(current_app.config["DATABASE"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        schema = Path(app.root_path).parent / "database" / "schema.sql"
        db.executescript(schema.read_text(encoding="utf-8"))
        # Additive migration for databases created by the first SmartSpend build.
        additions = {
            "user_settings": [("balance_is_demo", "INTEGER NOT NULL DEFAULT 0 CHECK(balance_is_demo IN (0,1))")],
            "budgets": [("is_demo", "INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1))")],
            "scheduled_commitments": [("is_demo", "INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1))")],
            "cooling_off_purchases": [("is_demo", "INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1))")],
            "savings_goals": [("is_demo", "INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1))")],
            "savings_challenges": [("category_id", "INTEGER REFERENCES categories(id) ON DELETE SET NULL"), ("is_demo", "INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1))")],
            "goal_contributions": [("is_demo", "INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1))")],
            "undo_events": [("related_entity_type", "TEXT"), ("related_entity_id", "INTEGER")],
        }
        for table, columns in additions.items():
            present = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
            for column, declaration in columns:
                if column not in present:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
        db.execute("CREATE TABLE IF NOT EXISTS challenge_checkins (id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,challenge_id INTEGER NOT NULL REFERENCES savings_challenges(id) ON DELETE CASCADE,check_on TEXT NOT NULL,result TEXT NOT NULL CHECK(result IN ('met','missed')),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,challenge_id,check_on))")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_commitment_series_occurrence ON scheduled_commitments(user_id,series_id,due_on) WHERE series_id IS NOT NULL")
        db.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (2)")
        db.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (3)")
        db.commit()
