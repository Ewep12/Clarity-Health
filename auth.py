# auth.py
import os
import jwt
from functools import wraps
from flask import request, jsonify, current_app
from database import User, db

SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma_chave_local_secreta_aleatoria'

def create_auth_token(user_id, expires_in_seconds=60*60*24*7):
    payload = {
        "user_id": user_id
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    # In modern PyJWT, jwt.encode returns a string
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token

def decode_auth_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except Exception as e:
        current_app.logger.debug("decode_auth_token error: %s", e)
        return None

def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth:
            return jsonify({"message":"Authorization header missing"}), 401
        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({"message":"Invalid authorization header"}), 401
        token = parts[1]
        payload = decode_auth_token(token)
        if not payload or 'user_id' not in payload:
            return jsonify({"message":"Invalid or expired token"}), 401
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({"message":"User not found"}), 401
        # pass current_user as first arg to route
        return f(user, *args, **kwargs)
    return wrapper
