import os
import sqlite3
import logging
import json


class NewsDatabase:
    def __init__(self, db_name='others/news.db'):
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
        """Создает таблицу новостей с оптимальной структурой"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    publication_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    news_type TEXT NOT NULL CHECK (news_type IN ('university', 'dormitory')),
                    message_ids TEXT DEFAULT '[]'
                )
            ''')
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_news_type ON news(news_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_publication_date ON news(publication_date)')

    def add_news(self, title, description, news_type, message_ids=None):
        """Добавляет новость в базу"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                # Сериализуем массив message_ids в JSON строку
                message_ids_json = json.dumps(message_ids if message_ids else [])

                cursor = conn.execute(
                    '''INSERT INTO news 
                    (title, description, news_type, message_ids) 
                    VALUES (?, ?, ?, ?)''',
                    (title, description, news_type, message_ids_json)
                )
                news_id = cursor.lastrowid
                self.logger.info(f"Добавлена новость: {news_id} - {title}, тип: {news_type}")
                return news_id
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении новости: {e}")
            return None

    def get_news(self, news_id):
        """Ищет новость по ID"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM news WHERE id = ?',
                    (news_id,)
                )
                result = cursor.fetchone()
                if result:
                    news_dict = dict(result)
                    # Десериализуем JSON строку обратно в массив
                    news_dict['message_ids'] = json.loads(news_dict['message_ids'])
                    return news_dict
                return None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при поиске новости: {e}")
            return None

    def get_news_by_type(self, news_type, limit=50, offset=0):
        """Получает новости по типу"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM news WHERE news_type = ? ORDER BY publication_date DESC LIMIT ? OFFSET ?',
                    (news_type, limit, offset)
                )
                news_list = []
                for row in cursor.fetchall():
                    news_dict = dict(row)
                    # Десериализуем JSON строку обратно в массив
                    news_dict['message_ids'] = json.loads(news_dict['message_ids'])
                    news_list.append(news_dict)
                return news_list
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении новостей по типу: {e}")
            return []

    def get_all_news(self, limit=100, offset=0):
        """Получает все новости с пагинацией"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM news ORDER BY publication_date DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                news_list = []
                for row in cursor.fetchall():
                    news_dict = dict(row)
                    # Десериализуем JSON строку обратно в массив
                    news_dict['message_ids'] = json.loads(news_dict['message_ids'])
                    news_list.append(news_dict)
                return news_list
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении всех новостей: {e}")
            return []

    def get_latest_news(self, news_type=None, limit=10):
        """Получает последние новости (все или по типу)"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                if news_type:
                    cursor = conn.execute(
                        'SELECT * FROM news WHERE news_type = ? ORDER BY publication_date DESC LIMIT ?',
                        (news_type, limit)
                    )
                else:
                    cursor = conn.execute(
                        'SELECT * FROM news ORDER BY publication_date DESC LIMIT ?',
                        (limit,)
                    )
                news_list = []
                for row in cursor.fetchall():
                    news_dict = dict(row)
                    # Десериализуем JSON строку обратно в массив
                    news_dict['message_ids'] = json.loads(news_dict['message_ids'])
                    news_list.append(news_dict)
                return news_list
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении последних новостей: {e}")
            return []

    def update_news(self, news_id, title=None, description=None, news_type=None, message_ids=None):
        """Обновляет новость"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                updates = []
                params = []

                if title:
                    updates.append("title = ?")
                    params.append(title)
                if description:
                    updates.append("description = ?")
                    params.append(description)
                if news_type:
                    updates.append("news_type = ?")
                    params.append(news_type)
                if message_ids is not None:
                    # Сериализуем массив message_ids в JSON строку
                    message_ids_json = json.dumps(message_ids)
                    updates.append("message_ids = ?")
                    params.append(message_ids_json)

                if updates:
                    params.append(news_id)
                    query = f"UPDATE news SET {', '.join(updates)} WHERE id = ?"
                    conn.execute(query, params)
                    self.logger.info(f"Обновлена новость: {news_id}")
                    return True
                return False
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при обновлении новости: {e}")
            return False

    def add_message_id(self, news_id, message_id):
        """Добавляет message_id к существующей новости"""
        try:
            news = self.get_news(news_id)
            if not news:
                return False

            message_ids = news.get('message_ids', [])
            if message_id not in message_ids:
                message_ids.append(message_id)
                return self.update_news(news_id, message_ids=message_ids)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при добавлении message_id: {e}")
            return False

    def remove_message_id(self, news_id, message_id):
        """Удаляет message_id из новости"""
        try:
            news = self.get_news(news_id)
            if not news:
                return False

            message_ids = news.get('message_ids', [])
            if message_id in message_ids:
                message_ids.remove(message_id)
                return self.update_news(news_id, message_ids=message_ids)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при удалении message_id: {e}")
            return False

    def delete_news(self, news_id):
        """Удаляет новость из базы"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM news WHERE id = ?', (news_id,))
                self.logger.info(f"Удалена новость: {news_id}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении новости: {e}")
            return False

    def get_news_count(self, news_type=None):
        """Возвращает количество новостей (всех или по типу)"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                if news_type:
                    cursor = conn.execute('SELECT COUNT(*) FROM news WHERE news_type = ?', (news_type,))
                else:
                    cursor = conn.execute('SELECT COUNT(*) FROM news')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете новостей: {e}")
            return 0

    def search_news(self, search_term, limit=20):
        """Ищет новости по заголовку или описанию"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                search_pattern = f'%{search_term}%'
                cursor = conn.execute(
                    'SELECT * FROM news WHERE title LIKE ? OR description LIKE ? ORDER BY publication_date DESC LIMIT ?',
                    (search_pattern, search_pattern, limit)
                )
                news_list = []
                for row in cursor.fetchall():
                    news_dict = dict(row)
                    # Десериализуем JSON строку обратно в массив
                    news_dict['message_ids'] = json.loads(news_dict['message_ids'])
                    news_list.append(news_dict)
                return news_list
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при поиске новостей: {e}")
            return []

    def clear_all(self):
        """Очищает всю таблицу новостей"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM news')
                self.logger.info("Таблица новостей очищена")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при очистке таблицы: {e}")
            return False