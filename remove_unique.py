from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # UNIQUE cheklovni olib tashlash
        db.session.execute(text('DROP INDEX IF EXISTS ix_word_word'))
        db.session.commit()
        print("✅ UNIQUE constraint removed successfully!")

        # Tekshirish
        result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_word_word'"))
        if result.fetchone():
            print("⚠️ Index still exists!")
        else:
            print("✅ Index removed confirmed!")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.session.rollback()