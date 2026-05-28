from app import app, db
from sqlalchemy import text

with app.app_context():
    print("=" * 50)
    print("🔒 ДОБАВЛЕНИЕ УНИКАЛЬНЫХ ИНДЕКСОВ")
    print("=" * 50)

    indexes = [
        ('word_category', ['word_id', 'category'], 'idx_unique_word_category'),
        ('word_synonym', ['word_id', 'related_word'], 'idx_unique_word_synonym'),
        ('word_antonym', ['word_id', 'related_word'], 'idx_unique_word_antonym'),
        ('word_hyperonym', ['word_id', 'related_word'], 'idx_unique_word_hyperonym'),
        ('word_hyponym', ['word_id', 'related_word'], 'idx_unique_word_hyponym'),
        ('word_holonym', ['word_id', 'related_word'], 'idx_unique_word_holonym'),
        ('word_meronym', ['word_id', 'related_word'], 'idx_unique_word_meronym'),
        ('word_homonym', ['word_id', 'related_word'], 'idx_unique_word_homonym'),
        ('word_paronym', ['word_id', 'related_word'], 'idx_unique_word_paronym'),
        ('word_usage_area', ['word_id', 'area'], 'idx_unique_word_usage_area'),
    ]

    for table, columns, idx_name in indexes:
        try:
            # Проверяем существование индекса
            if 'sqlite' in str(db.engine.url):
                # Для SQLite
                db.session.execute(text(f"DROP INDEX IF EXISTS {idx_name}"))
                db.session.execute(text(f"""
                    CREATE UNIQUE INDEX {idx_name} 
                    ON {table} ({', '.join(columns)})
                """))
            else:
                # Для PostgreSQL
                db.session.execute(text(f"""
                    CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {idx_name} 
                    ON {table} ({', '.join(columns)})
                """))

            print(f"✅ Уникальный индекс для {table}: {idx_name}")
        except Exception as e:
            print(f"⚠️ Ошибка для {table}: {e}")

    db.session.commit()
    print("\n✅ Все индексы добавлены!")