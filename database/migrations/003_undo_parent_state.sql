-- Applied by app/db.py with column-existence checks for existing databases.
ALTER TABLE undo_events ADD COLUMN related_entity_type TEXT;
ALTER TABLE undo_events ADD COLUMN related_entity_id INTEGER;
INSERT OR IGNORE INTO schema_migrations(version) VALUES (3);
