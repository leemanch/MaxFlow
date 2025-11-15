import asyncio
import logging
import os
import re
from typing import Dict, Any, Optional

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

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Словари для хранения состояния пользователей
user_states: Dict[int, str] = {}
user_temp_data: Dict[int, Dict[str, Any]] = {}

# Индексы для навигации по заявкам
current_dean_request_index: Dict[int, int] = {}
current_study_request_index: Dict[int, int] = {}
current_complaint_index: Dict[int, int] = {}
current_dorm_pass_index: Dict[int, int] = {}
current_unban_request_index: Dict[int, int] = {}
current_admission_news_index: Dict[int, int] = {}

# Инициализация баз данных
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


async def check_blacklist(user_id: int, chat_id: int, bot: Bot) -> bool:
    """Проверяет, находится ли пользователь в черном списке"""
    blacklisted_user = black_list.is_in_blacklist(user_id)
    if blacklisted_user:
        message = (
            f"Вы находитесь в черном списке и не можете использовать бота.\n"
            f"Причина: {blacklisted_user['reason']}\n"
            f"Дата добавления: {blacklisted_user['date_added']}\n"
            f"Заявка на разбан: /unban_request <Оправдание>"
        )
        await bot.send_message(chat_id=chat_id, text=message)
        return True
    return False


async def show_menu(chat_id: int, user_id: int, bot: Bot) -> None:
    """Функция для отображения меню"""
    role = users.get_user_role(user_id)
    if not role:
        return

    builder = InlineKeyboardBuilder()

    if role == "admin":
        unban_count = unban_requests.get_pending_requests_count()
        unban_text = f'Заявки на разбан ({unban_count})'

        builder.row(CallbackButton(text='Заявки от деканата', payload='requests_dean'))
        builder.row(
            CallbackButton(text='Выдать роль', payload='add_role'),
            CallbackButton(text='Удалить роль', payload='remove_role')
        )
        builder.row(
            CallbackButton(text='Добавить в ЧС', payload='add_user_to_black_list'),
            CallbackButton(text='Показать ЧС', payload='show_blacklist')
        )
        builder.row(
            CallbackButton(text='Удалить из ЧС', payload='remove_from_blacklist'),
            CallbackButton(text=unban_text, payload='show_unban_requests')
        )

    elif role == "dean":
        builder.row(CallbackButton(text='Заявки', payload='requests_student'))

    elif role == "student":
        builder.row(CallbackButton(text='Заказать справку об обучении', payload='information_about_training'))
        builder.row(CallbackButton(text='Подписки на новости', payload='subscribe_news'))
        builder.row(CallbackButton(text='Сообщить о проблеме', payload='submit_problem'))
        builder.row(CallbackButton(text='Запрос на пропуск', payload='submit_pass_request'))
        builder.row(CallbackButton(text='Электронная библиотека', payload='electronic_library'))

    elif role == "applicant":
        builder.row(
            CallbackButton(text='О ВУЗе', payload='about_university'),
            CallbackButton(text="События", payload='future_events')
        )

    elif role == "smm":
        builder.row(
            CallbackButton(text='Добавить новость', payload='add_news'),
            CallbackButton(text='Удалить новость', payload='delete_news')
        )
        builder.row(CallbackButton(text='Редактировать новость', payload='reedit_news'))
        builder.row(CallbackButton(text='Управление событиями', payload='manage_events'))

    elif role == "head_dormitory":
        builder.row(
            CallbackButton(text='Жалобы студентов', payload='students_complaints'),
            CallbackButton(text='Рассылка информации', payload='sending_info')
        )
        builder.row(CallbackButton(text='Заявки на пропуск', payload='pass_requests'))

    await bot.send_message(
        chat_id=chat_id,
        text="Выберите действие",
        attachments=[builder.as_markup()]
    )


async def show_next_unban_request(chat_id: int, bot: Bot, index: int = 0) -> None:
    """Показывает следующую заявку на разбан с кнопками управления"""
    all_requests = unban_requests.get_all_pending_requests()

    if not all_requests:
        await bot.send_message(chat_id=chat_id, text="Активных заявок на разбан нет.")
        return

    current_unban_request_index[chat_id] = index
    request = all_requests[index]

    message_text = (
        f"Заявки на разбан ({len(all_requests)} активных)\n\n"
        f"ID заявки: {request['id']}\n"
        f"Пользователь: {request['username']}\n"
        f"User ID: {request['user_id']}\n"
        f"Дата подачи: {request['date']}\n"
        f"Описание:\n{request['description']}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Одобрить", payload=f"approve_unban_{request['id']}"),
        CallbackButton(text="Отклонить", payload=f"reject_unban_{request['id']}")
    )
    builder.row(
        CallbackButton(text="Следующая", payload="next_unban_request"),
        CallbackButton(text="Стоп", payload="stop_unban_requests")
    )

    await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        attachments=[builder.as_markup()]
    )


async def show_next_complaint(chat_id: int, bot: Bot, index: int = 0) -> None:
    """Показывает следующую жалобу студента"""
    complaints = student_complaints.get_all_complaints()
    if not complaints:
        await bot.send_message(chat_id=chat_id, text="На данный момент жалоб нет.")
        return

    current_complaint_index[chat_id] = index
    complaint = complaints[index]

    text = (
        f"Всего жалоб {len(complaints)}\n\n"
        f"# {complaint['id']}\n"
        f"username: {complaint['username']}\n"
        f"Комната: {complaint['number_room']}\n"
        f"Текст: {complaint['description']}\n"
        f"Дата: {complaint['date_created']}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Ответить", payload=f"replyComplaint_{complaint['id']}"),
        CallbackButton(text="Закрыть", payload=f"closeComplaint_{complaint['id']}")
    )
    builder.row(
        CallbackButton(text="Следующая", payload="next_complaint"),
        CallbackButton(text="Стоп", payload="stop_complaints")
    )

    await bot.send_message(chat_id=chat_id, text=text, attachments=[builder.as_markup()])


async def show_next_pass_request(chat_id: int, bot: Bot, index: int = 0) -> None:
    """Показывает следующую заявку на пропуск"""
    all_requests = dormitory_requests.get_all_requests()
    if not all_requests:
        await bot.send_message(chat_id=chat_id, text="На данный момент заявок на пропуск нет.")
        return

    current_dorm_pass_index[chat_id] = index
    request = all_requests[index]

    message_text = (
        f"Всего заявок: {len(all_requests)}\n\n"
        f"ID: {request['id']}\n"
        f"Имя: {request['username']}\n"
        f"Группа: {request['user_group']}\n"
        f"Дата рождения: {request['date_of_birthday']}\n"
        f"Причина: {request['reason']}\n"
        f"Дата подачи: {request['submission_date']}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Ответить", payload=f"replyPass_{request['id']}"),
        CallbackButton(text="Автоответ", payload=f"autoReplyPass_{request['id']}"),
        CallbackButton(text="Отклонить", payload=f"rejectPass_{request['id']}")
    )
    builder.row(
        CallbackButton(text="Следующая", payload="next_pass_request"),
        CallbackButton(text="Стоп", payload="stop_pass_requests")
    )

    await bot.send_message(chat_id=chat_id, text=message_text, attachments=[builder.as_markup()])


async def show_next_request_dean(chat_id: int, bot: Bot, index: int = 0) -> None:
    """Показывает следующую заявку деканата с кнопками управления"""
    all_requests = request_dean.get_all_users()

    if not all_requests:
        await bot.send_message(chat_id=chat_id, text="На данный момент заявок нет.")
        return

    current_dean_request_index[chat_id] = index
    request = all_requests[index]

    message_text = (
        f"Всего заявок {len(all_requests)}\n\n"
        f"ID: {request['id']}\n"
        f"Имя: {request['username']}\n"
        f"Дата подачи: {request['date_created']}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Принять", payload=f"approveDean_{request['id']}"),
        CallbackButton(text="Отказать", payload=f"rejectDean_{request['id']}")
    )
    builder.row(
        CallbackButton(text="Следующая", payload="next_requestDean"),
        CallbackButton(text="Стоп", payload="stop_requests")
    )

    await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        attachments=[builder.as_markup()]
    )


async def show_next_request_student_info(chat_id: int, bot: Bot, index: int = 0) -> None:
    """Показывает следующую заявку на справку об обучении"""
    all_requests = study_certificate_requests.get_all_requests()

    if not all_requests:
        await bot.send_message(chat_id=chat_id, text="На данный момент заявок нет.")
        return

    current_study_request_index[chat_id] = index
    request = all_requests[index]

    message_text = (
        f"Всего заявок {len(all_requests)}\n\n"
        f"ID: {request['id']}\n"
        f"username: {request['username']}\n"
        f"ФИО: {request['full_name']}\n"
        f"Группа: {request['group_name']}\n"
        f"Количество: {request['count']}\n"
        f"Дата подачи: {request['date_created']}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Выдать", payload=f"approveStudy_{request['id']}"),
        CallbackButton(text="Отказать", payload=f"rejectStudy_{request['id']}")
    )
    builder.row(
        CallbackButton(text="Следующая", payload="next_requestStudy"),
        CallbackButton(text="Стоп", payload="stop_requests")
    )

    await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        attachments=[builder.as_markup()]
    )


async def update_news_messages(bot: Bot, news_item: Dict[str, Any]) -> None:
    """Обновляет сообщения новостей у подписчиков"""
    try:
        message_ids = news_item.get("message_ids", [])
        news_text = f"Новость ВУЗа\n\nЗаголовок: {news_item['title']}\n\n{news_item['description']}"

        for message_id in message_ids:
            try:
                await bot.edit_message(message_id=message_id, text=news_text)
            except Exception as e:
                logging.error(f"Ошибка при обновлении сообщения {message_id}: {e}")
                continue

    except Exception as e:
        logging.error(f"Ошибка в update_news_messages: {e}")


# Обработчики команд
@dp.bot_started()
async def bot_started(event: BotStarted):
    await event.bot.send_message(
        chat_id=event.chat_id,
        text='Привет! Отправь мне /start'
    )

@dp.message_created(Command("getadmin"))
async def getadmin(event: MessageCreated):
    admins.add_admin(event.from_user.user_id)


@dp.message_created(Command("unban_request"))
async def unban_request(event: MessageCreated):
    if black_list.is_in_blacklist(event.from_user.user_id) is None:
        await event.bot.send_message(
            user_id=event.from_user.user_id,
            text="Вы не в бане!"
        )
        return

    user_input = " ".join(event.message.body.text.split()[1:])

    if unban_requests.get_pending_request(user_id=event.from_user.user_id):
        await event.bot.send_message(
            user_id=event.from_user.user_id,
            text="У вас уже есть активная заявка! Ожидайте ответа!"
        )
        return

    await event.bot.send_message(
        user_id=event.from_user.user_id,
        text="Ваша заявка отправлена на рассмотрение! Ожидайте ответа!"
    )
    unban_requests.add_request(event.from_user.user_id, event.chat.chat_id, event.from_user.full_name, user_input)


@dp.message_created(Command('setd'))
async def set_dean(event: MessageCreated):
    if await check_blacklist(event.from_user.user_id, event.chat.chat_id, event.bot):
        return

    user_id = event.from_user.user_id

    if (dean_representatives.is_representative(user_id) and
            users.has_role(user_id, "dean")):
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Вы уже являетесь представителем деканата!"
        )
    elif request_dean.get_user(user_id=user_id) is None:
        request_dean.add_user(user_id=user_id, username=event.from_user.full_name)
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Заявка отправлена на рассмотрение!"
        )
    else:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Вы уже отправляли заявку!"
        )


@dp.message_created(Command('menu'))
async def print_menu(event: MessageCreated):
    if await check_blacklist(event.from_user.user_id, event.chat.chat_id, event.bot):
        return
    await show_menu(event.chat.chat_id, event.from_user.user_id, event.bot)


@dp.message_created(Command('start'))
async def hello(event: MessageCreated):
    if await check_blacklist(event.from_user.user_id, event.chat.chat_id, event.bot):
        return

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text='Абитуриент', payload='set_applicant'),
        CallbackButton(text='Студент', payload='set_student')
    )

    await event.message.answer(
        text="Выберите вашу роль (старая будет не действительна)",
        attachments=[builder.as_markup()]
    )
    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Используйте /menu для дальнейшей работы"
    )


@dp.message_created()
async def handle_text_input(event: MessageCreated):
    user_id = event.from_user.user_id

    if await check_blacklist(user_id, event.chat.chat_id, event.bot):
        return

    if user_id not in user_states:
        return

    current_state = user_states[user_id]
    user_input = event.message.body.text.strip()

    # Обработка различных состояний
    state_handlers = {
        "waiting_user_id": handle_waiting_user_id,
        "waiting_news_id_for_edit": handle_waiting_news_id_for_edit,
        "waiting_news_title_edit": handle_waiting_news_title_edit,
        "waiting_news_description_edit": handle_waiting_news_description_edit,
        "waiting_news_title_edit_both": handle_waiting_news_title_edit_both,
        "waiting_news_description_edit_both": handle_waiting_news_description_edit_both,
        "waiting_news_id_for_delete": handle_waiting_news_id_for_delete,
        "waiting_news_title": handle_waiting_news_title,
        "waiting_news_description": handle_waiting_news_description,
        "waiting_full_name": handle_waiting_full_name,
        "waiting_group": handle_waiting_group,
        "waiting_problem_room": handle_waiting_problem_room,
        "waiting_problem_description": handle_waiting_problem_description,
        "waiting_pass_group": handle_waiting_pass_group,
        "waiting_pass_birthdate": handle_waiting_pass_birthdate,
        "waiting_pass_reason": handle_waiting_pass_reason,
        "waiting_count": handle_waiting_count,
        "waiting_blacklist_user_id": handle_waiting_blacklist_user_id,
        "waiting_blacklist_reason": handle_waiting_blacklist_reason,
        "waiting_blacklist_remove_id": handle_waiting_blacklist_remove_id,
        "waiting_unban_description": handle_waiting_unban_description,
        "waiting_event_title": handle_waiting_event_title,
        "waiting_event_description": handle_waiting_event_description,
        "waiting_event_date": handle_waiting_event_date,
        "waiting_event_location": handle_waiting_event_location,
        "waiting_event_id_for_edit": handle_waiting_event_id_for_edit,
        "waiting_event_id_for_delete": handle_waiting_event_id_for_delete,
        "waiting_event_title_edit": handle_waiting_event_title_edit,
        "waiting_event_description_edit": handle_waiting_event_description_edit,
        "waiting_event_date_edit": handle_waiting_event_date_edit,
        "waiting_event_location_edit": handle_waiting_event_location_edit,
        "waiting_event_title_edit_all": handle_waiting_event_title_edit_all,
        "waiting_event_description_edit_all": handle_waiting_event_description_edit_all,
        "waiting_event_date_edit_all": handle_waiting_event_date_edit_all,
        "waiting_event_location_edit_all": handle_waiting_event_location_edit_all,
    }

    # Динамически вызываем обработчик состояния, если он существует
    state_handler = state_handlers.get(current_state)
    if state_handler:
        await state_handler(event, user_id, user_input)
        return

    # Обработка состояний с динамическими суффиксами
    if current_state.startswith("waiting_reply_text_"):
        await handle_waiting_reply_text(event, user_id, user_input, current_state)
    elif current_state.startswith("waiting_pass_reply_"):
        await handle_waiting_pass_reply(event, user_id, user_input, current_state)
    elif current_state.startswith("waiting_unban_reject_reason_"):
        await handle_waiting_unban_reject_reason(event, user_id, user_input, current_state)


# Функции-обработчики состояний
async def handle_waiting_user_id(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода ID пользователя"""
    try:
        target_user_id = int(user_input)

        if not users.is_user_exists(target_user_id):
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Пользователь с таким ID не найден в базе. Введите ID пользователя снова:"
            )
            return

        # Пытаемся отправить сообщение пользователю
        try:
            action_type = user_temp_data[user_id].get("action_type", "add")
            message_text = (
                f"Вас назначили на роль {user_temp_data[user_id]['selected_role']}"
                if action_type == "add" else "С вас снята роль"
            )

            await event.bot.send_message(user_id=target_user_id, text=message_text)

            user_temp_data[user_id]["target_user_id"] = target_user_id

            builder = InlineKeyboardBuilder()
            if action_type == "add":
                builder.row(
                    CallbackButton(text="Да", payload="confirm_user"),
                    CallbackButton(text="Нет", payload="deny_user"),
                    CallbackButton(text="Отмена", payload="cancel_operation")
                )
            else:
                builder.row(
                    CallbackButton(text="Да", payload="confirm_remove"),
                    CallbackButton(text="Нет", payload="deny_remove"),
                    CallbackButton(text="Отмена", payload="cancel_operation")
                )

            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Сообщение пользователю отправлено. Это нужный пользователь?",
                attachments=[builder.as_markup()]
            )

        except Exception:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Пользователь не найден. Введите ID пользователя снова:"
            )

    except ValueError:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="ID должен быть числом. Введите ID снова:"
        )


async def handle_waiting_news_id_for_edit(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода ID новости для редактирования"""
    try:
        news_id = int(user_input)
        news_item = news.get_news(news_id)
        if not news_item:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Новость с таким ID не найдена. Введите ID новости снова:"
            )
            return

        user_temp_data[user_id] = {"news_id": news_id, "current_news": news_item}

        confirmation_text = (
            f"ID: {news_item['id']}\n"
            f"Заголовок: {news_item['title']}\n"
            f"Дата: {news_item['publication_date']}\n\n"
            f"Текст: {news_item['description'][:100]}..."
            if len(news_item['description']) > 100
            else f"Текст: {news_item['description']}"
        )

        await event.bot.send_message(chat_id=event.chat.chat_id, text=confirmation_text)

        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="Заголовок", payload="edit_news_title"),
            CallbackButton(text="Текст", payload="edit_news_description")
        )
        builder.row(
            CallbackButton(text="Заголовок и текст", payload="edit_news_both"),
            CallbackButton(text="Отмена", payload="cancel_news_edit")
        )

        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Что вы хотите отредактировать?",
            attachments=[builder.as_markup()]
        )

        if user_id in user_states:
            del user_states[user_id]

    except ValueError:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="ID должен быть числом. Введите ID новости снова:"
        )


async def handle_waiting_news_title_edit(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования заголовка новости"""
    user_data = user_temp_data.get(user_id, {})
    news_id = user_data.get("news_id")
    new_title = user_input

    if news_id and new_title:
        success = news.update_news(news_id, title=new_title)
        if success:
            updated_news = news.get_news(news_id)
            await update_news_messages(event.bot, updated_news)

            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text=f"Заголовок новости успешно обновлен!\n\nНовый заголовок: {new_title}"
            )
            await show_menu(event.chat.chat_id, user_id, event.bot)
        else:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Ошибка при обновлении заголовка."
            )

    cleanup_user_state(user_id)


async def handle_waiting_news_description_edit(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования текста новости"""
    user_data = user_temp_data.get(user_id, {})
    news_id = user_data.get("news_id")
    new_description = user_input

    if news_id and new_description:
        success = news.update_news(news_id, description=new_description)
        if success:
            updated_news = news.get_news(news_id)
            await update_news_messages(event.bot, updated_news)

            message = (
                f"Текст новости успешно обновлен!\n\nНовый текст: {new_description[:100]}..."
                if len(new_description) > 100
                else f"Текст новости успешно обновлен!\n\nНовый текст: {new_description}"
            )
            await event.bot.send_message(chat_id=event.chat.chat_id, text=message)
            await show_menu(event.chat.chat_id, user_id, event.bot)
        else:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Ошибка при обновлении текста."
            )

    cleanup_user_state(user_id)


async def handle_waiting_news_title_edit_both(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования заголовка (первый шаг для полного редактирования)"""
    user_temp_data[user_id]["new_title"] = user_input
    user_states[user_id] = "waiting_news_description_edit_both"
    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Новый заголовок сохранен. Теперь введите новый текст новости:"
    )


async def handle_waiting_news_description_edit_both(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования текста (второй шаг для полного редактирования)"""
    user_data = user_temp_data.get(user_id, {})
    news_id = user_data.get("news_id")
    new_title = user_data.get("new_title")
    new_description = user_input

    if news_id and new_title and new_description:
        success = news.update_news(news_id, title=new_title, description=new_description)
        if success:
            updated_news = news.get_news(news_id)
            await update_news_messages(event.bot, updated_news)

            message = (
                f"Новость полностью обновлена!\n\nНовый заголовок: {new_title}\n\nНовый текст: {new_description[:100]}..."
                if len(new_description) > 100
                else f"Новость полностью обновлена!\n\nНовый заголовок: {new_title}\n\nНовый текст: {new_description}"
            )
            await event.bot.send_message(chat_id=event.chat.chat_id, text=message)
            await show_menu(event.chat.chat_id, user_id, event.bot)
        else:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Ошибка при обновлении новости."
            )

    cleanup_user_state(user_id)


async def handle_waiting_news_id_for_delete(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода ID новости для удаления"""
    try:
        news_id = int(user_input)
        news_item = news.get_news(news_id)
        if not news_item:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Новость с таким ID не найдена. Введите ID новости снова:"
            )
            return

        confirmation_text = (
            f"Вы уверены, что хотите удалить эту новость?\n\n"
            f"ID: {news_item['id']}\n"
            f"Заголовок: {news_item['title']}\n"
            f"Дата: {news_item['publication_date']}\n\n"
            f"Текст: {news_item['description'][:100]}..."
            if len(news_item['description']) > 100
            else f"Текст: {news_item['description']}"
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="Да, удалить", payload=f"confirm_delete_news_{news_id}"),
            CallbackButton(text="Нет, отмена", payload="cancel_delete_news")
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
            text="ID должен быть числом. Введите ID новости снова:"
        )


async def handle_waiting_news_title(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода заголовка новости"""
    user_temp_data[user_id]["title"] = user_input
    user_states[user_id] = "waiting_news_description"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Заголовок сохранен. Теперь введите текст новости одним сообщением:"
    )


async def handle_waiting_news_description(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода текста новости"""
    user_temp_data[user_id]["description"] = user_input

    title = user_temp_data[user_id]["title"]
    description = user_temp_data[user_id]["description"]

    preview_text = (
        f"Предпросмотр новости ВУЗа\n\n"
        f"Заголовок: {title}\n\n"
        f"Текст:\n{description}\n\n"
        "---\nВыберите действие:"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Разослать", payload="publish_news"),
        CallbackButton(text="Редактировать", payload="edit_news"),
        CallbackButton(text="Отмена", payload="cancel_news")
    )

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text=preview_text,
        attachments=[builder.as_markup()]
    )

    del user_states[user_id]


async def handle_waiting_full_name(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода ФИО для справки об обучении"""
    user_temp_data[user_id] = {"full_name": user_input}
    user_states[user_id] = "waiting_group"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="ФИО сохранено. Теперь введите вашу группу (Например: ИУК4-31Б):"
    )


async def handle_waiting_group(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода группы для справки об обучении"""
    user_temp_data[user_id]["group_name"] = user_input
    user_states[user_id] = "waiting_count"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Группа сохранена. Теперь введите количество справок:"
    )


async def handle_waiting_problem_room(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода номера комнаты для жалобы"""
    user_temp_data[user_id] = user_temp_data.get(user_id, {})
    user_temp_data[user_id]["number_room"] = user_input
    user_states[user_id] = "waiting_problem_description"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Опишите проблему (Например: Сломался слив):"
    )


async def handle_waiting_problem_description(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода описания проблемы"""
    description = user_input
    data = user_temp_data.get(user_id, {})
    number_room = data.get("number_room")

    if not number_room:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Не указан номер комнаты. Начните заново."
        )
        cleanup_user_state(user_id)
        return

    complaint_id = student_complaints.add_complaint(
        user_id=user_id,
        chat_id=event.chat.chat_id,
        username=event.from_user.full_name,
        description=description,
        number_room=number_room
    )

    cleanup_user_state(user_id)

    if complaint_id:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text=f"Заявка отправлена!\nID: {complaint_id}\nКомната: {number_room}\nПроблема: {description}"
        )
    else:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Ошибка при отправке заявки. Попробуйте ещё раз."
        )


async def handle_waiting_pass_group(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода группы для заявки на пропуск"""
    user_temp_data[user_id] = {"user_group": user_input}
    user_states[user_id] = "waiting_pass_birthdate"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Введите дату рождения (ДД.ММ.ГГГГ):"
    )


async def handle_waiting_pass_birthdate(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода даты рождения для заявки на пропуск"""
    pattern = r"^\d{2}\.\d{2}\.\d{4}$"
    if not re.match(pattern, user_input):
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Формат даты: ДД.ММ.ГГГГ (Например: 17.04.2005). Введите снова:"
        )
        return

    user_temp_data[user_id]["date_of_birthday"] = user_input
    user_states[user_id] = "waiting_pass_reason"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Введите причину потери пропуска:"
    )


async def handle_waiting_pass_reason(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода причины для заявки на пропуск"""
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

    cleanup_user_state(user_id)

    if success:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text=(
                f"Заявка на пропуск отправлена!\n"
                f"Группа: {user_group}\n"
                f"Дата рождения: {date_of_birthday}\n"
                f"Причина: {reason}"
            )
        )
    else:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Ошибка при отправке заявки."
        )


async def handle_waiting_reply_text(event: MessageCreated, user_id: int, user_input: str, current_state: str):
    """Обработка ввода текста ответа на жалобу"""
    complaint_id = int(current_state.split("_")[-1])
    reply_text = user_input
    complaint = student_complaints.get_complaint(complaint_id)

    cleanup_user_state(user_id)

    if not complaint:
        await event.bot.send_message(chat_id=event.chat.chat_id, text="Жалоба не найдена.")
        return

    await event.bot.send_message(
        chat_id=complaint["chat_id"],
        text=f"Ваше обращение рассмотрено.\nОтвет: {reply_text}"
    )

    student_complaints.delete_complaint(complaint_id)
    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Ответ отправлен студенту, жалоба закрыта."
    )


async def handle_waiting_pass_reply(event: MessageCreated, user_id: int, user_input: str, current_state: str):
    """Обработка ввода текста ответа на заявку о пропуске"""
    request_id = int(current_state.split("_")[-1])
    reply_text = user_input

    cleanup_user_state(user_id)

    all_requests = dormitory_requests.get_all_requests()
    target = next((r for r in all_requests if r["id"] == request_id), None)

    if not target:
        await event.bot.send_message(chat_id=event.chat.chat_id, text="Заявка не найдена.")
        return

    await event.bot.send_message(
        chat_id=target["chat_id"],
        text=f"Ваше обращение рассмотрено.\nОтвет: {reply_text}"
    )

    dormitory_requests.delete_request(request_id)
    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Ответ отправлен студенту, заявка закрыта."
    )


async def handle_waiting_count(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода количества справок"""
    try:
        count = int(user_input)
        if count <= 0:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Количество должно быть положительным числом. Введите количество справок:"
            )
            return
        if count > 5:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Максимальное количество справок - 5. Введите количество справок:"
            )
            return

        user_data = user_temp_data.get(user_id, {})
        full_name = user_data.get("full_name")
        group_name = user_data.get("group_name")

        if not full_name or not group_name:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Ошибка: данные не сохранены. Начните заново."
            )
            cleanup_user_state(user_id)
            return

        success = study_certificate_requests.add_request(
            user_id,
            event.from_user.full_name,
            full_name,
            group_name,
            count
        )

        cleanup_user_state(user_id)

        if success:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text=(
                    f"Заявка на справку успешно создана!\n\n"
                    f"Данные заявки:\n"
                    f"ФИО: {full_name}\n"
                    f"Группа: {group_name}\n"
                    f"Количество справок: {count}"
                )
            )
            await show_menu(event.chat.chat_id, user_id, event.bot)
        else:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Произошла ошибка при создании заявки. Попробуйте позже."
            )

    except ValueError:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Количество должно быть числом. Введите количество справок:"
        )


async def handle_waiting_blacklist_user_id(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода ID пользователя для добавления в черный список"""
    try:
        target_user_id = int(user_input)

        if not users.is_user_exists(target_user_id):
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Пользователь с таким ID не найден в базе. Введите ID пользователя снова:"
            )
            return

        if black_list.is_in_blacklist(target_user_id):
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Этот пользователь уже находится в черном списке. Введите другой ID:"
            )
            return

        user_temp_data[user_id] = {"target_user_id": target_user_id}
        user_states[user_id] = "waiting_blacklist_reason"

        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="ID пользователя принят. Теперь введите причину добавления в черный список:"
        )

    except ValueError:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="ID должен быть числом. Введите ID пользователя снова:"
        )


async def handle_waiting_blacklist_reason(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода причины для добавления в черный список"""
    reason = user_input
    user_data = user_temp_data.get(user_id, {})
    target_user_id = user_data.get("target_user_id")

    if not target_user_id:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Ошибка: данные не найдены. Начните заново."
        )
        cleanup_user_state(user_id)
        return

    success = black_list.add_to_blacklist(target_user_id, reason)

    if success:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text=f"Пользователь {target_user_id} успешно добавлен в черный список!\n\nПричина: {reason}"
        )

        try:
            await event.bot.send_message(
                user_id=target_user_id,
                text=f"Вы были добавлены в черный список бота.\nПричина: {reason}"
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить пользователя {target_user_id}: {e}")
    else:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Произошла ошибка при добавлении в черный список. Попробуйте позже."
        )

    cleanup_user_state(user_id)
    await show_menu(event.chat.chat_id, user_id, event.bot)


async def handle_waiting_blacklist_remove_id(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода ID пользователя для удаления из черного списка"""
    try:
        target_user_id = int(user_input)

        if not black_list.is_in_blacklist(target_user_id):
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Пользователь с таким ID не найден в черном списке. Введите ID снова:"
            )
            return

        success = black_list.remove_from_blacklist(target_user_id)

        if success:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text=f"Пользователь {target_user_id} успешно удален из черного списка!"
            )

            try:
                await event.bot.send_message(
                    user_id=target_user_id,
                    text="Вы были удалены из черного списка бота. Теперь вы можете использовать бота снова."
                )
            except Exception as e:
                logging.error(f"Не удалось уведомить пользователя {target_user_id}: {e}")
        else:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Произошла ошибка при удалении из черного списка. Попробуйте позже."
            )

        cleanup_user_state(user_id)
        await show_menu(event.chat.chat_id, user_id, event.bot)

    except ValueError:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="ID должен быть числом. Введите ID пользователя снова:"
        )


async def handle_waiting_unban_description(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода описания для заявки на разбан"""
    description = user_input
    user_data = user_temp_data.get(user_id, {})

    success = unban_requests.add_request(
        user_id=user_id,
        chat_id=event.chat.chat_id,
        username=event.from_user.full_name,
        description=description
    )

    if success:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Ваша заявка на разбан отправлена на рассмотрение. Мы уведомим вас о решении."
        )
    else:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="У вас уже есть активная заявка на разбан. Дождитесь ее рассмотрения."
        )

    cleanup_user_state(user_id)


async def handle_waiting_unban_reject_reason(event: MessageCreated, user_id: int, user_input: str, current_state: str):
    """Обработка ввода причины отклонения заявки на разбан"""
    request_id = int(current_state.split("_")[-1])
    reject_reason = user_input

    success = unban_requests.reject_request(
        request_id=request_id,
        admin_id=user_id,
        notes=reject_reason
    )

    if success:
        request = unban_requests.get_request_by_id(request_id)
        if request:
            try:
                await event.bot.send_message(
                    user_id=request['user_id'],
                    text=f"Ваша заявка на разбан отклонена.\nПричина: {reject_reason}"
                )
            except Exception as e:
                logging.error(f"Не удалось уведомить пользователя {request['user_id']}: {e}")

        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text=f"Заявка на разбан отклонена. Пользователь уведомлен."
        )
    else:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Ошибка при отклонении заявки. Возможно, заявка уже обработана."
        )

    cleanup_user_state(user_id)

    all_requests = unban_requests.get_all_pending_requests()
    if all_requests:
        current_index = current_unban_request_index.get(event.chat.chat_id, 0)
        await show_next_unban_request(event.chat.chat_id, event.bot, current_index)
    else:
        await event.bot.send_message(chat_id=event.chat.chat_id, text="Заявки на разбан закончились!")
        await show_menu(event.chat.chat_id, user_id, event.bot)


async def handle_waiting_event_title(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода заголовка события"""
    user_temp_data[user_id] = {"title": user_input}
    user_states[user_id] = "waiting_event_description"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Заголовок сохранен. Теперь введите описание события:"
    )


async def handle_waiting_event_description(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода описания события"""
    user_temp_data[user_id]["description"] = user_input
    user_states[user_id] = "waiting_event_date"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Описание сохранено. Теперь введите дату и время события (формат: ДД.ММ.ГГГГ ЧЧ:ММ):"
    )


async def handle_waiting_event_date(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода даты события"""
    user_temp_data[user_id]["event_date"] = user_input
    user_states[user_id] = "waiting_event_location"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Дата сохранена. Теперь введите место проведения события:"
    )


async def handle_waiting_event_location(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода места проведения события"""
    location = user_input
    user_data = user_temp_data.get(user_id, {})
    title = user_data.get("title")
    description = user_data.get("description")
    event_date = user_data.get("event_date")

    if not all([title, description, event_date, location]):
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Ошибка: данные не сохранены. Начните заново."
        )
        cleanup_user_state(user_id)
        return

    event_id = events_db.add_event(title, description, event_date, location)

    if event_id:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text=(
                f"Событие успешно добавлено!\n\n"
                f"{title}\n"
                f"{event_date}\n"
                f"{location}\n\n"
                f"{description}"
            )
        )
    else:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Ошибка при добавлении события. Попробуйте позже."
        )

    cleanup_user_state(user_id)
    await show_menu(event.chat.chat_id, user_id, event.bot)


async def handle_waiting_event_id_for_edit(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода ID события для редактирования"""
    try:
        event_id = int(user_input)
        event_item = events_db.get_event(event_id)
        if not event_item:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Событие с таким ID не найдено. Введите ID события снова:"
            )
            return

        user_temp_data[user_id] = {"event_id": event_id, "current_event": event_item}

        confirmation_text = (
            f"ID: {event_item['id']}\n"
            f"Заголовок: {event_item['title']}\n"
            f"Описание: {event_item['description']}\n"
            f"Дата: {event_item['event_date']}\n"
            f"Место: {event_item['location']}\n"
        )

        await event.bot.send_message(chat_id=event.chat.chat_id, text=confirmation_text)

        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="Заголовок", payload="edit_event_title"),
            CallbackButton(text="Описание", payload="edit_event_description")
        )
        builder.row(
            CallbackButton(text="Дата", payload="edit_event_date"),
            CallbackButton(text="Место", payload="edit_event_location")
        )
        builder.row(
            CallbackButton(text="Все поля", payload="edit_event_all"),
            CallbackButton(text="Отмена", payload="cancel_event_edit")
        )

        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="Что вы хотите отредактировать?",
            attachments=[builder.as_markup()]
        )

        if user_id in user_states:
            del user_states[user_id]

    except ValueError:
        await event.bot.send_message(
            chat_id=event.chat.chat_id,
            text="ID должен быть числом. Введите ID события снова:"
        )


async def handle_waiting_event_id_for_delete(event: MessageCreated, user_id: int, user_input: str):
    """Обработка ввода ID события для удаления"""
    try:
        event_id = int(user_input)
        event_item = events_db.get_event(event_id)
        if not event_item:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Событие с таким ID не найдено. Введите ID события снова:"
            )
            return

        confirmation_text = (
            f"Вы уверены, что хотите удалить это событие?\n\n"
            f"ID: {event_item['id']}\n"
            f"Заголовок: {event_item['title']}\n"
            f"Дата: {event_item['event_date']}\n"
            f"Место: {event_item['location']}\n"
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="Да, удалить", payload=f"confirm_delete_event_{event_id}"),
            CallbackButton(text="Нет, отмена", payload="cancel_delete_event")
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
            text="ID должен быть числом. Введите ID события снова:"
        )


async def handle_waiting_event_title_edit(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования заголовка события"""
    user_data = user_temp_data.get(user_id, {})
    event_id = user_data.get("event_id")
    new_title = user_input

    if event_id and new_title:
        success = events_db.update_event(event_id, title=new_title)
        if success:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text=f"Заголовок события успешно обновлен!\n\nНовый заголовок: {new_title}"
            )
        else:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Ошибка при обновлении заголовка."
            )

    cleanup_user_state(user_id)
    await show_menu(event.chat.chat_id, user_id, event.bot)


async def handle_waiting_event_description_edit(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования описания события"""
    user_data = user_temp_data.get(user_id, {})
    event_id = user_data.get("event_id")
    new_description = user_input

    if event_id and new_description:
        success = events_db.update_event(event_id, description=new_description)
        if success:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text=f"Описание события успешно обновлено!\n\nНовое описание: {new_description}"
            )
        else:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Ошибка при обновлении описания."
            )

    cleanup_user_state(user_id)
    await show_menu(event.chat.chat_id, user_id, event.bot)


async def handle_waiting_event_date_edit(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования даты события"""
    user_data = user_temp_data.get(user_id, {})
    event_id = user_data.get("event_id")
    new_date = user_input

    if event_id and new_date:
        success = events_db.update_event(event_id, event_date=new_date)
        if success:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text=f"Дата события успешно обновлена!\n\nНовая дата: {new_date}"
            )
        else:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Ошибка при обновлении даты."
            )

    cleanup_user_state(user_id)
    await show_menu(event.chat.chat_id, user_id, event.bot)


async def handle_waiting_event_location_edit(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования места события"""
    user_data = user_temp_data.get(user_id, {})
    event_id = user_data.get("event_id")
    new_location = user_input

    if event_id and new_location:
        success = events_db.update_event(event_id, location=new_location)
        if success:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text=f"Место события успешно обновлено!\n\nНовое место: {new_location}"
            )
        else:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Ошибка при обновлении места."
            )

    cleanup_user_state(user_id)
    await show_menu(event.chat.chat_id, user_id, event.bot)


async def handle_waiting_event_title_edit_all(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования заголовка (первый шаг полного редактирования)"""
    user_temp_data[user_id]["new_title"] = user_input
    user_states[user_id] = "waiting_event_description_edit_all"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Новый заголовок сохранен. Теперь введите новое описание события:"
    )


async def handle_waiting_event_description_edit_all(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования описания (второй шаг полного редактирования)"""
    user_temp_data[user_id]["new_description"] = user_input
    user_states[user_id] = "waiting_event_date_edit_all"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Новое описание сохранено. Теперь введите новую дату события (формат: ДД.ММ.ГГГГ ЧЧ:ММ):"
    )


async def handle_waiting_event_date_edit_all(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования даты (третий шаг полного редактирования)"""
    user_temp_data[user_id]["new_date"] = user_input
    user_states[user_id] = "waiting_event_location_edit_all"

    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text="Новая дата сохранена. Теперь введите новое место проведения события:"
    )


async def handle_waiting_event_location_edit_all(event: MessageCreated, user_id: int, user_input: str):
    """Обработка редактирования места (четвертый шаг полного редактирования)"""
    user_data = user_temp_data.get(user_id, {})
    event_id = user_data.get("event_id")
    new_title = user_data.get("new_title")
    new_description = user_data.get("new_description")
    new_date = user_data.get("new_date")
    new_location = user_input

    if event_id and new_title and new_description and new_date and new_location:
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
                text=(
                    f"Событие полностью обновлено!\n\n"
                    f"Новый заголовок: {new_title}\n\n"
                    f"Новое описание: {new_description}\n\n"
                    f"Новая дата: {new_date}\n\n"
                    f"Новое место: {new_location}"
                )
            )
        else:
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="Ошибка при обновлении события."
            )

    cleanup_user_state(user_id)
    await show_menu(event.chat.chat_id, user_id, event.bot)


def cleanup_user_state(user_id: int) -> None:
    """Очищает состояние и временные данные пользователя"""
    if user_id in user_states:
        del user_states[user_id]
    if user_id in user_temp_data:
        del user_temp_data[user_id]


# Обработчики callback'ов
@dp.message_callback()
async def message_callback(callback: MessageCallback):
    payload = callback.callback.payload
    chat_id = callback.chat.chat_id
    user_id = callback.from_user.user_id

    # Удаляем меню при выборе любого действия
    try:
        await callback.message.delete()
    except Exception as e:
        logging.error(f"Ошибка при удалении меню: {e}")

    # Группируем обработчики по функциональности
    navigation_handlers = {
        "requests_dean": lambda: show_next_request_dean(chat_id, callback.bot, 0),
        "requests_student": lambda: show_next_request_student_info(chat_id, callback.bot, 0),
        "students_complaints": lambda: show_next_complaint(chat_id, callback.bot, 0),
        "pass_requests": lambda: show_next_pass_request(chat_id, callback.bot, 0),
        "show_unban_requests": lambda: show_next_unban_request(chat_id, callback.bot, 0),
        "next_requestDean": handle_next_request_dean,
        "next_requestStudy": handle_next_request_study,
        "next_complaint": handle_next_complaint,
        "next_pass_request": handle_next_pass_request,
        "next_unban_request": lambda: handle_next_unban_request(callback, chat_id),
        "stop_requests": lambda: callback.bot.send_message(chat_id=chat_id, text="Просмотр заявок остановлен."),
        "stop_complaints": lambda: callback.message.answer("Просмотр жалоб остановлен."),
        "stop_pass_requests": lambda: callback.message.answer("Просмотр заявок на пропуск остановлен."),
        "stop_unban_requests": lambda: callback.bot.send_message(chat_id=chat_id,
                                                                 text="Просмотр заявок на разбан остановлен."),
    }

    action_handlers = {
        "information_about_training": handle_information_about_training,
        "submit_problem": handle_submit_problem,
        "submit_pass_request": handle_submit_pass_request,
        "electronic_library": handle_electronic_library,
        "about_university": handle_about_university,
        "subscribe_news": handle_subscribe_news,
        "subscribe_news_university": handle_subscribe_news_university,
        "subscribe_news_dormitory": handle_subscribe_news_dormitory,
        "add_news": handle_add_news,
        "delete_news": handle_delete_news,
        "reedit_news": handle_reedit_news,
        "publish_news": handle_publish_news,
        "edit_news": handle_edit_news,
        "cancel_news": handle_cancel_news,
        "edit_news_title": handle_edit_news_title,
        "edit_news_description": handle_edit_news_description,
        "edit_news_both": handle_edit_news_both,
        "cancel_news_edit": handle_cancel_news_edit,
        "add_user_to_black_list": handle_add_user_to_black_list,
        "show_blacklist": handle_show_blacklist,
        "remove_from_blacklist": handle_remove_from_blacklist,
        "add_role": handle_add_role,
        "remove_role": handle_remove_role,
        "set_applicant": handle_set_applicant,
        "set_student": handle_set_student,
        "confirm_user": handle_confirm_user,
        "deny_user": handle_deny_user,
        "confirm_remove": handle_confirm_remove,
        "deny_remove": handle_deny_remove,
        "cancel_operation": handle_cancel_operation,
        "future_events": handle_future_events,
        "manage_events": handle_manage_events,
        "add_event": handle_add_event,
        "list_events": handle_list_events,
        "edit_event": handle_edit_event,
        "delete_event": handle_delete_event,
        "edit_event_title": handle_edit_event_title,
        "edit_event_description": handle_edit_event_description,
        "edit_event_date": handle_edit_event_date,
        "edit_event_location": handle_edit_event_location,
        "edit_event_all": handle_edit_event_all,
        "cancel_event_edit": handle_cancel_event_edit,
        "cancel_delete_news": handle_cancel_delete_news,
        "cancel_delete_event": handle_cancel_delete_event,
    }

    # Обработка навигационных callback'ов
    if payload in navigation_handlers:
        await navigation_handlers[payload]()
        if payload.startswith("stop_"):
            await show_menu(chat_id, user_id, callback.bot)
        return

    # Обработка action callback'ов
    if payload in action_handlers:
        await action_handlers[payload](callback, chat_id, user_id)
        return

    # Обработка callback'ов с префиксами
    if payload.startswith("approveDean_"):
        await handle_approve_dean(callback, payload, chat_id, user_id)
    elif payload.startswith("rejectDean_"):
        await handle_reject_dean(callback, payload, chat_id, user_id)
    elif payload.startswith("approveStudy_"):
        await handle_approve_study(callback, payload, chat_id, user_id)
    elif payload.startswith("rejectStudy_"):
        await handle_reject_study(callback, payload, chat_id, user_id)
    elif payload.startswith("approve_unban_"):
        await handle_approve_unban(callback, payload, chat_id, user_id)
    elif payload.startswith("reject_unban_"):
        await handle_reject_unban(callback, payload, chat_id, user_id)
    elif payload.startswith("replyComplaint_"):
        await handle_reply_complaint(callback, payload)
    elif payload.startswith("closeComplaint_"):
        await handle_close_complaint(callback, payload, chat_id)
    elif payload.startswith("replyPass_"):
        await handle_reply_pass(callback, payload)
    elif payload.startswith("autoReplyPass_"):
        await handle_auto_reply_pass(callback, payload)
    elif payload.startswith("rejectPass_"):
        await handle_reject_pass(callback, payload)
    elif payload.startswith("confirm_delete_news_"):
        await handle_confirm_delete_news(callback, payload, chat_id, user_id)
    elif payload.startswith("confirm_delete_event_"):
        await handle_confirm_delete_event(callback, payload, chat_id, user_id)
    elif payload.startswith("role_"):
        await handle_role_selection(callback, payload, chat_id, user_id)


# Навигационные обработчики
async def handle_next_request_dean(callback, chat_id):
    all_requests = request_dean.get_all_users()
    if not all_requests:
        await callback.bot.send_message(chat_id=chat_id, text="Заявок нет!")
        return
    current_index = current_dean_request_index.get(chat_id, 0)
    next_index = (current_index + 1) % len(all_requests)
    await show_next_request_dean(chat_id, callback.bot, next_index)


async def handle_next_request_study(callback, chat_id):
    all_requests = study_certificate_requests.get_all_requests()
    if not all_requests:
        await callback.bot.send_message(chat_id=chat_id, text="Заявок нет!")
        return
    current_index = current_study_request_index.get(chat_id, 0)
    next_index = (current_index + 1) % len(all_requests)
    await show_next_request_student_info(chat_id, callback.bot, next_index)


async def handle_next_complaint(callback, chat_id):
    complaints = student_complaints.get_all_complaints()
    if not complaints:
        await callback.message.answer("Жалоб нет!")
        return
    current_index = current_complaint_index.get(chat_id, 0)
    next_index = (current_index + 1) % len(complaints)
    await show_next_complaint(chat_id, callback.bot, next_index)


async def handle_next_pass_request(callback, chat_id):
    all_requests = dormitory_requests.get_all_requests()
    if not all_requests:
        await callback.message.answer("Заявок на пропуск нет!")
        return
    current_index = current_dorm_pass_index.get(chat_id, 0)
    next_index = (current_index + 1) % len(all_requests)
    await show_next_pass_request(chat_id, callback.bot, next_index)


async def handle_next_unban_request(callback, chat_id):
    all_requests = unban_requests.get_all_pending_requests()
    if not all_requests:
        await callback.bot.send_message(chat_id=chat_id, text="Заявок на разбан нет!")
        return
    current_index = current_unban_request_index.get(chat_id, 0)
    next_index = (current_index + 1) % len(all_requests)
    await show_next_unban_request(chat_id, callback.bot, next_index)


# Action обработчики
async def handle_information_about_training(callback, chat_id, user_id):
    user_states[user_id] = "waiting_full_name"
    await callback.bot.send_message(
        chat_id=chat_id,
        text="Заполните данные для заявки на справку об обучении.\n\nВведите ваше ФИО (Например: Иванов Иван Иванович):"
    )


async def handle_submit_problem(callback, chat_id, user_id):
    user_states[user_id] = "waiting_problem_room"
    await callback.message.answer("Введите номер комнаты (Например: 1.4.12):")


async def handle_submit_pass_request(callback, chat_id, user_id):
    user_states[user_id] = "waiting_pass_group"
    await callback.message.answer("Введите вашу группу:")


async def handle_electronic_library(callback, chat_id, user_id):
    await callback.bot.send_message(
        chat_id=chat_id,
        text='''Информация по использованию электронной библиотеки
        Подключение осуществляется через сеть Интернет, в многопользовательском режиме по IP-адресам с компьютеров КФ МГТУ им. Н.Э. Баумана.
        Для того, чтобы начать пользоваться электронной библиотекой, вам необходимо обратиться в кабинет УАК3.216 для получения абонемента 1-2 курсов и в УАК3.217 для получения абонемента 3-6 курсов
        Для получения дополнительной информации перейдите по ссылке:"
        https://kf.bmstu.ru/units/nauchno-tehnicheskaya-biblioteka/elektronnye-informacionnye-resursy'''
    )
    await show_menu(chat_id, user_id, callback.bot)

async def handle_about_university(callback, chat_id, user_id):
    await callback.message.answer(
        text=(
            "В настоящее время Калужский филиал МГТУ им. Н. Э. Баумана является ведущим техническим вузом области, авторитетным и самым крупным из филиалов технических вузов России.\n\n"
            "Основан в 1959 году.\n"
            "Назван в честь Российского революционера Николая Эрнестовича Баумана.\n"
            "В филиале обучаются тысячи студентов по инженерным и IT‑направлениям.\n"
            "В распоряжении филиала несколько учебных корпусов и общежития.\n"
            "Подробнее: https://kf.bmstu.ru/"
        )
    )
    await show_menu(chat_id, user_id, callback.bot)

async def handle_subscribe_news(callback, chat_id, user_id):
    mailing_university = mailings.is_subscribed(user_id, "university")
    mailing_dormitory = mailings.is_subscribed(user_id, "dormitory")

    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(
        text="Подписаться" if not mailing_university else "Отписаться",
        payload="subscribe_news_university"
    ))

    await callback.bot.send_message(
        chat_id=chat_id,
        text=f"Подписка на новости ВУЗа: {'Подписан' if mailing_university else 'Не подписан'}",
        attachments=[builder.as_markup()]
    )

    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(
        text="Подписаться" if not mailing_dormitory else "Отписаться",
        payload="subscribe_news_dormitory"
    ))

    await callback.bot.send_message(
        chat_id=chat_id,
        text=f"Подписка на новости Общежития: {'Подписан' if mailing_dormitory else 'Не подписан'}",
        attachments=[builder.as_markup()]
    )


async def handle_subscribe_news_university(callback, chat_id, user_id):
    await callback.message.delete()

    if mailings.is_subscribed(user_id, "university"):
        mailings.remove_subscription(user_id, "university")
        new_status = False
    else:
        mailings.add_subscription(user_id, callback.chat.chat_id, "university")
        new_status = True

    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(
        text="Подписаться" if not new_status else "Отписаться",
        payload="subscribe_news_university"
    ))

    await callback.bot.send_message(
        chat_id=chat_id,
        text=f"Подписка на новости ВУЗа: {'Подписан' if new_status else 'Не подписан'}",
        attachments=[builder.as_markup()]
    )
    await show_menu(chat_id, user_id, callback.bot)


async def handle_subscribe_news_dormitory(callback, chat_id, user_id):
    await callback.message.delete()

    if mailings.is_subscribed(user_id, "dormitory"):
        mailings.remove_subscription(user_id, "dormitory")
        new_status = False
    else:
        mailings.add_subscription(user_id, callback.chat.chat_id, "dormitory")
        new_status = True

    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(
        text="Подписаться" if not new_status else "Отписаться",
        payload="subscribe_news_dormitory"
    ))

    await callback.bot.send_message(
        chat_id=chat_id,
        text=f"Подписка на новости Общежития: {'Подписан' if new_status else 'Не подписан'}",
        attachments=[builder.as_markup()]
    )
    await show_menu(chat_id, user_id, callback.bot)


async def handle_add_news(callback, chat_id, user_id):
    user_states[user_id] = "waiting_news_title"
    user_temp_data[user_id] = {}
    await callback.bot.send_message(chat_id=chat_id, text="Введите заголовок новости ВУЗа:")


async def handle_delete_news(callback, chat_id, user_id):
    all_news = news.get_all_news()
    if not all_news:
        await callback.bot.send_message(chat_id=chat_id, text="Новостей для удаления не найдено.")
        return

    news_list_text = "Список всех новостей ВУЗа:\n\n"
    for news_item in all_news:
        news_list_text += f"ID: {news_item['id']}\n"
        news_list_text += f"Заголовок: {news_item['title']}\n"
        news_list_text += f"Дата: {news_item['publication_date']}\n"
        news_list_text += "─" * 30 + "\n"

    await callback.bot.send_message(chat_id=chat_id, text=news_list_text)

    user_states[user_id] = "waiting_news_id_for_delete"
    await callback.bot.send_message(chat_id=chat_id, text="Введите ID новости для удаления:")


async def handle_reedit_news(callback, chat_id, user_id):
    all_news = news.get_all_news()
    if not all_news:
        await callback.bot.send_message(chat_id=chat_id, text="Новостей для редактирования не найдено.")
        return

    news_list_text = "Список всех новостей ВУЗа:\n\n"
    for news_item in all_news:
        news_list_text += f"ID: {news_item['id']}\n"
        news_list_text += f"Заголовок: {news_item['title']}\n"
        news_list_text += f"Дата: {news_item['publication_date']}\n"
        news_list_text += "─" * 30 + "\n"

    await callback.bot.send_message(chat_id=chat_id, text=news_list_text)

    user_states[user_id] = "waiting_news_id_for_edit"
    await callback.bot.send_message(chat_id=chat_id, text="Введите ID новости для редактирования:")


async def handle_publish_news(callback, chat_id, user_id):
    user_data = user_temp_data.get(user_id, {})
    title = user_data.get("title")
    description = user_data.get("description")

    if not title or not description:
        await callback.bot.send_message(chat_id=chat_id, text="Ошибка: данные новости не найдены.")
        return

    news_id = news.add_news(title, description, "university")
    if news_id:
        subscribers = mailings.get_subscribers_by_type("university")
        message_ids = []

        if subscribers:
            news_text = f"Новость ВУЗа\n\nЗаголовок: {title}\n\n{description}"
            for subscriber in subscribers:
                try:
                    message = await callback.bot.send_message(
                        user_id=subscriber['user_id'],
                        text=news_text
                    )
                    message_ids.append(str(message.message.body.mid))
                except Exception as e:
                    logging.error(f"Ошибка отправки пользователю {subscriber['user_id']}: {e}")

            news.update_news(news_id, message_ids=message_ids)

        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Новость ВУЗа успешно опубликована и отправлена {len(subscribers)} подписчикам!"
        )

        if user_id in user_temp_data:
            del user_temp_data[user_id]

        await show_menu(chat_id, user_id, callback.bot)
    else:
        await callback.bot.send_message(chat_id=chat_id, text="Ошибка при сохранении новости.")


async def handle_edit_news(callback, chat_id, user_id):
    user_states[user_id] = "waiting_news_title"
    await callback.bot.send_message(chat_id=chat_id, text="Введите новый заголовок новости ВУЗа:")


async def handle_cancel_news(callback, chat_id, user_id):
    cleanup_user_state(user_id)
    await callback.bot.send_message(chat_id=chat_id, text="Создание новости отменено.")
    await show_menu(chat_id, user_id, callback.bot)


async def handle_edit_news_title(callback, chat_id, user_id):
    user_states[user_id] = "waiting_news_title_edit"
    await callback.bot.send_message(chat_id=chat_id, text="Введите новый заголовок новости:")


async def handle_edit_news_description(callback, chat_id, user_id):
    user_states[user_id] = "waiting_news_description_edit"
    await callback.bot.send_message(chat_id=chat_id, text="Введите новый текст новости:")


async def handle_edit_news_both(callback, chat_id, user_id):
    user_states[user_id] = "waiting_news_title_edit_both"
    await callback.bot.send_message(chat_id=chat_id, text="Введите новый заголовок новости:")


async def handle_cancel_news_edit(callback, chat_id, user_id):
    cleanup_user_state(user_id)
    await callback.bot.send_message(chat_id=chat_id, text="Редактирование новости отменено.")
    await show_menu(chat_id, user_id, callback.bot)


async def handle_add_user_to_black_list(callback, chat_id, user_id):
    user_states[user_id] = "waiting_blacklist_user_id"
    await callback.bot.send_message(
        chat_id=chat_id,
        text="Введите ID пользователя для добавления в черный список:"
    )


async def handle_show_blacklist(callback, chat_id, user_id):
    blacklisted_users = black_list.get_all_blacklisted()
    if not blacklisted_users:
        await callback.bot.send_message(chat_id=chat_id, text="Черный список пуст.")
        return

    message_text = "Черный список пользователей:\n\n"
    for user in blacklisted_users:
        message_text += f"ID: {user['user_id']}\n"
        message_text += f"Причина: {user['reason']}\n"
        message_text += f"Дата добавления: {user['date_added']}\n"
        message_text += "─" * 30 + "\n"

    await callback.bot.send_message(chat_id=chat_id, text=message_text)
    await show_menu(chat_id, user_id, callback.bot)


async def handle_remove_from_blacklist(callback, chat_id, user_id):
    blacklisted_users = black_list.get_all_blacklisted()
    if not blacklisted_users:
        await callback.bot.send_message(chat_id=chat_id, text="Черный список пуст.")
        return

    message_text = "Пользователи в черном списке:\n\n"
    for user in blacklisted_users:
        message_text += f"ID: {user['user_id']}\n"
        message_text += f"Причина: {user['reason']}\n\n"

    await callback.bot.send_message(chat_id=chat_id, text=message_text)

    user_states[user_id] = "waiting_blacklist_remove_id"
    await callback.bot.send_message(
        chat_id=chat_id,
        text="Введите ID пользователя для удаления из черного списка:"
    )


async def handle_add_role(callback, chat_id, user_id):
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="admin", payload="role_admin"),
        CallbackButton(text="dean", payload="role_dean"),
        CallbackButton(text="smm", payload="role_smm"),
    )
    builder.row(CallbackButton(text="head_dormitory", payload="role_head_dormitory"))

    await callback.bot.send_message(
        chat_id=chat_id,
        text="Выберите роль",
        attachments=[builder.as_markup()]
    )


async def handle_remove_role(callback, chat_id, user_id):
    admin_users = users.get_users_by_role("admin")
    dean_users = users.get_users_by_role("dean")
    smm_users = users.get_users_by_role("smm")
    head_dormitory_users = users.get_users_by_role("head_dormitory")

    message_text = "Пользователи с ролями:\n\n"

    if admin_users:
        message_text += "Админы:\n"
        for user in admin_users:
            message_text += f"• ID: {user['id']}\n"
        message_text += "\n"

    if dean_users:
        message_text += "Деканат:\n"
        for user in dean_users:
            message_text += f"• ID: {user['id']}\n"
        message_text += "\n"

    if smm_users:
        message_text += "SMM:\n"
        for user in smm_users:
            message_text += f"• ID: {user['id']}\n"
        message_text += "\n"

    if head_dormitory_users:
        message_text += "Заведующие общежитием:\n"
        for user in head_dormitory_users:
            message_text += f"• ID: {user['id']}\n"
        message_text += "\n"

    if not admin_users and not dean_users and not smm_users and not head_dormitory_users:
        message_text = "Пользователей с ролями не найдено"

    await callback.bot.send_message(chat_id=chat_id, text=message_text)

    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Отмена", payload="cancel_operation"))

    user_temp_data[user_id] = {"action_type": "remove"}
    user_states[user_id] = "waiting_user_id"

    await callback.bot.send_message(
        chat_id=chat_id,
        text="Введите ID пользователя для удаления роли:",
        attachments=[builder.as_markup()]
    )


async def handle_set_applicant(callback, chat_id, user_id):
    if not users.has_role(user_id, "admin"):
        users.add_user(user_id, "applicant")
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Ваша роль сменена на Абитуриент\nИспользуйте /menu"
        )


async def handle_set_student(callback, chat_id, user_id):
    if not users.has_role(user_id, "admin"):
        users.add_user(user_id, "student")
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Ваша роль сменена на Студент\nИспользуйте /menu"
        )


async def handle_confirm_user(callback, chat_id, user_id):
    user_data = user_temp_data.get(user_id, {})
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
        await callback.bot.send_message(chat_id=chat_id, text="Ошибка: данные не найдены")

    cleanup_user_state(user_id)
    await show_menu(chat_id, user_id, callback.bot)


async def handle_deny_user(callback, chat_id, user_id):
    user_states[user_id] = "waiting_user_id"
    await callback.bot.send_message(chat_id=chat_id, text="Введите ID пользователя снова:")


async def handle_confirm_remove(callback, chat_id, user_id):
    user_data = user_temp_data.get(user_id, {})
    target_user_id = user_data.get("target_user_id")

    if target_user_id:
        current_role = users.get_user_role(target_user_id)
        admins.remove_admin(target_user_id)
        dean_representatives.remove_representative(target_user_id)
        users.update_user_role(target_user_id, "user")

        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Пользователю {target_user_id} удалена роль {current_role}"
        )
    else:
        await callback.bot.send_message(chat_id=chat_id, text="Ошибка: данные не найдены")

    cleanup_user_state(user_id)
    await show_menu(chat_id, user_id, callback.bot)


async def handle_deny_remove(callback, chat_id, user_id):
    user_states[user_id] = "waiting_user_id"
    await callback.bot.send_message(chat_id=chat_id, text="Введите ID пользователя снова:")


async def handle_cancel_operation(callback, chat_id, user_id):
    cleanup_user_state(user_id)
    await callback.bot.send_message(chat_id=chat_id, text="Операция отменена.")
    await show_menu(chat_id, user_id, callback.bot)


async def handle_future_events(callback, chat_id, user_id):
    upcoming_events = events_db.get_upcoming_events()
    if not upcoming_events:
        await callback.bot.send_message(
            chat_id=chat_id,
            text="На данный момент предстоящих событий нет. Следите за обновлениями!"
        )
        return

    message_text = "Предстоящие события ВУЗа:\n\n"

    for i, event in enumerate(upcoming_events, 1):
        message_text += f"{i}. {event['title']}\n"
        message_text += f"Когда: {event['event_date']}\n"
        message_text += f"Где: {event['location']}\n"
        message_text += f"Описание: {event['description']}\n"
        message_text += "─" * 30 + "\n\n"

    await callback.bot.send_message(chat_id=chat_id, text=message_text)


async def handle_manage_events(callback, chat_id, user_id):
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Добавить событие", payload="add_event"),
        CallbackButton(text="Список событий", payload="list_events")
    )
    builder.row(
        CallbackButton(text="Редактировать событие", payload="edit_event"),
        CallbackButton(text="Удалить событие", payload="delete_event")
    )

    events_count = events_db.get_events_count()

    await callback.bot.send_message(
        chat_id=chat_id,
        text=f"Статистика событий:\nВсего событий: {events_count}",
        attachments=[builder.as_markup()]
    )


async def handle_add_event(callback, chat_id, user_id):
    user_states[user_id] = "waiting_event_title"
    user_temp_data[user_id] = {}
    await callback.bot.send_message(chat_id=chat_id, text="Введите заголовок события:")


async def handle_list_events(callback, chat_id, user_id):
    all_events = events_db.get_all_events(limit=10)
    if not all_events:
        await callback.bot.send_message(chat_id=chat_id, text="Событий пока нет.")
        return

    message_text = "Все события:\n\n"
    for event in all_events:
        message_text += f"ID: {event['id']}\n"
        message_text += f"Заголовок: {event['title']}\n"
        message_text += f"Дата: {event['event_date']}\n"
        message_text += f"Место: {event['location']}\n"
        message_text += "─" * 30 + "\n"

    await callback.bot.send_message(chat_id=chat_id, text=message_text)


async def handle_edit_event(callback, chat_id, user_id):
    all_events = events_db.get_all_events(limit=10)
    if not all_events:
        await callback.bot.send_message(chat_id=chat_id, text="Событий для редактирования не найдено.")
        return

    events_list_text = "Список всех событий:\n\n"
    for event in all_events:
        events_list_text += f"ID: {event['id']}\n"
        events_list_text += f"Заголовок: {event['title']}\n"
        events_list_text += f"Дата: {event['event_date']}\n"
        events_list_text += "─" * 30 + "\n"

    await callback.bot.send_message(chat_id=chat_id, text=events_list_text)

    user_states[user_id] = "waiting_event_id_for_edit"
    await callback.bot.send_message(chat_id=chat_id, text="Введите ID события для редактирования:")


async def handle_delete_event(callback, chat_id, user_id):
    all_events = events_db.get_all_events(limit=10)
    if not all_events:
        await callback.bot.send_message(chat_id=chat_id, text="Событий для удаления не найдено.")
        return

    events_list_text = "Список всех событий:\n\n"
    for event in all_events:
        events_list_text += f"ID: {event['id']}\n"
        events_list_text += f"Заголовок: {event['title']}\n"
        events_list_text += f"Дата: {event['event_date']}\n"
        events_list_text += "─" * 30 + "\n"

    await callback.bot.send_message(chat_id=chat_id, text=events_list_text)

    user_states[user_id] = "waiting_event_id_for_delete"
    await callback.bot.send_message(chat_id=chat_id, text="Введите ID события для удаления:")


async def handle_edit_event_title(callback, chat_id, user_id):
    user_states[user_id] = "waiting_event_title_edit"
    await callback.bot.send_message(chat_id=chat_id, text="Введите новый заголовок события:")


async def handle_edit_event_description(callback, chat_id, user_id):
    user_states[user_id] = "waiting_event_description_edit"
    await callback.bot.send_message(chat_id=chat_id, text="Введите новое описание события:")


async def handle_edit_event_date(callback, chat_id, user_id):
    user_states[user_id] = "waiting_event_date_edit"
    await callback.bot.send_message(chat_id=chat_id, text="Введите новую дату события (формат: ДД.ММ.ГГГГ ЧЧ:ММ):")


async def handle_edit_event_location(callback, chat_id, user_id):
    user_states[user_id] = "waiting_event_location_edit"
    await callback.bot.send_message(chat_id=chat_id, text="Введите новое место проведения события:")


async def handle_edit_event_all(callback, chat_id, user_id):
    user_states[user_id] = "waiting_event_title_edit_all"
    await callback.bot.send_message(chat_id=chat_id, text="Введите новый заголовок события:")


async def handle_cancel_event_edit(callback, chat_id, user_id):
    cleanup_user_state(user_id)
    await callback.bot.send_message(chat_id=chat_id, text="Редактирование события отменено.")
    await show_menu(chat_id, user_id, callback.bot)


async def handle_cancel_delete_news(callback, chat_id, user_id):
    await callback.bot.send_message(chat_id=chat_id, text="Удаление новости отменено.")
    await show_menu(chat_id, user_id, callback.bot)


async def handle_cancel_delete_event(callback, chat_id, user_id):
    await callback.bot.send_message(chat_id=chat_id, text="Удаление события отменено.")
    await show_menu(chat_id, user_id, callback.bot)


# Обработчики с префиксами
async def handle_approve_dean(callback, payload, chat_id, user_id):
    user_id_payload = int(payload.split("_")[1])
    if request_dean.get_user(user_id_payload):
        request_dean.delete_user(user_id=user_id_payload)
        dean_representatives.add_representative(user_id=user_id_payload)
        users.add_user(user_id_payload, "dean")

        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Заявка пользователя {user_id_payload} принята!"
        )
        await callback.bot.send_message(
            user_id=user_id_payload,
            text="Вашу заявку приняли! Вам доступны новые возможности!"
        )

        all_requests = request_dean.get_all_users()
        if all_requests:
            current_index = current_dean_request_index.get(chat_id, 0)
            await show_next_request_dean(chat_id, callback.bot, current_index)
        else:
            await callback.bot.send_message(chat_id=chat_id, text=f"Заявки закончились!")
            await show_menu(chat_id, user_id, callback.bot)


async def handle_reject_dean(callback, payload, chat_id, user_id):
    user_id_payload = int(payload.split("_")[1])
    if request_dean.get_user(user_id_payload):
        request_dean.delete_user(user_id=user_id_payload)

        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Заявка пользователя {user_id_payload} отклонена!"
        )
        await callback.bot.send_message(
            user_id=user_id_payload,
            text="Вашу заявку отклонили!"
        )

        all_requests = request_dean.get_all_users()
        if all_requests:
            current_index = current_dean_request_index.get(chat_id, 0)
            await show_next_request_dean(chat_id, callback.bot, current_index)
        else:
            await callback.bot.send_message(chat_id=chat_id, text=f"Заявки закончились!")
            await show_menu(chat_id, user_id, callback.bot)


async def handle_approve_study(callback, payload, chat_id, user_id):
    user_id_payload = int(payload.split("_")[1])
    if study_certificate_requests.is_request_exists(user_id_payload):
        study_certificate_requests.delete_request(request_id=user_id_payload)

        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Заявка студента {user_id_payload} принята!"
        )
        await callback.bot.send_message(
            user_id=user_id_payload,
            text="Ваша справка готова к получению!"
        )

        all_requests = study_certificate_requests.get_all_requests()
        if all_requests:
            current_index = current_study_request_index.get(chat_id, 0)
            await show_next_request_student_info(chat_id, callback.bot, current_index)
        else:
            await callback.bot.send_message(chat_id=chat_id, text=f"Заявки закончились!")
            await show_menu(chat_id, user_id, callback.bot)


async def handle_reject_study(callback, payload, chat_id, user_id):
    user_id_payload = int(payload.split("_")[1])
    if study_certificate_requests.is_request_exists(user_id_payload):
        study_certificate_requests.delete_request(request_id=user_id_payload)

        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Заявка студента {user_id_payload} отклонена!"
        )
        await callback.bot.send_message(
            user_id=user_id_payload,
            text="Вам отказали в выдаче справки! Обратитесь в деканат!"
        )

        all_requests = study_certificate_requests.get_all_requests()
        if all_requests:
            current_index = current_study_request_index.get(chat_id, 0)
            await show_next_request_student_info(chat_id, callback.bot, current_index)
        else:
            await callback.bot.send_message(chat_id=chat_id, text=f"Заявки закончились!")
            await show_menu(chat_id, user_id, callback.bot)


async def handle_approve_unban(callback, payload, chat_id, user_id):
    request_id = int(payload.split("_")[2])
    success = unban_requests.approve_request(
        request_id=request_id,
        admin_id=user_id,
        notes="Заявка одобрена администратором"
    )

    if success:
        request = unban_requests.get_request_by_id(request_id)
        if request:
            black_list.remove_from_blacklist(request['user_id'])
            try:
                await callback.bot.send_message(
                    user_id=request['user_id'],
                    text="Ваша заявка на разбан одобрена! Теперь вы можете использовать бота."
                )
            except Exception as e:
                logging.error(f"Не удалось уведомить пользователя {request['user_id']}: {e}")

        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Заявка на разбан одобрена! Пользователь {request['user_id']} удален из черного списка."
        )
    else:
        await callback.bot.send_message(
            chat_id=chat_id,
            text="Ошибка при одобрении заявки. Возможно, заявка уже обработана."
        )

    all_requests = unban_requests.get_all_pending_requests()
    if all_requests:
        current_index = current_unban_request_index.get(chat_id, 0)
        await show_next_unban_request(chat_id, callback.bot, current_index)
    else:
        await callback.bot.send_message(chat_id=chat_id, text="Заявки на разбан закончились!")
        await show_menu(chat_id, user_id, callback.bot)


async def handle_reject_unban(callback, payload, chat_id, user_id):
    request_id = int(payload.split("_")[2])
    user_states[user_id] = f"waiting_unban_reject_reason_{request_id}"
    await callback.bot.send_message(
        chat_id=chat_id,
        text="Введите причину отклонения заявки:"
    )


async def handle_reply_complaint(callback, payload):
    complaint_id = int(payload.split("_")[1])
    complaint = student_complaints.get_complaint(complaint_id)
    if not complaint:
        await callback.message.answer("Жалоба не найдена.")
        return

    user_states[callback.from_user.user_id] = f"waiting_reply_text_{complaint_id}"
    await callback.message.answer("Введите текст ответа студенту:")


async def handle_close_complaint(callback, payload, chat_id):
    complaint_id = int(payload.split("_")[1])
    if student_complaints.delete_complaint(complaint_id):
        await callback.message.answer("Жалоба закрыта.")
        complaints = student_complaints.get_all_complaints()
        if complaints:
            current_index = current_complaint_index.get(chat_id, 0)
            await show_next_complaint(chat_id, callback.bot, current_index % len(complaints))
        else:
            await callback.message.answer("Жалобы закончились!")
    else:
        await callback.message.answer("Не удалось закрыть жалобу.")


async def handle_reply_pass(callback, payload):
    request_id = int(payload.split("_")[1])
    user_states[callback.from_user.user_id] = f"waiting_pass_reply_{request_id}"
    await callback.message.answer("Введите текст ответа студенту:")


async def handle_auto_reply_pass(callback, payload):
    request_id = int(payload.split("_")[1])
    all_requests = dormitory_requests.get_all_requests()
    target = next((r for r in all_requests if r["id"] == request_id), None)

    if target:
        await callback.bot.send_message(
            chat_id=target["chat_id"],
            text="Ваша заявка принята. Получите пропуск в кабинете 2.1.06, с 8:00 до 20:00 пн-пт, с 10:00 до 18:00 сб-вс"
        )
        dormitory_requests.delete_request(request_id)
        await callback.message.answer("Автоответ отправлен студенту, заявка закрыта.")


async def handle_reject_pass(callback, payload):
    request_id = int(payload.split("_")[1])
    if dormitory_requests.delete_request(request_id):
        await callback.message.answer("Заявка отклонена и удалена.")
    else:
        await callback.message.answer("Не удалось удалить заявку.")


async def handle_confirm_delete_news(callback, payload, chat_id, user_id):
    news_id = int(payload.split("_")[3])
    message_ids = news.get_news(news_id)["message_ids"]
    success = news.delete_news(news_id)

    for message_id in message_ids:
        await bot.delete_message(message_id)

    if success:
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Новость с ID {news_id} успешно удалена!"
        )
    else:
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Ошибка при удалении новости с ID {news_id}."
        )

    await show_menu(chat_id, user_id, callback.bot)


async def handle_confirm_delete_event(callback, payload, chat_id, user_id):
    event_id = int(payload.split("_")[3])
    success = events_db.delete_event(event_id)

    if success:
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Событие с ID {event_id} успешно удалено!"
        )
    else:
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"Ошибка при удалении события с ID {event_id}."
        )

    await show_menu(chat_id, user_id, callback.bot)


async def handle_role_selection(callback, payload, chat_id, user_id):
    selected_role = "_".join(payload.split("_")[1:])
    user_temp_data[user_id] = {"selected_role": selected_role, "action_type": "add"}
    user_states[user_id] = "waiting_user_id"

    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Отмена", payload="cancel_operation"))

    await callback.bot.send_message(
        chat_id=chat_id,
        text="Введите ID пользователя:",
        attachments=[builder.as_markup()]
    )


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
