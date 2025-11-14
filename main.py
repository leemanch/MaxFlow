import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.filters.command import Command
from maxapi.types import BotStarted, MessageCreated, CallbackButton, MessageCallback
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from database.mailing import MailingDatabase
from database.news import NewsDatabase
from database.users.admins import AdminsDatabase
from database.users.dean import DeanRepresentativesDatabase
from database.requests.requests_dean import DeanRequestDataBase
from database.requests.study_certificate_requests import StudyCertificateRequestsDatabase
from database.users.users import UsersDatabase

logging.basicConfig(level=logging.INFO)

bot = Bot('f9LHodD0cOI4Nzoz-gc_ai7lui-e1pirN99Zm8Ek8Tg8cV777eF3lGQZE7TMdTZjZeolhySXve_zm8x_bSfs')
dp = Dispatcher()

# Словари для хранения состояния пользователей
user_states = {}  # Хранит текущее состояние пользователя (шаг ввода)
user_temp_data = {}  # Хранит временные данные пользователя

current_dean_request_index = {}
current_study_request_index = {}

users = UsersDatabase()
admins = AdminsDatabase()
request_dean = DeanRequestDataBase()
study_certificate_requests = StudyCertificateRequestsDatabase()
dean_representatives = DeanRepresentativesDatabase()
mailings = MailingDatabase()
news = NewsDatabase()


@dp.bot_started()
async def bot_started(event: BotStarted):
    await event.bot.send_message(
        chat_id=event.chat_id,
        text='Привет! Отправь мне /start'
    )


@dp.message_created(Command('setd'))
async def setd(event: MessageCreated):
    if (dean_representatives.is_representative(event.from_user.user_id) and users.has_role(event.from_user.user_id,
                                                                                           "dean")):
        await event.bot.send_message(chat_id=event.chat.chat_id, text="Вы уже являетесь представителем деканата!")
    elif (request_dean.get_user(user_id=event.from_user.user_id) == None):
        request_dean.add_user(user_id=event.from_user.user_id, username=event.from_user.full_name)
        await event.bot.send_message(chat_id=event.chat.chat_id, text="Заявка отправлена на рассмотрение!")
    else:
        await event.bot.send_message(chat_id=event.chat.chat_id, text="Вы уже отправляли заявку!")


async def show_menu(chat_id, user_id, bot):
    """Функция для отображения меню"""
    text_builder = "Выберите действие"
    role = users.get_user_role(user_id)
    builder = InlineKeyboardBuilder()
    if role == None:
        return
    elif role == "admin":
        builder.row(
            CallbackButton(
                text='Заявки от деканата',
                payload='requests_dean',
            )
        )
        builder.row(
            CallbackButton(
                text='Выдать роль',
                payload='add_role',
            ),
            CallbackButton(
                text='Удалить роль',
                payload='remove_role',
            )
        )
    elif role == "dean":
        builder.row(
            CallbackButton(
                text='Заявки',
                payload='requests_student',
            ),
        )
    elif role == "student":
        builder.row(
            CallbackButton(
                text='Заказать справку об обучении',
                payload='information_about_training',
            )
        )
        builder.row(
            CallbackButton(
                text='Подписки на новости',
                payload='subscribe_news',
            )
        ),
        builder.row(
            CallbackButton(
                text='Электронная библиотека',
                payload='electronic_library',
            )
        )
    elif role == "applicant":
        builder.row(
            CallbackButton(
                text='О ВУЗе',
                payload='about_university',
            ),
            CallbackButton(
                text='Предстоящие события',
                payload='future_events',
            )
        )
    elif role == "smm":
        builder.row(
            CallbackButton(
                text='Добавить новость',
                payload='add_news',
            ),
            CallbackButton(
                text='Удалить новость',
                payload='delete_news',
            )
        )
        builder.row(
            CallbackButton(
                text='Редактировать новость',
                payload='reedit_news',
            )
        )
    elif role == "head_dormitory":
        builder.row(
            CallbackButton(
                text='Жалобы студентов',
                payload='students_complaints',
            ),
            CallbackButton(
                text='Рассылка информации',
                payload='sending_info',
            )
        )
    elif role == "user":
        text_lable = "Вы пользователь! Используйте /start чтобы выбрать роль:)"
    else:
        text_lable = "Используйте /start чтобы выбрать роль:)"
    await bot.send_message(
        chat_id=chat_id,
        text=text_builder,
        attachments=[
            builder.as_markup()
        ]
    )


@dp.message_created(Command('menu'))
async def print_menu(event: MessageCreated):
    await show_menu(event.chat.chat_id, event.from_user.user_id, event.bot)


@dp.message_created(Command('start'))
async def hello(event: MessageCreated):
    text_builder = "Выберите вашу роль (старая будет не действительна)"
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(
            text='Абитуриент',
            payload='set_applicant',
        ),
        CallbackButton(
            text='Студент',
            payload='set_student',
        )
    )
    await event.message.answer(
        text=text_builder,
        attachments=[
            builder.as_markup()
        ]
    )
    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Используйте /menu для дальнейшей работы"
    )


async def show_next_request_dean(chat_id, bot, index=0):
    """Показывает следующую заявку с кнопками управления"""
    all_requests = request_dean.get_all_users()

    if not all_requests:
        await bot.send_message(chat_id=chat_id, text="На данный момент заявок нет.")
        return

    current_dean_request_index[chat_id] = index

    request = all_requests[index]

    message_text = f"📋 Всего заявок {len(all_requests)}\n\n"
    message_text += f"👤 ID: {request['id']}\n"
    message_text += f"📛 Имя: {request['username']}\n"
    message_text += f"📅 Дата подачи: {request['date_created']}\n"

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="✅ Принять", payload=f"approveDean_{request['id']}"),
        CallbackButton(text="❌ Отказать", payload=f"rejectDean_{request['id']}")
    )
    builder.row(
        CallbackButton(text="⏭️ Следующая", payload="next_requestDean"),
        CallbackButton(text="🛑 Стоп", payload="stop_requests")
    )

    await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        attachments=[builder.as_markup()]
    )


async def show_next_request_student_info(chat_id, bot, index=0):
    all_requests = study_certificate_requests.get_all_requests()

    if not all_requests:
        await bot.send_message(chat_id=chat_id, text="На данный момент заявок нет.")
        return

    current_study_request_index[chat_id] = index

    request = all_requests[index]

    message_text = f"📋 Всего заявок {len(all_requests)}\n\n"
    message_text += f"👤 ID: {request['id']}\n"
    message_text += f"👤 username: {request['username']}\n"
    message_text += f"📛 ФИО: {request['full_name']}\n"
    message_text += f"📛 Группа: {request['group_name']}\n"
    message_text += f"📛 Количество: {request['count']}\n"
    message_text += f"📅 Дата подачи: {request['date_created']}\n"

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="✅ Выдать", payload=f"approveStudy_{request['id']}"),
        CallbackButton(text="❌ Отказать", payload=f"rejectStudy_{request['id']}")
    )
    builder.row(
        CallbackButton(text="⏭️ Следующая", payload="next_requestStudy"),
        CallbackButton(text="🛑 Стоп", payload="stop_requests")
    )

    await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        attachments=[builder.as_markup()]
    )


async def update_news_messages(bot, news_item):
    try:
        message_ids = news_item.get("message_ids", [])
        news_text = f"📢 Новость ВУЗа\n\nЗаголовок: {news_item['title']}\n\n{news_item['description']}"

        for message_id in message_ids:
            try:
                await bot.edit_message(
                    message_id=message_id,
                    text=news_text
                )
            except Exception as e:
                print(f"Ошибка при обновлении сообщения {message_id}: {e}")
                continue

    except Exception as e:
        print(f"Ошибка в update_news_messages: {e}")


@dp.message_created()
async def handle_text_input(event: MessageCreated):
    user_id = event.from_user.user_id
    if user_id in user_states:
        current_state = user_states[user_id]
        user_input = event.message.body.text.strip()

        if current_state == "waiting_user_id":
            try:
                target_user_id = int(user_input)

                # Проверяем существование пользователя в базе
                if not users.is_user_exists(target_user_id):
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Пользователь с таким ID не найден в базе. Введите ID пользователя снова:"
                    )
                    return

                # Пытаемся отправить сообщение пользователю
                try:
                    action_type = user_temp_data[user_id].get("action_type", "add")
                    if action_type == "add":
                        await event.bot.send_message(
                            user_id=target_user_id,
                            text=f"Вас назначили на роль {user_temp_data[user_id]['selected_role']}"
                        )
                    else:  # remove
                        await event.bot.send_message(
                            user_id=target_user_id,
                            text="С вас снята роль"
                        )

                    # Если сообщение отправлено успешно, сохраняем ID и запрашиваем подтверждение
                    user_temp_data[user_id]["target_user_id"] = target_user_id

                    builder = InlineKeyboardBuilder()
                    if action_type == "add":
                        builder.row(
                            CallbackButton(text="Да", payload="confirm_user"),
                            CallbackButton(text="Нет", payload="deny_user"),
                            CallbackButton(text="❌ Отмена", payload="cancel_operation")
                        )
                    else:  # remove
                        builder.row(
                            CallbackButton(text="Да", payload="confirm_remove"),
                            CallbackButton(text="Нет", payload="deny_remove"),
                            CallbackButton(text="❌ Отмена", payload="cancel_operation")
                        )

                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="✅ Сообщение пользователю отправлено. Это нужный пользователь?",
                        attachments=[builder.as_markup()]
                    )

                except Exception as e:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Пользователь не найден. Введите ID пользователя снова:"
                    )

            except ValueError:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ ID должен быть числом. Введите ID снова:"
                )
        elif current_state == "waiting_news_id_for_edit":
            try:
                news_id = int(user_input)
                news_item = news.get_news(news_id)
                if not news_item:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Новость с таким ID не найдена. Введите ID новости снова:"
                    )
                    return

                # Сохраняем ID новости для редактирования
                user_temp_data[event.from_user.user_id] = {
                    "news_id": news_id,
                    "current_news": news_item
                }

                confirmation_text = f"🆔 ID: {news_item['id']}\n"
                confirmation_text += f"📰 Заголовок: {news_item['title']}\n"
                confirmation_text += f"📅 Дата: {news_item['publication_date']}\n\n"
                confirmation_text += f"📝 Текст: {news_item['description'][:100]}..." if len(
                    news_item['description']) > 100 else f"📝 Текст: {news_item['description']}"

                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text=confirmation_text
                )

                # Предлагаем выбрать что редактировать
                builder = InlineKeyboardBuilder()
                builder.row(
                    CallbackButton(text="✏️ Заголовок", payload="edit_news_title"),
                    CallbackButton(text="📝 Текст", payload="edit_news_description")
                )
                builder.row(
                    CallbackButton(text="📰 Заголовок и текст", payload="edit_news_both"),
                    CallbackButton(text="❌ Отмена", payload="cancel_news_edit")
                )

                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="Что вы хотите отредактировать?",
                    attachments=[builder.as_markup()]
                )

                # Убираем состояние, так как дальше работаем через callback
                if event.from_user.user_id in user_states:
                    del user_states[event.from_user.user_id]

            except ValueError:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ ID должен быть числом. Введите ID новости снова:"
                )
        elif current_state == "waiting_news_title_edit":
            user_data = user_temp_data.get(user_id, {})
            news_id = user_data.get("news_id")
            new_title = user_input

            if news_id and new_title:
                # Обновляем только заголовок
                success = news.update_news(news_id, title=new_title)
                if success:
                    # Получаем обновленную новость
                    updated_news = news.get_news(news_id)

                    # Обновляем сообщения у подписчиков
                    await update_news_messages(event.bot, updated_news)

                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text=f"✅ Заголовок новости успешно обновлен!\n\nНовый заголовок: {new_title}"
                    )
                    # Показываем меню после завершения операции
                    await show_menu(event.chat.chat_id, user_id, event.bot)
                else:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Ошибка при обновлении заголовка."
                    )

            # Очищаем состояние
            if user_id in user_states:
                del user_states[user_id]
            if user_id in user_temp_data:
                del user_temp_data[user_id]

        elif current_state == "waiting_news_description_edit":
            user_data = user_temp_data.get(user_id, {})
            news_id = user_data.get("news_id")
            new_description = user_input

            if news_id and new_description:
                # Обновляем только описание
                success = news.update_news(news_id, description=new_description)
                if success:
                    # Получаем обновленную новость
                    updated_news = news.get_news(news_id)

                    # Обновляем сообщения у подписчиков
                    await update_news_messages(event.bot, updated_news)

                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text=f"✅ Текст новости успешно обновлен!\n\nНовый текст: {new_description[:100]}..." if len(
                            new_description) > 100 else f"✅ Текст новости успешно обновлен!\n\nНовый текст: {new_description}"
                    )
                    # Показываем меню после завершения операции
                    await show_menu(event.chat.chat_id, user_id, event.bot)
                else:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Ошибка при обновлении текста."
                    )

            # Очищаем состояние
            if user_id in user_states:
                del user_states[user_id]
            if user_id in user_temp_data:
                del user_temp_data[user_id]

        elif current_state == "waiting_news_title_edit_both":
            # Сохраняем новый заголовок и запрашиваем текст
            user_temp_data[user_id]["new_title"] = user_input
            user_states[user_id] = "waiting_news_description_edit_both"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ Новый заголовок сохранен. Теперь введите новый текст новости:"
            )

        elif current_state == "waiting_news_description_edit_both":
            user_data = user_temp_data.get(user_id, {})
            news_id = user_data.get("news_id")
            new_title = user_data.get("new_title")
            new_description = user_input

            if news_id and new_title and new_description:
                # Обновляем и заголовок и описание
                success = news.update_news(news_id, title=new_title, description=new_description)
                if success:
                    # Получаем обновленную новость
                    updated_news = news.get_news(news_id)

                    # Обновляем сообщения у подписчиков
                    await update_news_messages(event.bot, updated_news)

                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text=f"✅ Новость полностью обновлена!\n\nНовый заголовок: {new_title}\n\nНовый текст: {new_description[:100]}..." if len(
                            new_description) > 100 else f"✅ Новость полностью обновлена!\n\nНовый заголовок: {new_title}\n\nНовый текст: {new_description}"
                    )
                    # Показываем меню после завершения операции
                    await show_menu(event.chat.chat_id, user_id, event.bot)
                else:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Ошибка при обновлении новости."
                    )

            # Очищаем состояние
            if user_id in user_states:
                del user_states[user_id]
            if user_id in user_temp_data:
                del user_temp_data[user_id]
        elif current_state == "waiting_news_id_for_delete":
            try:
                news_id = int(user_input)
                # Проверяем существование новости
                news_item = news.get_news(news_id)
                if not news_item:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Новость с таким ID не найдена. Введите ID новости снова:"
                    )
                    return
                # Подтверждаем удаление
                confirmation_text = f"❓ Вы уверены, что хотите удалить эту новость?\n\n"
                confirmation_text += f"🆔 ID: {news_item['id']}\n"
                confirmation_text += f"📰 Заголовок: {news_item['title']}\n"
                confirmation_text += f"📅 Дата: {news_item['publication_date']}\n\n"
                confirmation_text += f"📝 Текст: {news_item['description'][:100]}..." if len(
                    news_item['description']) > 100 else f"📝 Текст: {news_item['description']}"
                builder = InlineKeyboardBuilder()
                builder.row(
                    CallbackButton(text="✅ Да, удалить", payload=f"confirm_delete_news_{news_id}"),
                    CallbackButton(text="❌ Нет, отмена", payload="cancel_delete_news")
                )
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text=confirmation_text,
                    attachments=[builder.as_markup()]
                )
                del user_states[user_id]

            except ValueError:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ ID должен быть числом. Введите ID новости снова:"
                )
        elif current_state == "waiting_news_title":
            # Сохраняем заголовок и запрашиваем текст новости
            user_temp_data[user_id]["title"] = user_input
            user_states[user_id] = "waiting_news_description"

            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ Заголовок сохранен. Теперь введите текст новости одним сообщением:"
            )

        elif current_state == "waiting_news_description":
            # Сохраняем описание и показываем предпросмотр с кнопками
            user_temp_data[user_id]["description"] = user_input

            # Формируем предпросмотр новости
            title = user_temp_data[user_id]["title"]
            description = user_temp_data[user_id]["description"]

            preview_text = f"📰 **Предпросмотр новости ВУЗа**\n\n"
            preview_text += f"**Заголовок:** {title}\n\n"
            preview_text += f"**Текст:**\n{description}\n\n"
            preview_text += "---\nВыберите действие:"

            builder = InlineKeyboardBuilder()
            builder.row(
                CallbackButton(text="📤 Разослать", payload="publish_news"),
                CallbackButton(text="✏️ Редактировать", payload="edit_news"),
                CallbackButton(text="❌ Отмена", payload="cancel_news")
            )

            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text=preview_text,
                attachments=[builder.as_markup()]
            )

            # Очищаем состояние, но сохраняем данные для возможного редактирования
            del user_states[user_id]
        elif current_state == "waiting_full_name":
            # Сохраняем ФИО и запрашиваем группу
            user_temp_data[user_id] = {"full_name": user_input}
            user_states[user_id] = "waiting_group"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ ФИО сохранено. Теперь введите вашу группу (Например: ИУК4-31Б):"
            )
        elif current_state == "waiting_group":
            # Сохраняем группу и запрашиваем количество справок
            user_temp_data[user_id]["group_name"] = user_input
            user_states[user_id] = "waiting_count"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ Группа сохранена. Теперь введите количество справок:"
            )
        elif current_state == "waiting_count":
            try:
                count = int(user_input)
                if count <= 0:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Количество должно быть положительным числом. Введите количество справок:"
                    )
                    return
                if count > 5:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Максимальное количество справок - 5. Введите количество справок:"
                    )
                    return
                # Получаем сохраненные данные
                user_data = user_temp_data.get(user_id, {})
                full_name = user_data.get("full_name")
                group_name = user_data.get("group_name")

                if not full_name or not group_name:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Ошибка: данные не сохранены. Начните заново."
                    )
                    # Очищаем состояние
                    if user_id in user_states:
                        del user_states[user_id]
                    if user_id in user_temp_data:
                        del user_temp_data[user_id]
                    return
                success = study_certificate_requests.add_request(
                    user_id,
                    event.from_user.full_name,
                    full_name,
                    group_name,
                    count
                )
                # Очищаем состояние пользователя
                if user_id in user_states:
                    del user_states[user_id]
                if user_id in user_temp_data:
                    del user_temp_data[user_id]
                if success:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text=f"✅ Заявка на справку успешно создана!\n\n📋 Данные заявки:\n👤 ФИО: {full_name}\n🎓 Группа: {group_name}\n📄 Количество справок: {count}"
                    )
                    # Показываем меню после завершения операции
                    await show_menu(event.chat.chat_id, user_id, event.bot)
                else:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Произошла ошибка при создании заявки. Попробуйте позже."
                    )

            except ValueError:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ Количество должно быть числом. Введите количество справок:"
                )


@dp.message_callback()
async def message_callback(callback: MessageCallback):
    payload = callback.callback.payload
    chat_id = callback.chat.chat_id
    user_id = callback.from_user.user_id

    # Удаляем меню при выборе любого действия
    try:
        await callback.message.delete()
    except Exception as e:
        print(f"Ошибка при удалении меню: {e}")

    if payload == "requests_dean":
        await show_next_request_dean(chat_id, callback.bot, 0)
    elif payload == "requests_student":
        await show_next_request_student_info(chat_id, callback.bot, 0)
    elif payload == "information_about_training":
        user_states[callback.from_user.user_id] = "waiting_full_name"
        await callback.bot.send_message(chat_id=chat_id,
                                        text="📝 Заполните данные для заявки на справку об обучении.\n\nВведите ваше ФИО (Например: Иванов Иван Иванович):")
    elif payload == "next_requestDean":
        all_requests = request_dean.get_all_users()
        if not all_requests:
            await callback.bot.send_message(chat_id=chat_id, text="Заявок нет!")
            return
        current_index = current_dean_request_index.get(chat_id, 0)
        next_index = (current_index + 1) % len(all_requests)
        await show_next_request_dean(chat_id, callback.bot, next_index)

    elif payload == "next_requestStudy":
        all_requests = study_certificate_requests.get_all_requests()
        if not all_requests:
            await callback.bot.send_message(chat_id=chat_id, text="Заявок нет!")
            return
        current_index = current_study_request_index.get(chat_id, 0)
        next_index = (current_index + 1) % len(all_requests)
        await show_next_request_student_info(chat_id, callback.bot, next_index)

    elif payload == "stop_requests":
        await callback.bot.send_message(chat_id=chat_id, text="Просмотр заявок остановлен.")
        # Показываем меню после остановки просмотра заявок
        await show_menu(chat_id, user_id, callback.bot)

    elif payload.startswith("approveDean_"):
        user_id_payload = int(payload.split("_")[1])
        if request_dean.get_user(user_id_payload):
            request_dean.delete_user(user_id=user_id_payload)
            dean_representatives.add_representative(user_id=user_id_payload)
            users.add_user(user_id_payload, "dean")
            await callback.bot.send_message(chat_id=chat_id, text=f"✅ Заявка пользователя {user_id_payload} принята!")
            await callback.bot.send_message(user_id=user_id_payload,
                                            text="✅ Вашу заявку приняли! Вам доступны новые возможности!")
            all_requests = request_dean.get_all_users()
            if all_requests:
                current_index = current_dean_request_index.get(chat_id, 0)
                await show_next_request_dean(chat_id, callback.bot, current_index)
            else:
                await callback.bot.send_message(chat_id=chat_id, text=f"Заявки закончились!")
                await show_menu(chat_id, user_id, callback.bot)
    elif payload.startswith("approveStudy_"):
        user_id_payload = int(payload.split("_")[1])
        if study_certificate_requests.is_request_exists(user_id_payload):
            study_certificate_requests.delete_request(request_id=user_id_payload)
            await callback.bot.send_message(chat_id=chat_id, text=f"✅ Заявка студента {user_id_payload} принята!")
            await callback.bot.send_message(user_id=user_id_payload, text="✅ Ваша справка готова к получению!")
            all_requests = study_certificate_requests.get_all_requests()
            if all_requests:
                current_index = current_study_request_index.get(chat_id, 0)
                await show_next_request_student_info(chat_id, callback.bot, current_index)
            else:
                await callback.bot.send_message(chat_id=chat_id, text=f"Заявки закончились!")
                await show_menu(chat_id, user_id, callback.bot)

    elif payload.startswith("rejectDean_"):
        user_id_payload = int(payload.split("_")[1])
        if request_dean.get_user(user_id_payload):
            request_dean.delete_user(user_id=user_id_payload)
            await callback.bot.send_message(chat_id=chat_id, text=f"❌ Заявка пользователя {user_id_payload} отклонена!")
            await callback.bot.send_message(user_id=user_id_payload, text="❌ Вашу заявку отклонили!")
            all_requests = request_dean.get_all_users()
            if all_requests:
                current_index = current_dean_request_index.get(chat_id, 0)
                await show_next_request_dean(chat_id, callback.bot, current_index)
            else:
                await callback.bot.send_message(chat_id=chat_id, text=f"Заявки закончились!")
                await show_menu(chat_id, user_id, callback.bot)

    elif payload.startswith("rejectStudy_"):
        user_id_payload = int(payload.split("_")[1])
        if study_certificate_requests.is_request_exists(user_id_payload):
            study_certificate_requests.delete_request(request_id=user_id_payload)
            await callback.bot.send_message(chat_id=chat_id, text=f"❌ Заявка студента {user_id_payload} отклонена!")
            await callback.bot.send_message(user_id=user_id_payload,
                                            text="❌ Вам отказали в выдаче справки! Обратитесь в деканат!")
            all_requests = study_certificate_requests.get_all_requests()
            if all_requests:
                current_index = current_study_request_index.get(chat_id, 0)
                await show_next_request_student_info(chat_id, callback.bot, current_index)
            else:
                await callback.bot.send_message(chat_id=chat_id, text=f"Заявки закончились!")
                await show_menu(chat_id, user_id, callback.bot)

    elif payload == "set_applicant":
        if not users.has_role(callback.from_user.user_id, "admin"):
            users.add_user(callback.from_user.user_id, "applicant")
            await callback.bot.send_message(chat_id=chat_id, text=f"Ваша роль сменена на Абитуриент\nИспользуйте /menu")

    elif payload == "set_student":
        if not users.has_role(callback.from_user.user_id, "admin"):
            users.add_user(callback.from_user.user_id, "student")
            await callback.bot.send_message(chat_id=chat_id, text=f"Ваша роль сменена на Студент\nИспользуйте /menu")

    elif payload == "future_events":
        pass
    elif payload == "add_role":
        builder = InlineKeyboardBuilder()

        builder.row(
            CallbackButton(
                text="admin",
                payload="role_admin"
            ),
            CallbackButton(
                text="dean",
                payload="role_dean"
            ),
            CallbackButton(
                text="smm",
                payload="role_smm"
            ),
        )
        builder.row(
            CallbackButton(
                text="head_dormitory",
                payload="role_head_dormitory"
            ),
        )
        await callback.bot.send_message(
            chat_id=chat_id,
            text="Выберите роль",
            attachments=[
                builder.as_markup()
            ]
        )
    elif payload == "remove_role":
        # Получаем пользователей по ролям
        admin_users = users.get_users_by_role("admin")
        dean_users = users.get_users_by_role("dean")
        smm_users = users.get_users_by_role("smm")
        head_dormitory_users = users.get_users_by_role("head_dormitory")

        # Формируем сообщение со списком пользователей
        message_text = "📋 Пользователи с ролями:\n\n"

        if admin_users:
            message_text += "👑 Админы:\n"
            for user in admin_users:
                message_text += f"• ID: {user['id']}\n"
            message_text += "\n"

        if dean_users:
            message_text += "🎓 Деканат:\n"
            for user in dean_users:
                message_text += f"• ID: {user['id']}\n"
            message_text += "\n"

        if smm_users:
            message_text += "📱 SMM:\n"
            for user in smm_users:
                message_text += f"• ID: {user['id']}\n"
            message_text += "\n"

        if head_dormitory_users:
            message_text += "🏠 Заведующие общежитием:\n"
            for user in head_dormitory_users:
                message_text += f"• ID: {user['id']}\n"
            message_text += "\n"

        if not admin_users and not dean_users and not smm_users and not head_dormitory_users:
            message_text = "❌ Пользователей с ролями не найдено"

        # Отправляем список пользователей
        await callback.bot.send_message(chat_id=chat_id, text=message_text)

        # Затем запрашиваем ID для удаления с кнопкой отмены
        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="❌ Отмена", payload="cancel_operation"))

        user_temp_data[callback.from_user.user_id] = {"action_type": "remove"}
        user_states[callback.from_user.user_id] = "waiting_user_id"
        await callback.bot.send_message(
            chat_id=chat_id,
            text="Введите ID пользователя для удаления роли:",
            attachments=[builder.as_markup()]
        )

    elif payload.startswith("role_"):
        selected_role = "_".join(payload.split("_")[1:])
        user_temp_data[callback.from_user.user_id] = {"selected_role": selected_role, "action_type": "add"}
        user_states[callback.from_user.user_id] = "waiting_user_id"

        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="❌ Отмена", payload="cancel_operation"))

        await callback.bot.send_message(
            chat_id=chat_id,
            text="Введите ID пользователя:",
            attachments=[builder.as_markup()]
        )

    elif payload == "confirm_user":
        user_data = user_temp_data.get(callback.from_user.user_id, {})
        role = user_data.get("selected_role")
        target_user_id = user_data.get("target_user_id")

        if role and target_user_id:
            if role == "admin":
                admins.add_admin(target_user_id)
            elif role == "dean":
                dean_representatives.add_representative(target_user_id)
            users.add_user(target_user_id, role)
            await callback.bot.send_message(chat_id=chat_id, text=f"Пользователю назначена роль {role}")
        else:
            await callback.bot.send_message(chat_id=chat_id, text="❌ Ошибка: данные не найдены")

        if callback.from_user.user_id in user_states:
            del user_states[callback.from_user.user_id]
        if callback.from_user.user_id in user_temp_data:
            del user_temp_data[callback.from_user.user_id]

        # Показываем меню после завершения операции
        await show_menu(chat_id, user_id, callback.bot)

    elif payload == "deny_user":
        # Сбрасываем состояние до шага ввода ID
        user_states[callback.from_user.user_id] = "waiting_user_id"
        await callback.bot.send_message(chat_id=chat_id, text="Введите ID пользователя снова:")

    elif payload == "confirm_remove":
        user_data = user_temp_data.get(callback.from_user.user_id, {})
        target_user_id = user_data.get("target_user_id")

        if target_user_id:
            # Получаем текущую роль пользователя для информационного сообщения
            current_role = users.get_user_role(target_user_id)

            # Удаляем пользователя из всех таблиц
            admins.remove_admin(target_user_id)
            dean_representatives.remove_representative(target_user_id)
            users.update_user_role(target_user_id, "user")

            await callback.bot.send_message(chat_id=chat_id,
                                            text=f"Пользователю {target_user_id} удалена роль {current_role}")
        else:
            await callback.bot.send_message(chat_id=chat_id, text="❌ Ошибка: данные не найдены")

        if callback.from_user.user_id in user_states:
            del user_states[callback.from_user.user_id]
        if callback.from_user.user_id in user_temp_data:
            del user_temp_data[callback.from_user.user_id]

        # Показываем меню после завершения операции
        await show_menu(chat_id, user_id, callback.bot)

    elif payload == "deny_remove":
        # Сбрасываем состояние до шага ввода ID
        user_states[callback.from_user.user_id] = "waiting_user_id"
        await callback.bot.send_message(chat_id=chat_id, text="Введите ID пользователя снова:")

    elif payload == "cancel_operation":
        # Очищаем состояние и данные пользователя
        if callback.from_user.user_id in user_states:
            del user_states[callback.from_user.user_id]
        if callback.from_user.user_id in user_temp_data:
            del user_temp_data[callback.from_user.user_id]
        await callback.bot.send_message(chat_id=chat_id, text="❌ Операция отменена.")
        # Показываем меню после отмены операции
        await show_menu(chat_id, user_id, callback.bot)
    elif payload == "subscribe_news":
        mailing_university = mailings.is_subscribed(callback.from_user.user_id, "university")
        mailing_dormitory = mailings.is_subscribed(callback.from_user.user_id, "dormitory")

        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(
                text="Подписаться" if not mailing_university else "Отписаться",
                payload="subscribe_news_university"
            ),
        )
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Подписка на новости ВУЗа: {'✅ Подписан' if mailing_university else '❌ Не подписан'}",
            attachments=[
                builder.as_markup()
            ]
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(
                text="Подписаться" if not mailing_dormitory else "Отписаться",
                payload="subscribe_news_dormitory"
            ),
        )
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Подписка на новости Общежития: {'✅ Подписан' if mailing_dormitory else '❌ Не подписан'}",
            attachments=[
                builder.as_markup()
            ]
        )
    elif payload == "subscribe_news_university":
        # Удаляем старое сообщение
        await callback.message.delete()

        if mailings.is_subscribed(callback.from_user.user_id, "university"):
            mailings.remove_subscription(callback.from_user.user_id, "university")
            new_status = False
        else:
            mailings.add_subscription(callback.from_user.user_id, callback.chat.chat_id, "university")
            new_status = True

        # Обновляем кнопки
        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(
                text="Подписаться" if not new_status else "Отписаться",
                payload="subscribe_news_university"
            ),
        )
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Подписка на новости ВУЗа: {'✅ Подписан' if new_status else '❌ Не подписан'}",
            attachments=[
                builder.as_markup()
            ]
        )
        # Показываем меню после завершения операции
        await show_menu(chat_id, user_id, callback.bot)

    elif payload == "subscribe_news_dormitory":
        # Удаляем старое сообщение
        await callback.message.delete()

        if mailings.is_subscribed(callback.from_user.user_id, "dormitory"):
            mailings.remove_subscription(callback.from_user.user_id, "dormitory")
            new_status = False
        else:
            mailings.add_subscription(callback.from_user.user_id, callback.chat.chat_id, "dormitory")
            new_status = True

        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(
                text="Подписаться" if not new_status else "Отписаться",
                payload="subscribe_news_dormitory"
            ),
        )
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Подписка на новости Общежития: {'✅ Подписан' if new_status else '❌ Не подписан'}",
            attachments=[
                builder.as_markup()
            ]
        )
        # Показываем меню после завершения операции
        await show_menu(chat_id, user_id, callback.bot)
    elif payload == "electronic_library":
        await callback.bot.send_message(chat_id=chat_id, text='''Информация по использованию электронной библиотеки
        Подключение осуществляется через сеть Интернет, в многопользовательском режиме по IP-адресам с компьютеров КФ МГТУ им. Н.Э. Баумана.
        Для того, чтобы начать пользоваться электронной библиотекой, вам необходимо обратиться в кабинет УАК3.216 для получения абонемента 1-2 курсов и в УАК3.217 для получения абонемента 3-6 курсов
        Для получения дополнительной информации перейдите по ссылке:"
        https://kf.bmstu.ru/units/nauchno-tehnicheskaya-biblioteka/elektronnye-informacionnye-resursy''')
        # Показываем меню после завершения операции
        await show_menu(chat_id, user_id, callback.bot)

    elif payload == "add_news":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_news_title"
        user_temp_data[user_id] = {}
        await callback.bot.send_message(chat_id=chat_id, text="📝 Введите заголовок новости ВУЗа:")

    elif payload == "publish_news":
        user_id = callback.from_user.user_id
        user_data = user_temp_data.get(user_id, {})
        title = user_data.get("title")
        description = user_data.get("description")
        if not title or not description:
            await callback.bot.send_message(chat_id=chat_id, text="❌ Ошибка: данные новости не найдены.")
            return
        news_id = news.add_news(title, description, "university")
        if news_id:
            subscribers = mailings.get_subscribers_by_type("university")
            message_ids = []
            if subscribers:
                news_text = f"📢 Новость ВУЗа\n\nЗаголовок: {title}\n\n{description}"
                for subscriber in subscribers:
                    try:
                        message = await callback.bot.send_message(
                            user_id=subscriber['user_id'],
                            text=news_text
                        )
                        message_ids.append(str(message.message.body.mid))
                    except Exception as e:
                        print(f"Ошибка отправки пользователю {subscriber['user_id']}: {e}")
                news.update_news(news_id, message_ids=message_ids)
            await callback.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Новость ВУЗа успешно опубликована и отправлена {len(subscribers)} подписчикам!"
            )
            if user_id in user_temp_data:
                del user_temp_data[user_id]
            # Показываем меню после завершения операции
            await show_menu(chat_id, user_id, callback.bot)
        else:
            await callback.bot.send_message(chat_id=chat_id, text="❌ Ошибка при сохранении новости.")
    elif payload == "edit_news":
        user_states[callback.from_user.user_id] = "waiting_news_title"

        await callback.bot.send_message(chat_id=chat_id, text="📝 Введите новый заголовок новости ВУЗа:")

    elif payload == "delete_news":
        all_news = news.get_all_news()
        if not all_news:
            await callback.bot.send_message(chat_id=chat_id, text="❌ Новостей для удаления не найдено.")
            return
        news_list_text = "📋 Список всех новостей ВУЗа:\n\n"
        for news_item in all_news:
            news_list_text += f"🆔 ID: {news_item['id']}\n"
            news_list_text += f"📰 Заголовок: {news_item['title']}\n"
            news_list_text += f"📅 Дата: {news_item['publication_date']}\n"
            news_list_text += "─" * 30 + "\n"

        await callback.bot.send_message(chat_id=chat_id, text=news_list_text)

        user_states[callback.from_user.user_id] = "waiting_news_id_for_delete"
        await callback.bot.send_message(chat_id=chat_id, text="Введите ID новости для удаления:")

    elif payload.startswith("confirm_delete_news_"):
        news_id = int(payload.split("_")[3])
        message_ids = news.get_news(news_id)["message_ids"]
        success = news.delete_news(news_id)
        for message_id in message_ids:
            await bot.delete_message(message_id)
        if success:
            await callback.bot.send_message(chat_id=chat_id, text=f"✅ Новость с ID {news_id} успешно удалена!")
        else:
            await callback.bot.send_message(chat_id=chat_id, text=f"❌ Ошибка при удалении новости с ID {news_id}.")
        # Показываем меню после завершения операции
        await show_menu(chat_id, user_id, callback.bot)

    elif payload == "cancel_delete_news":
        await callback.bot.send_message(chat_id=chat_id, text="❌ Удаление новости отменено.")
        # Показываем меню после отмены операции
        await show_menu(chat_id, user_id, callback.bot)

    elif payload == "reedit_news":
        all_news = news.get_all_news()
        if not all_news:
            await callback.bot.send_message(chat_id=chat_id, text="❌ Новостей для редактирования не найдено.")
            return
        news_list_text = "📋 Список всех новостей ВУЗа:\n\n"
        for news_item in all_news:
            news_list_text += f"🆔 ID: {news_item['id']}\n"
            news_list_text += f"📰 Заголовок: {news_item['title']}\n"
            news_list_text += f"📅 Дата: {news_item['publication_date']}\n"
            news_list_text += "─" * 30 + "\n"

        await callback.bot.send_message(chat_id=chat_id, text=news_list_text)

        user_states[callback.from_user.user_id] = "waiting_news_id_for_edit"
        await callback.bot.send_message(chat_id=chat_id, text="Введите ID новости для редактирования:")
    elif payload == "cancel_news":
        user_id = callback.from_user.user_id
        if user_id in user_temp_data:
            del user_temp_data[user_id]
        if user_id in user_states:
            del user_states[user_id]
        await callback.bot.send_message(chat_id=chat_id, text="❌ Создание новости отменено.")
        # Показываем меню после отмены операции
        await show_menu(chat_id, user_id, callback.bot)
    elif payload == "edit_news_title":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_news_title_edit"
        await callback.bot.send_message(chat_id=chat_id, text="Введите новый заголовок новости:")

    elif payload == "edit_news_description":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_news_description_edit"
        await callback.bot.send_message(chat_id=chat_id, text="Введите новый текст новости:")

    elif payload == "edit_news_both":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_news_title_edit_both"
        await callback.bot.send_message(chat_id=chat_id, text="Введите новый заголовок новости:")

    elif payload == "cancel_news_edit":
        user_id = callback.from_user.user_id
        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_temp_data:
            del user_temp_data[user_id]
        await callback.bot.send_message(chat_id=chat_id, text="❌ Редактирование новости отменено.")
        # Показываем меню после отмены операции
        await show_menu(chat_id, user_id, callback.bot)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())