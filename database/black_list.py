import os
import sqlite3
import logging


class BlacklistDatabase:
    def __init__(self, db_name='others/blacklist.db'):
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
        """Создает таблицу черного списка"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    reason TEXT NOT NULL,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON blacklist(user_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_date_added ON blacklist(date_added)')

    def add_to_blacklist(self, user_id, reason):
        """Добавляет пользователя в черный список"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO blacklist 
                    (user_id, reason, date_modified) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)''',
                    (user_id, reason)
                )
                self.logger.info(f"Пользователь {user_id} добавлен в черный список. Причина: {reason}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении в черный список: {e}")
            return False

    def remove_from_blacklist(self, user_id):
        """Удаляет пользователя из черного списка"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'DELETE FROM blacklist WHERE user_id = ?',
                    (user_id,)
                )
                if cursor.rowcount > 0:
                    self.logger.info(f"Пользователь {user_id} удален из черного списка")
                    return True
                else:
                    self.logger.warning(f"Пользователь {user_id} не найден в черном списке")
                    return False
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении из черного списка: {e}")
            return False

    def is_in_blacklist(self, user_id):
        """Проверяет, находится ли пользователь в черном списке"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM blacklist WHERE user_id = ?',
                    (user_id,)
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при проверке черного списка: {e}")
            return None

    def get_all_blacklisted(self, limit=100, offset=0):
        """Получает всех пользователей из черного списка с пагинацией"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM blacklist ORDER BY date_added DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении черного списка: {e}")
            return []

    def update_reason(self, user_id, new_reason):
        """Обновляет причину нахождения в черном списке"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    '''UPDATE blacklist 
                    SET reason = ?, date_modified = CURRENT_TIMESTAMP 
                    WHERE user_id = ?''',
                    (new_reason, user_id)
                )
                if cursor.rowcount > 0:
                    self.logger.info(f"Причина для пользователя {user_id} обновлена: {new_reason}")
                    return True
                else:
                    self.logger.warning(f"Пользователь {user_id} не найден в черном списке")
                    return False
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при обновлении причины: {e}")
            return False

    def get_blacklist_count(self):
        """Возвращает количество пользователей в черном списке"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM blacklist')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете черного списка: {e}")
            return 0

    def search_blacklist(self, search_term):
        """Ищет в черном списке по user_id или причине"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    '''SELECT * FROM blacklist 
                    WHERE user_id LIKE ? OR reason LIKE ? 
                    ORDER BY date_added DESC''',
                    (f'%{search_term}%', f'%{search_term}%')
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при поиске в черном списке: {e}")
            return []

    def clear_blacklist(self):
        """Очищает весь черный список"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM blacklist')
                self.logger.info("Черный список полностью очищен")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при очистке черного списка: {e}")
            return False