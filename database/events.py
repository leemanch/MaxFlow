import sqlite3
import logging
from datetime import datetime


class EventsDatabase:
    def __init__(self, db_name='events.db'):
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
        """Создает таблицу событий"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    location TEXT NOT NULL,
                    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_event_date ON events(event_date)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_date_created ON events(date_created)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_title ON events(title)')

    def add_event(self, title, description, event_date, location):
        """Добавляет новое событие"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    '''INSERT INTO events 
                    (title, description, event_date, location) 
                    VALUES (?, ?, ?, ?)''',
                    (title, description, event_date, location)
                )
                event_id = cursor.lastrowid
                self.logger.info(f"Добавлено событие: {title} (ID: {event_id})")
                return event_id
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении события: {e}")
            return None

    def get_event(self, event_id):
        """Получает событие по ID"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM events WHERE id = ?',
                    (event_id,)
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении события: {e}")
            return None

    def get_all_events(self, limit=100, offset=0):
        """Получает все события с пагинацией"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM events ORDER BY event_date DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении событий: {e}")
            return []

    def get_upcoming_events(self, limit=10):
        """Получает предстоящие события"""
        try:
            current_date = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM events WHERE event_date >= ? ORDER BY event_date ASC LIMIT ?',
                    (current_date, limit)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении предстоящих событий: {e}")
            return []

    def get_past_events(self, limit=10):
        """Получает прошедшие события"""
        try:
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM events WHERE event_date < ? ORDER BY event_date DESC LIMIT ?',
                    (current_date, limit)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении прошедших событий: {e}")
            return []

    def update_event(self, event_id, title=None, description=None, event_date=None, location=None):
        """Обновляет событие"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                updates = []
                params = []

                if title is not None:
                    updates.append("title = ?")
                    params.append(title)
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                if event_date is not None:
                    updates.append("event_date = ?")
                    params.append(event_date)
                if location is not None:
                    updates.append("location = ?")
                    params.append(location)

                if updates:
                    updates.append("date_modified = CURRENT_TIMESTAMP")
                    params.append(event_id)
                    query = f"UPDATE events SET {', '.join(updates)} WHERE id = ?"
                    cursor = conn.execute(query, params)

                    if cursor.rowcount > 0:
                        self.logger.info(f"Событие {event_id} обновлено")
                        return True
                    else:
                        self.logger.warning(f"Событие {event_id} не найдено")
                        return False
                return False
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при обновлении события: {e}")
            return False

    def delete_event(self, event_id):
        """Удаляет событие"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'DELETE FROM events WHERE id = ?',
                    (event_id,)
                )
                if cursor.rowcount > 0:
                    self.logger.info(f"Событие {event_id} удалено")
                    return True
                else:
                    self.logger.warning(f"Событие {event_id} не найдено")
                    return False
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении события: {e}")
            return False

    def search_events(self, search_term):
        """Ищет события по заголовку или описанию"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    '''SELECT * FROM events 
                    WHERE title LIKE ? OR description LIKE ? 
                    ORDER BY event_date DESC''',
                    (f'%{search_term}%', f'%{search_term}%')
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при поиске событий: {e}")
            return []

    def get_events_by_date_range(self, start_date, end_date):
        """Получает события в указанном диапазоне дат"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM events WHERE event_date BETWEEN ? AND ? ORDER BY event_date ASC',
                    (start_date, end_date)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении событий по диапазону дат: {e}")
            return []

    def get_events_count(self):
        """Возвращает общее количество событий"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM events')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете событий: {e}")
            return 0

    def get_upcoming_events_count(self):
        """Возвращает количество предстоящих событий"""
        try:
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM events WHERE event_date >= ?',
                    (current_date,)
                )
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете предстоящих событий: {e}")
            return 0