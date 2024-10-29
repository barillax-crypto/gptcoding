import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime, timedelta

# Вставьте ваш токен от BotFather
TOKEN = "7662974159:AAHlvoRjIXGeyPdNiE_IJB3LeMvzLJHUHDE"
bot = telebot.TeleBot(TOKEN)

# Путь к базе данных
DB_PATH = "financial_helper.db"

# Словарь для хранения промежуточных данных пользователей
user_data = {}

# Функция для создания таблиц в базе данных, если они не существуют
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            login TEXT PRIMARY KEY,
            user_id INTEGER,
            password TEXT,
            token_expiry TIMESTAMP
        )
    ''')
    # Таблица реквизитов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT,
            name TEXT,
            value TEXT,
            FOREIGN KEY (login) REFERENCES users (login)
        )
    ''')
    conn.commit()
    conn.close()

# Создание базы данных при запуске
init_db()

# Функция для проверки авторизации пользователя
def is_authorized(login):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT token_expiry FROM users WHERE login=?", (login,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        token_expiry = result[0]
        if token_expiry and datetime.now() < datetime.fromisoformat(token_expiry):
            return True
    return False

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_login = user_data.get(message.chat.id, {}).get('login')
    if user_login and is_authorized(user_login):
        send_requisites_menu(user_login, message.chat.id)
    else:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Регистрация", callback_data="register"))
        markup.add(InlineKeyboardButton("Авторизация", callback_data="login"))
        bot.send_message(message.chat.id, "Добро пожаловать! Пожалуйста, зарегистрируйтесь или авторизуйтесь.", reply_markup=markup)

# Функция для отправки меню с реквизитами
def send_requisites_menu(login, chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получение реквизитов для пользователя
    cursor.execute("SELECT id, name FROM requisites WHERE login=?", (login,))
    requisites = cursor.fetchall()
    conn.close()

    markup = InlineKeyboardMarkup()
    if requisites:
        for req_id, name in requisites:
            markup.add(InlineKeyboardButton(name, callback_data=f"view_{req_id}"))
    markup.add(InlineKeyboardButton("Добавить реквизит", callback_data="add_requisite"))
    markup.add(InlineKeyboardButton("Выход", callback_data="logout"))
    
    bot.send_message(chat_id, "Ваши реквизиты:", reply_markup=markup)

# Обработка инлайн кнопок для просмотра реквизита
@bot.callback_query_handler(func=lambda call: call.data.startswith("view_"))
def view_requisite(call):
    req_id = int(call.data.split('_')[1])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получение реквизита для пользователя
    cursor.execute("SELECT name, value FROM requisites WHERE id=?", (req_id,))
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Удаление реквизита
    cursor.execute("DELETE FROM requisites WHERE id=?", (req_id,))
    if cursor.rowcount > 0:
        bot.send_message(call.message.chat.id, "Реквизит успешно удален.")
    else:
        bot.send_message(call.message.chat.id, "Реквизит не найден.")
    conn.commit()
    conn.close()

    # Вернуться к списку реквизитов после удаления
    user_login = user_data.get(call.message.chat.id, {}).get('login')
    if user_login:
        send_requisites_menu(user_login, call.message.chat.id)

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
    user_data[message.chat.id] = {'name': name, **user_data.get(message.chat.id, {})}
    msg = bot.send_message(message.chat.id, "Введите значение реквизита:")
    bot.register_next_step_handler(msg, process_add_requisite_value)

def process_add_requisite_value(message):
    value = message.text.strip()
    if not value:
        bot.send_message(message.chat.id, "Значение не может быть пустым. Пожалуйста, попробуйте снова.")
        return
    name = user_data.get(message.chat.id, {}).get('name')
    login = user_data.get(message.chat.id, {}).get('login')
    if not name or not login:
        bot.send_message(message.chat.id, "Что-то пошло не так. Попробуйте снова.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Добавление реквизита в базу данных
    cursor.execute("INSERT INTO requisites (login, name, value) VALUES (?, ?, ?)",
                   (login, name, value))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "Реквизит успешно добавлен.")
    send_requisites_menu(login, message.chat.id)

# Обработка инлайн кнопок для выхода из аккаунта
@bot.callback_query_handler(func=lambda call: call.data == "logout")
def logout_user(call):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Удаление токена авторизации пользователя
    user_login = user_data.get(call.message.chat.id, {}).get('login')
    if user_login:
        cursor.execute("UPDATE users SET token_expiry=NULL WHERE login=?", (user_login,))
        conn.commit()
    conn.close()

    user_data.pop(call.message.chat.id, None)
    bot.send_message(call.message.chat.id, "Вы успешно вышли из системы. Для повторного доступа авторизуйтесь снова.")
    send_welcome(call.message)

# Обработка инлайн кнопок для навигации "Назад"
@bot.callback_query_handler(func=lambda call: call.data == "back_to_requisites")
def back_to_requisites(call):
    user_login = user_data.get(call.message.chat.id, {}).get('login')
    if user_login:
        send_requisites_menu(user_login, call.message.chat.id)

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
    user_data[message.chat.id] = {'login': login}
    msg = bot.send_message(message.chat.id, "Введите пароль для регистрации:")
    bot.register_next_step_handler(msg, process_registration_password)

def process_registration_password(message):
    password = message.text.strip()
    if not password:
        bot.send_message(message.chat.id, "Пароль не может быть пустым. Пожалуйста, попробуйте снова.")
        return
    login = user_data.get(message.chat.id, {}).get('login')
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
        cursor.execute("INSERT INTO users (login, user_id, password) VALUES (?, ?, ?)",
                       (login, message.chat.id, password))
        conn.commit()
        bot.send_message(message.chat.id, "Регистрация успешна. Теперь вы можете авторизоваться.")
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data == "login")
def login_user(call):
    msg = bot.send_message(call.message.chat.id, "Введите логин для авторизации:")
    bot.register_next_step_handler(msg, process_login_login)

def process_login_login(message):
    login = message.text.strip()
    if not login:
        bot.send_message(message.chat.id, "Логин не может быть пустым. Пожалуйста, попробуйте снова.")
        return
    user_data[message.chat.id] = {'login': login}
    msg = bot.send_message(message.chat.id, "Введите пароль для авторизации:")
    bot.register_next_step_handler(msg, process_login_password)

def process_login_password(message):
    password = message.text.strip()
    if not password:
        bot.send_message(message.chat.id, "Пароль не может быть пустым. Пожалуйста, попробуйте снова.")
        return
    login = user_data.get(message.chat.id, {}).get('login')
    if not login:
        bot.send_message(message.chat.id, "Что-то пошло не так. Попробуйте начать заново.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Проверка логина и пароля
    cursor.execute("SELECT * FROM users WHERE login=? AND password=?", (login, password))
    user = cursor.fetchone()
    if user:
        # Обновление токена авторизации на 24 часа
        token_expiry = datetime.now() + timedelta(hours=24)
        cursor.execute("UPDATE users SET token_expiry=? WHERE login=?", (token_expiry.isoformat(), login))
        conn.commit()
        bot.send_message(message.chat.id, "Авторизация успешна. Доступ активен на 24 часа.")
        user_data[message.chat.id]['login'] = login
        send_requisites_menu(login, message.chat.id)
    else:
        bot.send_message(message.chat.id, "Неверный логин или пароль.")
    conn.close()

# Запуск бота
bot.polling()
 
