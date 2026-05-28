from app import app, db
from sqlalchemy import text


def fix_table_duplicates(table_name, columns):
    """Удаляет дубликаты в указанной таблице"""
    print(f"\n🔍 Проверка таблицы: {table_name}")

    # Находим дубликаты
    if len(columns) == 2:
        where_clause = f"{columns[0]} = :col1 AND {columns[1]} = :col2"
    else:
        where_clause = f"{columns[0]} = :col1"

    duplicates = db.session.execute(text(f"""
        SELECT {', '.join(columns)}, COUNT(*) as cnt 
        FROM {table_name} 
        GROUP BY {', '.join(columns)} 
        HAVING COUNT(*) > 1
    """)).fetchall()

    if duplicates:
        print(f"  📊 Найдено {len(duplicates)} групп дубликатов")

        for dup in duplicates:
            params = {}
            for i, col in enumerate(columns):
                params[f'col{i + 1}'] = dup[i]

            # Удаляем дубликаты, оставляя только один
            if len(columns) == 2:
                db.session.execute(text(f"""
                    DELETE FROM {table_name} 
                    WHERE id NOT IN (
                        SELECT MIN(id) FROM {table_name} 
                        WHERE {columns[0]} = :col1 AND {columns[1]} = :col2
                    )
                    AND {columns[0]} = :col1 AND {columns[1]} = :col2
                """), {'col1': params['col1'], 'col2': params['col2']})
            else:
                db.session.execute(text(f"""
                    DELETE FROM {table_name} 
                    WHERE id NOT IN (
                        SELECT MIN(id) FROM {table_name} 
                        WHERE {columns[0]} = :col1
                    )
                    AND {columns[0]} = :col1
                """), {'col1': params['col1']})

        db.session.commit()
        print(f"  ✅ Дубликаты удалены")
    else:
        print(f"  ✅ Дубликатов не найдено")


with app.app_context():
    print("=" * 50)
    print("🔄 НАЧАЛО ОЧИСТКИ ДУБЛИКАТОВ")
    print("=" * 50)

    # Список таблиц и их столбцов для проверки уникальности
    tables = [
        ('word_category', ['word_id', 'category']),
        ('word_synonym', ['word_id', 'related_word']),
        ('word_antonym', ['word_id', 'related_word']),
        ('word_hyperonym', ['word_id', 'related_word']),
        ('word_hyponym', ['word_id', 'related_word']),
        ('word_holonym', ['word_id', 'related_word']),
        ('word_meronym', ['word_id', 'related_word']),
        ('word_homonym', ['word_id', 'related_word']),
        ('word_paronym', ['word_id', 'related_word']),
        ('word_usage_area', ['word_id', 'area']),
    ]

    for table_name, columns in tables:
        fix_table_duplicates(table_name, columns)

    print("\n" + "=" * 50)
    print("✅ ОЧИСТКА ЗАВЕРШЕНА")
    print("=" * 50)

    # Финальная статистика
    print("\n📊 ИТОГОВАЯ СТАТИСТИКА:")
    for table_name, _ in tables:
        count = db.session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).fetchone()[0]
        print(f"   {table_name}: {count} записей")