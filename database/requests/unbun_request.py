import os
import sqlite3
import logging
from datetime import datetime


class UnbanRequestsDatabase:
    def __init__(self, db_name='others/unban_requests.db'):
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
        """Создает таблицу заявок на разбан"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS unban_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
                    reviewed_by INTEGER,  -- ID админа, который рассмотрел заявку
                    review_date TIMESTAMP,
                    review_notes TEXT
                )
            ''')
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON unban_requests(user_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_id ON unban_requests(chat_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_date ON unban_requests(date)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_status ON unban_requests(status)')


    def add_request(self, user_id, chat_id, username, description):
        """Добавляет заявку на разбан"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                # Проверяем, есть ли уже активная заявка от этого пользователя
                existing_request = self.get_pending_request(user_id)
                if existing_request:
                    self.logger.warning(f"У пользователя {user_id} уже есть активная заявка на разбан")
                    return False

                conn.execute(
                    '''INSERT INTO unban_requests 
                    (user_id, chat_id, username, description) 
                    VALUES (?, ?, ?, ?)''',
                    (user_id, chat_id, username, description)
                )
                self.logger.info(f"Добавлена заявка на разбан от пользователя {username} (ID: {user_id})")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении заявки на разбан: {e}")
            return False

    def get_pending_request(self, user_id):
        """Получает активную заявку пользователя"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM unban_requests WHERE user_id = ? AND status = "pending"',
                    (user_id,)
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении заявки: {e}")
            return None

    def get_all_pending_requests(self, limit=100, offset=0):
        """Получает все активные заявки с пагинацией"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM unban_requests WHERE status = "pending" ORDER BY date DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении активных заявок: {e}")
            return []

    def get_all_requests(self, limit=100, offset=0):
        """Получает все заявки с пагинацией"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM unban_requests ORDER BY date DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении всех заявок: {e}")
            return []

    def approve_request(self, request_id, admin_id, notes=None):
        """Одобряет заявку на разбан"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    '''UPDATE unban_requests 
                    SET status = "approved", reviewed_by = ?, review_date = CURRENT_TIMESTAMP, review_notes = ?
                    WHERE id = ? AND status = "pending"''',
                    (admin_id, notes, request_id)
                )
                if cursor.rowcount > 0:
                    self.logger.info(f"Заявка {request_id} одобрена администратором {admin_id}")
                    return True
                else:
                    self.logger.warning(f"Заявка {request_id} не найдена или уже обработана")
                    return False
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при одобрении заявки: {e}")
            return False

    def reject_request(self, request_id, admin_id, notes=None):
        """Отклоняет заявку на разбан"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    '''UPDATE unban_requests 
                    SET status = "rejected", reviewed_by = ?, review_date = CURRENT_TIMESTAMP, review_notes = ?
                    WHERE id = ? AND status = "pending"''',
                    (admin_id, notes, request_id)
                )
                if cursor.rowcount > 0:
                    self.logger.info(f"Заявка {request_id} отклонена администратором {admin_id}")
                    return True
                else:
                    self.logger.warning(f"Заявка {request_id} не найдена или уже обработана")
                    return False
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при отклонении заявки: {e}")
            return False

    def delete_request(self, request_id):
        """Удаляет заявку"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'DELETE FROM unban_requests WHERE id = ?',
                    (request_id,)
                )
                if cursor.rowcount > 0:
                    self.logger.info(f"Заявка {request_id} удалена")
                    return True
                else:
                    self.logger.warning(f"Заявка {request_id} не найдена")
                    return False
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении заявки: {e}")
            return False

    def get_request_by_id(self, request_id):
        """Получает заявку по ID"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM unban_requests WHERE id = ?',
                    (request_id,)
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении заявки по ID: {e}")
            return None

    def get_requests_by_user(self, user_id):
        """Получает все заявки пользователя"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM unban_requests WHERE user_id = ? ORDER BY date DESC',
                    (user_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении заявок пользователя: {e}")
            return []

    def get_pending_requests_count(self):
        """Возвращает количество активных заявок"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM unban_requests WHERE status = "pending"')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете активных заявок: {e}")
            return 0

    def get_user_requests_count(self, user_id):
        """Возвращает количество заявок пользователя"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM unban_requests WHERE user_id = ?', (user_id,))
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете заявок пользователя: {e}")
            return 0