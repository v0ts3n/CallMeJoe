import os
import asyncio
import traceback
import configparser
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PasswordHashInvalidError, PhoneCodeInvalidError, PhoneCodeExpiredError

class AccountManager:
    def __init__(self, sessions_dir: str, api_id: int, api_hash: str, device_model: str, system_version: str, app_version: str, lang_code: str, system_lang_code: str, proxy: dict | None = None):
        self.sessions_dir = sessions_dir
        self.api_id = api_id
        self.api_hash = api_hash
        self.device_model = device_model
        self.system_version = system_version
        self.app_version = app_version
        self.lang_code = lang_code
        self.system_lang_code = system_lang_code
        self.proxy = proxy
        self._lock = asyncio.Lock()
        self._state = {}
        os.makedirs(self.sessions_dir, exist_ok=True)

    def _find_session_dir_by_phone(self, phone: str) -> str | None:
        for name in sorted(os.listdir(self.sessions_dir)):
            p = os.path.join(self.sessions_dir, name)
            if not os.path.isdir(p):
                continue
            info_path = os.path.join(p, "info.ini")
            if not os.path.exists(info_path):
                continue
            cfg = configparser.ConfigParser()
            cfg.read(info_path, encoding="utf-8")
            acc = cfg.get("ACCOUNT_INFO", "acc_number", fallback=None)
            if acc and acc.strip() == phone.strip():
                return p
        return None

    def _allocate_session_dir(self, phone: str) -> str:
        existing = [d for d in os.listdir(self.sessions_dir) if os.path.isdir(os.path.join(self.sessions_dir, d)) and d.startswith("Session_")]
        idx = len(existing) + 1
        while True:
            name = f"Session_{idx}"
            path = os.path.join(self.sessions_dir, name)
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
                cfg = configparser.ConfigParser()
                cfg["ACCOUNT_INFO"] = {"acc_number": phone, "session_dir": name}
                with open(os.path.join(path, "info.ini"), "w", encoding="utf-8") as f:
                    cfg.write(f)
                return path
            idx += 1

    def _client_from_dir(self, session_dir: str) -> TelegramClient:
        session_path = os.path.join(session_dir, "telethon.session")
        client = TelegramClient(
            session=session_path,
            api_id=self.api_id,
            api_hash=self.api_hash,
            device_model=self.device_model,
            system_version=self.system_version,
            app_version=self.app_version,
            lang_code=self.lang_code,
            system_lang_code=self.system_lang_code,
            proxy=self.proxy
        )
        return client

    async def init_new(self, phone: str) -> dict:
        async with self._lock:
            try:
                print(f"[AccountManager] init_new start phone={phone}")
                session_dir = self._find_session_dir_by_phone(phone)
                if session_dir is None:
                    session_dir = self._allocate_session_dir(phone)
                client = self._client_from_dir(session_dir)
                await client.connect()
                if await client.is_user_authorized():
                    await client.disconnect()
                    self._state[phone] = {"session_dir": session_dir, "authorized": True, "client": None, "code": None, "twofa": False}
                    print(f"[AccountManager] already_authorized phone={phone}")
                    return {"status": "already_authorized", "number": phone}
                await client.send_code_request(phone)
                self._state[phone] = {"session_dir": session_dir, "authorized": False, "client": client, "code": None, "twofa": False}
                print(f"[AccountManager] code_sent phone={phone}")
                return {"status": "code_sent", "number": phone}
            except Exception as e:
                print(f"[AccountManager] init_new error phone={phone} err={e}")
                traceback.print_exc()
                return {"status": "error", "number": phone, "detail": str(e)}

    async def enter_code(self, phone: str, code: str) -> dict:
        async with self._lock:
            try:
                print(f"[AccountManager] enter_code start phone={phone}")
                st = self._state.get(phone)
                if st is None:
                    session_dir = self._find_session_dir_by_phone(phone)
                    if session_dir is None:
                        print(f"[AccountManager] no_session phone={phone}")
                        return {"status": "no_session", "number": phone}
                    client = self._client_from_dir(session_dir)
                    await client.connect()
                    st = {"session_dir": session_dir, "authorized": await client.is_user_authorized(), "client": client, "code": None, "twofa": False}
                    self._state[phone] = st
                client = st["client"]
                if client is None:
                    client = self._client_from_dir(st["session_dir"])
                    await client.connect()
                    st["client"] = client
                if await client.is_user_authorized():
                    await client.disconnect()
                    st["authorized"] = True
                    st["client"] = None
                    print(f"[AccountManager] already_authorized phone={phone}")
                    return {"status": "already_authorized", "number": phone}
                try:
                    await client.sign_in(phone=phone, code=code)
                    st["authorized"] = True
                    st["code"] = code
                    st["twofa"] = False
                    await client.disconnect()
                    st["client"] = None
                    print(f"[AccountManager] authorized phone={phone}")
                    return {"status": "authorized", "number": phone}
                except SessionPasswordNeededError:
                    st["code"] = code
                    st["twofa"] = True
                    print(f"[AccountManager] 2fa_required phone={phone}")
                    return {"status": "2fa_required", "number": phone}
                except PhoneCodeInvalidError:
                    print(f"[AccountManager] code_invalid phone={phone}")
                    return {"status": "code_invalid", "number": phone}
                except PhoneCodeExpiredError:
                    print(f"[AccountManager] code_expired phone={phone}")
                    return {"status": "code_expired", "number": phone}
            except Exception as e:
                print(f"[AccountManager] enter_code error phone={phone} err={e}")
                traceback.print_exc()
                return {"status": "error", "number": phone, "detail": str(e)}

    async def enter_2fa(self, phone: str, password: str) -> dict:
        async with self._lock:
            try:
                print(f"[AccountManager] enter_2fa start phone={phone}")
                st = self._state.get(phone)
                if st is None:
                    session_dir = self._find_session_dir_by_phone(phone)
                    if session_dir is None:
                        print(f"[AccountManager] no_session phone={phone}")
                        return {"status": "no_session", "number": phone}
                    client = self._client_from_dir(session_dir)
                    await client.connect()
                    st = {"session_dir": session_dir, "authorized": await client.is_user_authorized(), "client": client, "code": None, "twofa": True}
                    self._state[phone] = st
                client = st["client"]
                if client is None:
                    client = self._client_from_dir(st["session_dir"])
                    await client.connect()
                    st["client"] = client
                try:
                    await client.sign_in(password=password)
                    st["authorized"] = True
                    st["twofa"] = False
                    await client.disconnect()
                    st["client"] = None
                    print(f"[AccountManager] authorized phone={phone}")
                    return {"status": "authorized", "number": phone}
                except PasswordHashInvalidError:
                    print(f"[AccountManager] 2fa_incorrect phone={phone}")
                    return {"status": "2fa_incorrect", "number": phone}
            except Exception as e:
                print(f"[AccountManager] enter_2fa error phone={phone} err={e}")
                traceback.print_exc()
                return {"status": "error", "number": phone, "detail": str(e)}

    async def get_client(self, phone: str) -> TelegramClient | None:
        try:
            print(f"[AccountManager] get_client phone={phone}")
            session_dir = self._find_session_dir_by_phone(phone)
            if session_dir is None:
                print(f"[AccountManager] get_client not_found phone={phone}")
                return None
            client = self._client_from_dir(session_dir)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                print(f"[AccountManager] get_client unauthorized phone={phone}")
                return None
            print(f"[AccountManager] get_client ready phone={phone}")
            return client
        except Exception as e:
            print(f"[AccountManager] get_client error phone={phone} err={e}")
            traceback.print_exc()
            return None
