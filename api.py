from fastapi import FastAPI, Request, status, Query
from fastapi.responses import JSONResponse
import traceback
import uvicorn
import os
import configparser
from pytgcalls import PyTgCalls
from pytgcalls.types import CallConfig

from account_manager import AccountManager

app = FastAPI()

manager = AccountManager(
    sessions_dir="sessions",
    api_id=2040,
    api_hash="b18441a1ff607e10a989891a5462e627",
    device_model="ASUS ZenBook 13",
    system_version="Windows 10",
    app_version="1.0.0",
    lang_code="en",
    system_lang_code="en",
    proxy=None
)

ACTIVE_CALLS = {}

@app.post("/sessions/initNew")
async def init_new(request: Request):
    try:
        data = await request.json()
        number = data["number"]
        print(f"[API] /sessions/initNew number={number}")
        res = await manager.init_new(number)
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=res)
    except Exception as e:
        print(f"[API] /sessions/initNew error err={e}")
        traceback.print_exc()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "detail": str(e)})

@app.post("/sessions/enterCode")
async def enter_code(request: Request):
    try:
        data = await request.json()
        number = data["number"]
        code = data["code"]
        print(f"[API] /sessions/enterCode number={number} code_len={len(str(code))}")
        res = await manager.enter_code(number, code)
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=res)
    except Exception as e:
        print(f"[API] /sessions/enterCode error err={e}")
        traceback.print_exc()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "detail": str(e)})

@app.post("/sessions/enter2FA")
async def enter_2fa(request: Request):
    try:
        data = await request.json()
        number = data["number"]
        password = data["password"]
        print(f"[API] /sessions/enter2FA number={number} pwd_len={len(str(password))}")
        res = await manager.enter_2fa(number, password)
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=res)
    except Exception as e:
        print(f"[API] /sessions/enter2FA error err={e}")
        traceback.print_exc()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "detail": str(e)})

@app.get("/sessions/list")
async def sessions_list():
    try:
        print(f"[API] /sessions/list")
        items = []
        os.makedirs(manager.sessions_dir, exist_ok=True)
        for name in sorted(os.listdir(manager.sessions_dir)):
            p = os.path.join(manager.sessions_dir, name)
            if not os.path.isdir(p):
                continue
            info_path = os.path.join(p, "info.ini")
            if not os.path.exists(info_path):
                continue
            cfg = configparser.ConfigParser()
            cfg.read(info_path, encoding="utf-8")
            number = cfg.get("ACCOUNT_INFO", "acc_number", fallback=None)
            if not number:
                continue
            authorized = False
            username = None
            first_name = None
            client = await manager.get_client(number)
            if client:
                me = await client.get_me()
                username = me.username
                first_name = me.first_name
                authorized = True
                await client.disconnect()
            items.append({"number": number, "authorized": authorized, "username": username, "first_name": first_name})
        return JSONResponse(status_code=status.HTTP_200_OK, content={"sessions": items})
    except Exception as e:
        print(f"[API] /sessions/list error err={e}")
        traceback.print_exc()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "detail": str(e)})

@app.get("/sessions/info")
async def sessions_info(number: str = Query(...)):
    try:
        print(f"[API] /sessions/info number={number}")
        authorized = False
        username = None
        first_name = None
        client = await manager.get_client(number)
        if client:
            me = await client.get_me()
            username = me.username
            first_name = me.first_name
            authorized = True
            await client.disconnect()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "number": number, "authorized": authorized, "username": username, "first_name": first_name})
    except Exception as e:
        print(f"[API] /sessions/info error err={e}")
        traceback.print_exc()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "detail": str(e)})

@app.post("/call/start")
async def call_start(request: Request):
    try:
        data = await request.json()
        number = data["number"]
        to_username = data["username"]
        print(f"[API] /call/start number={number} to={to_username}")
        if number in ACTIVE_CALLS:
            return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"status": "already_in_call", "number": number, "to": ACTIVE_CALLS[number]["to"]})
        client = await manager.get_client(number)
        if not client:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": "not_authorized", "number": number})
        try:
            await client.get_entity(to_username)
            call_py = PyTgCalls(client)
            await call_py.start()
            await call_py.play(chat_id=to_username, stream=None, config=CallConfig())
            ACTIVE_CALLS[number] = {"to": to_username, "pytgcalls": call_py, "client": client}
            print(f"[API] /call/start started number={number} to={to_username}")
            return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "call_started", "number": number, "to": to_username})
        except Exception as e:
            print(f"[API] /call/start error number={number} err={e}")
            traceback.print_exc()
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "detail": str(e)})
    except Exception as e:
        print(f"[API] /call/start outer error err={e}")
        traceback.print_exc()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "detail": str(e)})
    finally:
        await client.disconnect()

if __name__ == "__main__":
    print("[INFO] Starting CallMeJoe...")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
