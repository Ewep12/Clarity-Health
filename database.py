# database.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(256), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    telegram_chat_id = db.Column(db.String(64), nullable=True)      # chat_id do próprio usuário (opcional)
    trusted_telegram_id = db.Column(db.String(64), nullable=True)   # chat_id da pessoa de confiança
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GlucoseRecord(db.Model):
    __tablename__ = 'glucose_record'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    meal_time = db.Column(db.String(256), nullable=True)
    exercise_time = db.Column(db.String(256), nullable=True)
    symptoms = db.Column(db.Text, nullable=True)

    user = db.relationship('User', backref=db.backref('glucose_records', lazy=True))

class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(256), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('chat_messages', lazy=True))
