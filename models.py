from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Администратор"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Word(db.Model):
    """So'z (dublikatlarga ruxsat beriladi)"""
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False, index=True)  # unique=True ni olib tashladik!
    definition = db.Column(db.Text, nullable=False)
    etymology = db.Column(db.Text)
    translation_en = db.Column(db.String(200))

    # Связи с другими таблицами - используем разные имена для backref
    categories = db.relationship('WordCategory', backref='word_item', lazy='dynamic', cascade='all, delete-orphan')
    synonyms = db.relationship('WordSynonym', backref='word_item', lazy='dynamic', cascade='all, delete-orphan')
    antonyms = db.relationship('WordAntonym', backref='word_item', lazy='dynamic', cascade='all, delete-orphan')
    hyperonyms = db.relationship('WordHyperonym', backref='word_item', lazy='dynamic', cascade='all, delete-orphan')
    hyponyms = db.relationship('WordHyponym', backref='word_item', lazy='dynamic', cascade='all, delete-orphan')
    holonyms = db.relationship('WordHolonym', backref='word_item', lazy='dynamic', cascade='all, delete-orphan')
    meronyms = db.relationship('WordMeronym', backref='word_item', lazy='dynamic', cascade='all, delete-orphan')
    homonyms = db.relationship('WordHomonym', backref='word_item', lazy='dynamic', cascade='all, delete-orphan')
    paronyms = db.relationship('WordParonym', backref='word_item', lazy='dynamic', cascade='all, delete-orphan')
    usage_areas = db.relationship('WordUsageArea', backref='word_item', lazy='dynamic', cascade='all, delete-orphan')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Преобразование в словарь для API"""
        return {
            'id': self.id,
            'word': self.word,
            'определение': self.definition,
            'translation_en': self.translation_en,  # <--- YANGI
            'turkumi': [cat.category for cat in self.categories],
            'синонимы': [rel.related_word for rel in self.synonyms],
            'антонимы': [rel.related_word for rel in self.antonyms],
            'гиперонимы': [rel.related_word for rel in self.hyperonyms],
            'гипонимы': [rel.related_word for rel in self.hyponyms],
            'xolonim': [rel.related_word for rel in self.holonyms],
            'meronim': [rel.related_word for rel in self.meronyms],
            'omonim': [rel.related_word for rel in self.homonyms],
            'paronim': [rel.related_word for rel in self.paronyms],
            'qollanilishi': [area.area for area in self.usage_areas],
            'etimologiyasi': [self.etymology] if self.etymology else []
        }


# Таблицы для отношений между словами
class WordCategory(db.Model):
    """Категория слова (turkumi)"""
    __tablename__ = 'word_category'
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)

    def __repr__(self):
        return f'<WordCategory {self.category}>'


class WordSynonym(db.Model):
    """Синонимы"""
    __tablename__ = 'word_synonym'
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    related_word = db.Column(db.String(100), nullable=False, index=True)


class WordAntonym(db.Model):
    """Антонимы"""
    __tablename__ = 'word_antonym'
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    related_word = db.Column(db.String(100), nullable=False, index=True)


class WordHyperonym(db.Model):
    """Гиперонимы"""
    __tablename__ = 'word_hyperonym'
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    related_word = db.Column(db.String(100), nullable=False, index=True)


class WordHyponym(db.Model):
    """Гипонимы"""
    __tablename__ = 'word_hyponym'
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    related_word = db.Column(db.String(100), nullable=False, index=True)


class WordHolonym(db.Model):
    """Холонимы"""
    __tablename__ = 'word_holonym'
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    related_word = db.Column(db.String(100), nullable=False, index=True)


class WordMeronym(db.Model):
    """Меронимы"""
    __tablename__ = 'word_meronym'
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    related_word = db.Column(db.String(100), nullable=False, index=True)


class WordHomonym(db.Model):
    """Омонимы"""
    __tablename__ = 'word_homonym'
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    related_word = db.Column(db.String(100), nullable=False, index=True)


class WordParonym(db.Model):
    """Паронимы"""
    __tablename__ = 'word_paronym'
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    related_word = db.Column(db.String(100), nullable=False, index=True)


class WordUsageArea(db.Model):
    """Область применения"""
    __tablename__ = 'word_usage_area'
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    area = db.Column(db.String(100), nullable=False, index=True)


class Visit(db.Model):
    """Модель для отслеживания посещений"""
    __tablename__ = 'visit'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(200))
    visited_at = db.Column(db.DateTime, default=datetime.utcnow)
    page = db.Column(db.String(100))


class UserVisit(db.Model):
    """Уникальные посетители (по IP)"""
    __tablename__ = 'user_visit'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), unique=True)
    first_visit = db.Column(db.DateTime, default=datetime.utcnow)
    last_visit = db.Column(db.DateTime, default=datetime.utcnow)
    visit_count = db.Column(db.Integer, default=1)