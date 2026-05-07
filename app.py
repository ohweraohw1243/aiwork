import os
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set")

app = Flask(__name__)
app.secret_key = "super_secret_key_for_session"

# Конфигурация БД: если есть DATABASE_URL (для Render/Railway), берем ее. 
# Иначе создаем локальный SQLite-файл "salon.db"
db_url = os.environ.get("DATABASE_URL", "sqlite:///salon.db")
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

class AvailableSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(50), nullable=False)
    master = db.Column(db.String(50), nullable=False)
    avatar = db.Column(db.String(250), nullable=False)

# Статический список услуг
SERVICES_LIST = [
    {"name": "💅 Маникюр с покрытием", "price": 1800},
    {"name": "🦶 Педикюр", "price": 2500},
    {"name": "💇‍♀️ Стрижка женская", "price": 3000},
    {"name": "✂️ Стрижка мужская", "price": 1500},
    {"name": "🎨 Окрашивание (сложное)", "price": 6500},
    {"name": "💆‍♀️ SPA-уход для волос", "price": 3500},
    {"name": "🧖‍♀️ Массаж лица", "price": 2000},
    {"name": "✨ Коррекция и окрашивание бровей", "price": 1500},
    {"name": "🌟 Ламинирование ресниц", "price": 2200},
    {"name": "💄 Вечерний макияж", "price": 3500},
    {"name": "🧴 Шугаринг/Эпиляция", "price": 1800}
]

# Инициализация БД и стартовых данных
with app.app_context():
    db.create_all()
    
    # Если слоты пусты, заполняем базу
    if not AvailableSlot.query.first():
        db.session.add(AvailableSlot(date="2026-05-08 12:00", master="Елена", avatar="https://ui-avatars.com/api/?name=Елена&background=fdf4ff&color=4f46e5"))
        db.session.add(AvailableSlot(date="2026-05-09 10:00", master="Олег", avatar="https://ui-avatars.com/api/?name=Олег&background=f0f9ff&color=c026d3"))
        db.session.add(AvailableSlot(date="2026-05-11 16:00", master="Ирина", avatar="https://ui-avatars.com/api/?name=Ирина&background=fff1f2&color=db2777"))
        db.session.add(AvailableSlot(date="2026-05-12 18:30", master="Елена", avatar="https://ui-avatars.com/api/?name=Елена&background=fdf4ff&color=4f46e5"))
        db.session.add(AvailableSlot(date="2026-05-14 14:00", master="Анна", avatar="https://ui-avatars.com/api/?name=Анна&background=fef2f2&color=e11d48"))
        
    # Добавляем тестового юзера, если его нет
    if not User.query.filter_by(email="test@test.ru").first():
        test_user = User(email="test@test.ru", password="123", name="Александра")
        db.session.add(test_user)
        db.session.commit() # коммитим, чтобы получить id
        
        # Добавляем историю
        db.session.add(History(user_id=test_user.id, date="2026-04-05", service_name="🎨 Окрашивание (сложное)", price=6500))
        db.session.add(History(user_id=test_user.id, date="2026-03-12", service_name="💅 Маникюр с покрытием", price=1800))
        db.session.add(History(user_id=test_user.id, date="2026-02-20", service_name="✨ Коррекция и окрашивание бровей", price=1500))
        
        # Добавляем актуальные записи
        db.session.add(Appointment(user_id=test_user.id, date="2026-05-10 14:00", service_name="💅 Маникюр с покрытием", master="Елена"))
        db.session.add(Appointment(user_id=test_user.id, date="2026-05-15 18:00", service_name="💇‍♀️ Стрижка женская", master="Олег"))
        
    db.session.commit()

# ==== РОУТЫ ====

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            session['user_id'] = user.id
            return redirect(url_for('index'))
        return render_template('login.html', error="Неверный email или пароль")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error="Пользователь с таким email уже существует")
        
        new_user = User(email=email, password=password, name=name)
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/cancel', methods=['POST'])
def cancel_appointment():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    date_to_cancel = data.get('date')
    
    appt = Appointment.query.filter_by(user_id=session['user_id'], date=date_to_cancel).first()
    if appt:
        # Возвращаем это время как свободное окно
        slot = AvailableSlot(
            date=date_to_cancel, 
            master=appt.master, 
            avatar=f"https://ui-avatars.com/api/?name={appt.master}&background=random"
        )
        db.session.add(slot)
        db.session.delete(appt)
        db.session.commit()
        return jsonify({"success": True})
            
    return jsonify({"error": "Запись не найдена"}), 404

@app.route('/api/book', methods=['POST'])
def book_appointment():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    date_to_book = data.get('date')
    
    slot = AvailableSlot.query.filter_by(date=date_to_book).first()
    if slot:
        appt = Appointment(
            user_id=session['user_id'], 
            date=date_to_book, 
            service_name="🎉 Желаемая услуга (выбрана из окна)", 
            master=slot.master
        )
        db.session.add(appt)
        db.session.delete(slot)
        db.session.commit()
        return jsonify({"success": True})
            
    return jsonify({"error": "Окно не найдено"}), 404

@app.route('/api/add_history', methods=['POST'])
def add_history():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    service_name = request.form.get('service')
    price = 0
    for s in SERVICES_LIST:
        if s['name'] == service_name:
            price = s['price']
            break
            
    if price:
        hist = History(
            user_id=session['user_id'],
            date=datetime.now().strftime("%Y-%m-%d"), 
            service_name=service_name, 
            price=price
        )
        db.session.add(hist)
        db.session.commit()
        
    return redirect(url_for('index'))

# Главная страница (Профиль)
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    appts = Appointment.query.filter_by(user_id=user.id).order_by(Appointment.date).all()
    history = History.query.filter_by(user_id=user.id).order_by(History.date.desc()).all()
    
    display_data = {
        "name": user.name,
        "active_appointments": [{"date": a.date, "service": a.service_name, "master": a.master} for a in appts],
        "history": [{"date": h.date, "service": h.service_name, "price": h.price} for h in history],
        "services_list": SERVICES_LIST
    }
    
    return render_template('dashboard.html', data=display_data)

# Страница онлайн-записи
@app.route('/booking')
def booking():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    slots = AvailableSlot.query.order_by(AvailableSlot.date).all()
    
    display_data = {
        "name": user.name,
        "available_slots": [{"date": s.date, "master": s.master, "avatar": s.avatar} for s in slots]
    }
    
    return render_template('booking.html', data=display_data)

@app.route('/services')
def services_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    
    display_data = {
        "name": user.name if user else "Гость",
        "services_list": SERVICES_LIST
    }
    return render_template('services.html', data=display_data)

@app.route('/service/<path:service_name>')
def service_detail(service_name):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    
    # Ищем услугу в списке
    service_info = next((s for s in SERVICES_LIST if s["name"] == service_name), None)
    if not service_info:
        return redirect(url_for('services_page'))
        
    display_data = {
        "name": user.name if user else "Гость",
        "service": service_info
    }
    return render_template('service_detail.html', data=display_data)

@app.route('/qa')
def qa_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    
    display_data = {
        "name": user.name if user else "Гость"
    }
    return render_template('qa.html', data=display_data)

@app.route('/api/ask_question', methods=['POST'])
def ask_question():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    question = data.get('question', '')
    
    prompt = f"""
    Твоя роль - вежливый AI-консультант салона красоты "Стиль и Грация".
    Клиент задает вопрос: "{question}"
    
    Ответь вежливо, профессионально и подробно, но не слишком длинно.
    """
    return call_groq_api(prompt, system_role="Ты AI-ассистент салона. Отвечай дружелюбно.")

@app.route('/api/service_info', methods=['POST'])
def get_service_info():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    service_name = data.get('service_name', '')
    
    prompt = f"""
    Твоя роль - эксперт-косметолог и мастер салона красоты "Стиль и Грация".
    Расскажи подробно и привлекательно об услуге "{service_name}". 
    Зачем она нужна клиентам, какой будет эффект и почему клиенту стоит записаться прямо сейчас?
    Разбей на 2-3 небольших абзаца и добавь немного эмодзи.
    """
    return call_groq_api(prompt, system_role="Ты эксперт салона красоты. Отвечай увлекательно и профессионально.")

def call_groq_api(prompt, system_role="Ты AI-ассистент."):
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
        
        data = response.json()
        result = data["choices"][0]["message"]["content"]
        return jsonify({"answer": result})
    except Exception as e:
        print("GROQ API ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate_offer', methods=['POST'])
def generate_offer():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
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
    
    Основываясь на истории клиента, предложи услугу, которая идеально дополнит этот опыт. 
    Если истории нет - предложи популярную классику (например, легкий маникюр или уход) как новому клиенту.
    Напиши предложение в 2-3 доброжелательных предложениях. Обращайся к клиенту по имени, не используй приветствие (сразу к сути).
    Сделай так, чтобы захотелось сразу записаться!
    """

    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama-3.1-8b-instant", 
            "messages": [
                {
                    "role": "system",
                    "content": "Ты услужливый AI-ассистент салона красоты. Отвечай кратко, красиво и профессионально. Не пиши лишних рассуждений."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.7
        }
        
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        offer = data["choices"][0]["message"]["content"]
        return jsonify({"offer": offer})
    except Exception as e:
        print("GROQ API ERROR:", str(e))
        if hasattr(e, 'response') and e.response is not None:
            print("Response:", e.response.text)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Эта конфигурация подходит как для локального запуска, так и для некоторых хостингов (вроде Render)
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)