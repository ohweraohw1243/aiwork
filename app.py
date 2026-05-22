import os
import json
import random
import re
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_key_for_session")

db_url = (os.environ.get("DATABASE_URL") or "sqlite:///salon.db").strip()
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==== МОДЕЛИ БД ====
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(80), nullable=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    service_name = db.Column(db.String(120), nullable=False)
    master = db.Column(db.String(50), nullable=False)

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    service_name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Integer, nullable=False)

# ==== БАЗА УСЛУГ ====
SERVICES_LIST = [
    {"id": "manicure", "name": "💅 Маникюр с покрытием", "price": 1800, "category": "Ногти", "duration": "1.5 ч", "description": "Комбинированный маникюр с выравниванием и стойким покрытием гель-лаком.", "ai_info": "Идеально подходит для ухоженного вида на несколько недель."},
    {"id": "pedicure", "name": "🦶 Педикюр", "price": 2500, "category": "Ногти", "duration": "1.5 ч", "description": "Аппаратный или комбинированный педикюр.", "ai_info": "Важно для здоровья и эстетики ваших ног."},
    {"id": "haircut-f", "name": "💇‍♀️ Стрижка женская", "price": 3000, "category": "Волосы", "duration": "1 ч", "description": "Стильная стрижка с подбором формы.", "ai_info": "Поможет освежить образ и избавиться от секущихся кончиков."},
    {"id": "haircut-m", "name": "✂️ Стрижка мужская", "price": 1500, "category": "Волосы", "duration": "45 мин", "description": "Классическая или модельная мужская стрижка.", "ai_info": "Поддерживает аккуратный и деловой вид."},
    {"id": "coloring", "name": "🎨 Окрашивание (сложное)", "price": 6500, "category": "Волосы", "duration": "3-4 ч", "description": "Омбре, шатуш, балаяж или мелирование.", "ai_info": "Визуально добавит волосам объем и переливы цвета."},
    {"id": "hair-spa", "name": "💆‍♀️ SPA-уход для волос", "price": 3500, "category": "Волосы", "duration": "1 ч", "description": "Глубокое восстановление и питание волос.", "ai_info": "Вернет волосам блеск, мягкость и силу."},
    {"id": "face-massage", "name": "🧖‍♀️ Массаж лица", "price": 2000, "category": "Лицо", "duration": "45 мин", "description": "Скульптурный массаж для тонуса кожи.", "ai_info": "Отлично снимает отеки и улучшает цвет лица."},
    {"id": "brows", "name": "✨ Коррекция и окрашивание бровей", "price": 1500, "category": "Лицо", "duration": "45 мин", "description": "Архитектура бровей хной или краской.", "ai_info": "Сделает взгляд более выразительным."},
    {"id": "lashes", "name": "🌟 Ламинирование ресниц", "price": 2200, "category": "Лицо", "duration": "1 ч", "description": "Подкручивание, окрашивание и питание ресниц.", "ai_info": "Визуально удлиняет ресницы без наращивания."},
    {"id": "makeup", "name": "💄 Вечерний макияж", "price": 3500, "category": "Макияж", "duration": "1.5 ч", "description": "Стойкий макияж для особых случаев.", "ai_info": "Поможет стать звездой на любом мероприятии."},
    {"id": "epilation", "name": "🧴 Шугаринг/Эпиляция", "price": 1800, "category": "Тело", "duration": "30-60 мин", "description": "Бережное удаление нежелательных волос.", "ai_info": "Обеспечит гладкость кожи на длительное время."}
]

def build_services_catalog():
    return "\n".join([
        f"- {s['id']}: {s['name']} ({s['category']}, {s['duration']}, {s['price']} ₽)"
        for s in SERVICES_LIST
    ])

def match_service_from_text(text):
    if not text:
        return None
    lowered = text.lower()
    for s in SERVICES_LIST:
        name_no_emoji = s['name'].split(" ", 1)[-1].lower()
        if s['id'].lower() in lowered or s['name'].lower() in lowered or name_no_emoji in lowered:
            return s
    return None

def extract_json_block(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{.*?\}", text, flags=re.DOTALL)
    return match.group(0) if match else None

def get_base_data():
    """Хелпер, чтобы во все шаблоны передавался необходимый минимум (data)."""
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            return {"name": user.name, "services_list": SERVICES_LIST}
    return {"name": "Гость", "services_list": SERVICES_LIST}

# Инициализация БД
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email="test@test.ru").first():
        test_user = User(email="test@test.ru", password="123", name="Александра")
        db.session.add(test_user)
        db.session.commit()
        db.session.add(History(user_id=test_user.id, date="2026-04-05", service_name="🎨 Окрашивание (сложное)", price=6500))
        db.session.add(History(user_id=test_user.id, date="2026-03-12", service_name="💅 Маникюр с покрытием", price=1800))
        db.session.add(Appointment(user_id=test_user.id, date="2026-05-10 14:00", service_name="💅 Маникюр с покрытием", master="Елена"))
        db.session.commit()

# ==== РОУТЫ ====

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next')
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        next_url = request.form.get('next')
        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            session['user_id'] = user.id
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('cabinet'))
        return render_template('login.html', error="Неверный email или пароль", next_url=next_url)
    return render_template('login.html', next_url=next_url)

@app.route('/register', methods=['GET', 'POST'])
def register():
    next_url = request.args.get('next')
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        next_url = request.form.get('next')
        
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error="Пользователь с таким email уже существует", next_url=next_url)
        
        new_user = User(email=email, password=password, name=name)
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('cabinet'))
    return render_template('register.html', next_url=next_url)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route('/smart-booking')
def smart_booking():
    is_authenticated = 'user_id' in session
    booking_url = '/booking' if is_authenticated else url_for('login', next='/booking')
    
    display_data = get_base_data()
    return render_template('smart_booking.html', is_authenticated=is_authenticated, booking_url=booking_url, data=display_data)

@app.route('/cabinet')
def cabinet():
    if 'user_id' not in session:
        return redirect(url_for('login', next=request.path))
        
    user = db.session.get(User, session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    appts = Appointment.query.filter_by(user_id=user.id).order_by(Appointment.date).all()
    history = History.query.filter_by(user_id=user.id).order_by(History.date.desc()).all()
    
    display_data = get_base_data()
    display_data["active_appointments"] = [{"date": a.date, "service": a.service_name, "master": a.master} for a in appts]
    display_data["history"] = [{"date": h.date, "service": h.service_name, "price": h.price} for h in history]
    
    return render_template('cabinet.html', data=display_data)

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if 'user_id' not in session:
        return redirect(url_for('login', next=request.path))
        
    user = db.session.get(User, session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    masters_list = ["Елена", "Олег", "Ирина", "Анна"]
    message = None
    
    if request.method == 'POST':
        service = request.form.get('service')
        master = request.form.get('master')
        dt = request.form.get('datetime')
        if service and master and dt:
            dt_str = dt.replace("T", " ")
            appt = Appointment(user_id=user.id, date=dt_str, service_name=service, master=master)
            db.session.add(appt)
            db.session.commit()
            message = "Запись успешно оформлена!"
            
    display_data = get_base_data()
    display_data["masters"] = masters_list
    
    selected_service = request.args.get('service')
    return render_template('booking.html', data=display_data, message=message, selected_service=selected_service)

@app.route('/services')
def services_page():
    display_data = get_base_data()
    return render_template('services.html', data=display_data)

@app.route('/services/<service_id>')
def service_detail(service_id):
    display_data = get_base_data()
    service_info = next((s for s in SERVICES_LIST if s["id"] == service_id), None)
    if not service_info:
        return redirect(url_for('services_page'))
    display_data['service'] = service_info
    return render_template('service_detail.html', data=display_data, service=service_info)

@app.route('/qa')
def qa_page():
    display_data = get_base_data()
    return render_template('qa.html', data=display_data)

# ==== API ЭНДПОИНТЫ ====

@app.route('/api/cancel-appointment', methods=['POST'])
def cancel_appointment():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json or {}
    date_to_cancel = data.get('date')
    
    appt = Appointment.query.filter_by(user_id=session['user_id'], date=date_to_cancel).first()
    if appt:
        db.session.delete(appt)
        db.session.commit()
        return jsonify({"success": True})
            
    return jsonify({"error": "Запись не найдена"}), 404

@app.route('/api/smart-booking', methods=['POST'])
def api_smart_booking():
    data = request.json or {}
    history = data.get('history', [])
    
    if not history:
        return jsonify({"reply": "Опишите ваш запрос, и я помогу вам."})
        
    system_role = (
        "Ты AI-ассистент салона красоты 'Стиль и Грация'. Твоя цель - помочь клиенту выбрать услугу. "
        "Отвечай кратко и приветливо (1-3 предложения). "
        "Ты ОБЯЗАН выбирать только услуги из списка ниже, любые другие услуги запрещены. "
        "Ответ возвращай ТОЛЬКО в формате JSON: {\"reply\": \"...\", \"service_id\": \"id или null\"}. "
        "Список услуг:\n" + build_services_catalog()
    )
    
    messages = [{"role": "system", "content": system_role}]
    for msg in history:
        messages.append({"role": msg['role'], "content": msg['content']})
        
    if not GROQ_API_KEY:
        # Мок, если не указан API-ключ
        last_msg = history[-1]['content'].lower()
        if "ногти" in last_msg or "маникюр" in last_msg:
            return jsonify({
                "reply": "Рекомендую наш фирменный маникюр с покрытием! Займет около 1.5 часов.",
                "service_suggestion": "💅 Маникюр с покрытием",
                "service_id": "manicure"
            })
        return jsonify({"reply": "Замечательно. Может, хотите обновить стрижку или сделать уход за лицом?"})
        
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": messages,
            "temperature": 0.7
        }
        
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        
        raw_reply = response.json()["choices"][0]["message"]["content"]
        reply_text = raw_reply
        suggested = None

        json_block = extract_json_block(raw_reply)
        if json_block:
            try:
                parsed = json.loads(json_block)
                reply_text = parsed.get("reply") or reply_text
                service_id = parsed.get("service_id")
                if service_id:
                    suggested = next((s for s in SERVICES_LIST if s["id"] == service_id), None)
            except json.JSONDecodeError:
                pass

        if not suggested:
            suggested = match_service_from_text(reply_text)

        resp_data = {"reply": reply_text}
        if suggested:
            resp_data["service_suggestion"] = suggested["name"]
            resp_data["service_id"] = suggested["id"]

        return jsonify(resp_data)
    except Exception as e:
        print("GROQ API ERROR:", str(e))
        return jsonify({"reply": "Извините, сейчас я не могу ответить. Попробуйте позже."})

@app.route('/api/qa', methods=['POST'])
def api_qa():
    data = request.json or {}
    question = data.get('question', '')
    
    if not question:
        return jsonify({"error": "Пустой вопрос"}), 400
        
    system_role = (
        "Ты AI-ассистент салона красоты «Стиль и Грация». "
        "Ты отвечаешь ТОЛЬКО на вопросы, связанные с салоном красоты: услуги, цены, запись, уход за собой, мастера, акции. "
        "На любые другие темы ты вежливо отказываешься отвечать. Отвечай кратко."
    )
    prompt = f"Вопрос клиента: {question}"
    
    if not GROQ_API_KEY:
        return jsonify({"answer": "Для генерации ответа нужен GROQ_API_KEY, но мы всегда рады помочь вам."})
        
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.1-8b-instant", 
            "messages": [
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        
        reply_data = response.json()
        result = reply_data["choices"][0]["message"]["content"]
        return jsonify({"answer": result})
    except Exception as e:
        print("GROQ API ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai-offer', methods=['POST'])
def api_ai_offer():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({"error": "User not found"}), 401

    history_items = History.query.filter_by(user_id=user.id).all()
    
    if len(history_items) == 0:
        history_str = "Новый клиент, пока нет истории визитов."
    else:
        history_str = ", ".join([f"{item.service_name} ({item.date})" for item in history_items])
    
    prompt = f"""
    Твоя роль - вежливый AI-консультант и маркетолог салона красоты "Стиль и Грация".
    Разработай уникальное выгодное предложение на 1 услугу для нашего клиента по имени {user.name}.
    История визитов клиента: {history_str}.

    ОБЯЗАТЕЛЬНО выбери услугу только из списка ниже. Любые другие услуги запрещены.
    Список услуг:\n{build_services_catalog()}.

    Ответ возвращай ТОЛЬКО в формате JSON:
    {{"offer": "...", "service_id": "id"}}
    """

    if not GROQ_API_KEY:
        return jsonify({"offer": f"{user.name}, как насчет освежить образ? Попробуйте наш SPA-уход для волос!"})

    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama-3.1-8b-instant", 
            "messages": [
                {"role": "system", "content": "Ты AI-ассистент салона красоты. Соблюдай формат JSON и используй только услуги из списка."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        
        reply_data = response.json()
        raw_offer = reply_data["choices"][0]["message"]["content"]
        offer_text = raw_offer
        suggested = None

        json_block = extract_json_block(raw_offer)
        if json_block:
            try:
                parsed = json.loads(json_block)
                offer_text = parsed.get("offer") or offer_text
                service_id = parsed.get("service_id")
                if service_id:
                    suggested = next((s for s in SERVICES_LIST if s["id"] == service_id), None)
            except json.JSONDecodeError:
                pass

        if not suggested:
            suggested = match_service_from_text(offer_text)

        if not suggested:
            suggested = random.choice(SERVICES_LIST)
            offer_text = (
                f"{user.name}, рекомендую {suggested['name']} — это отличный вариант, чтобы усилить эффект ваших предыдущих визитов. "
                "Запишем для вас удобное время?"
            )

        return jsonify({"offer": offer_text, "service_id": suggested["id"], "service_name": suggested["name"]})
    except Exception as e:
        print("GROQ API ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)