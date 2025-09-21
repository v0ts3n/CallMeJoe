from telethon import TelegramClient

from pytgcalls import idle
from pytgcalls import PyTgCalls
from pytgcalls.types import CallConfig
import asyncio
import os
import configparser
from telethon.errors import SessionPasswordNeededError, PasswordHashInvalidError


        
        





async def callHim(client: TelegramClient, to_username: str):
    try:

        await client.get_entity(to_username)
        call_py = PyTgCalls(client)
        await call_py.start()
        await call_py.play(
            chat_id=to_username,
            stream=None, config=CallConfig())
        
        await client.disconnect()
        print("disconnected from session")
        return True
    except Exception as e:
        print(e)
        await client.disconnect()
        return False