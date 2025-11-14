import os
import sqlite3
import logging
from typing import List, Dict, Optional, Union


class StudyCertificateRequestsDatabase:
    def __init__(self, db_name: str = 'others/study_certificate_requests.db'):
        """
        База данных для заявок на справку об обучении

        Args:
            db_name: Имя файла базы данных
        """
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
        """Создает таблицу заявок на справку об обучении"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS certificate_requests (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    count INTEGER DEFAULT 1,
                    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_request_id ON certificate_requests(id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_request_username ON certificate_requests(username)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_request_group ON certificate_requests(group_name)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_request_date_created ON certificate_requests(date_created)')

    def add_request(self, request_id: int, username: str, full_name: str, group_name: str, count: int = 1) -> bool:
        """
        Добавляет заявку на справку об обучении

        Args:
            request_id: ID заявки (передается явно)
            username: Имя пользователя
            full_name: Полное имя
            group_name: Группа
            count: Количество справок (по умолчанию 1)

        Returns:
            True если успешно, False если ошибка
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO certificate_requests 
                    (id, username, full_name, group_name, count) 
                    VALUES (?, ?, ?, ?, ?)''',
                    (request_id, username, full_name, group_name, count)
                )
                self.logger.info(f"Добавлена заявка #{request_id} от пользователя {username}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении заявки #{request_id}: {e}")
            return False

    def get_request(self, request_id: int) -> Optional[Dict[str, Union[int, str]]]:
        """
        Получает информацию о заявке по ID

        Args:
            request_id: ID заявки

        Returns:
            Словарь с информацией о заявке или None если не найдена
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM certificate_requests WHERE id = ?',
                    (request_id,)
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении заявки #{request_id}: {e}")
            return None

    def get_requests_by_username(self, username: str) -> List[Dict[str, Union[int, str]]]:
        """
        Получает все заявки по имени пользователя

        Args:
            username: Имя пользователя

        Returns:
            Список заявок пользователя
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM certificate_requests WHERE username = ? ORDER BY date_created DESC',
                    (username,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении заявок пользователя {username}: {e}")
            return []

    def get_requests_by_group(self, group_name: str) -> List[Dict[str, Union[int, str]]]:
        """
        Получает все заявки по группе

        Args:
            group_name: Название группы

        Returns:
            Список заявок группы
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM certificate_requests WHERE group_name = ? ORDER BY date_created DESC',
                    (group_name,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении заявок группы {group_name}: {e}")
            return []

    def get_all_requests(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Union[int, str]]]:
        """
        Получает все заявки

        Args:
            limit: Ограничение количества записей
            offset: Смещение

        Returns:
            Список всех заявок
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM certificate_requests ORDER BY date_created DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении всех заявок: {e}")
            return []

    def delete_request(self, request_id: int) -> bool:
        """
        Удаляет заявку

        Args:
            request_id: ID заявки

        Returns:
            True если успешно, False если ошибка
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('DELETE FROM certificate_requests WHERE id = ?', (request_id,))
                success = cursor.rowcount > 0
                if success:
                    self.logger.info(f"Удалена заявка: #{request_id}")
                else:
                    self.logger.warning(f"Заявка #{request_id} не найдена")
                return success
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении заявки #{request_id}: {e}")
            return False

    def update_request(self, request_id: int, username: str = None, full_name: str = None,
                       group_name: str = None, count: int = None) -> bool:
        """
        Обновляет информацию о заявке

        Args:
            request_id: ID заявки
            username: Новое имя пользователя (опционально)
            full_name: Новое полное имя (опционально)
            group_name: Новая группа (опционально)
            count: Новое количество (опционально)

        Returns:
            True если успешно, False если ошибка
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                # Строим запрос динамически в зависимости от переданных параметров
                update_fields = []
                params = []

                if username is not None:
                    update_fields.append("username = ?")
                    params.append(username)

                if full_name is not None:
                    update_fields.append("full_name = ?")
                    params.append(full_name)

                if group_name is not None:
                    update_fields.append("group_name = ?")
                    params.append(group_name)

                if count is not None:
                    update_fields.append("count = ?")
                    params.append(count)

                if not update_fields:
                    self.logger.warning("Не указаны поля для обновления")
                    return False

                params.append(request_id)

                query = f"UPDATE certificate_requests SET {', '.join(update_fields)} WHERE id = ?"
                cursor = conn.execute(query, params)

                success = cursor.rowcount > 0
                if success:
                    self.logger.info(f"Обновлена заявка #{request_id}")
                else:
                    self.logger.warning(f"Заявка #{request_id} не найдена")
                return success
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при обновлении заявки #{request_id}: {e}")
            return False

    def is_request_exists(self, request_id: int) -> bool:
        """
        Проверяет, существует ли заявка

        Args:
            request_id: ID заявки

        Returns:
            True если существует, False если нет
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT 1 FROM certificate_requests WHERE id = ?', (request_id,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при проверке существования заявки #{request_id}: {e}")
            return False

    def get_requests_count(self) -> int:
        """
        Возвращает общее количество заявок

        Returns:
            Количество заявок
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM certificate_requests')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете заявок: {e}")
            return 0

    def get_statistics(self) -> Dict[str, Union[int, Dict[str, int]]]:
        """
        Возвращает статистику по заявкам

        Returns:
            Словарь со статистикой
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                # Общее количество заявок
                total_count = conn.execute('SELECT COUNT(*) FROM certificate_requests').fetchone()[0]

                # Количество заявок по группам
                group_stats = {}
                cursor = conn.execute('SELECT group_name, COUNT(*) FROM certificate_requests GROUP BY group_name')
                for row in cursor.fetchall():
                    group_stats[row[0]] = row[1]

                # Общее количество запрошенных справок
                total_certificates = conn.execute('SELECT SUM(count) FROM certificate_requests').fetchone()[0] or 0

                # Последняя добавленная заявка
                last_request = conn.execute(
                    'SELECT * FROM certificate_requests ORDER BY date_created DESC LIMIT 1'
                ).fetchone()

                return {
                    'total_requests': total_count,
                    'total_certificates': total_certificates,
                    'group_statistics': group_stats,
                    'last_request': dict(last_request) if last_request else None
                }
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении статистики: {e}")
            return {
                'total_requests': 0,
                'total_certificates': 0,
                'group_statistics': {},
                'last_request': None
            }

    def clear_all_requests(self) -> bool:
        """
        Очищает всю таблицу заявок

        Returns:
            True если успешно, False если ошибка
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM certificate_requests')
                self.logger.info("Таблица заявок очищена")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при очистке таблицы заявок: {e}")
            return False