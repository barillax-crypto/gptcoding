import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime, timedelta

# Вставьте ваш токен от BotFather
TOKEN = "7662974159:AAHlvoRjIXGeyPdNiE_IJB3LeMvzLJHUHDE"
bot = telebot.TeleBot(TOKEN)

# Путь к базе данных
DB_PATH = "/financial_helper.db"

# Словарь для хранения промежуточных данных пользователей
user_data = {}

# Словарь для хранения сессий пользователей
user_sessions = {}

# Функция для создания таблиц в базе данных, если они не существуют
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE,
            password TEXT,
            token_expiry TIMESTAMP
        )
    ''')
    # Таблица реквизитов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            value TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

# Создание базы данных при запуске
init_db()

# Функция для проверки авторизации пользователя
def is_authorized(chat_id):
    session = user_sessions.get(chat_id)
    if session:
        token_expiry = session.get('token_expiry')
        if token_expiry and datetime.now() < token_expiry:
            return True
    return False

# Функция для получения user_id из сессии
def get_user_id(chat_id):
    session = user_sessions.get(chat_id)
    if session:
        token_expiry = session.get('token_expiry')
        if token_expiry and datetime.now() < token_expiry:
            return session['user_id']
    return None

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if is_authorized(message.chat.id):
        send_main_menu(message.chat.id)
    else:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Регистрация", callback_data="register"))
        markup.add(InlineKeyboardButton("Авторизация", callback_data="login"))
        bot.send_message(message.chat.id, "Добро пожаловать! Пожалуйста, зарегистрируйтесь или авторизуйтесь.", reply_markup=markup)

# Функция для отправки главного меню
def send_main_menu(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Выставить счёт", callback_data="issue_invoice"))
    markup.add(InlineKeyboardButton("Реквизиты", callback_data="requisites"))
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)

# Функция для отправки меню с реквизитами
def send_requisites_menu(chat_id):
    user_id = get_user_id(chat_id)
    if not user_id:
        bot.send_message(chat_id, "Вы не авторизованы. Пожалуйста, авторизуйтесь.")
        send_welcome(chat_id)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получение реквизитов для пользователя
    cursor.execute("SELECT id, name FROM requisites WHERE user_id=?", (user_id,))
    requisites = cursor.fetchall()
    conn.close()

    markup = InlineKeyboardMarkup()
    if requisites:
        for req_id, name in requisites:
            markup.add(InlineKeyboardButton(name, callback_data=f"view_{req_id}"))
    markup.add(InlineKeyboardButton("Добавить реквизит", callback_data="add_requisite"))
    markup.add(InlineKeyboardButton("Назад", callback_data="back_to_main"))
    bot.send_message(chat_id, "Ваши реквизиты:", reply_markup=markup)

# Обработка инлайн кнопок для просмотра реквизита
@bot.callback_query_handler(func=lambda call: call.data.startswith("view_"))
def view_requisite(call):
    req_id = int(call.data.split('_')[1])
    user_id = get_user_id(call.message.chat.id)
    if not user_id:
        bot.send_message(call.message.chat.id, "Вы не авторизованы. Пожалуйста, авторизуйтесь.")
        send_welcome(call.message)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получение реквизита для пользователя
    cursor.execute("SELECT name, value FROM requisites WHERE id=? AND user_id=?", (req_id, user_id))
    requisite = cursor.fetchone()
    conn.close()

    if requisite:
        name, value = requisite
        response = f"**{name}**\n{value}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Удалить реквизит", callback_data=f"delete_{req_id}"))
        markup.add(InlineKeyboardButton("Назад", callback_data="back_to_requisites"))
        bot.send_message(call.message.chat.id, response, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(call.message.chat.id, "Реквизит не найден.")

# Обработка инлайн кнопок для удаления реквизита
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_requisite(call):
    req_id = int(call.data.split('_')[1])
    user_id = get_user_id(call.message.chat.id)
    if not user_id:
        bot.send_message(call.message.chat.id, "Вы не авторизованы. Пожалуйста, авторизуйтесь.")
        send_welcome(call.message)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Удаление реквизита
    cursor.execute("DELETE FROM requisites WHERE id=? AND user_id=?", (req_id, user_id))
    if cursor.rowcount > 0:
        bot.send_message(call.message.chat.id, "Реквизит успешно удален.")
    else:
        bot.send_message(call.message.chat.id, "Реквизит не найден.")
    conn.commit()
    conn.close()

    # Вернуться к списку реквизитов после удаления
    send_requisites_menu(call.message.chat.id)

# Обработка инлайн кнопок для добавления реквизита
@bot.callback_query_handler(func=lambda call: call.data == "add_requisite")
def add_requisite(call):
    msg = bot.send_message(call.message.chat.id, "Введите название реквизита:")
    bot.register_next_step_handler(msg, process_add_requisite_name)

def process_add_requisite_name(message):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "Название не может быть пустым. Пожалуйста, попробуйте снова.")
        return

    if message.chat.id not in user_data:
        user_data[message.chat.id] = {}

    user_data[message.chat.id]['add_requisite'] = {'name': name}
    msg = bot.send_message(message.chat.id, "Введите значение реквизита:")
    bot.register_next_step_handler(msg, process_add_requisite_value)

def process_add_requisite_value(message):
    value = message.text.strip()
    if not value:
        bot.send_message(message.chat.id, "Значение не может быть пустым. Пожалуйста, попробуйте снова.")
        return

    user_id = get_user_id(message.chat.id)
    if not user_id:
        bot.send_message(message.chat.id, "Вы не авторизованы. Пожалуйста, авторизуйтесь.")
        send_welcome(message)
        return

    name = user_data.get(message.chat.id, {}).get('add_requisite', {}).get('name')
    if not name:
        bot.send_message(message.chat.id, "Что-то пошло не так. Попробуйте снова.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Добавление реквизита в базу данных
    cursor.execute("INSERT INTO requisites (user_id, name, value) VALUES (?, ?, ?)",
                   (user_id, name, value))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "Реквизит успешно добавлен.")

    # Очистка данных
    user_data[message.chat.id].pop('add_requisite', None)
    send_requisites_menu(message.chat.id)

# Обработка инлайн кнопок для выхода из аккаунта
@bot.callback_query_handler(func=lambda call: call.data == "logout")
def logout_user(call):
    user_id = get_user_id(call.message.chat.id)
    if user_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Удаление токена авторизации пользователя
        cursor.execute("UPDATE users SET token_expiry=NULL WHERE id=?", (user_id,))
        conn.commit()
        conn.close()

        # Удаление сессии пользователя
        del user_sessions[call.message.chat.id]

        bot.send_message(call.message.chat.id, "Вы успешно вышли из системы. Для повторного доступа авторизуйтесь снова.")
        send_welcome(call.message)
    else:
        bot.send_message(call.message.chat.id, "Вы не авторизованы.")

# Обработка инлайн кнопок для навигации "Назад"
@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main(call):
    send_main_menu(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_requisites")
def back_to_requisites(call):
    send_requisites_menu(call.message.chat.id)

# Обработка инлайн кнопок для регистрации и авторизации
@bot.callback_query_handler(func=lambda call: call.data == "register")
def register_user(call):
    msg = bot.send_message(call.message.chat.id, "Введите логин для регистрации:")
    bot.register_next_step_handler(msg, process_registration_login)

def process_registration_login(message):
    login = message.text.strip()
    if not login:
        bot.send_message(message.chat.id, "Логин не может быть пустым. Пожалуйста, попробуйте снова.")
        return

    if message.chat.id not in user_data:
        user_data[message.chat.id] = {}

    user_data[message.chat.id]['registration'] = {'login': login}
    msg = bot.send_message(message.chat.id, "Введите пароль для регистрации:")
    bot.register_next_step_handler(msg, process_registration_password)

def process_registration_password(message):
    password = message.text.strip()
    if not password:
        bot.send_message(message.chat.id, "Пароль не может быть пустым. Пожалуйста, попробуйте снова.")
        return
    login = user_data.get(message.chat.id, {}).get('registration', {}).get('login')
    if not login:
        bot.send_message(message.chat.id, "Что-то пошло не так. Попробуйте начать заново.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Проверка, существует ли уже пользователь с таким логином
    cursor.execute("SELECT * FROM users WHERE login=?", (login,))
    if cursor.fetchone() is not None:
        bot.send_message(message.chat.id, "Пользователь с таким логином уже существует.")
    else:
        # Добавление нового пользователя
        cursor.execute("INSERT INTO users (login, password) VALUES (?, ?)",
                       (login, password))
        conn.commit()
        bot.send_message(message.chat.id, "Регистрация успешна. Теперь вы можете авторизоваться.")
    conn.close()

    # Очистка данных
    user_data[message.chat.id].pop('registration', None)

@bot.callback_query_handler(func=lambda call: call.data == "login")
def login_user(call):
    msg = bot.send_message(call.message.chat.id, "Введите логин для авторизации:")
    bot.register_next_step_handler(msg, process_login_login)

def process_login_login(message):
    login = message.text.strip()
    if not login:
        bot.send_message(message.chat.id, "Логин не может быть пустым. Пожалуйста, попробуйте снова.")
        return

    if message.chat.id not in user_data:
        user_data[message.chat.id] = {}

    user_data[message.chat.id]['login'] = {'login': login}
    msg = bot.send_message(message.chat.id, "Введите пароль для авторизации:")
    bot.register_next_step_handler(msg, process_login_password)

def process_login_password(message):
    password = message.text.strip()
    if not password:
        bot.send_message(message.chat.id, "Пароль не может быть пустым. Пожалуйста, попробуйте снова.")
        return
    login = user_data.get(message.chat.id, {}).get('login', {}).get('login')
    if not login:
        bot.send_message(message.chat.id, "Что-то пошло не так. Попробуйте начать заново.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Проверка логина и пароля
    cursor.execute("SELECT id FROM users WHERE login=? AND password=?", (login, password))
    user = cursor.fetchone()
    if user:
        user_id = user[0]
        # Обновление токена авторизации на 24 часа
        token_expiry = datetime.now() + timedelta(hours=24)
        cursor.execute("UPDATE users SET token_expiry=? WHERE id=?", (token_expiry.isoformat(), user_id))
        conn.commit()

        # Сохранение сессии пользователя
        user_sessions[message.chat.id] = {
            'user_id': user_id,
            'token_expiry': token_expiry
        }

        bot.send_message(message.chat.id, "Авторизация успешна. Доступ активен на 24 часа.")
        send_main_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "Неверный логин или пароль.")
    conn.close()

    # Очистка данных
    user_data[message.chat.id].pop('login', None)

# Обработка выбора в главном меню
@bot.callback_query_handler(func=lambda call: call.data == "issue_invoice")
def issue_invoice(call):
    msg = bot.send_message(call.message.chat.id, "Введите валюту:")
    bot.register_next_step_handler(msg, process_invoice_currency)

@bot.callback_query_handler(func=lambda call: call.data == "requisites")
def show_requisites(call):
    send_requisites_menu(call.message.chat.id)

def process_invoice_currency(message):
    currency = message.text.strip()
    if not currency:
        bot.send_message(message.chat.id, "Валюта не может быть пустой. Пожалуйста, попробуйте снова.")
        return

    if message.chat.id not in user_data:
        user_data[message.chat.id] = {}

    user_data[message.chat.id]['invoice'] = {'currency': currency}
    msg = bot.send_message(message.chat.id, "Введите сумму:")
    bot.register_next_step_handler(msg, process_invoice_amount)

def process_invoice_amount(message):
    amount = message.text.strip()
    if not amount:
        bot.send_message(message.chat.id, "Сумма не может быть пустой. Пожалуйста, попробуйте снова.")
        return

    if message.chat.id not in user_data or 'invoice' not in user_data[message.chat.id]:
        bot.send_message(message.chat.id, "Что-то пошло не так. Пожалуйста, начните сначала.")
        send_main_menu(message.chat.id)
        return

    user_data[message.chat.id]['invoice']['amount'] = amount

    user_id = get_user_id(message.chat.id)
    if not user_id:
        bot.send_message(message.chat.id, "Вы не авторизованы. Пожалуйста, авторизуйтесь.")
        send_welcome(message)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получение реквизитов для пользователя
    cursor.execute("SELECT id, name FROM requisites WHERE user_id=?", (user_id,))
    requisites = cursor.fetchall()
    conn.close()

    if not requisites:
        bot.send_message(message.chat.id, "У вас нет сохраненных реквизитов. Пожалуйста, добавьте реквизиты.")
        send_requisites_menu(message.chat.id)
        return

    markup = InlineKeyboardMarkup()
    for req_id, name in requisites:
        markup.add(InlineKeyboardButton(name, callback_data=f"select_requisite_{req_id}"))
    markup.add(InlineKeyboardButton("Отмена", callback_data="back_to_main"))
    bot.send_message(message.chat.id, "Выберите реквизит для счёта:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_requisite_"))
def select_requisite_for_invoice(call):
    req_id = int(call.data.split('_')[-1])
    user_id = get_user_id(call.message.chat.id)
    if not user_id:
        bot.send_message(call.message.chat.id, "Вы не авторизованы. Пожалуйста, авторизуйтесь.")
        send_welcome(call.message)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, value FROM requisites WHERE id=? AND user_id=?", (req_id, user_id))
    requisite = cursor.fetchone()
    conn.close()

    if not requisite:
        bot.send_message(call.message.chat.id, "Реквизит не найден.")
        return

    invoice_data = user_data.get(call.message.chat.id, {}).get('invoice')
    if not invoice_data:
        bot.send_message(call.message.chat.id, "Что-то пошло не так. Пожалуйста, начните сначала.")
        send_main_menu(call.message.chat.id)
        return

    currency = invoice_data.get('currency')
    amount = invoice_data.get('amount')

    if not currency or not amount:
        bot.send_message(call.message.chat.id, "Что-то пошло не так. Пожалуйста, начните сначала.")
        send_main_menu(call.message.chat.id)
        return

    name, value = requisite
    invoice_message = f"Выставлен счёт:\n\nСумма: {amount} {currency}\nРеквизиты:\n{name}\n{value}"

    bot.send_message(call.message.chat.id, invoice_message)

    # Очистка данных
    user_data[call.message.chat.id].pop('invoice', None)

    # Предложение вернуться в главное меню
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Назад в меню", callback_data="back_to_main"))
    bot.send_message(call.message.chat.id, "Что вы хотите сделать дальше?", reply_markup=markup)

# Запуск бота
bot.polling()
