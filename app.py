

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bootstrap import Bootstrap
import sqlite3
import os
from functools import wraps
import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Замените на свой секретный ключ
bootstrap = Bootstrap(app)

DATABASE_URL = os.getenv('DATABASE_URL', 'Tanya.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            telegram_id INTEGER,
            role INTEGER DEFAULT 0
        )
    ''')
    # Таблица ролей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roles (
            role_id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL UNIQUE
        )
    ''')
    # Таблица использования команд ботом
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS command_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            command TEXT,
            date TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    # Таблица пользовательских кнопок бота
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_buttons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            callback_data TEXT NOT NULL
        )
    ''')
    # Инициализация ролей
    cursor.execute("INSERT OR IGNORE INTO roles (role_id, role_name) VALUES (1, 'Управляющий'), (2, 'Руководитель')")
    conn.commit()
    conn.close()

init_db()




def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                flash('У вас нет доступа к этой странице.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash('Регистрация прошла успешно. Пожалуйста, войдите.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Имя пользователя уже занято.', 'danger')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Вы успешно вошли в систему.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверные имя пользователя или пароль.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы успешно вышли из системы.', 'success')
    return redirect(url_for('index'))


@app.route('/statistics', methods=['GET', 'POST'])
@login_required
@role_required([1, 2])
def statistics():
    conn = get_db_connection()
    cursor = conn.cursor()

    conn.commit()

    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
    else:
        today = datetime.date.today()
        start_date = str(today - datetime.timedelta(days=7))
        end_date = str(today)

    cursor.execute('''
        SELECT u.username, COUNT(c.command) as command_count, c.date
        FROM command_usage c
        JOIN users u ON c.user_id = u.user_id
        WHERE c.date BETWEEN ? AND ?
        GROUP BY u.username, c.date
        ORDER BY c.date ASC
    ''', (start_date, end_date))

    data = cursor.fetchall()
    conn.close()

    # Подготовка данных для графика
    dates = sorted(list(set(row['date'] for row in data)))
    usernames = sorted(list(set(row['username'] for row in data)))

    graph_data = {username: [0] * len(dates) for username in usernames}
    for row in data:
        graph_data[row['username']][dates.index(row['date'])] += row['command_count']

    return render_template('statistics.html', dates=dates, graph_data=graph_data, usernames=usernames,
                           start_date=start_date, end_date=end_date)


@app.route('/manage_roles', methods=['GET', 'POST'])
@login_required
@role_required([2])
def manage_roles():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        user_id = request.form['user_id']
        role = request.form['role']
        cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
        conn.commit()
        flash('Роль пользователя обновлена.', 'success')
    cursor.execute("SELECT user_id, username, role FROM users")
    users = cursor.fetchall()
    cursor.execute("SELECT role_id, role_name FROM roles")
    roles = cursor.fetchall()
    conn.close()
    return render_template('manage_roles.html', users=users, roles=roles)

@app.route('/manage_bot', methods=['GET', 'POST'])
@login_required
@role_required([1, 2])
def manage_bot():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        button_text = request.form['button_text']
        callback_data = request.form['callback_data']
        cursor.execute("INSERT INTO bot_buttons (text, callback_data) VALUES (?, ?)", (button_text, callback_data))
        conn.commit()
        flash('Кнопка бота добавлена.', 'success')
    cursor.execute("SELECT * FROM bot_buttons")
    buttons = cursor.fetchall()
    conn.close()
    return render_template('manage_bot.html', buttons=buttons)

@app.route('/remove_button/<int:button_id>', methods=['POST'])
@login_required
@role_required([1, 2])
def remove_button(button_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bot_buttons WHERE id = ?", (button_id,))
    conn.commit()
    conn.close()
    flash('Кнопка бота удалена.', 'success')
    return redirect(url_for('manage_bot'))

if __name__ == '__main__':
    app.run(port=5000, debug=True)