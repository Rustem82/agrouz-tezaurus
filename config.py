import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this'
    # Теперь ищем переменные с префиксом PRISMA_
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('PRISMA_POSTGRES_URL') or        # Прямое подключение
        os.environ.get('PRISMA_DATABASE_URL') or         # Альтернативное имя
        os.environ.get('DATABASE_URL') or                # Старое имя (на всякий случай)
        'sqlite:///thesaurus_data.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
