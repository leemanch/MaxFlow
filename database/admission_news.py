import os
import sqlite3
import logging

class AdmissionNewsDatabase:
    def __init__(self, db_name='others/admission_news.db'):
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        self.db_name = db_name
        self._create_tables()
        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def _create_tables(self):
        with sqlite3.connect(self.db_name) as conn:
            # Таблица новостей о поступлении
            conn.execute('''
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_date TEXT NOT NULL,
                    text TEXT NOT NULL
                )
            ''')
            # Таблица записей абитуриентов на событие
            conn.execute('''
                CREATE TABLE IF NOT EXISTS registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    date_registered TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(news_id) REFERENCES news(id)
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_news_id ON registrations(news_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON registrations(user_id)')

    # Добавить новость
    def add_news(self, news_date, text):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.execute(
                'INSERT INTO news (news_date, text) VALUES (?, ?)',
                (news_date, text)
            )
            return cursor.lastrowid

    # Получить все новости
    def get_all_news(self):
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM news ORDER BY news_date ASC')
            return [dict(row) for row in cursor.fetchall()]

    # Записать абитуриента на событие
    def register_user(self, news_id, user_id, chat_id, username):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.execute(
                'INSERT INTO registrations (news_id, user_id, chat_id, username) VALUES (?, ?, ?, ?)',
                (news_id, user_id, chat_id, username)
            )
            return cursor.lastrowid

    # Получить список записавшихся на событие
    def get_registrations(self, news_id):
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM registrations WHERE news_id = ? ORDER BY date_registered ASC',
                (news_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    def get_future_events(self):
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM news WHERE date(news_date) >= date('now') ORDER BY news_date ASC"
            )
            return [dict(row) for row in cursor.fetchall()]

