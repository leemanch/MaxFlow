import sqlite3
import logging


class StudentComplaintsDatabase:
    def __init__(self, db_name='student_complaints.db'):
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
        """Создает таблицу жалоб студентов с оптимальной структурой"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS complaints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    description TEXT NOT NULL,
                    number_room TEXT NOT NULL,
                    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON complaints(user_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_id ON complaints(chat_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_username ON complaints(username)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_number_room ON complaints(number_room)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_date_created ON complaints(date_created)')

    def add_complaint(self, user_id, chat_id, username, description, number_room):
        """Добавляет жалобу студента в базу"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    '''INSERT INTO complaints 
                    (user_id, chat_id, username, description, number_room) 
                    VALUES (?, ?, ?, ?, ?)''',
                    (user_id, chat_id, username, description, number_room)
                )
                complaint_id = cursor.lastrowid
                self.logger.info(f"Добавлена жалоба: {complaint_id} - пользователь {user_id}, комната {number_room}")
                return complaint_id
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении жалобы: {e}")
            return None

    def get_complaint(self, complaint_id):
        """Ищет жалобу по ID"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM complaints WHERE id = ?',
                    (complaint_id,)
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при поиске жалобы: {e}")
            return None

    def get_complaints_by_user(self, user_id, limit=50, offset=0):
        """Получает все жалобы пользователя"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM complaints WHERE user_id = ? ORDER BY date_created DESC LIMIT ? OFFSET ?',
                    (user_id, limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении жалоб пользователя: {e}")
            return []

    def get_complaints_by_room(self, number_room, limit=50, offset=0):
        """Получает все жалобы по номеру комнаты"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM complaints WHERE number_room = ? ORDER BY date_created DESC LIMIT ? OFFSET ?',
                    (number_room, limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении жалоб по комнате: {e}")
            return []

    def get_all_complaints(self, limit=100, offset=0):
        """Получает все жалобы с пагинацией"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM complaints ORDER BY date_created DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении всех жалоб: {e}")
            return []

    def update_complaint(self, complaint_id, description=None, number_room=None):
        """Обновляет описание и/или номер комнаты в жалобе"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                if description and number_room:
                    conn.execute(
                        'UPDATE complaints SET description = ?, number_room = ? WHERE id = ?',
                        (description, number_room, complaint_id)
                    )
                elif description:
                    conn.execute(
                        'UPDATE complaints SET description = ? WHERE id = ?',
                        (description, complaint_id)
                    )
                elif number_room:
                    conn.execute(
                        'UPDATE complaints SET number_room = ? WHERE id = ?',
                        (number_room, complaint_id)
                    )

                self.logger.info(f"Обновлена жалоба: {complaint_id}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при обновлении жалобы: {e}")
            return False

    def delete_complaint(self, complaint_id):
        """Удаляет жалобу из базы"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM complaints WHERE id = ?', (complaint_id,))
                self.logger.info(f"Удалена жалоба: {complaint_id}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении жалобы: {e}")
            return False

    def get_complaints_count(self):
        """Возвращает количество жалоб"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM complaints')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете жалоб: {e}")
            return 0

    def get_user_complaints_count(self, user_id):
        """Возвращает количество жалоб пользователя"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM complaints WHERE user_id = ?', (user_id,))
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете жалоб пользователя: {e}")
            return 0

    def clear_all(self):
        """Очищает всю таблицу жалоб"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM complaints')
                self.logger.info("Таблица жалоб очищена")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при очистке таблицы: {e}")
            return False