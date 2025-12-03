# app.py
import os
import re
from flask import Flask, request, jsonify, current_app, send_from_directory
from flask_cors import CORS
from datetime import datetime, timezone
import requests
from analysis import train_model, predict_risk_v2 # Depende de analysis.py
from database import db, User, GlucoseRecord, ChatMessage # Depende de database.py
from auth import create_auth_token, auth_required # Depende de auth.py
from werkzeug.security import generate_password_hash, check_password_hash

# Configurações de Padrão
LOW_GLUCOSE_THRESHOLD = float(os.environ.get('LOW_GLUCOSE_THRESHOLD', 70.0))
EMAIL_MENTION_PATTERN = re.compile(r"@[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Config
APP = Flask(__name__, static_folder='static', static_url_path='/static')
APP.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clarity_health.db'
APP.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
APP.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'uma_chave_local_secreta_aleatoria'

CORS(APP, resources={r"/api/*": {"origins": "*"}})
db.init_app(APP)

with APP.app_context():
    db.create_all()

# Telegram config
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_ENABLED = str(os.environ.get('TELEGRAM_ENABLED', '')).lower() in ('1', 'true', 'yes')

def send_telegram_message(chat_id: str, text: str):
    """Send message to Telegram chat_id using bot token if enabled"""
    if not TELEGRAM_ENABLED:
        current_app.logger.debug("Telegram disabled (TELEGRAM_ENABLED!=1). Not sending.")
        return False
    if not TELEGRAM_BOT_TOKEN:
        current_app.logger.error("Telegram enabled but TELEGRAM_BOT_TOKEN not set.")
        return False
    if not chat_id:
        current_app.logger.debug("No chat_id provided; skipping telegram send.")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": str(chat_id), "text": str(text)}
        r = requests.post(url, json=payload, timeout=10)
        current_app.logger.debug("Telegram send status: %s %s", r.status_code, r.text)
        return r.ok
    except Exception as e:
        current_app.logger.exception("Error sending Telegram message: %s", e)
        return False

def send_emergency_alert(user: User, is_critical: bool, report_info: dict = None):
    """Envia um alerta crítico para o contato de confiança e o usuário via Telegram."""
    if report_info is None:
        report_info = {'value': 'N/A', 'risk_level': 'N/A', 'message': 'Detalhes de análise indisponíveis.'}

    message = (f"[ALERTA GLICEMIA {'CRÍTICA' if is_critical else 'RÁPIDA'}] "
               f"Usuário {user.email} registrou um nível de glicemia de {report_info['value']} mg/dL. "
               f"Risco: {report_info['risk_level']}. "
               f"Mensagem da análise: {report_info['message']}")

    # 1) Enviar para o contato de confiança (se configurado)
    if user.trusted_telegram_id:
        send_telegram_message(user.trusted_telegram_id, f"🚨 ALERTA DE EMERGÊNCIA (Confiança) 🚨\n{message}")

    # 2) Enviar para o usuário (eles devem receber todas as notificações)
    if user.telegram_chat_id:
        send_telegram_message(user.telegram_chat_id, f"⚠️ ALERTA DE MONITORAMENTO ⚠️\n{message}")


# -------------------------
# Auth endpoints
# -------------------------
@APP.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'message':'Email and password required'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'message':'Email already registered'}), 409
    hashed = generate_password_hash(password)
    u = User(email=email, password_hash=hashed)
    db.session.add(u)
    db.session.commit()
    token = create_auth_token(u.id)
    return jsonify({'message':'Registered','token':token}), 201

@APP.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'message':'Email and password required'}), 400
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'message':'Invalid credentials'}), 401
    token = create_auth_token(user.id)
    return jsonify({'message':'Logged in','token':token}), 200

# -------------------------
# Endpoint to set telegram IDs for user
# POST /api/user/telegram { telegram_chat_id, trusted_telegram_id }
# -------------------------
@APP.route('/api/user/telegram', methods=['POST'])
@auth_required
def set_telegram_ids(current_user):
    data = request.get_json() or {}
    telegram_chat_id = data.get('telegram_chat_id')
    trusted_telegram_id = data.get('trusted_telegram_id')
    
    # Previne que strings vazias sejam salvas como 'None' no banco, mas mantém o tipo string
    if telegram_chat_id is not None:
        current_user.telegram_chat_id = str(telegram_chat_id) if telegram_chat_id != '' else None
    if trusted_telegram_id is not None:
        current_user.trusted_telegram_id = str(trusted_telegram_id) if trusted_telegram_id != '' else None
    db.session.commit()
    return jsonify({'message':'Saved'}), 200

# -------------------------
# Endpoint to get user profile 
# GET /api/user/me
# -------------------------
@APP.route('/api/user/me', methods=['GET'])
@auth_required
def get_my_profile(current_user):
    return jsonify({
        'email': current_user.email,
        'telegram_chat_id': current_user.telegram_chat_id,
        'trusted_telegram_id': current_user.trusted_telegram_id
    }), 200

# -------------------------
# Glucose records (create)
# POST /api/record
# -------------------------
@APP.route('/api/record', methods=['POST'])
@auth_required
def create_record(current_user):
    data = request.get_json() or {}
    raw_value = data.get('valorGlicemia') or data.get('value') or None
    try:
        value = float(raw_value)
    except Exception:
        return jsonify({'message':'Invalid or missing glicemia value'}), 400
    
    meal_time = data.get('ultimaRefeicao') or data.get('meal_time')
    exercise_time = data.get('ultimoExercicio') or data.get('exercise_time')
    symptoms = data.get('sintomas') or data.get('symptoms')
    
    r = GlucoseRecord(value=value, user_id=current_user.id, meal_time=meal_time, exercise_time=exercise_time, symptoms=symptoms)
    db.session.add(r)
    db.session.commit()

    # ------------- Notifications -------------
    # 1) Notificar o próprio usuário (via Telegram)
    user_msg = f"[Clarity Health] Novo registro de glicemia: {value} mg/dL em {r.timestamp.strftime('%Y-%m-%d %H:%M:%S')}."
    if meal_time: user_msg += f" Última refeição: {meal_time}."
    if symptoms: user_msg += f" Sintomas: {str(symptoms)[:300]}."
    if current_user.telegram_chat_id:
        send_telegram_message(current_user.telegram_chat_id, user_msg)

    # 2) Se glicemia muito baixa (alerta crítico), notificar contato de confiança/emergência
    if value <= LOW_GLUCOSE_THRESHOLD:
        report_info = {'value': value, 'risk_level': 'HIGH', 'message': f'Nível de glicemia CRITICAMENTE BAIXO: {value} mg/dL.'}
        send_emergency_alert(current_user, is_critical=True, report_info=report_info)

    return jsonify({
        'id': r.id,
        'value': r.value,
        'timestamp': r.timestamp.isoformat()
    }), 201

# -------------------------
# Glucose records (list)
# GET /api/records
# -------------------------
@APP.route('/api/records', methods=['GET'])
@auth_required
def get_records(current_user):
    # Retorna registros ordenados do mais recente para o mais antigo (para exibição em tabela)
    records = GlucoseRecord.query.filter_by(user_id=current_user.id)\
                                 .order_by(GlucoseRecord.timestamp.desc()).all()
    return jsonify([
        {
            'id': r.id,
            'value': r.value,
            'timestamp': r.timestamp.isoformat(),
            'meal_time': r.meal_time,
            'exercise_time': r.exercise_time,
            'symptoms': r.symptoms
        } for r in records
    ]), 200

# -------------------------
# Glucose analysis (Corrected)
# GET /api/analyze
# -------------------------
@APP.route('/api/analyze', methods=['GET'])
@auth_required
def analyze_glucose(current_user):
    # Buscar registros do usuário
    records = GlucoseRecord.query.filter_by(user_id=current_user.id)\
                                 .order_by(GlucoseRecord.timestamp.asc()).all()

    if not records:
        return jsonify({
            "message": "Nenhum registro encontrado.",
            "risk_level": "N/A"
        }), 200

    # Converter para formato de dicionário
    all_records = []
    for r in records:
        all_records.append({
            "value": r.value,
            "timestamp": r.timestamp.isoformat(),
            "meal_time": r.meal_time,
            "exercise_time": r.exercise_time,
            "symptoms": r.symptoms
        })

    # Analisar o risco
    # CORREÇÃO: Adicionando o segundo argumento posicional "glucose_model.pkl"
    # que a função predict_risk_v2() do analysis.py está esperando.
    try:
        analysis_result = predict_risk_v2(all_records, "glucose_model.pkl") 
    except TypeError as e:
        # Se o TypeError persistir, é porque a função no analysis.py pode estar definida
        # para esperar exatamente 2 argumentos sem valor default. 
        # Esta é a correção baseada na mensagem de erro.
        current_app.logger.error("Error calling predict_risk_v2: %s", str(e))
        return jsonify({
            "message": "Erro de análise (verificar analysis.py).",
            "risk_level": "ERROR"
        }), 500
        
    # Notificação se o risco for MEDIUM ou HIGH
    if analysis_result['risk_level'] in ['MEDIUM', 'HIGH']:
        # Alerta se houver risco de queda/subida rápida ou se já estiver em estado crítico
        is_critical = analysis_result['risk_level'] == 'HIGH'
        send_emergency_alert(current_user, is_critical=is_critical, report_info={
            'value': all_records[-1]['value'],
            'risk_level': analysis_result['risk_level'],
            'message': analysis_result['message']
        })
        
    return jsonify(analysis_result), 200

# -------------------------
# Chat messages
# -------------------------
@APP.route('/api/chat/messages', methods=['GET'])
@auth_required
def get_chat_messages(current_user):
    # Buscar as últimas 50 mensagens
    messages = ChatMessage.query.order_by(ChatMessage.timestamp.desc()).limit(50).all()
    # Inverter a ordem para mostrar o mais antigo primeiro (chat)
    messages.reverse() 
    return jsonify([
        {
            'id': m.id,
            'user_id': m.user_id,
            'username': m.username,
            'content': m.content,
            'timestamp': m.timestamp.isoformat()
        } for m in messages
    ]), 200


@APP.route('/api/chat/messages', methods=['POST'])
@auth_required
def send_chat_message(current_user):
    data = request.get_json() or {}
    content = data.get('content')
    if not content or not content.strip():
        return jsonify({'message': 'Content required'}), 400

    m = ChatMessage(user_id=current_user.id, username=current_user.email, content=content)
    db.session.add(m)
    db.session.commit()

    # Notify the author (user) via Telegram (they want to receive all notifications)
    if current_user.telegram_chat_id:
        send_telegram_message(current_user.telegram_chat_id, f"[Chat] Você enviou uma mensagem: {content[:300]}")

    # Detect mentions like @email@domain.com
    mentions = EMAIL_MENTION_PATTERN.findall(content)
    for email in mentions:
        # Remove the leading '@' for the database lookup
        user_email = email[1:]
        user = User.query.filter_by(email=user_email).first()
        if user and user.telegram_chat_id:
            # notify mentioned user
            send_telegram_message(user.telegram_chat_id, f"[Mencionado] Você foi mencionado no chat por {current_user.email}: {content[:300]}")

    return jsonify({
        'id': m.id,
        'user_id': m.user_id,
        'username': m.username,
        'content': m.content,
        'timestamp': m.timestamp.isoformat()
    }), 201

# -------------------------
# Emergency Endpoints
# -------------------------
@APP.route('/api/emergency', methods=['POST'])
@auth_required
def trigger_emergency(current_user):
    # Simula um registro crítico para acionar o alerta (o ideal seria um registro real ou um sinal específico)
    report_info = {'value': 'ALERTA MANUAL', 'risk_level': 'HIGH', 'message': 'O usuário acionou o botão de emergência manualmente.'}
    send_emergency_alert(current_user, is_critical=True, report_info=report_info)
    
    return jsonify({'message': 'Alerta de emergência acionado! Notificação enviada ao contato de confiança (se configurado).'}), 200

@APP.route('/api/chat/emergency', methods=['POST'])
@auth_required
def send_emergency_chat_message(current_user):
    data = request.get_json() or {}
    content = data.get('content')
    if not content or not content.strip():
        return jsonify({'message': 'Content required'}), 400

    # Cria a mensagem de chat (publica no chat normal, mas com indicação de emergência)
    emergency_content = f"🚨 MENSAGEM DE EMERGÊNCIA: {content.strip()[:400]}"
    m = ChatMessage(user_id=current_user.id, username=current_user.email, content=emergency_content)
    db.session.add(m)
    db.session.commit()

    # 1. Envia a mensagem de chat para o usuário (via Telegram)
    if current_user.telegram_chat_id:
        send_telegram_message(current_user.telegram_chat_id, f"[Chat Emergência] Você enviou: {emergency_content}")

    # 2. Envia um alerta mais direto para o contato de confiança
    if current_user.trusted_telegram_id:
         message_trusted = f"⚠️ ALERTA: Mensagem de emergência de {current_user.email}: {emergency_content}"
         send_telegram_message(current_user.trusted_telegram_id, message_trusted)

    return jsonify({'message': 'Mensagem de emergência enviada e notificação acionada.'}), 201


# -------------------------
# Static File Serving (Index.html and others)
# -------------------------
@APP.route('/')
def serve_index():
    """Serves index.html as default route."""
    try:
        # Tenta servir o arquivo index.html da pasta 'templates' (se existir)
        # Se não, tenta o default 'index.html' da raiz ou da pasta 'static'
        return send_from_directory('templates', 'index.html')
    except Exception:
        try:
            return APP.send_static_file('index.html')
        except Exception:
            return send_from_directory('.', 'index.html')

@APP.route('/<path:path>')
def serve_static(path):
    """Serves other static files (js, css, etc.) or HTML pages."""
    try:
        # Tenta servir o arquivo da pasta 'templates' (ex: historico.html)
        return send_from_directory('templates', path)
    except Exception:
        # Se falhar, tenta servir como um arquivo estático normal (ex: script.js, style.css)
        try:
            return APP.send_static_file(path)
        except Exception:
            # Caso não encontre, serve o arquivo da raiz do projeto, se existir
            return send_from_directory('.', path)

# -------------------------
# Run app
# -------------------------
if __name__ == '__main__':
    # Esta é a última linha de código executada.
    # Todas as rotas precisam estar definidas acima desta linha.
    APP.run(debug=True)