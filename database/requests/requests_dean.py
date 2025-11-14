import os
import sqlite3
import logging


class DeanRequestDataBase:
    def __init__(self, db_name='others/requests_dean.db'):
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        self.db_name = db_name
        self._create_table()
        self._setup_logging()

    def _setup_logging(self):
        """Настройка логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _create_table(self):
        """Создает таблицу пользователей с оптимальной структурой"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(id, username)
                )
            ''')
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON users(id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_username ON users(username)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_date_created ON users(date_created)')

    def add_user(self, user_id, username):
        """Добавляет пользователя в базу"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO users 
                    (id, username, date_modified) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)''',
                    (user_id, username)
                )
                self.logger.info(f"Добавлен пользователь: {user_id} - {username}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении пользователя: {e}")
            return False

    def get_user(self, user_id=None, username=None):
        """Ищет пользователя по ID или username"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row  # Для доступа к столбцам по имени

                if user_id:
                    cursor = conn.execute(
                        'SELECT * FROM users WHERE id = ?',
                        (user_id,)
                    )
                elif username:
                    cursor = conn.execute(
                        'SELECT * FROM users WHERE username = ?',
                        (username,)
                    )
                else:
                    return None

                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при поиске пользователя: {e}")
            return None

    def get_all_users(self, limit=100, offset=0):
        """Получает всех пользователей с пагинацией"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM users ORDER BY date_created DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении пользователей: {e}")
            return []

    def delete_user(self, user_id):
        """Удаляет пользователя из базы"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
                self.logger.info(f"Удален пользователь: {user_id}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении пользователя: {e}")
            return False
