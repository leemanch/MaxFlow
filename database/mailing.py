import os
import sqlite3
import logging

class MailingDatabase:
    def __init__(self, db_name='others/mailing_subscriptions.db'):
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
        """Создает таблицу подписок на рассылки"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mailing_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('university', 'dormitory')),
                    date_subscribed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, type)
                )
            ''')
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON mailing_subscriptions(user_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_id ON mailing_subscriptions(chat_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_type ON mailing_subscriptions(type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_type ON mailing_subscriptions(user_id, type)')

    def add_subscription(self, user_id, chat_id, subscription_type):
        """Добавляет подписку на рассылку"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    'INSERT OR REPLACE INTO mailing_subscriptions (user_id, chat_id, type) VALUES (?, ?, ?)',
                    (user_id, chat_id, subscription_type)
                )
                self.logger.info(f"Добавлена подписка: user_id={user_id}, chat_id={chat_id}, type={subscription_type}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении подписки: {e}")
            return False

    def remove_subscription(self, user_id, subscription_type):
        """Удаляет подписку на рассылку"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    'DELETE FROM mailing_subscriptions WHERE user_id = ? AND type = ?',
                    (user_id, subscription_type)
                )
                self.logger.info(f"Удалена подписка: user_id={user_id}, type={subscription_type}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении подписки: {e}")
            return False

    def remove_all_user_subscriptions(self, user_id):
        """Удаляет все подписки пользователя"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    'DELETE FROM mailing_subscriptions WHERE user_id = ?',
                    (user_id,)
                )
                self.logger.info(f"Удалены все подписки пользователя: {user_id}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении всех подписок пользователя: {e}")
            return False

    def is_subscribed(self, user_id, subscription_type):
        """Проверяет, подписан ли пользователь на указанный тип рассылки"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'SELECT 1 FROM mailing_subscriptions WHERE user_id = ? AND type = ?',
                    (user_id, subscription_type)
                )
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при проверке подписки: {e}")
            return False

    def get_user_subscriptions(self, user_id):
        """Получает все подписки пользователя"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'SELECT type, chat_id, date_subscribed FROM mailing_subscriptions WHERE user_id = ? ORDER BY date_subscribed',
                    (user_id,)
                )
                return [{'type': row[0], 'chat_id': row[1], 'date_subscribed': row[2]} for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении подписок пользователя: {e}")
            return []

    def get_subscribers_by_type(self, subscription_type):
        """Получает всех подписчиков указанного типа рассылки"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'SELECT user_id, chat_id FROM mailing_subscriptions WHERE type = ? ORDER BY date_subscribed',
                    (subscription_type,)
                )
                return [{'user_id': row[0], 'chat_id': row[1]} for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении подписчиков по типу: {e}")
            return []

    def get_all_subscriptions(self):
        """Получает все подписки"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'SELECT user_id, chat_id, type, date_subscribed FROM mailing_subscriptions ORDER BY date_subscribed'
                )
                return [{'user_id': row[0], 'chat_id': row[1], 'type': row[2], 'date_subscribed': row[3]}
                        for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении всех подписок: {e}")
            return []

    def get_count_by_type(self, subscription_type):
        """Возвращает количество подписчиков указанного типа"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM mailing_subscriptions WHERE type = ?',
                    (subscription_type,)
                )
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете подписчиков по типу: {e}")
            return 0

    def get_total_count(self):
        """Возвращает общее количество подписок"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM mailing_subscriptions')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете всех подписок: {e}")
            return 0

    def clear_all(self):
        """Очищает всю таблицу подписок"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM mailing_subscriptions')
                self.logger.info("Таблица подписок очищена")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при очистке таблицы: {e}")
            return False

    def toggle_subscription(self, user_id, chat_id, subscription_type):
        """Переключает подписку (добавляет если нет, удаляет если есть)"""
        try:
            if self.is_subscribed(user_id, subscription_type):
                return self.remove_subscription(user_id, subscription_type), 'removed'
            else:
                return self.add_subscription(user_id, chat_id, subscription_type), 'added'
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при переключении подписки: {e}")
            return False, 'error'