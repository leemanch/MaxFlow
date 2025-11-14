import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.filters.command import Command
from maxapi.types import BotStarted, MessageCreated, CallbackButton, MessageCallback, OpenAppButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from database.admins import AdminsDatabase
from database.dean import DeanRepresentativesDatabase
from database.requests_dean import DeanRequestDataBase
from database.study_certificate_requests import StudyCertificateRequestsDatabase
from database.users import UsersDatabase

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

@dp.bot_started()
async def bot_started(event: BotStarted):
    await event.bot.send_message(
        chat_id=event.chat_id,
        text='Привет! Отправь мне /start'
    )

@dp.message_created(Command('setd'))
async def setd(event: MessageCreated):
    if (dean_representatives.is_representative(event.from_user.user_id) and users.has_role(event.from_user.user_id, "dean")):
        await event.bot.send_message(chat_id=event.chat.chat_id, text="Вы уже являетесь представителем деканата!")
    elif (request_dean.get_user(user_id=event.from_user.user_id) == None):
        request_dean.add_user(user_id=event.from_user.user_id, username=event.from_user.full_name)
        await event.bot.send_message(chat_id = event.chat.chat_id, text="Заявка отправлена на рассмотрение!")
    else:
        await event.bot.send_message(chat_id=event.chat.chat_id, text="Вы уже отправляли заявку!")


@dp.message_created(Command('menu'))
async def print_menu(event: MessageCreated):
    print(users.get_all_users())
    text_builder = "Выберите действие"
    text_lable = ""
    role = users.get_user_role(event.from_user.user_id)
    print(role)
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
                text='Добавить админа',
                payload='add_admin',
            ),
            CallbackButton(
                text='Удалить админа',
                payload='remove_admin',
            )
        )
        builder.row(
            CallbackButton(
                text='Добавить представителя деканата',
                payload='add_dean',
            ),
            CallbackButton(
                text='Удалить представителя деканата',
                payload='remove_dean',
            )
        )
        text_lable="Вы админ!"
    elif role == "dean":
        builder.row(
            CallbackButton(
                text='Заявки',
                payload='requests_student',
            ),
        )
        text_lable = "Вы представитель деканата!"
    elif role == "student":
        builder.row(
            CallbackButton(
                text='Заказать справку об обучении',
                payload='information_about_training',
            )
        )
        text_lable = "Вы студент!"
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
        text_lable = "Вы абитуриент!"
    elif role == "smm":
        builder.row(
            CallbackButton(
                text='Добавить новость',
                payload='add_news',
            )
        )
        text_lable = "Вы сммщик!"
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
        text_lable = "Вы заведующий общежитием!"
    elif role == "user":
        text_lable = "Вы пользователь! Используйте /start чтобы выбрать роль:)"
    else:
        text_lable = "Используйте /start чтобы выбрать роль:)"
    await event.bot.send_message(
        chat_id=event.chat.chat_id,
        text=text_lable
    )
    await event.message.answer(
        text=text_builder,
        attachments=[
            builder.as_markup()
        ]
    )


@dp.message_created(Command('start'))
async def hello(event: MessageCreated):
    text_builder = "Выберите вашу роль(старая будет не действительна)"
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
        await bot.send_message(chat_id=chat_id, text = "На данный момент заявок нет.")
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


@dp.message_created()
async def handle_text_input(event: MessageCreated):
    user_id = event.from_user.user_id
    if user_id in user_states:
        current_state = user_states[user_id]
        user_input = event.message.body.text.strip()
        if current_state == "waiting_full_name":
            # Сохраняем ФИО и запрашиваем группу
            user_temp_data[user_id] = {"full_name": user_input}
            user_states[user_id] = "waiting_group"
            await event.bot.send_message(
                chat_id=event.chat.chat_id,
                text="✅ ФИО сохранено. Теперь введите вашу группу:"
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

    if payload == "requests_dean":
        await show_next_request_dean(chat_id, callback.bot, 0)
    elif payload == "requests_student":
        await show_next_request_student_info(chat_id, callback.bot, 0)
    elif payload == "information_about_training":
        user_states[callback.from_user.user_id] = "waiting_full_name"
        await callback.message.answer("📝 Заполните данные для заявки на справку об обучении.\n\nВведите ваше ФИО:")
    elif payload == "next_requestDean":
        all_requests = request_dean.get_all_users()
        if not all_requests:
            await callback.message.answer("Заявок нет!")
            return
        current_index = current_dean_request_index.get(chat_id, 0)
        next_index = (current_index + 1) % len(all_requests)
        await show_next_request_dean(chat_id, callback.bot, next_index)

    elif payload == "next_requestStudy":
        all_requests = study_certificate_requests.get_all_requests()
        if not all_requests:
            await callback.message.answer("Заявок нет!")
            return
        current_index = current_study_request_index.get(chat_id, 0)
        next_index = (current_index + 1) % len(all_requests)
        await show_next_request_student_info(chat_id, callback.bot, next_index)

    elif payload == "stop_requests":
        await callback.message.answer("Просмотр заявок остановлен.")

    elif payload.startswith("approveDean_"):
        user_id = int(payload.split("_")[1])
        if request_dean.get_user(user_id):
            request_dean.delete_user(user_id=user_id)
            dean_representatives.add_representative(user_id=user_id)
            users.add_user(user_id, "dean")
            await callback.message.answer(f"✅ Заявка пользователя {user_id} принята!")
            await callback.bot.send_message(user_id=user_id, text="✅ Вашу заявку приняли! Вам доступны новые возможности!")
            all_requests = request_dean.get_all_users()
            if all_requests:
                current_index = current_dean_request_index.get(chat_id, 0)
                await show_next_request_dean(chat_id, callback.bot, current_index)
            else:
                await callback.message.answer(f"Заявки закончились!")
    elif payload.startswith("approveStudy_"):
        user_id = int(payload.split("_")[1])
        if study_certificate_requests.is_request_exists(user_id):
            study_certificate_requests.delete_request(request_id=user_id)
            await callback.message.answer(f"✅ Заявка студента {user_id} принята!")
            await callback.bot.send_message(user_id=user_id, text="✅ Ваша справка готова к получению!")
            all_requests = study_certificate_requests.get_all_requests()
            if all_requests:
                current_index = current_study_request_index.get(chat_id, 0)
                await show_next_request_student_info(chat_id, callback.bot, current_index)
            else:
                await callback.message.answer(f"Заявки закончились!")

    elif payload.startswith("rejectDean_"):
        user_id = int(payload.split("_")[1])
        if request_dean.get_user(user_id):
            request_dean.delete_user(user_id=user_id)
            await callback.message.answer(f"❌ Заявка пользователя {user_id} отклонена!")
            await callback.bot.send_message(user_id=user_id, text="❌ Вашу заявку отклонили!")
            all_requests = request_dean.get_all_users()
            if all_requests:
                current_index = current_dean_request_index.get(chat_id, 0)
                await show_next_request_dean(chat_id, callback.bot, current_index)
            else:
                await callback.message.answer(f"Заявки закончились!")

    elif payload.startswith("rejectStudy_"):
        user_id = int(payload.split("_")[1])
        if study_certificate_requests.is_request_exists(user_id):
            study_certificate_requests.delete_request(request_id=user_id)
            await callback.message.answer(f"❌ Заявка студента {user_id} отклонена!")
            await callback.bot.send_message(user_id=user_id, text="❌ Вам отказали в выдаче справки! Обратитесь в деканат!")
            all_requests = study_certificate_requests.get_all_requests()
            if all_requests:
                current_index = current_study_request_index.get(chat_id, 0)
                await show_next_request_student_info(chat_id, callback.bot, current_index)
            else:
                await callback.message.answer(f"Заявки закончились!")

    elif payload == "set_applicant":
        if not users.is_user_exists(callback.from_user.user_id):
            users.add_user(callback.from_user.user_id, "applicant")
        await callback.message.answer(f"Ваша роль сменена на Абитуриент\nИспользуйте /menu")

    elif payload == "set_student":
        if not users.is_user_exists(callback.from_user.user_id):
            users.add_user(callback.from_user.user_id, "student")
        await callback.message.answer(f"Ваша роль сменена на Студент\nИспользуйте /menu")

    elif payload == "future_events":
        pass

async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())