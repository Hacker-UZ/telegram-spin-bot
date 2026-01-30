import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('pul_yutish.db')
    cursor = conn.cursor()
    
   # Foydalanuvchilar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY, 
                     username TEXT,
                     full_name TEXT,
                     balance INTEGER DEFAULT 0,
                     spins_left INTEGER DEFAULT 0,
                     last_spin TEXT)''')
    
    # Referallar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS referals
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     referer_id INTEGER,
                     referee_id INTEGER,
                     date TEXT,
                     FOREIGN KEY(referer_id) REFERENCES users(user_id),
                     FOREIGN KEY(referee_id) REFERENCES users(user_id))''')
    
    # Yutuqlar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS prizes
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     amount INTEGER,
                     date TEXT,
                     FOREIGN KEY(user_id) REFERENCES users(user_id))''')
    
    # To'lov so'rovlari
    cursor.execute('''CREATE TABLE IF NOT EXISTS payments
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     card_number TEXT,
                     card_holder TEXT,
                     amount INTEGER,
                     request_date TEXT,
                     status TEXT DEFAULT 'pending',
                     FOREIGN KEY(user_id) REFERENCES users(user_id))''')
    
    # Kanalar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     channel_id TEXT UNIQUE,
                     channel_name TEXT,
                     added_by INTEGER,
                     add_date TEXT,
                     FOREIGN KEY(added_by) REFERENCES users(user_id))''')
    
    # Foydalanuvchi kanal obunalari
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_subscriptions
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     channel_id TEXT,
                     subscribe_date TEXT,
                     FOREIGN KEY(user_id) REFERENCES users(user_id),
                     FOREIGN KEY(channel_id) REFERENCES channels(channel_id))''')
    
    # Add settings table for storing configuration values
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Add temp_data table for storing temporary data like subscription message IDs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temp_data (
            user_id INTEGER PRIMARY KEY,
            message_id INTEGER
        )
    ''')

    # Add phone_number column to users table if it doesn't exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if "phone_number" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")

    # Add bonus_given column to users table if it doesn't exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if "bonus_given" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN bonus_given INTEGER DEFAULT 0")

    # Add bonus_given column to referals table if it doesn't exist
    cursor.execute("PRAGMA table_info(referals)")
    columns = [column[1] for column in cursor.fetchall()]
    if "bonus_given" not in columns:
        cursor.execute("ALTER TABLE referals ADD COLUMN bonus_given INTEGER DEFAULT 0")

    # Add created_at column to users table if it doesn't exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if "created_at" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TEXT")

    # Qora ro'yxat jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS blacklist
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER UNIQUE,
                     reason TEXT,
                     added_date TEXT)''')

    # Set default ACTIVE_PRIZES if not already set
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ACTIVE_PRIZES', 'PRIZES')")

    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('pul_yutish.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user(user_id, **kwargs):
    conn = sqlite3.connect('pul_yutish.db')
    cursor = conn.cursor()
    
    set_clause = ", ".join([f"{key}=?" for key in kwargs])
    values = list(kwargs.values()) + [user_id]
    
    cursor.execute(f"UPDATE users SET {set_clause} WHERE user_id=?", values)
    conn.commit()
    conn.close()

def add_referal(referer_id, referee_id):
    conn = sqlite3.connect('pul_yutish.db')
    cursor = conn.cursor()
    
    cursor.execute("INSERT INTO referals (referer_id, referee_id, date) VALUES (?, ?, ?)",
                  (referer_id, referee_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    # Referal uchun spin qo'shamiz
    cursor.execute("UPDATE users SET spins_left=spins_left+1 WHERE user_id=?", (referer_id,))
    
    conn.commit()
    conn.close()

def add_prize(user_id, amount):
    conn = sqlite3.connect('pul_yutish.db')
    cursor = conn.cursor()
    
    cursor.execute("INSERT INTO prizes (user_id, amount, date) VALUES (?, ?, ?)",
                  (user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    # Balansni yangilaymiz
    cursor.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
    
    conn.commit()
    conn.close()