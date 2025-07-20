from flask import Flask, request, render_template, redirect, jsonify, session, g, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, timedelta, datetime
import sqlite3
import os
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))

# Update database path for production
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'tracker.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)

# Initialize SQLite DB
conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS scores (
        date TEXT PRIMARY KEY,
        tasks TEXT,
        score REAL,
        delta_pct REAL,
        improved INTEGER
    )
""")
c.execute("""
    CREATE TABLE IF NOT EXISTS task_points (
        name TEXT PRIMARY KEY,
        points REAL
    )
""")
c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        last_sync TIMESTAMP
    )
""")
c.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        token TEXT PRIMARY KEY,
        user_id INTEGER,
        last_active TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
""")
conn.commit()

# In Python console or add to app.py temporarily:
from werkzeug.security import generate_password_hash
c.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
         ("admin", generate_password_hash("admin123")))
conn.commit()

#####################************

def get_task_points():
    c.execute("SELECT name, points FROM task_points")
    return dict(c.fetchall())

def parse_tasks_by_name(task_str, task_dict):
    tasks = []
    total = 0
    for line in task_str.splitlines():
        line = line.strip()
        if not line:
            continue
        if '=' in line:
            name, val = line.split('=')
            try:
                pts = float(val.strip())
                tasks.append((name.strip(), pts))
                total += pts
            except:
                continue
        elif line in task_dict:
            pts = task_dict[line]
            tasks.append((line, pts))
            total += pts
    return tasks, total

def get_yesterday_score():
    yesterday = str(date.today() - timedelta(days=1))
    c.execute("SELECT score FROM scores WHERE date = ?", (yesterday,))
    row = c.fetchone()
    return row[0] if row else None

def save_today(date_str, tasks, score, delta_pct, improved):
    task_repr = ", ".join([f"{name}={pts}" for name, pts in tasks])
    c.execute("REPLACE INTO scores (date, tasks, score, delta_pct, improved) VALUES (?, ?, ?, ?, ?)",
              (date_str, task_repr, score, delta_pct, int(improved)))
    conn.commit()

def seed_default_tasks():
    c.execute("SELECT COUNT(*) FROM task_points")
    if c.fetchone()[0] == 0:
        default_tasks = {
            "Write": 5,
            "Read": 3,
            "Workout": 4,
            "Meditate": 2,
            "Code": 6,
            "Plan": 2,
            "Journal": 2.5,
            "Stretch": 1.5,
        }
        for name, pts in default_tasks.items():
            c.execute("INSERT INTO task_points (name, points) VALUES (?, ?)", (name, pts))
        conn.commit()

seed_default_tasks()

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("EMAIL_USERNAME", "your-email@gmail.com")
SMTP_PASSWORD = os.getenv("EMAIL_PASSWORD", "your-app-password")  # Use app-specific password

def send_reminder_email(to_email):
    msg = MIMEText("Don't forget to log your daily tasks!")
    msg['Subject'] = "Daily Reflection Reminder"
    msg['From'] = SMTP_USERNAME
    msg['To'] = to_email
    
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)

def schedule_reminder():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        send_reminder_email,
        'cron',
        hour=20,  # 8 PM
        minute=0,
        args=[SMTP_USERNAME]
    )
    scheduler.start()

@app.before_request
def check_auth():
    public_routes = ['login', 'register', 'static']
    if not any(route in request.path for route in public_routes):
        if 'user_id' not in session:
            return redirect('/login')

# Update database connection to handle concurrent requests
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Add error handler
@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html'), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        
        if user is None:
            error = 'Invalid username or password'
        elif not check_password_hash(user['password'], password):
            error = 'Invalid username or password'
        else:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('home'))
            
    return render_template('login.html', error=error)

@app.route('/register-device', methods=['POST'])
def register_device():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    token = request.form['token']
    c.execute("INSERT INTO devices (token, user_id, last_active) VALUES (?, ?, CURRENT_TIMESTAMP)",
              (token, session['user_id']))
    conn.commit()
    return jsonify({'status': 'success'})

@app.route('/notify-success')
def notify_success():
    return jsonify({
        'title': '🎉 Goal Achieved!',
        'body': 'Congratulations! You met your 1% improvement goal today!'
    })

# Update home route
@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect('/login')
    feedback = ""
    if request.method == 'POST':
        raw_tasks = request.form['tasks']
        task_dict = get_task_points()
        tasks, score_today = parse_tasks_by_name(raw_tasks, task_dict)
        if not tasks:
            feedback = "No valid tasks found. Define them first under Manage Tasks."
        else:
            yesterday_score = get_yesterday_score()
            if yesterday_score is None:
                feedback = f"Great – your first score is {score_today:.2f} points. Come back tomorrow to compare!"
                delta_pct = 0.0
                improved = False
            else:
                delta_pct = ((score_today - yesterday_score) / yesterday_score) * 100
                improved = delta_pct >= 1
                feedback = (f"Today’s score: {score_today:.2f} pts; Yesterday’s: {yesterday_score:.2f} pts; "
                            f"Improvement: {delta_pct:.2f}%. ")
                if improved:
                    feedback += "🎉 You met your 1% improvement goal!"
                    return render_template('home.html', feedback=feedback, show_success=True)
                else:
                    feedback += "😐 You didn't hit 1% growth today. Try again tomorrow!"
            save_today(str(date.today()), tasks, score_today, delta_pct, improved)

    return render_template('home.html', feedback=feedback)

@app.route('/manage', methods=['GET', 'POST'])
def manage():
    if request.method == 'POST':
        definitions = request.form['definitions']
        for line in definitions.splitlines():
            if '=' in line:
                name, val = line.split('=')
                try:
                    pts = float(val.strip())
                    c.execute("REPLACE INTO task_points (name, points) VALUES (?, ?)", (name.strip(), pts))
                except:
                    continue
        conn.commit()
    return render_template('manage.html')

@app.route('/stats')
def stats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    try:
        db = get_db()
        rows = db.execute("""
            SELECT date, score, improved 
            FROM scores 
            ORDER BY date DESC 
            LIMIT 30
        """).fetchall()
        
        dates = []
        scores = []
        improved_days = []
        
        for row in rows:
            dates.append(row['date'])
            scores.append(float(row['score']))
            improved_days.append(bool(row['improved']))
        
        return render_template('stats.html', 
                            dates=dates[::-1], 
                            scores=scores[::-1], 
                            improved_days=improved_days[::-1])
    except Exception as e:
        app.logger.error(f"Error in stats route: {str(e)}")
        return render_template('error.html', message="Could not load statistics"), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)