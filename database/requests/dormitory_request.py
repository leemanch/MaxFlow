import sqlite3
import logging
import os


class DormitoryRequestDatabase:
    def __init__(self, db_name='others/dormitory_requests.db'):
        # Создаем папку others, если она не существует
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
        """Создает таблицу заявок с оптимальной структурой"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    user_group TEXT NOT NULL,
                    date_of_birthday TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, submission_date)
                )
            ''')
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON requests(user_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_id ON requests(chat_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_submission_date ON requests(submission_date)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_group ON requests(user_group)')

    def add_request(self, user_id, chat_id, username, user_group, date_of_birthday, reason):
        """Добавляет заявку в базу данных"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    '''INSERT INTO requests 
                    (user_id, chat_id, username, user_group, date_of_birthday, reason) 
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (user_id, chat_id, username, user_group, date_of_birthday, reason)
                )
                self.logger.info(f"Добавлена заявка от пользователя: {username} (ID: {user_id})")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении заявки: {e}")
            return False

    def get_requests_by_user(self, user_id):
        """Ищет заявки по user_id"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM requests WHERE user_id = ? ORDER BY submission_date DESC',
                    (user_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при поиске заявок: {e}")
            return []

    def get_requests_by_chat(self, chat_id):
        """Ищет заявки по chat_id"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM requests WHERE chat_id = ? ORDER BY submission_date DESC',
                    (chat_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при поиске заявок: {e}")
            return []

    def get_all_requests(self, limit=100, offset=0):
        """Получает все заявки с пагинацией"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM requests ORDER BY submission_date DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении заявок: {e}")
            return []

    def delete_request(self, request_id):
        """Удаляет заявку по ID"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM requests WHERE id = ?', (request_id,))
                self.logger.info(f"Удалена заявка: {request_id}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении заявки: {e}")
            return False

    def get_requests_by_group(self, user_group):
        """Ищет заявки по группе"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM requests WHERE user_group = ? ORDER BY submission_date DESC',
                    (user_group,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при поиске заявок по группе: {e}")
            return []