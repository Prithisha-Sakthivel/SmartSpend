PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 display_name TEXT NOT NULL, avatar_storage_key TEXT, is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_settings (
 user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, currency_code TEXT NOT NULL DEFAULT 'INR',
 default_buffer_paise INTEGER NOT NULL DEFAULT 0 CHECK(default_buffer_paise >= 0), planning_horizon_days INTEGER NOT NULL DEFAULT 30 CHECK(planning_horizon_days > 0),
 available_balance_paise INTEGER, balance_as_of_date TEXT, timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
 balance_is_demo INTEGER NOT NULL DEFAULT 0 CHECK(balance_is_demo IN (0,1)),
 CHECK((available_balance_paise IS NULL AND balance_as_of_date IS NULL) OR (available_balance_paise IS NOT NULL AND balance_as_of_date IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS password_reset_tokens (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, token_hash TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_reset_user ON password_reset_tokens(user_id, expires_at);
CREATE TABLE IF NOT EXISTS categories (
 id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, name TEXT NOT NULL,
 kind TEXT NOT NULL DEFAULT 'expense' CHECK(kind IN ('expense','income')), is_active INTEGER NOT NULL DEFAULT 1,
 UNIQUE(user_id,name,kind)
);
CREATE TABLE IF NOT EXISTS transactions (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 type TEXT NOT NULL CHECK(type IN ('income','expense')), amount_paise INTEGER NOT NULL CHECK(amount_paise > 0),
 description TEXT NOT NULL, category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
 occurred_on TEXT NOT NULL, notes TEXT, source TEXT NOT NULL DEFAULT 'manual',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id,occurred_on,id);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(user_id,category_id,occurred_on);
CREATE TABLE IF NOT EXISTS budgets (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE, period_type TEXT NOT NULL DEFAULT 'monthly' CHECK(period_type='monthly'),
 period_start TEXT NOT NULL, period_end TEXT NOT NULL, limit_paise INTEGER NOT NULL CHECK(limit_paise > 0),
 is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1)),
 UNIQUE(user_id,category_id,period_start)
);
CREATE TABLE IF NOT EXISTS scheduled_commitments (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('bill','income','savings')), description TEXT NOT NULL,
 amount_paise INTEGER NOT NULL CHECK(amount_paise > 0), due_on TEXT NOT NULL,
 category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
 status TEXT NOT NULL DEFAULT 'scheduled' CHECK(status IN ('scheduled','completed','cancelled')),
 recurrence_rule TEXT, series_id TEXT, linked_transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
 is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_commitments_due ON scheduled_commitments(user_id,status,due_on);
CREATE UNIQUE INDEX IF NOT EXISTS idx_commitment_series_occurrence ON scheduled_commitments(user_id,series_id,due_on) WHERE series_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS cooling_off_purchases (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 description TEXT NOT NULL, amount_paise INTEGER NOT NULL CHECK(amount_paise > 0), category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, review_on TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','proceeded','cancelled')),
 linked_transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL, is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_cooling_queue ON cooling_off_purchases(user_id,status,review_on,id);
CREATE TABLE IF NOT EXISTS savings_goals (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL, target_paise INTEGER NOT NULL CHECK(target_paise > 0), target_date TEXT,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','archived')),
 is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS savings_challenges (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL, challenge_type TEXT NOT NULL CHECK(challenge_type IN ('target_by_end','fixed_cadence','no_spend')),
 target_paise INTEGER NOT NULL DEFAULT 0 CHECK(target_paise >= 0), installment_paise INTEGER,
 start_on TEXT NOT NULL, end_on TEXT NOT NULL, cadence TEXT NOT NULL DEFAULT 'once' CHECK(cadence IN ('once','daily','weekly','monthly')),
 goal_id INTEGER REFERENCES savings_goals(id) ON DELETE SET NULL, category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
 is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1)),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('scheduled','active','completed','cancelled')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(end_on >= start_on), CHECK(installment_paise IS NULL OR installment_paise > 0)
);
CREATE TABLE IF NOT EXISTS goal_contributions (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 goal_id INTEGER REFERENCES savings_goals(id) ON DELETE CASCADE,
 challenge_id INTEGER REFERENCES savings_challenges(id) ON DELETE CASCADE,
 amount_paise INTEGER NOT NULL CHECK(amount_paise > 0), contributed_on TEXT NOT NULL,
 note TEXT, source TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','challenge')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reversed_at TEXT,
 is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1)),
 CHECK(goal_id IS NOT NULL OR challenge_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS challenge_checkins (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 challenge_id INTEGER NOT NULL REFERENCES savings_challenges(id) ON DELETE CASCADE,
 check_on TEXT NOT NULL, result TEXT NOT NULL CHECK(result IN ('met','missed')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,challenge_id,check_on)
);
CREATE INDEX IF NOT EXISTS idx_contributions_goal ON goal_contributions(user_id,goal_id,contributed_on,reversed_at);
CREATE INDEX IF NOT EXISTS idx_contributions_challenge ON goal_contributions(user_id,challenge_id,contributed_on,reversed_at);
CREATE TABLE IF NOT EXISTS undo_events (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 sequence_no INTEGER NOT NULL, entity_type TEXT NOT NULL DEFAULT 'transaction' CHECK(entity_type='transaction'),
 entity_id INTEGER NOT NULL, operation TEXT NOT NULL CHECK(operation IN ('create','edit','delete')),
 related_entity_type TEXT, related_entity_id INTEGER,
 payload_version INTEGER NOT NULL DEFAULT 1, before_image TEXT, after_image TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, undone_at TEXT,
 UNIQUE(user_id,sequence_no)
);
CREATE INDEX IF NOT EXISTS idx_undo_user_seq ON undo_events(user_id,undone_at,sequence_no DESC);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);
