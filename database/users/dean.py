import os
import sqlite3
import logging

from database.users.users import UsersDatabase


class DeanRepresentativesDatabase:
    def __init__(self, db_name='others/dean_representatives.db'):
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        self.db_name = db_name
        self._create_table()
        self._setup_logging()
        self.users = UsersDatabase()

    def _setup_logging(self):
        """Настройка логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _create_table(self):
        """Создает таблицу представителей деканата только с ID"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS dean_representatives (
                    id INTEGER PRIMARY KEY,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Создаем индекс для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_rep_id ON dean_representatives(id)')

    def add_representative(self, user_id):
        """Добавляет представителя деканата по ID"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    'INSERT OR IGNORE INTO dean_representatives (id) VALUES (?)',
                    (user_id,)
                )
                self.logger.info(f"Добавлен представитель деканата: {user_id}")
                self.users.add_user(user_id=user_id, role="dean")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении представителя: {e}")
            return False

    def is_representative(self, user_id):
        """Проверяет, является ли пользователь представителем деканата"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'SELECT 1 FROM dean_representatives WHERE id = ?',
                    (user_id,)
                )
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при проверке представителя: {e}")
            return False

    def remove_representative(self, user_id):
        """Удаляет представителя деканата"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM dean_representatives WHERE id = ?', (user_id,))
                self.logger.info(f"Удален представитель деканата: {user_id}")
                self.users.update_user_role(user_id=user_id, new_role="user")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении представителя: {e}")
            return False

    def get_all_representatives(self):
        """Получает список всех представителей деканата"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT id FROM dean_representatives ORDER BY date_added')
                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении списка представителей: {e}")
            return []

    def get_count(self):
        """Возвращает количество представителей деканата"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM dean_representatives')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете представителей: {e}")
            return 0

    def add_default_representatives(self, representative_ids):
        """Добавляет представителей деканата по умолчанию"""
        for user_id in representative_ids:
            self.add_representative(user_id)
        self.logger.info(f"Добавлены представители по умолчанию: {representative_ids}")

    def clear_all(self):
        """Очищает всю таблицу представителей"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM dean_representatives')
                self.logger.info("Таблица представителей очищена")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при очистке таблицы: {e}")
            return False