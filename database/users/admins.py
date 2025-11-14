import os
import sqlite3
from database.users.users import UsersDatabase


class AdminsDatabase:
    def __init__(self, db_name='others/admins.db'):
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        self.db_name = db_name
        self._create_table()
        self.users = UsersDatabase()

    def _create_table(self):
        """Создает таблицу если она не существует"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')


    def add_admin(self, admin_id, username=None):
        """Добавляет администратора в базу"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute(
                'INSERT OR IGNORE INTO admins (id, username) VALUES (?, ?)',
                (admin_id, username)
            )
        self.users.add_user(admin_id, "admin")

    def is_admin(self, admin_id):
        """Проверяет, является ли пользователь администратором"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.execute('SELECT 1 FROM admins WHERE id = ?', (admin_id,))
            return cursor.fetchone() is not None

    def remove_admin(self, admin_id):
        """Удаляет администратора из базы"""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute('DELETE FROM admins WHERE id = ?', (admin_id,))
        self.users.update_user_role(admin_id, "user")

    def get_all_admins(self):
        """Возвращает список всех администраторов"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.execute('SELECT id, username FROM admins')
            return cursor.fetchall()
