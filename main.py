import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime, timedelta

# Вставьте ваш токен от BotFather
TOKEN = "7662974159:AAHlvoRjIXGeyPdNiE_IJB3LeMvzLJHUHDE"
bot = telebot.TeleBot(TOKEN)

# Путь к базе данных
DB_PATH = "/storage/emulated/0/FinancialHelperBot/financial_helper.db"

# Словарь для хранения промежуточных данных пользователей
user_data = {}

# Функция для создания таблиц в базе данных, если они не существуют
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            login TEXT,
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
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    conn.commit()
    conn.close()

# Создание базы данных при запуске
init_db()

# Функция для проверки авторизации пользователя
def is_authorized(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT token_expiry FROM users WHERE user_id=?", (user_id,))
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
    if is_authorized(message.chat.id):
        send_requisites_menu(message.chat.id)
    else:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Регистрация", callback_data="register"))
        markup.add(InlineKeyboardButton("Авторизация", callback_data="login"))
        bot.send_message(message.chat.id, "Добро пожаловать! Пожалуйста, зарегистрируйтесь или авторизуйтесь.", reply_markup=markup)

# Функция для отправки меню с реквизитами
def send_requisites_menu(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получение реквизитов для пользователя
    cursor.execute("SELECT id, name FROM requisites WHERE user_id=?", (chat_id,))
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
    cursor.execute("SELECT name, value FROM requisites WHERE id=? AND user_id=?", (req_id, call.message.chat.id))
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
    cursor.execute("DELETE FROM requisites WHERE id=? AND user_id=?", (req_id, call.message.chat.id))
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
    user_data[message.chat.id] = {'name': name}
    msg = bot.send_message(message.chat.id, "Введите значение реквизита:")
    bot.register_next_step_handler(msg, process_add_requisite_value)

def process_add_requisite_value(message):
    value = message.text.strip()
    if not value:
        bot.send_message(message.chat.id, "Значение не может быть пустым. Пожалуйста, попробуйте снова.")
        return
    name = user_data.get(message.chat.id, {}).get('name')
    if not name:
        bot.send_message(message.chat.id, "Что-то пошло не так. Попробуйте снова.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Добавление реквизита в базу данных
    cursor.execute("INSERT INTO requisites (user_id, name, value) VALUES (?, ?, ?)",
                   (message.chat.id, name, value))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "Реквизит успешно добавлен.")
    send_requisites_menu(message.chat.id)

# Обработка инлайн кнопок для выхода из аккаунта
@bot.callback_query_handler(func=lambda call: call.data == "logout")
def logout_user(call):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Удаление токена авторизации пользователя
    cursor.execute("UPDATE users SET token_expiry=NULL WHERE user_id=?", (call.message.chat.id,))
    conn.commit()
    conn.close()

    bot.send_message(call.message.chat.id, "Вы успешно вышли из системы. Для повторного доступа авторизуйтесь снова.")
    send_welcome(call.message)

# Обработка инлайн кнопок для навигации "Назад"
@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main(call):
    send_welcome(call.message)

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
        cursor.execute("INSERT INTO users (user_id, login, password) VALUES (?, ?, ?)",
                       (message.chat.id, login, password))
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
        cursor.execute("UPDATE users SET token_expiry=? WHERE user_id=?", (token_expiry.isoformat(), message.chat.id))
        conn.commit()
        bot.send_message(message.chat.id, "Авторизация успешна. Доступ активен на 24 часа.")
        send_requisites_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "Неверный логин или пароль.")
    conn.close()

# Запуск бота
bot.polling()