import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this'
    # Vercel сам подставит переменную DATABASE_URL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///thesaurus_data.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False