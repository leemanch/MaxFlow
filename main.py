import asyncio
import logging
import re

from maxapi import Bot, Dispatcher
from maxapi.filters.command import Command
from maxapi.types import BotStarted, MessageCreated, CallbackButton, MessageCallback
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from database.black_list import BlacklistDatabase
from database.events import EventsDatabase
from database.mailing import MailingDatabase
from database.news import NewsDatabase
from database.requests.dormitory_request import DormitoryRequestDatabase
from database.requests.students_complaints import StudentComplaintsDatabase
from database.requests.unbun_request import UnbanRequestsDatabase
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
current_complaint_index = {}
current_dorm_pass_index = {}
current_unban_request_index = {}

users = UsersDatabase()
admins = AdminsDatabase()
request_dean = DeanRequestDataBase()
study_certificate_requests = StudyCertificateRequestsDatabase()
dean_representatives = DeanRepresentativesDatabase()
mailings = MailingDatabase()
news = NewsDatabase()
student_complaints = StudentComplaintsDatabase()
dormitory_requests = DormitoryRequestDatabase()
black_list = BlacklistDatabase()
unban_requests = UnbanRequestsDatabase()
events_db = EventsDatabase()

@dp.bot_started()
async def bot_started(event: BotStarted):
    await event.bot.send_message(
        chat_id=event.chat_id,
        text='Привет! Отправь мне /start'
    )


@dp.message_created(Command("unban_request"))
async def unban_r(event: MessageCreated):
    if black_list.is_in_blacklist(event.from_user.user_id) == None:
        await event.bot.send_message(user_id=event.from_user.user_id,
                                     text="Вы не в бане!")
        return
    user_input = " ".join(event.message.body.text.split()[1:])
    if(unban_requests.get_pending_request(user_id=event.from_user.user_id)):
        await event.bot.send_message(user_id=event.from_user.user_id,
                                     text="У вас уже есть активная заявка! Ожидайте ответа!")
        return
    await event.bot.send_message(user_id=event.from_user.user_id,
                                 text="Ваша заявка отправлена на рассмотрение! Ожидайте ответа!")
    unban_requests.add_request(event.from_user.user_id, event.chat.chat_id, event.from_user.full_name, user_input)

@dp.message_created(Command('setd'))
async def setd(event: MessageCreated):
    if black_list.is_in_blacklist(event.from_user.user_id):
        blacklisted_user = black_list.is_in_blacklist(event.from_user.user_id)
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text=f"❌ Вы находитесь в черном списке и не можете использовать бота.\nПричина: {blacklisted_user['reason']}\nДата добавления: {blacklisted_user['date_added']}\nЗаявка на разбан: /unban_request <Оправдание>"
        )
        return
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
        unban_count = unban_requests.get_pending_requests_count()
        unban_text = f'Заявки на разбан {unban_count}'
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
        builder.row(
            CallbackButton(
                text='Добавить в ЧС',
                payload='add_user_to_black_list',
            ),
            CallbackButton(
                text='Показать ЧС',
                payload='show_blacklist',
            )
        )
        builder.row(
            CallbackButton(
                text='Удалить из ЧС',
                payload='remove_from_blacklist',
            ),
            CallbackButton(
                text=unban_text,
                payload='show_unban_requests',
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
                text='Сообщить о проблеме',
                payload='submit_problem',
            )
        )
        builder.row(
            CallbackButton(
                text='Запрос на пропуск',
                payload='submit_pass_request',
            )
        )
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
                text="События",
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
        builder.row(
            CallbackButton(
                text='Управление событиями',
                payload='manage_events',
            ),
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
        builder.row(
            CallbackButton(
                text='Заявки на пропуск',
                payload='pass_requests',
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

async def show_next_unban_request(chat_id, bot, index=0):
    """Показывает следующую заявку на разбан с кнопками управления"""
    all_requests = unban_requests.get_all_pending_requests()

    if not all_requests:
        await bot.send_message(chat_id=chat_id, text="📭 Активных заявок на разбан нет.")
        return

    current_unban_request_index[chat_id] = index
    request = all_requests[index]

    message_text = f"📨 Заявки на разбан ({len(all_requests)} активных)\n\n"
    message_text += f"🆔 ID заявки: {request['id']}\n"
    message_text += f"👤 Пользователь: {request['username']}\n"
    message_text += f"🆔 User ID: {request['user_id']}\n"
    message_text += f"📅 Дата подачи: {request['date']}\n"
    message_text += f"📝 Описание:\n{request['description']}\n"

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="✅ Одобрить", payload=f"approve_unban_{request['id']}"),
        CallbackButton(text="❌ Отклонить", payload=f"reject_unban_{request['id']}")
    )
    builder.row(
        CallbackButton(text="⏭️ Следующая", payload="next_unban_request"),
        CallbackButton(text="🛑 Стоп", payload="stop_unban_requests")
    )

    await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        attachments=[builder.as_markup()]
    )

@dp.message_created(Command('menu'))
async def print_menu(event: MessageCreated):
    if black_list.is_in_blacklist(event.from_user.user_id):
        blacklisted_user = black_list.is_in_blacklist(event.from_user.user_id)
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text=f"❌ Вы находитесь в черном списке и не можете использовать бота.\nПричина: {blacklisted_user['reason']}\nДата добавления: {blacklisted_user['date_added']}\nЗаявка на разбан: /unban_request <Оправдание>"
        )
        return
    await show_menu(event.chat.chat_id, event.from_user.user_id, event.bot)


async def show_next_complaint(chat_id, bot, index=0): #ВОВА1
    complaints = student_complaints.get_all_complaints()
    if not complaints:
        await bot.send_message(chat_id=chat_id, text="На данный момент жалоб нет.")
        return

    current_complaint_index[chat_id] = index
    c = complaints[index]

    text = (
        f"📋 Всего жалоб {len(complaints)}\n\n"
        f"# {c['id']}\n"
        f"👤 username: {c['username']}\n"
        f"🏠 Комната: {c['number_room']}\n"
        f"📝 Текст: {c['description']}\n"
        f"📅 Дата: {c['date_created']}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="✅ Ответить", payload=f"replyComplaint_{c['id']}"),
        CallbackButton(text="❌ Закрыть", payload=f"closeComplaint_{c['id']}")
    )
    builder.row(
        CallbackButton(text="⏭️ Следующая", payload="next_complaint"),
        CallbackButton(text="🛑 Стоп", payload="stop_complaints")
    )
    await bot.send_message(chat_id=chat_id, text=text, attachments=[builder.as_markup()]) #ВОВА2
async def show_next_pass_request(chat_id, bot, index=0):
    all_requests = dormitory_requests.get_all_requests()
    if not all_requests:
        await bot.send_message(chat_id=chat_id, text="На данный момент заявок на пропуск нет.")
        return

    current_dorm_pass_index[chat_id] = index
    r = all_requests[index]

    message_text = (
        f"📋 Всего заявок: {len(all_requests)}\n\n"
        f"🆔 ID: {r['id']}\n"
        f"👤 Имя: {r['username']}\n"
        f"🎓 Группа: {r['user_group']}\n"
        f"📅 Дата рождения: {r['date_of_birthday']}\n"
        f"📝 Причина: {r['reason']}\n"
        f"📅 Дата подачи: {r['submission_date']}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="✅ Ответить", payload=f"replyPass_{r['id']}"),
        CallbackButton(text="📄 Автоответ", payload=f"autoReplyPass_{r['id']}"),
        CallbackButton(text="❌ Отклонить", payload=f"rejectPass_{r['id']}")
    )
    builder.row(
        CallbackButton(text="⏭️ Следующая", payload="next_pass_request"),
        CallbackButton(text="🛑 Стоп", payload="stop_pass_requests")
    )

    await bot.send_message(chat_id=chat_id, text=message_text, attachments=[builder.as_markup()])

@dp.message_created(Command('start'))
async def hello(event: MessageCreated):
    if black_list.is_in_blacklist(event.from_user.user_id):
        blacklisted_user = black_list.is_in_blacklist(event.from_user.user_id)
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text=f"❌ Вы находитесь в черном списке и не можете использовать бота.\nПричина: {blacklisted_user['reason']}\nДата добавления: {blacklisted_user['date_added']}\nЗаявка на разбан: /unban_request <Оправдание>"
        )
        return
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

    if black_list.is_in_blacklist(user_id):
        blacklisted_user = black_list.is_in_blacklist(user_id)
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text=f"❌ Вы находитесь в черном списке и не можете использовать бота.\nПричина: {blacklisted_user['reason']}\nДата добавления: {blacklisted_user['date_added']}\nЗаявка на разбан: /unban_request <Оправдание>"
        )
        return
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
        elif current_state == "waiting_problem_room":  # ВОВА1
            user_temp_data[user_id] = user_temp_data.get(user_id, {})
            user_temp_data[user_id]["number_room"] = user_input
            user_states[user_id] = "waiting_problem_description"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Опишите проблему (Например: Сломался слив):"
            )

        elif current_state == "waiting_problem_description":
            description = user_input
            data = user_temp_data.get(user_id, {})
            number_room = data.get("number_room")

            if not number_room:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ Не указан номер комнаты. Начните заново."
                )
                user_states.pop(user_id, None)
                user_temp_data.pop(user_id, None)
                return

            # Используем ту же таблицу complaints
            complaint_id = student_complaints.add_complaint(
                user_id=user_id,
                chat_id=event.chat.chat_id,
                username=event.from_user.full_name,
                description=description,
                number_room=number_room
            )

            user_states.pop(user_id, None)
            user_temp_data.pop(user_id, None)

            if complaint_id:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text=f"✅ Заявка отправлена!\nID: {complaint_id}\nКомната: {number_room}\nПроблема: {description}"
                )
            else:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ Ошибка при отправке заявки. Попробуйте ещё раз."
                )
        elif current_state == "waiting_pass_group":
            user_temp_data[user_id] = {"user_group": user_input}
            user_states[user_id] = "waiting_pass_birthdate"
            await event.bot.send_message(chat_id=event.chat.chat_id, text="Введите дату рождения (ДД.ММ.ГГГГ):")

        elif current_state == "waiting_pass_birthdate":
            pattern = r"^\d{2}\.\d{2}\.\d{4}$"
            if not re.match(pattern, user_input):
                await event.bot.send_message(chat_id=event.chat.chat_id,
                                             text="❌ Формат даты: ДД.ММ.ГГГГ (Например: 17.04.2005). Введите снова:")
                return

            user_temp_data[user_id]["date_of_birthday"] = user_input
            user_states[user_id] = "waiting_pass_reason"
            await event.bot.send_message(chat_id=event.chat.chat_id, text="Введите причину потери пропуска:")

        elif current_state == "waiting_pass_reason":
            reason = user_input
            data = user_temp_data.get(user_id, {})
            user_group = data.get("user_group")
            date_of_birthday = data.get("date_of_birthday")

            success = dormitory_requests.add_request(
                user_id=user_id,
                chat_id=event.chat.chat_id,
                username=event.from_user.full_name,
                user_group=user_group,
                date_of_birthday=date_of_birthday,
                reason=reason
            )

            user_states.pop(user_id, None)
            user_temp_data.pop(user_id, None)

            if success:
                await event.bot.send_message(chat_id=event.chat.chat_id,
                                             text=f"✅ Заявка на пропуск отправлена!\nГруппа: {user_group}\nДата рождения: {date_of_birthday}\nПричина: {reason}")
            else:
                await event.bot.send_message(chat_id=event.chat.chat_id, text="❌ Ошибка при отправке заявки.")
        elif current_state.startswith("waiting_reply_text_"):
            complaint_id = int(current_state.split("_")[-1])
            reply_text = user_input
            complaint = student_complaints.get_complaint(complaint_id)
            user_states.pop(user_id, None)

            if not complaint:
                await event.bot.send_message(chat_id=event.chat.chat_id, text="❌ Жалоба не найдена.")
                return

            # Отправляем ответ студенту по chat_id жалобы
            await event.bot.send_message(
                chat_id=complaint["chat_id"],
                text=f"✅ Ваше обращение рассмотрено.\nОтвет: {reply_text}"
            )
            # По желанию — удаляем жалобу после ответа:
            student_complaints.delete_complaint(complaint_id)

            await event.bot.send_message(chat_id=event.chat.chat_id,
                                         text="Ответ отправлен студенту, жалоба закрыта.")  # ВОВА2
        elif current_state.startswith("waiting_pass_reply_"):
            request_id = int(current_state.split("_")[-1])
            reply_text = user_input
            user_states.pop(user_id, None)

            all_requests = dormitory_requests.get_all_requests()
            target = next((r for r in all_requests if r["id"] == request_id), None)

            if not target:
                await event.bot.send_message(chat_id=event.chat.chat_id, text="❌ Заявка не найдена.")
                return

            await event.bot.send_message(
                chat_id=target["chat_id"],
                text=f"✅ Ваше обращение рассмотрено.\nОтвет: {reply_text}"
            )
            dormitory_requests.delete_request(request_id)
            await event.bot.send_message(chat_id=event.chat.chat_id,
                                         text="Ответ отправлен студенту, заявка закрыта.")  # ВОВА2

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
        # Добавьте эти состояния в обработчик handle_text_input
        elif current_state == "waiting_blacklist_user_id":
            try:
                target_user_id = int(user_input)

                # Проверяем, существует ли пользователь
                if not users.is_user_exists(target_user_id):
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Пользователь с таким ID не найден в базе. Введите ID пользователя снова:"
                    )
                    return

                # Проверяем, не находится ли пользователь уже в черном списке
                if black_list.is_in_blacklist(target_user_id):
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Этот пользователь уже находится в черном списке. Введите другой ID:"
                    )
                    return

                # Сохраняем ID пользователя и переходим к вводу причины
                user_temp_data[user_id] = {"target_user_id": target_user_id}
                user_states[user_id] = "waiting_blacklist_reason"

                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="✅ ID пользователя принят. Теперь введите причину добавления в черный список:"
                )

            except ValueError:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ ID должен быть числом. Введите ID пользователя снова:"
                )
        elif current_state == "waiting_blacklist_remove_id":
            try:
                target_user_id = int(user_input)

                # Проверяем, находится ли пользователь в черном списке
                if not black_list.is_in_blacklist(target_user_id):
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Пользователь с таким ID не найден в черном списке. Введите ID снова:"
                    )
                    return

                # Удаляем пользователя из черного списка
                success = black_list.remove_from_blacklist(target_user_id)

                if success:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text=f"✅ Пользователь {target_user_id} успешно удален из черного списка!"
                    )

                    # Пытаемся уведомить пользователя
                    try:
                        await event.bot.send_message(
                            user_id=target_user_id,
                            text="✅ Вы были удалены из черного списка бота. Теперь вы можете использовать бота снова."
                        )
                    except Exception as e:
                        print(f"Не удалось уведомить пользователя {target_user_id}: {e}")
                else:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Произошла ошибка при удалении из черного списка. Попробуйте позже."
                    )

                # Очищаем состояние и показываем меню
                if user_id in user_states:
                    del user_states[user_id]

                await show_menu(event.chat.chat_id, user_id, event.bot)

            except ValueError:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ ID должен быть числом. Введите ID пользователя снова:"
                )
        elif current_state == "waiting_unban_description":
            description = user_input
            user_data = user_temp_data.get(user_id, {})

            # Добавляем заявку на разбан
            success = unban_requests.add_request(
                user_id=user_id,
                chat_id=event.chat.chat_id,
                username=event.from_user.full_name,
                description=description
            )

            if success:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="✅ Ваша заявка на разбан отправлена на рассмотрение. Мы уведомим вас о решении."
                )
            else:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ У вас уже есть активная заявка на разбан. Дождитесь ее рассмотрения."
                )

            # Очищаем состояние
            if user_id in user_states:
                del user_states[user_id]
        elif current_state.startswith("waiting_unban_reject_reason_"):
            request_id = int(current_state.split("_")[-1])
            reject_reason = user_input

            # Отклоняем заявку
            success = unban_requests.reject_request(
                request_id=request_id,
                admin_id=user_id,
                notes=reject_reason
            )

            if success:
                # Получаем информацию о заявке
                request = unban_requests.get_request_by_id(request_id)
                if request:
                    # Уведомляем пользователя
                    try:
                        await event.bot.send_message(
                            user_id=request['user_id'],
                            text=f"❌ Ваша заявка на разбан отклонена.\nПричина: {reject_reason}"
                        )
                    except Exception as e:
                        print(f"Не удалось уведомить пользователя {request['user_id']}: {e}")

                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text=f"✅ Заявка на разбан отклонена. Пользователь уведомлен."
                )
            else:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ Ошибка при отклонении заявки. Возможно, заявка уже обработана."
                )

            # Очищаем состояние
            if user_id in user_states:
                del user_states[user_id]

            # Показываем следующую заявку или сообщение об окончании
            all_requests = unban_requests.get_all_pending_requests()
            if all_requests:
                current_index = current_unban_request_index.get(event.chat.chat_id, 0)
                await show_next_unban_request(event.chat.chat_id, event.bot, current_index)
            else:
                await event.bot.send_message(chat_id=event.chat.chat_id, text="📭 Заявки на разбан закончились!")
                await show_menu(event.chat.chat_id, user_id, event.bot)

        elif current_state == "waiting_event_title":
            user_temp_data[user_id] = {"title": user_input}
            user_states[user_id] = "waiting_event_description"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ Заголовок сохранен. Теперь введите описание события:"
            )
        elif current_state == "waiting_event_description":
            user_temp_data[user_id]["description"] = user_input
            user_states[user_id] = "waiting_event_date"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ Описание сохранено. Теперь введите дату и время события (формат: ДД.ММ.ГГГГ ЧЧ:ММ):"
            )
        elif current_state == "waiting_event_date":
            user_temp_data[user_id]["event_date"] = user_input
            user_states[user_id] = "waiting_event_location"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ Дата сохранена. Теперь введите место проведения события:"
            )
        elif current_state == "waiting_event_location":
            location = user_input
            user_data = user_temp_data.get(user_id, {})
            title = user_data.get("title")
            description = user_data.get("description")
            event_date = user_data.get("event_date")

            if not all([title, description, event_date, location]):
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
            event_id = events_db.add_event(title, description, event_date, location)

            if event_id:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text=f"✅ Событие успешно добавлено!\n\n**{title}**\n📅 {event_date}\n📍 {location}\n\n{description}"
                )
            else:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ Ошибка при добавлении события. Попробуйте позже."
                )

            if user_id in user_states:
                del user_states[user_id]
            if user_id in user_temp_data:
                del user_temp_data[user_id]

            await show_menu(event.chat.chat_id, user_id, event.bot)
        elif current_state == "waiting_event_id_for_edit":
            try:
                event_id = int(user_input)
                event_item = events_db.get_event(event_id)
                if not event_item:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Событие с таким ID не найдено. Введите ID события снова:"
                    )
                    return

                # Сохраняем ID события для редактирования
                user_temp_data[event.from_user.user_id] = {
                    "event_id": event_id,
                    "current_event": event_item
                }

                confirmation_text = f"🆔 ID: {event_item['id']}\n"
                confirmation_text += f"📰 Заголовок: {event_item['title']}\n"
                confirmation_text += f"📝 Описание: {event_item['description']}\n"
                confirmation_text += f"📅 Дата: {event_item['event_date']}\n"
                confirmation_text += f"📍 Место: {event_item['location']}\n"

                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text=confirmation_text
                )

                # Предлагаем выбрать что редактировать
                builder = InlineKeyboardBuilder()
                builder.row(
                    CallbackButton(text="✏️ Заголовок", payload="edit_event_title"),
                    CallbackButton(text="📝 Описание", payload="edit_event_description")
                )
                builder.row(
                    CallbackButton(text="📅 Дата", payload="edit_event_date"),
                    CallbackButton(text="📍 Место", payload="edit_event_location")
                )
                builder.row(
                    CallbackButton(text="📝 Все поля", payload="edit_event_all"),
                    CallbackButton(text="❌ Отмена", payload="cancel_event_edit")
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
                    text="❌ ID должен быть числом. Введите ID события снова:"
                )

        elif current_state == "waiting_event_id_for_delete":
            try:
                event_id = int(user_input)
                # Проверяем существование события
                event_item = events_db.get_event(event_id)
                if not event_item:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Событие с таким ID не найдено. Введите ID события снова:"
                    )
                    return

                # Подтверждаем удаление
                confirmation_text = f"❓ Вы уверены, что хотите удалить это событие?\n\n"
                confirmation_text += f"🆔 ID: {event_item['id']}\n"
                confirmation_text += f"📰 Заголовок: {event_item['title']}\n"
                confirmation_text += f"📅 Дата: {event_item['event_date']}\n"
                confirmation_text += f"📍 Место: {event_item['location']}\n"

                builder = InlineKeyboardBuilder()
                builder.row(
                    CallbackButton(text="✅ Да, удалить", payload=f"confirm_delete_event_{event_id}"),
                    CallbackButton(text="❌ Нет, отмена", payload="cancel_delete_event")
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
                    text="❌ ID должен быть числом. Введите ID события снова:"
                )
        elif current_state == "waiting_event_title_edit":
            user_data = user_temp_data.get(user_id, {})
            event_id = user_data.get("event_id")
            new_title = user_input

            if event_id and new_title:
                # Обновляем только заголовок
                success = events_db.update_event(event_id, title=new_title)
                if success:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text=f"✅ Заголовок события успешно обновлен!\n\nНовый заголовок: {new_title}"
                    )
                else:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Ошибка при обновлении заголовка."
                    )

            # Очищаем состояние и показываем меню
            if user_id in user_states:
                del user_states[user_id]
            if user_id in user_temp_data:
                del user_temp_data[user_id]

            await show_menu(event.chat.chat_id, user_id, event.bot)

        elif current_state == "waiting_event_description_edit":
            user_data = user_temp_data.get(user_id, {})
            event_id = user_data.get("event_id")
            new_description = user_input

            if event_id and new_description:
                # Обновляем только описание
                success = events_db.update_event(event_id, description=new_description)
                if success:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text=f"✅ Описание события успешно обновлено!\n\nНовое описание: {new_description}"
                    )
                else:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Ошибка при обновлении описания."
                    )

            # Очищаем состояние и показываем меню
            if user_id in user_states:
                del user_states[user_id]
            if user_id in user_temp_data:
                del user_temp_data[user_id]

            await show_menu(event.chat.chat_id, user_id, event.bot)

        elif current_state == "waiting_event_date_edit":
            user_data = user_temp_data.get(user_id, {})
            event_id = user_data.get("event_id")
            new_date = user_input

            if event_id and new_date:
                # Обновляем только дату
                success = events_db.update_event(event_id, event_date=new_date)
                if success:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text=f"✅ Дата события успешно обновлена!\n\nНовая дата: {new_date}"
                    )
                else:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Ошибка при обновлении даты."
                    )

            # Очищаем состояние и показываем меню
            if user_id in user_states:
                del user_states[user_id]
            if user_id in user_temp_data:
                del user_temp_data[user_id]

            await show_menu(event.chat.chat_id, user_id, event.bot)

        elif current_state == "waiting_event_location_edit":
            user_data = user_temp_data.get(user_id, {})
            event_id = user_data.get("event_id")
            new_location = user_input

            if event_id and new_location:
                # Обновляем только место
                success = events_db.update_event(event_id, location=new_location)
                if success:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text=f"✅ Место события успешно обновлено!\n\nНовое место: {new_location}"
                    )
                else:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Ошибка при обновлении места."
                    )

            # Очищаем состояние и показываем меню
            if user_id in user_states:
                del user_states[user_id]
            if user_id in user_temp_data:
                del user_temp_data[user_id]

            await show_menu(event.chat.chat_id, user_id, event.bot)

        elif current_state == "waiting_event_title_edit_all":
            # Сохраняем новый заголовок и запрашиваем описание
            user_temp_data[user_id]["new_title"] = user_input
            user_states[user_id] = "waiting_event_description_edit_all"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ Новый заголовок сохранен. Теперь введите новое описание события:"
            )

        elif current_state == "waiting_event_description_edit_all":
            # Сохраняем новое описание и запрашиваем дату
            user_temp_data[user_id]["new_description"] = user_input
            user_states[user_id] = "waiting_event_date_edit_all"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ Новое описание сохранено. Теперь введите новую дату события (формат: ДД.ММ.ГГГГ ЧЧ:ММ):"
            )

        elif current_state == "waiting_event_date_edit_all":
            # Сохраняем новую дату и запрашиваем место
            user_temp_data[user_id]["new_date"] = user_input
            user_states[user_id] = "waiting_event_location_edit_all"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ Новая дата сохранена. Теперь введите новое место проведения события:"
            )

        elif current_state == "waiting_event_location_edit_all":
            user_data = user_temp_data.get(user_id, {})
            event_id = user_data.get("event_id")
            new_title = user_data.get("new_title")
            new_description = user_data.get("new_description")
            new_date = user_data.get("new_date")
            new_location = user_input

            if event_id and new_title and new_description and new_date and new_location:
                # Обновляем все поля
                success = events_db.update_event(
                    event_id,
                    title=new_title,
                    description=new_description,
                    event_date=new_date,
                    location=new_location
                )
                if success:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text=f"✅ Событие полностью обновлено!\n\nНовый заголовок: {new_title}\n\nНовое описание: {new_description}\n\nНовая дата: {new_date}\n\nНовое место: {new_location}"
                    )
                else:
                    await event.bot.send_message(
                        chat_id=event.chat.chat_id,
                        text="❌ Ошибка при обновлении события."
                    )

            # Очищаем состояние и показываем меню
            if user_id in user_states:
                del user_states[user_id]
            if user_id in user_temp_data:
                del user_temp_data[user_id]

            await show_menu(event.chat.chat_id, user_id, event.bot)
        elif current_state == "waiting_blacklist_reason":
            reason = user_input
            user_data = user_temp_data.get(user_id, {})
            target_user_id = user_data.get("target_user_id")

            if not target_user_id:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ Ошибка: данные не найдены. Начните заново."
                )
                # Очищаем состояние
                if user_id in user_states:
                    del user_states[user_id]
                if user_id in user_temp_data:
                    del user_temp_data[user_id]
                return

            # Добавляем пользователя в черный список
            success = black_list.add_to_blacklist(target_user_id, reason)

            if success:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text=f"✅ Пользователь {target_user_id} успешно добавлен в черный список!\n\nПричина: {reason}"
                )

                # Пытаемся уведомить пользователя
                try:
                    await event.bot.send_message(
                        user_id=target_user_id,
                        text=f"❌ Вы были добавлены в черный список бота.\nПричина: {reason}"
                    )
                except Exception as e:
                    print(f"Не удалось уведомить пользователя {target_user_id}: {e}")
            else:
                await event.bot.send_message(
                    chat_id=event.chat.chat_id,
                    text="❌ Произошла ошибка при добавлении в черный список. Попробуйте позже."
                )

            # Очищаем состояние и показываем меню
            if user_id in user_states:
                del user_states[user_id]
            if user_id in user_temp_data:
                del user_temp_data[user_id]

            await show_menu(event.chat.chat_id, user_id, event.bot)


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
    elif payload == "submit_problem":  # ВОВА1
        user_states[callback.from_user.user_id] = "waiting_problem_room"
        await callback.message.answer("Введите номер комнаты (Например: 1.4.12):")  # ВОВА2
    elif payload == "students_complaints":  # ВОВА1
        await show_next_complaint(chat_id, callback.bot, 0)
    elif payload == "next_complaint":
        complaints = student_complaints.get_all_complaints()
        if not complaints:
            await callback.message.answer("Жалоб нет!")
            return
        current_index = current_complaint_index.get(chat_id, 0)
        next_index = (current_index + 1) % len(complaints)
        await show_next_complaint(chat_id, callback.bot, next_index)
    elif payload == "stop_complaints":
        await callback.message.answer("Просмотр жалоб остановлен.")
    elif payload == "submit_pass_request":
        user_states[callback.from_user.user_id] = "waiting_pass_group"
        await callback.message.answer("Введите вашу группу:")
    elif payload == "pass_requests":
        await show_next_pass_request(chat_id, callback.bot, 0)
    elif payload == "next_pass_request":
        all_requests = dormitory_requests.get_all_requests()
        if not all_requests:
            await callback.message.answer("Заявок на пропуск нет!")
            return
        current_index = current_dorm_pass_index.get(chat_id, 0)
        next_index = (current_index + 1) % len(all_requests)
        await show_next_pass_request(chat_id, callback.bot, next_index)
    elif payload == "stop_pass_requests":
        await callback.message.answer("Просмотр заявок на пропуск остановлен.")

    elif payload.startswith("replyPass_"):
        request_id = int(payload.split("_")[1])
        user_states[callback.from_user.user_id] = f"waiting_pass_reply_{request_id}"
        await callback.message.answer("Введите текст ответа студенту:")
    elif payload.startswith("autoReplyPass_"):
        request_id = int(payload.split("_")[1])
        all_requests = dormitory_requests.get_all_requests()
        target = next((r for r in all_requests if r["id"] == request_id), None)
        if target:
            await callback.bot.send_message(
                chat_id=target["chat_id"],
                text="✅ Ваша заявка принята. Получите пропуск в кабинете 2.1.06, с 8:00 до 20:00 пн-пт, с 10:00 до 18:00 сб-вс"
            )
            dormitory_requests.delete_request(request_id)
            await callback.message.answer("Автоответ отправлен студенту, заявка закрыта.")
    elif payload.startswith("rejectPass_"):
        request_id = int(payload.split("_")[1])
        if dormitory_requests.delete_request(request_id):
            await callback.message.answer("❌ Заявка отклонена и удалена.")
        else:
            await callback.message.answer("❌ Не удалось удалить заявку.")  # ВОВА2

    elif payload.startswith("replyComplaint_"):  # ВОВА1
        complaint_id = int(payload.split("_")[1])
        complaint = student_complaints.get_complaint(complaint_id)
        if not complaint:
            await callback.message.answer("❌ Жалоба не найдена.")
            return

        # Просим ввести текст ответа — сохраним состояние для head_dormitory
        user_states[callback.from_user.user_id] = f"waiting_reply_text_{complaint_id}"
        await callback.message.answer("Введите текст ответа студенту:")

    elif payload.startswith("closeComplaint_"):
        complaint_id = int(payload.split("_")[1])
        if student_complaints.delete_complaint(complaint_id):
            await callback.message.answer("✅ Жалоба закрыта.")
            complaints = student_complaints.get_all_complaints()
            if complaints:
                current_index = current_complaint_index.get(chat_id, 0)
                await show_next_complaint(chat_id, callback.bot, current_index % len(complaints))
            else:
                await callback.message.answer("Жалобы закончились!")
        else:
            await callback.message.answer("❌ Не удалось закрыть жалобу.")
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
    elif payload == "add_user_to_black_list":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_blacklist_user_id"
        await callback.bot.send_message(
            chat_id=chat_id,
            text="Введите ID пользователя для добавления в черный список:"
        )
    elif payload == "show_blacklist":
        blacklisted_users = black_list.get_all_blacklisted()
        if not blacklisted_users:
            await callback.bot.send_message(chat_id=chat_id, text="📋 Черный список пуст.")
            return

        message_text = "📋 Черный список пользователей:\n\n"
        for user in blacklisted_users:
            message_text += f"🆔 ID: {user['user_id']}\n"
            message_text += f"📝 Причина: {user['reason']}\n"
            message_text += f"📅 Дата добавления: {user['date_added']}\n"
            message_text += "─" * 30 + "\n"

        await callback.bot.send_message(chat_id=chat_id, text=message_text)
        await show_menu(chat_id, user_id, callback.bot)

    elif payload == "remove_from_blacklist":
        blacklisted_users = black_list.get_all_blacklisted()
        if not blacklisted_users:
            await callback.bot.send_message(chat_id=chat_id, text="❌ Черный список пуст.")
            return

        message_text = "📋 Пользователи в черном списке:\n\n"
        for user in blacklisted_users:
            message_text += f"🆔 ID: {user['user_id']}\n"
            message_text += f"📝 Причина: {user['reason']}\n\n"

        await callback.bot.send_message(chat_id=chat_id, text=message_text)

        user_states[user_id] = "waiting_blacklist_remove_id"
        await callback.bot.send_message(
            chat_id=chat_id,
            text="Введите ID пользователя для удаления из черного списка:"
        )
    elif payload == "show_unban_requests":
        await show_next_unban_request(chat_id, callback.bot, 0)

    # Добавьте обработчики для кнопок
    elif payload == "next_unban_request":
        all_requests = unban_requests.get_all_pending_requests()
        if not all_requests:
            await callback.bot.send_message(chat_id=chat_id, text="Заявок на разбан нет!")
            return
        current_index = current_unban_request_index.get(chat_id, 0)
        next_index = (current_index + 1) % len(all_requests)
        await show_next_unban_request(chat_id, callback.bot, next_index)

    elif payload == "stop_unban_requests":
        await callback.bot.send_message(chat_id=chat_id, text="Просмотр заявок на разбан остановлен.")
        # Показываем меню после остановки
        await show_menu(chat_id, user_id, callback.bot)
    elif payload == "future_events":
        upcoming_events = events_db.get_upcoming_events()
        print(upcoming_events)
        if not upcoming_events:
            await callback.bot.send_message(
                chat_id=chat_id,
                text="📅 На данный момент предстоящих событий нет. Следите за обновлениями!"
            )
            return

        message_text = "📅 **Предстоящие события ВУЗа:**\n\n"

        for i, event in enumerate(upcoming_events, 1):
            message_text += f"**{i}. {event['title']}**\n"
            message_text += f"📅 **Когда:** {event['event_date']}\n"
            message_text += f"📍 **Где:** {event['location']}\n"
            message_text += f"📝 **Описание:** {event['description']}\n"
            message_text += "─" * 30 + "\n\n"

        await callback.bot.send_message(
            chat_id=chat_id,
            text=message_text
        )
    elif payload.startswith("approve_unban_"):
        request_id = int(payload.split("_")[2])

        # Одобряем заявку
        success = unban_requests.approve_request(
            request_id=request_id,
            admin_id=user_id,
            notes="Заявка одобрена администратором"
        )

        if success:
            # Получаем информацию о заявке
            request = unban_requests.get_request_by_id(request_id)
            if request:
                # Удаляем пользователя из черного списка
                black_list.remove_from_blacklist(request['user_id'])

                # Уведомляем пользователя
                try:
                    await callback.bot.send_message(
                        user_id=request['user_id'],
                        text="✅ Ваша заявка на разбан одобрена! Теперь вы можете использовать бота."
                    )
                except Exception as e:
                    print(f"Не удалось уведомить пользователя {request['user_id']}: {e}")

            await callback.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Заявка на разбан одобрена! Пользователь {request['user_id']} удален из черного списка."
            )
        else:
            await callback.bot.send_message(
                chat_id=chat_id,
                text="❌ Ошибка при одобрении заявки. Возможно, заявка уже обработана."
            )

        # Показываем следующую заявку или сообщение об окончании
        all_requests = unban_requests.get_all_pending_requests()
        if all_requests:
            current_index = current_unban_request_index.get(chat_id, 0)
            await show_next_unban_request(chat_id, callback.bot, current_index)
        else:
            await callback.bot.send_message(chat_id=chat_id, text="📭 Заявки на разбан закончились!")
            await show_menu(chat_id, user_id, callback.bot)

    elif payload.startswith("reject_unban_"):
        request_id = int(payload.split("_")[2])

        # Запрашиваем причину отклонения
        user_states[user_id] = f"waiting_unban_reject_reason_{request_id}"
        await callback.bot.send_message(
            chat_id=chat_id,
            text="📝 Введите причину отклонения заявки:"
        )
    elif payload == "manage_events":
        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="➕ Добавить событие", payload="add_event"),
            CallbackButton(text="📋 Список событий", payload="list_events")
        )
        builder.row(
            CallbackButton(text="✏️ Редактировать событие", payload="edit_event"),
            CallbackButton(text="❌ Удалить событие", payload="delete_event")
        )

        events_count = events_db.get_events_count()
        upcoming_count = events_db.get_upcoming_events_count()

        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"📊 **Статистика событий:**\nВсего событий: {events_count}\nПредстоящих: {upcoming_count}",
            attachments=[builder.as_markup()]
        )
    elif payload == "add_event":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_event_title"
        user_temp_data[user_id] = {}
        await callback.bot.send_message(chat_id=chat_id, text="📝 Введите заголовок события:")

    elif payload == "list_events":
        all_events = events_db.get_all_events(limit=10)
        if not all_events:
            await callback.bot.send_message(chat_id=chat_id, text="📭 Событий пока нет.")
            return

        message_text = "📋 **Все события:**\n\n"
        for event in all_events:
            message_text += f"🆔 ID: {event['id']}\n"
            message_text += f"📰 Заголовок: {event['title']}\n"
            message_text += f"📅 Дата: {event['event_date']}\n"
            message_text += f"📍 Место: {event['location']}\n"
            message_text += "─" * 30 + "\n"

        await callback.bot.send_message(chat_id=chat_id, text=message_text)

    elif payload == "edit_event":
        all_events = events_db.get_all_events(limit=10)
        if not all_events:
            await callback.bot.send_message(chat_id=chat_id, text="❌ Событий для редактирования не найдено.")
            return

        events_list_text = "📋 Список всех событий:\n\n"
        for event in all_events:
            events_list_text += f"🆔 ID: {event['id']}\n"
            events_list_text += f"📰 Заголовок: {event['title']}\n"
            events_list_text += f"📅 Дата: {event['event_date']}\n"
            events_list_text += "─" * 30 + "\n"

        await callback.bot.send_message(chat_id=chat_id, text=events_list_text)

        user_states[callback.from_user.user_id] = "waiting_event_id_for_edit"
        await callback.bot.send_message(chat_id=chat_id, text="Введите ID события для редактирования:")

    elif payload == "delete_event":
        all_events = events_db.get_all_events(limit=10)
        if not all_events:
            await callback.bot.send_message(chat_id=chat_id, text="❌ Событий для удаления не найдено.")
            return

        events_list_text = "📋 Список всех событий:\n\n"
        for event in all_events:
            events_list_text += f"🆔 ID: {event['id']}\n"
            events_list_text += f"📰 Заголовок: {event['title']}\n"
            events_list_text += f"📅 Дата: {event['event_date']}\n"
            events_list_text += "─" * 30 + "\n"

        await callback.bot.send_message(chat_id=chat_id, text=events_list_text)

        user_states[callback.from_user.user_id] = "waiting_event_id_for_delete"
        await callback.bot.send_message(chat_id=chat_id, text="Введите ID события для удаления:")
    elif payload == "edit_event_title":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_event_title_edit"
        await callback.bot.send_message(chat_id=chat_id, text="Введите новый заголовок события:")

    elif payload == "edit_event_description":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_event_description_edit"
        await callback.bot.send_message(chat_id=chat_id, text="Введите новое описание события:")

    elif payload == "edit_event_date":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_event_date_edit"
        await callback.bot.send_message(chat_id=chat_id, text="Введите новую дату события (формат: ДД.ММ.ГГГГ ЧЧ:ММ):")

    elif payload == "edit_event_location":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_event_location_edit"
        await callback.bot.send_message(chat_id=chat_id, text="Введите новое место проведения события:")

    elif payload == "edit_event_all":
        user_id = callback.from_user.user_id
        user_states[user_id] = "waiting_event_title_edit_all"
        await callback.bot.send_message(chat_id=chat_id, text="Введите новый заголовок события:")

    elif payload.startswith("confirm_delete_event_"):
        event_id = int(payload.split("_")[3])
        success = events_db.delete_event(event_id)
        if success:
            await callback.bot.send_message(chat_id=chat_id, text=f"✅ Событие с ID {event_id} успешно удалено!")
        else:
            await callback.bot.send_message(chat_id=chat_id, text=f"❌ Ошибка при удалении события с ID {event_id}.")

        # Показываем меню после завершения операции
        await show_menu(chat_id, user_id, callback.bot)

    elif payload == "cancel_delete_event":
        await callback.bot.send_message(chat_id=chat_id, text="❌ Удаление события отменено.")
        # Показываем меню после отмены операции
        await show_menu(chat_id, user_id, callback.bot)

    elif payload == "cancel_event_edit":
        user_id = callback.from_user.user_id
        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_temp_data:
            del user_temp_data[user_id]
        await callback.bot.send_message(chat_id=chat_id, text="❌ Редактирование события отменено.")
        # Показываем меню после отмены операции
        await show_menu(chat_id, user_id, callback.bot)



async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())