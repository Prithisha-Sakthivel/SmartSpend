-- Applied by app/db.py with column-existence checks so it is safe for an existing v1 database.
-- Adds demo provenance, no-spend challenge check-ins, and unique dated recurrence occurrences.
ALTER TABLE user_settings ADD COLUMN balance_is_demo INTEGER NOT NULL DEFAULT 0 CHECK(balance_is_demo IN (0,1));
ALTER TABLE budgets ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1));
ALTER TABLE scheduled_commitments ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1));
ALTER TABLE cooling_off_purchases ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1));
ALTER TABLE savings_goals ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1));
ALTER TABLE savings_challenges ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL;
ALTER TABLE savings_challenges ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1));
ALTER TABLE goal_contributions ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1));
CREATE TABLE IF NOT EXISTS challenge_checkins (
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 challenge_id INTEGER NOT NULL REFERENCES savings_challenges(id) ON DELETE CASCADE,
 check_on TEXT NOT NULL,
 result TEXT NOT NULL CHECK(result IN ('met','missed')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(user_id,challenge_id,check_on)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_commitment_series_occurrence
 ON scheduled_commitments(user_id,series_id,due_on) WHERE series_id IS NOT NULL;
INSERT OR IGNORE INTO schema_migrations(version) VALUES (2);
