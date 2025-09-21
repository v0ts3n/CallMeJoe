import os
import re
import asyncio
import logging
from typing import List, Dict, Any
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State

from bot_api_client import CallMeJoeAPI

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = ""
API_BASE = ""

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
api = CallMeJoeAPI(API_BASE)

class AddSessionStates(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_2fa = State()

class CallStates(StatesGroup):
    waiting_username = State()

def start_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Меню сессий", callback_data="menu:sessions")
    kb.button(text="Позвонить", callback_data="menu:call")
    kb.adjust(1, 1)
    return kb.as_markup()

def sessions_keyboard(items: List[Dict[str, Any]]):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить новую", callback_data="sessions:add")
    for it in items:
        num = str(it.get("number") or it.get("phone") or "")
        lbl = it.get("label") or it.get("username") or ""
        auth = it.get("authorized")
        suffix = ""
        if auth is True:
            suffix = " ✅"
        elif auth is False:
            suffix = " ❌"
        title = num if not lbl else f"{num} ({lbl})"
        kb.button(text=title + suffix, callback_data=f"sessions:one:{num}")
    kb.button(text="↩️ Назад", callback_data="back:home")
    kb.adjust(1)
    return kb.as_markup()

def call_sessions_keyboard(items: List[Dict[str, Any]]):
    kb = InlineKeyboardBuilder()
    auth_items = [it for it in items if it.get("authorized") is True]
    for it in auth_items:
        num = str(it.get("number") or "")
        lbl = it.get("username") or it.get("first_name") or ""
        title = num if not lbl else f"{num} ({lbl})"
        kb.button(text=title, callback_data=f"call:from:{num}")
    kb.button(text="↩️ Назад", callback_data="back:home")
    if not auth_items:
        kb.button(text="Нет авторизованных сессий", callback_data="noop")
    kb.adjust(1)
    return kb.as_markup()

def code_keyboard(current):
    kb = InlineKeyboardBuilder()
    for row in (("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9")):
        for d in row:
            kb.button(text=d, callback_data=f"code:add:{d}")
        kb.adjust(3)
    kb.button(text="←", callback_data="code:del")
    kb.button(text="0", callback_data="code:add:0")
    kb.button(text="OK", callback_data="code:ok")
    kb.adjust(3)
    kb.button(text="Очистить", callback_data="code:clear")
    kb.button(text="Отмена", callback_data="code:cancel")
    kb.adjust(2)
    return kb.as_markup()

async def api_call_start(number: str, username: str) -> Dict[str, Any]:
    url = f"{API_BASE}/call/start"
    payload = {"number": number, "username": username}
    print(f"[BOT] POST {url} {payload}")
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload) as r:
            txt = await r.text()
            print(f"[BOT] {r.status} {txt}")
            try:
                return {"http": r.status, **(await r.json())}
            except Exception:
                return {"http": r.status, "raw": txt}

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    print(f"[BOT] /start from={message.from_user.id}")
    await state.clear()
    await message.answer("Выберите действие:", reply_markup=start_keyboard())

@dp.callback_query(F.data == "back:home")
async def back_home(call: types.CallbackQuery, state: FSMContext):
    print(f"[BOT] back_home from={call.from_user.id}")
    await state.clear()
    await call.message.edit_text("Выберите действие:", reply_markup=start_keyboard())

@dp.callback_query(F.data == "menu:sessions")
async def menu_sessions(call: types.CallbackQuery, state: FSMContext):
    print(f"[BOT] open sessions menu from={call.from_user.id}")
    sessions = await api.list_sessions()
    await call.message.edit_text("Сессии:", reply_markup=sessions_keyboard(sessions))

@dp.callback_query(F.data == "sessions:add")
async def sessions_add(call: types.CallbackQuery, state: FSMContext):
    print(f"[BOT] sessions_add start from={call.from_user.id}")
    await state.set_state(AddSessionStates.waiting_phone)
    await state.update_data(new_phone=None, code_buffer="")
    await call.message.edit_text("Введите номер телефона в международном формате. Пример: +380XXXXXXXXX")

@dp.message(AddSessionStates.waiting_phone)
async def input_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    print(f"[BOT] input_phone from={message.from_user.id} phone={phone}")
    if not re.fullmatch(r"\+\d{10,15}", phone):
        await message.answer("Неверный формат. Пример: +380XXXXXXXXX")
        return
    await state.update_data(new_phone=phone, code_buffer="")
    res = await api.init_new(phone)
    print(f"[BOT] init_new result phone={phone} res={res}")
    st = res.get("status")
    if st == "already_authorized":
        await state.clear()
        sessions = await api.list_sessions()
        await message.answer(f"Готово. Сессия уже авторизована для {phone}.", reply_markup=sessions_keyboard(sessions))
        return
    if st == "code_sent":
        await state.set_state(AddSessionStates.waiting_code)
        await message.answer(f"Код отправлен на {phone}. Введите код через клавиатуру ниже.\nКод: ", reply_markup=code_keyboard(""))
        return
    await state.clear()
    sessions = await api.list_sessions()
    await message.answer(f"Ошибка: {res.get('detail','unknown')}", reply_markup=sessions_keyboard(sessions))

@dp.callback_query(AddSessionStates.waiting_code, F.data.startswith("code:add:"))
async def code_add_digit(call: types.CallbackQuery, state: FSMContext):
    d = call.data.split(":")[-1]
    data = await state.get_data()
    buf = data.get("code_buffer", "")
    if len(buf) >= 6:
        await call.answer("Максимум 6 символов")
        return
    buf += d
    await state.update_data(code_buffer=buf)
    print(f"[BOT] code_add_digit user={call.from_user.id} buf={buf}")
    await call.message.edit_text(f"Код: {buf}", reply_markup=code_keyboard(buf))

@dp.callback_query(AddSessionStates.waiting_code, F.data == "code:del")
async def code_del(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    buf = data.get("code_buffer", "")
    buf = buf[:-1] if buf else ""
    await state.update_data(code_buffer=buf)
    print(f"[BOT] code_del user={call.from_user.id} buf={buf}")
    await call.message.edit_text(f"Код: {buf}", reply_markup=code_keyboard(buf))

@dp.callback_query(AddSessionStates.waiting_code, F.data == "code:clear")
async def code_clear(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(code_buffer="")
    print(f"[BOT] code_clear user={call.from_user.id}")
    await call.message.edit_text("Код: ", reply_markup=code_keyboard(""))

@dp.callback_query(AddSessionStates.waiting_code, F.data == "code:cancel")
async def code_cancel(call: types.CallbackQuery, state: FSMContext):
    print(f"[BOT] code_cancel user={call.from_user.id}")
    await state.clear()
    sessions = await api.list_sessions()
    await call.message.edit_text("Сессии:", reply_markup=sessions_keyboard(sessions))

@dp.callback_query(AddSessionStates.waiting_code, F.data == "code:ok")
async def code_submit(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    phone = data.get("new_phone")
    buf = data.get("code_buffer", "")
    print(f"[BOT] code_submit user={call.from_user.id} phone={phone} code={buf}")
    if not buf or len(buf) < 4:
        await call.answer("Слишком короткий код")
        return
    res = await api.enter_code(phone, buf)
    print(f"[BOT] enter_code result phone={phone} res={res}")
    st = res.get("status")
    if st == "authorized":
        await state.clear()
        sessions = await api.list_sessions()
        await call.message.edit_text(f"Авторизовано: {phone}", reply_markup=sessions_keyboard(sessions))
        return
    if st == "2fa_required":
        await state.set_state(AddSessionStates.waiting_2fa)
        await call.message.edit_text("Требуется пароль 2FA. Отправьте пароль текстом.")
        return
    if st == "code_invalid":
        await state.update_data(code_buffer="")
        await call.message.edit_text("Неверный код. Введите снова.\nКод: ", reply_markup=code_keyboard(""))
        return
    if st == "code_expired":
        await state.update_data(code_buffer="")
        sessions = await api.list_sessions()
        await call.message.edit_text("Срок кода истёк. Запросите новый через /start -> Меню сессий -> Добавить новую.", reply_markup=sessions_keyboard(sessions))
        await state.clear()
        return
    await state.clear()
    sessions = await api.list_sessions()
    await call.message.edit_text(f"Ошибка: {res.get('detail','unknown')}", reply_markup=sessions_keyboard(sessions))

@dp.message(AddSessionStates.waiting_2fa)
async def input_2fa(message: types.Message, state: FSMContext):
    data = await state.get_data()
    phone = data.get("new_phone")
    password = message.text
    print(f"[BOT] input_2fa user={message.from_user.id} phone={phone}")
    res = await api.enter_2fa(phone, password)
    print(f"[BOT] enter_2fa result phone={phone} res={res}")
    st = res.get("status")
    if st == "authorized":
        await state.clear()
        sessions = await api.list_sessions()
        await message.answer(f"Авторизовано: {phone}", reply_markup=sessions_keyboard(sessions))
        return
    if st == "2fa_incorrect":
        await message.answer("Неверный пароль 2FA. Повторите.")
        return
    await state.clear()
    sessions = await api.list_sessions()
    await message.answer(f"Ошибка: {res.get('detail','unknown')}", reply_markup=sessions_keyboard(sessions))

@dp.callback_query(F.data.startswith("sessions:one:"))
async def session_one(call: types.CallbackQuery, state: FSMContext):
    phone = call.data.split(":", 2)[-1]
    print(f"[BOT] session_one from={call.from_user.id} phone={phone}")
    info = await api.session_info(phone)
    status_text = "Неизвестно"
    if info.get("status") == "ok":
        auth = info.get("authorized")
        if auth:
            uname = info.get("username") or info.get("first_name") or ""
            if uname:
                status_text = f"Авторизовано как @{uname}" if not uname.isnumeric() else f"Авторизовано"
            else:
                status_text = "Авторизовано"
        else:
            status_text = "Не авторизовано"
    kb = InlineKeyboardBuilder()
    kb.button(text="↩️ Назад", callback_data="menu:sessions")
    await call.message.edit_text(f"Сессия: {phone}\nСтатус: {status_text}", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "menu:call")
async def menu_call(call: types.CallbackQuery, state: FSMContext):
    print(f"[BOT] menu_call pressed from={call.from_user.id}")
    sessions = await api.list_sessions()
    await state.clear()
    await call.message.edit_text("Выберите сессию для звонка:", reply_markup=call_sessions_keyboard(sessions))

@dp.callback_query(F.data.startswith("call:from:"))
async def call_from_selected(call: types.CallbackQuery, state: FSMContext):
    number = call.data.split(":", 2)[-1]
    print(f"[BOT] call_from_selected from={call.from_user.id} number={number}")
    await state.set_state(CallStates.waiting_username)
    await state.update_data(call_from=number)
    await call.message.edit_text(f"Введите @username или ссылку на пользователя для звонка от {number}:")

@dp.message(CallStates.waiting_username)
async def call_enter_username(message: types.Message, state: FSMContext):
    data = await state.get_data()
    number = data.get("call_from")
    username = message.text.strip()
    await message.reply("Позвоним через 30 секунд....")
    await asyncio.sleep(30)
    await message.reply_sticker("CAACAgIAAxkBAAEN1fNntLPXRVc5iyd-PqrIrNZYy7PDswACQQEAAs0bMAjx8GIY3_aWWDYE")
    print(f"[BOT] call_enter_username from={message.from_user.id} number={number} to={username}")
    res = await api_call_start(number, username)
    http = res.get("http")
    status_val = res.get("status")
    if http in (200, 202) and status_val == "call_started":
        await state.clear()
        await message.answer(f"Звонок запущен от {number} к {username}.", reply_markup=start_keyboard())
        return
    if status_val == "already_in_call":
        await message.answer(f"Уже идёт звонок от {number} к {res.get('to')}.")
        return
    if status_val == "not_authorized":
        await state.clear()
        await message.answer(f"Сессия {number} не авторизована.", reply_markup=start_keyboard())
        return
    await state.clear()
    await message.answer(f"Ошибка запуска звонка: {res}", reply_markup=start_keyboard())
    

async def on_shutdown():
    await api.close()

if __name__ == '__main__':
    try:
        dp.run_polling(bot)
    finally:
        asyncio.run(on_shutdown())
