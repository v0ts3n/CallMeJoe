import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import aiohttp

logging.basicConfig(level=logging.INFO)

class CallMeJoeAPI:
    def __init__(self, base_url: str, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_sess(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def list_sessions(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/sessions/list"
        sess = await self._get_sess()
        try:
            print(f"[API] GET {url}")
            async with sess.get(url) as r:
                txt = await r.text()
                print(f"[API] {r.status} {txt}")
                if r.status == 200:
                    data = json.loads(txt)
                    return data.get("sessions", [])
        except Exception as e:
            print(f"[API] list_sessions error {e}")
        return []

    async def session_info(self, number: str) -> Dict[str, Any]:
        url = f"{self.base_url}/sessions/info"
        params = {"number": number}
        sess = await self._get_sess()
        try:
            print(f"[API] GET {url} {params}")
            async with sess.get(url, params=params) as r:
                txt = await r.text()
                print(f"[API] {r.status} {txt}")
                if r.status == 200:
                    return json.loads(txt)
        except Exception as e:
            print(f"[API] session_info error {e}")
        return {"status": "error"}

    async def init_new(self, number: str) -> Dict[str, Any]:
        url = f"{self.base_url}/sessions/initNew"
        payload = {"number": number}
        sess = await self._get_sess()
        try:
            print(f"[API] POST {url} {payload}")
            async with sess.post(url, json=payload) as r:
                txt = await r.text()
                print(f"[API] {r.status} {txt}")
                if r.status in (200, 202):
                    return json.loads(txt)
        except Exception as e:
            print(f"[API] init_new error {e}")
        return {"status": "error"}

    async def enter_code(self, number: str, code: str) -> Dict[str, Any]:
        url = f"{self.base_url}/sessions/enterCode"
        payload = {"number": number, "code": code}
        sess = await self._get_sess()
        try:
            print(f"[API] POST {url} {payload}")
            async with sess.post(url, json=payload) as r:
                txt = await r.text()
                print(f"[API] {r.status} {txt}")
                if r.status in (200, 202):
                    return json.loads(txt)
        except Exception as e:
            print(f"[API] enter_code error {e}")
        return {"status": "error"}

    async def enter_2fa(self, number: str, password: str) -> Dict[str, Any]:
        url = f"{self.base_url}/sessions/enter2FA"
        payload = {"number": number, "password": password}
        sess = await self._get_sess()
        try:
            print(f"[API] POST {url} {payload}")
            async with sess.post(url, json=payload) as r:
                txt = await r.text()
                print(f"[API] {r.status} {txt}")
                if r.status in (200, 202):
                    return json.loads(txt)
        except Exception as e:
            print(f"[API] enter_2fa error {e}")
        return {"status": "error"}
