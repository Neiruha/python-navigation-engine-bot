"""
Простой Telegram-бот, использующий NavigationEngine для навигации.

Для запуска:
1. pip install aiogram
2. Заведите бота у @BotFather, получите токен.
3. Установите переменную окружения BOT_TOKEN или измените `BOT_TOKEN` в коде.
4. python bot_interface.py
"""

import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from navigation.engine import NavigationEngine
from navigation.api_stub import APISimulator

# Импортируем load_dotenv из python-dotenv
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# --- Конфигурация ---
#BOT_TOKEN = os.getenv("BOT_TOKEN", "8354012195:AAF0WDGvFh3gX1wEbEOduat3g3nui8AbG-g")  # Замените на реальный токен или укажите в env
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не установлен BOT_TOKEN. Укажите его в файле .env или в переменной окружения.")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()

# Инициализация навигационного движка
# Можно передать кастомный api_client, если нужен реальный API
nav_engine = NavigationEngine(manifest_path="menu-manifest.json", api_client=APISimulator())

# --- Вспомогательные функции ---

def actions_to_inline_keyboard(actions: list) -> types.InlineKeyboardMarkup:
    """Преобразует список действий из engine в InlineKeyboardMarkup."""
    keyboard = []
    row = []
    # Предположим, что для grid layout мы хотим N кнопок в ряд.
    # Это грубая эмуляция сетки через строки.
    # Более точно - сложно, зависит от клиента.
    # Пока просто по 2 в ряд как компромисс.
    COLS_IN_GRID = 2
    for action in actions:
        # Создаём callback_data для кнопки
        # Это строка, которую бот получит при нажатии
        # Формат: type|id|label|target|payload|context
        # Упрощённый вариант: type|id
        # Или, чтобы передать больше данных, можно сериализовать action_data
        # Но для простоты, передадим id кнопки, а полные данные будем хранить в сессии.
        # НО! aiogram callback_data ограничен 64 байтами.
        # Лучше: type|index
        # И хранить список actions в состоянии пользователя.
        # Пока простой вариант: type|id
        callback_data_str = f"{action['type']}|{action['id']}"
        button = types.InlineKeyboardButton(text=action["label"], callback_data=callback_data_str)
        row.append(button)
        # Если это grid, и длина ряда достигла COLS_IN_GRID, закрываем ряд
        # Или просто добавляем по одной кнопке в ряд, если не grid.
        # Упрощение: делаем по 2 в ряд всегда.
        if len(row) == COLS_IN_GRID:
            keyboard.append(row)
            row = []
    if row:  # Добавляем оставшиеся кнопки
        keyboard.append(row)

    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_user_session(user_id: int) -> dict:
    """Получает сессию пользователя из engine."""
    # В engine сессии хранятся по user_id (строке)
    return nav_engine.get_user_state(str(user_id))

# --- Хендлеры ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработка команды /start."""
    user_id = str(message.from_user.id)
    nav_engine.init_user(user_id)
    view = nav_engine.get_current_view(user_id)

    text = view["text"]
    actions = view["actions"]

    keyboard = actions_to_inline_keyboard(actions) if actions else None

    await message.answer(text=text, reply_markup=keyboard)

@dp.callback_query()
async def handle_callback(callback_query: types.CallbackQuery):
    """Обработка нажатия inline-кнопки."""
    user_id = str(callback_query.from_user.id)
    # callback_data в формате "type|id"
    data_parts = callback_query.data.split("|", 1)
    if len(data_parts) != 2:
        await callback_query.answer("Неверный формат данных кнопки.")
        return

    action_type, action_id = data_parts[0], data_parts[1]

    # Получаем текущий список действий, чтобы найти полные данные
    # Это не идеально, т.к. список мог измениться с момента отправки.
    # Лучше было бы хранить `action_data` отдельно при отправке.
    # Но для простоты и текущей архитектуры, попробуем найти по id.
    current_view = nav_engine.get_current_view(user_id)
    # Ищем action с нужным id
    found_action = None
    for action in current_view["actions"]:
        if action["id"] == action_id:
            found_action = action
            break

    if not found_action:
        await callback_query.answer("Данные кнопки устарели. Пожалуйста, обновите меню.")
        # Повторно отправляем текущее состояние
        keyboard = actions_to_inline_keyboard(current_view["actions"]) if current_view["actions"] else None
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=current_view["text"],
            reply_markup=keyboard
        )
        return

    # Обновляем состояние через engine
    nav_engine.handle_action(user_id, found_action)

    # Получаем новое состояние
    new_view = nav_engine.get_current_view(user_id)

    text = new_view["text"]
    actions = new_view["actions"]

    keyboard = actions_to_inline_keyboard(actions) if actions else None

    # Отвечаем на callback (убирает "часики" у кнопки)
    await callback_query.answer()

    # Редактируем сообщение (или отправляем новое, если редактировать нельзя)
    # Некоторые типы сообщений (например, из уведомлений) нельзя редактировать.
    # Или если слишком старое. Обернём в try.
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            reply_markup=keyboard
        )
    except Exception:
        # Если редактировать нельзя, отправляем новое
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=text,
            reply_markup=keyboard
        )

@dp.message()
async def handle_text_message(message: types.Message):
    """Обработка текстового сообщения (для чат-режима)."""
    user_id = str(message.from_user.id)
    text = message.text

    # Проверяем, находится ли пользователь в чат-режиме
    current_view = nav_engine.get_current_view(user_id)
    if current_view.get("screen_type") == "chat_input":
        # Передаём текст в engine
        nav_engine.handle_user_input(user_id, text)

        # Получаем обновлённое состояние
        new_view = nav_engine.get_current_view(user_id)

        # Если мы всё ещё в чат-режиме, просто отвечаем "принято"
        # (в реальности, тут мог бы быть ответ от AI)
        if new_view.get("screen_type") == "chat_input":
            await message.answer("Сообщение отправлено. (Имитация)")
            return # Не обновляем клавиатуру, она не нужна в чате

        # Если вышли из чат-режима (например, по команде /finish)
        # Отправляем новое сообщение с новым меню
        keyboard = actions_to_inline_keyboard(new_view["actions"]) if new_view["actions"] else None
        await message.answer(text=new_view["text"], reply_markup=keyboard)
    else:
        # Если не в чат-режиме, просто отвечаем, что текст не ожидается
        await message.answer("Пожалуйста, используйте кнопки для навигации.")

# --- Запуск бота ---

async def main():
    print("Бот запускается...")
    # Запуск long polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Проверка, установлен ли токен
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Ошибка: Не установлен BOT_TOKEN. Укажите его в переменной окружения BOT_TOKEN или в коде.")
        exit(1)
    asyncio.run(main())