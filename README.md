# 📞 CallMeJoe — бот для "спасительных" звонков

**CallMeJoe** — это Telegram-бот, который может **позвонить вам самому себе**.  
Полезен в неловких и неудобных ситуациях, когда нужен "спасительный звонок":

- 💬 Надо выйти из скучного разговора.  
- 🚪 Хочется уйти из встречи.  
- 📱 Нужно сделать вид, что кто-то звонит.  

---

## 🚀 Возможности
- Добавление нескольких Telegram-аккаунтов.  
- Авторизация через код и 2FA.  
- Просмотр и управление сессиями.  
- Запуск звонка самому себе с выбранного аккаунта.  

---

## ⚙️ Технологии
- Python 3.11+  
- [Telethon](https://github.com/LonamiWebs/Telethon)  
- [PyTgCalls](https://github.com/pytgcalls/pytgcalls)  
- [FastAPI](https://fastapi.tiangolo.com/)  
- [Aiogram v3](https://github.com/aiogram/aiogram)  
- [Uvicorn](https://www.uvicorn.org/)  

---

## 📦 Установка
```bash
git clone https://github.com/yourusername/CallMeJoe.git
cd CallMeJoe
python -m venv venv
source venv/bin/activate   # или venv\Scripts\activate на Windows
pip install -r req.txt
