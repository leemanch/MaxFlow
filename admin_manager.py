from database.users.admins import AdminsDatabase


def manage_admins():
    db = AdminsDatabase()
    while True:
        print("\nУправление администраторами")
        print("1. Добавить администратора")
        print("2. Удалить администратора")
        print("3. Показать всех администраторов")
        print("4. Проверить статус пользователя")
        print("5. Выход")

        choice = input("\nВыберите действие: ")

        if choice == '1':
            admin_id = int(input("Введите ID администратора: "))
            username = input("Введите username (опционально): ") or None
            db.add_admin(admin_id, username)
            print(f"Администратор {admin_id} добавлен")

        elif choice == '2':
            admin_id = int(input("Введите ID администратора для удаления: "))
            db.remove_admin(admin_id)
            print(f"Администратор {admin_id} удален")

        elif choice == '3':
            admins = db.get_all_admins()
            print("\nСписок администраторов:")
            for admin_id, username in admins:
                print(f"  - ID: {admin_id}, Username: {username or 'Не указан'}")

        elif choice == '4':
            user_id = int(input("Введите ID пользователя для проверки: "))
            if db.is_admin(user_id):
                print(f"Пользователь {user_id} является администратором")
            else:
                print(f"Пользователь {user_id} НЕ администратор")

        elif choice == '5':
            break
        else:
            print("Неверный выбор")


if __name__ == "__main__":
    manage_admins()
