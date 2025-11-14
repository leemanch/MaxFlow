import sqlite3
import logging
from typing import List, Dict, Optional, Union


class UsersDatabase:
    def __init__(self, db_name: str = 'users.db'):
        """
        База данных пользователей с ролями (только ID и роль)

        Args:
            db_name: Имя файла базы данных
        """
        self.db_name = db_name
        self._create_table()
        self._setup_logging()
        self._initialize_default_roles()

    def _setup_logging(self):
        """Настройка логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _create_table(self):
        """Создает таблицу пользователей только с ID и ролью"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'dean', 'student', 'applicant', 'smm', 'head_dormitory', 'user')),
                    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(id)
                )
            ''')
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON users(id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_role ON users(role)')

    def _initialize_default_roles(self):
        """Инициализирует доступные роли"""
        self.available_roles = {
            'admin': 'Администратор',
            'dean': 'Представитель деканата',
            'student': 'Студент',
            'applicant': 'Абитуриент',
            'smm': 'SMM-менеджер',
            'head_dormitory': 'Староста общежития',
            'user': 'Пользователь'  # Новая роль по умолчанию
        }

    def add_user(self, user_id: int, role: str = 'user') -> bool:
        """
        Добавляет пользователя в базу данных

        Args:
            user_id: ID пользователя
            role: Роль пользователя (по умолчанию 'user')

        Returns:
            True если успешно, False если ошибка
        """
        try:
            # Проверяем валидность роли
            if role not in self.available_roles:
                self.logger.error(f"Недопустимая роль: {role}")
                return False

            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO users 
                    (id, role, date_modified) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)''',
                    (user_id, role)
                )
                self.logger.info(f"Добавлен пользователь: {user_id} с ролью {role}")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при добавлении пользователя {user_id}: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[Dict[str, Union[int, str]]]:
        """
        Получает информацию о пользователе

        Args:
            user_id: ID пользователя

        Returns:
            Словарь с информацией о пользователе или None если не найден
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM users WHERE id = ?',
                    (user_id,)
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
            return None

    def update_user_role(self, user_id: int, new_role: str) -> bool:
        """
        Обновляет роль пользователя

        Args:
            user_id: ID пользователя
            new_role: Новая роль

        Returns:
            True если успешно, False если ошибка
        """
        try:
            # Проверяем валидность роли
            if new_role not in self.available_roles:
                self.logger.error(f"Недопустимая роль: {new_role}")
                return False

            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    '''UPDATE users 
                    SET role = ?, date_modified = CURRENT_TIMESTAMP 
                    WHERE id = ?''',
                    (new_role, user_id)
                )
                success = cursor.rowcount > 0
                if success:
                    self.logger.info(f"Обновлена роль пользователя {user_id}: {new_role}")
                else:
                    self.logger.warning(f"Пользователь {user_id} не найден")
                return success
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при обновлении роли пользователя {user_id}: {e}")
            return False

    def delete_user(self, user_id: int) -> bool:
        """
        Удаляет пользователя из базы данных

        Args:
            user_id: ID пользователя

        Returns:
            True если успешно, False если ошибка
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
                success = cursor.rowcount > 0
                if success:
                    self.logger.info(f"Удален пользователь: {user_id}")
                else:
                    self.logger.warning(f"Пользователь {user_id} не найден")
                return success
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при удалении пользователя {user_id}: {e}")
            return False

    def is_user_exists(self, user_id: int) -> bool:
        """
        Проверяет, существует ли пользователь в базе

        Args:
            user_id: ID пользователя

        Returns:
            True если существует, False если нет
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT 1 FROM users WHERE id = ?', (user_id,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при проверке существования пользователя {user_id}: {e}")
            return False

    def get_user_role(self, user_id: int) -> Optional[str]:
        """
        Получает роль пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Роль пользователя или None если не найден
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT role FROM users WHERE id = ?', (user_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении роли пользователя {user_id}: {e}")
            return None

    def has_role(self, user_id: int, role: str) -> bool:
        """
        Проверяет, имеет ли пользователь указанную роль

        Args:
            user_id: ID пользователя
            role: Роль для проверки

        Returns:
            True если пользователь имеет указанную роль, False если нет
        """
        user_role = self.get_user_role(user_id)
        return user_role == role

    def get_users_by_role(self, role: str) -> List[Dict[str, Union[int, str]]]:
        """
        Получает всех пользователей с указанной ролью

        Args:
            role: Роль для фильтрации

        Returns:
            Список пользователей с указанной ролью
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM users WHERE role = ? ORDER BY date_created',
                    (role,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении пользователей с ролью {role}: {e}")
            return []

    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Union[int, str]]]:
        """
        Получает всех пользователей

        Args:
            limit: Ограничение количества записей
            offset: Смещение

        Returns:
            Список всех пользователей
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM users ORDER BY date_created DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении всех пользователей: {e}")
            return []

    def get_users_count(self) -> int:
        """
        Возвращает общее количество пользователей

        Returns:
            Количество пользователей
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM users')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете пользователей: {e}")
            return 0

    def get_users_count_by_role(self, role: str) -> int:
        """
        Возвращает количество пользователей с указанной ролью

        Args:
            role: Роль для подсчета

        Returns:
            Количество пользователей с указанной ролью
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM users WHERE role = ?', (role,))
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при подсчете пользователей с ролью {role}: {e}")
            return 0

    def get_available_roles(self) -> Dict[str, str]:
        """
        Возвращает доступные роли и их описания

        Returns:
            Словарь с ролями и описаниями
        """
        return self.available_roles.copy()

    def get_role_description(self, role: str) -> Optional[str]:
        """
        Получает описание роли

        Args:
            role: Роль

        Returns:
            Описание роли или None если роль не существует
        """
        return self.available_roles.get(role)

    def get_statistics(self) -> Dict[str, Union[int, Dict[str, int]]]:
        """
        Возвращает статистику по пользователям

        Returns:
            Словарь со статистикой
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                # Общее количество пользователей
                total_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]

                # Количество по ролям
                role_stats = {}
                for role in self.available_roles:
                    count = conn.execute(
                        'SELECT COUNT(*) FROM users WHERE role = ?',
                        (role,)
                    ).fetchone()[0]
                    role_stats[role] = count

                # Последний добавленный пользователь
                last_user = conn.execute(
                    'SELECT * FROM users ORDER BY date_created DESC LIMIT 1'
                ).fetchone()

                return {
                    'total_users': total_count,
                    'roles_statistics': role_stats,
                    'last_user': dict(last_user) if last_user else None
                }
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при получении статистики: {e}")
            return {
                'total_users': 0,
                'roles_statistics': {},
                'last_user': None
            }

    def clear_all_users(self) -> bool:
        """
        Очищает всю таблицу пользователей

        Returns:
            True если успешно, False если ошибка
        """
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('DELETE FROM users')
                self.logger.info("Таблица пользователей очищена")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при очистке таблицы пользователей: {e}")
            return False

    def ensure_user_exists(self, user_id: int) -> bool:
        """
        Гарантирует, что пользователь существует в базе с ролью по умолчанию 'user'

        Args:
            user_id: ID пользователя

        Returns:
            True если пользователь существует или был создан, False при ошибке
        """
        if self.is_user_exists(user_id):
            return True
        return self.add_user(user_id)  # Использует роль по умолчанию 'user'