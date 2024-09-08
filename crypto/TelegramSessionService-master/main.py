import asyncio
import json
import os
import random
import re
import string
from random import choice
from urllib.parse import unquote

import python_socks
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telethon import TelegramClient, functions
from telethon.errors import PhoneNumberInvalidError
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import InputPeerNotifySettings, NotificationSoundNone, InputBotAppShortName
from unidecode import unidecode

from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException

from openteleMain.src.api import UseCurrentSession
from openteleMain.src.exception import TDesktopUnauthorized, OpenTeleException
from openteleMain.src.td import TDesktop
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ApiJsonError(Exception):
    pass

class ProxyError(Exception):
    pass

class SessionInvalidError(Exception):
    pass

app = FastAPI()

SYSTEM_VERSIONS = ["Windows 10", "Windows 11"]
APP_VERSIONS = [
    "5.3.1", "5.3.0", "5.2.3, ""5.2.2",
    "5.2.0", "5.1.8", "5.1.7", "5.1.6", "5.1.5", "5.1.4", "5.1.3", "5.1.2", "5.1.1", "5.1.0",
    "5.0.0", "4.16.10", "4.16.9", "4.16.8", "4.16.7", "4.16.6", "4.16.5", "4.16.4", "4.16.3",
    "4.16.2", "4.16.1", "4.16.0"
]
DEFAULT_MUTE_SETTINGS = InputPeerNotifySettings(
    silent=True,
    sound=NotificationSoundNone()
)

def handle_exceptions(e, client=None):
    if isinstance(e, ConnectionError):
        logger.error(f"Proxy connection error: {str(e)}")
        raise ProxyError("Failed to connect to proxy")
    elif isinstance(e, asyncio.TimeoutError):
        logger.error(f"Proxy connection timed out: {str(e)}")
        raise ProxyError("Proxy connection timed out")
    else:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(ProxyError)
async def proxy_error_handler(request: Request, exc: ProxyError):
    return JSONResponse(
        status_code=502,
        content={"status": "proxy_error", "detail": str(exc)},
    )

@app.exception_handler(SessionInvalidError)
async def session_invalid_error_handler(request: Request, exc: SessionInvalidError):
    return JSONResponse(
        status_code=400,
        content={"status": "session_invalid", "detail": str(exc)},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"status": "validation_error", "detail": exc.errors()},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "detail": exc.detail},
    )

def proccess_api_json(api_json):
    if "app_id" in api_json:
        api_json["api_id"] = api_json["app_id"]
    elif "api_id" in api_json:
        api_json["app_id"] = api_json["api_id"]
    else:
        raise ApiJsonError()

    if "app_hash" in api_json:
        api_json["api_hash"] = api_json["app_hash"]
    elif "api_hash" in api_json:
        api_json["app_hash"] = api_json["api_hash"]
    else:
        raise ApiJsonError()

    if "device" in api_json:
        api_json["device_model"] = api_json["device"]
    elif "device_model" in api_json:
        api_json["device"] = api_json["device_model"]
    else:
        raise ApiJsonError()

    if "system_version" not in api_json:
        api_json["system_version"] = ""

    if "app_version" not in api_json:
        raise ApiJsonError()

    if "system_lang_code" not in api_json:
        raise ApiJsonError()

    if "lang_code" not in api_json:
        api_json["lang_code"] = api_json["system_lang_code"]

    if "lang_pack" not in api_json:
        raise ApiJsonError()

    return api_json


def get_system_version():
    return choice(SYSTEM_VERSIONS)


def get_app_version():
    return choice(APP_VERSIONS) + " x64"


async def _get_client(data, proxy_dict):
    if data['sessionType'] == 'tdata':
        tdata = TDesktop(os.path.join(data['pathDirectory'], data['id']))
        tdata.api.system_version = get_system_version()
        tdata.api.app_version = get_app_version()
        client = await tdata.ToTelethon(
            os.path.join(data['pathDirectory'], str(data['id']) + '.session'),
            api=tdata.api,
            proxy=proxy_dict,
            auto_reconnect=False,
            connection_retries=0,
            api_id=tdata.api.api_id,
            api_hash=tdata.api.api_hash,
            device_model=tdata.api.device_model,
            system_version=tdata.api.system_version,
            app_version=tdata.api.app_version,
            lang_code=tdata.api.lang_code,
            system_lang_code=tdata.api.system_lang_code,
            receive_updates=False,
            flag=UseCurrentSession
        )
        data["type"] = "telethon"
        data['apiJson'] = proccess_api_json({
            "api_id": tdata.api.api_id,
            "api_hash": tdata.api.api_hash,
            "device_model": tdata.api.device_model,
            "device": tdata.api.device_model,
            "system_version": tdata.api.system_version,
            "app_version": tdata.api.app_version,
            "system_lang_code": tdata.api.system_lang_code,
            "app_version": tdata.api.app_version,
            "lang_code": tdata.api.lang_code,
            "lang_pack": tdata.api.lang_pack,
            "pid": tdata.api.pid
        })
    else:
        client = TelegramClient(
            session=os.path.join(data['pathDirectory'], data['id']) + ".session",
            api_id=data['apiJson']['api_id'],
            api_hash=data['apiJson']['api_hash'],
            device_model=data['apiJson']['device_model'],
            system_version=data['apiJson']['system_version'],
            app_version=data['apiJson']['app_version'],
            lang_code=data['apiJson']['lang_code'],
            receive_updates=False,
            proxy=proxy_dict,
            auto_reconnect=False,
            connection_retries=0
        )

    return client


async def set_username_if_not_exists(client):
    me = await client.get_me()
    if me.username is None:
        username = generate_username(me.first_name, me.last_name)
        await client(functions.account.UpdateUsernameRequest(username))
        me = await client.get_me()
        if me.username is None:
            raise Exception("Username not set")


async def _get_blum(client, data):
    if data["referralCode"] is not None:
        web_view = await client(functions.messages.RequestWebViewRequest(
            peer='BlumCryptoBot',
            bot='BlumCryptoBot',
            platform='android',
            from_bot_menu=True,
            url="https://telegram.blum.codes/",
            start_param=data["referralCode"]
        ))
    else:
        web_view = await client(functions.messages.RequestWebViewRequest(
            peer='BlumCryptoBot',
            bot='BlumCryptoBot',
            platform='android',
            from_bot_menu=True,
            url="https://telegram.blum.codes/"
        ))

    auth_url = web_view.url
    tg_web_app_data = unquote(
        string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
    return tg_web_app_data, auth_url


async def _get_iceberg(client, data):
    try:
        chat = await client.get_input_entity('IcebergAppBot')
        messages = await client.get_messages(chat, limit=1)
        if not len(messages):
            if data["referralCode"] is None or data["referralCode"] == "":
                await client.send_message('IcebergAppBot', '/start')
            else:
                await client.send_message('IcebergAppBot', '/start ' + data["referralCode"])
    except:
        pass
    web_view = await client(functions.messages.RequestWebViewRequest(
        peer='IcebergAppBot',
        bot='IcebergAppBot',
        platform='android',
        from_bot_menu=True,
        url='https://0xiceberg.com/webapp/',
    ))
    auth_url = web_view.url
    tg_web_app_data = unquote(
        string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
    return tg_web_app_data, auth_url


async def _get_tapswap(client, data):
    try:
        chat = await client.get_input_entity('tapswap_bot')
        messages = await client.get_messages(chat, limit=1)
        if not len(messages):
            if data["referralCode"] is None or data["referralCode"] == "":
                await client.send_message('tapswap_bot', '/start')
            else:
                await client.send_message('tapswap_bot', '/start ' + data["referralCode"])
    except:
        pass
    web_view = await client(functions.messages.RequestWebViewRequest(
        peer='tapswap_bot',
        bot='tapswap_bot',
        platform='android',
        from_bot_menu=True,
        url='https://app.tapswap.club/',
    ))
    auth_url = web_view.url
    tg_web_app_data = unquote(
        string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
    return tg_web_app_data, auth_url


async def _get_banana(client, data):
    chat = await client.get_input_entity('OfficialBananaBot')
    if data["referralCode"] is not None:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="banana"),
            platform='android',
            write_allowed=True,
            start_param="referral=" + data["referralCode"]
        ))
    else:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="banana"),
            platform='android',
            write_allowed=True,
        ))
    auth_url = web_view.url
    tg_web_app_data = unquote(
        string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
    return tg_web_app_data, auth_url


async def _get_onewin(client, data):
    chat = await client.get_input_entity('token1win_bot')
    if data["referralCode"] is not None:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="start"),
            platform='android',
            write_allowed=True,
            start_param=data["referralCode"]
        ))
    else:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="start"),
            platform='android',
            write_allowed=True,
        ))
    auth_url = web_view.url
    tg_web_app_data = unquote(
        string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
    return tg_web_app_data, auth_url


async def _get_clayton(client, data):
    chat = await client.get_input_entity('claytoncoinbot')
    if data["referralCode"] is not None:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="game"),
            platform='android',
            write_allowed=True,
            start_param=data["referralCode"]
        ))
    else:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="game"),
            platform='android',
            write_allowed=True,
        ))
    auth_url = web_view.url
    tg_web_app_data = unquote(
        string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
    return tg_web_app_data, auth_url


async def _get_cats(client, data):
    chat = await client.get_input_entity('catsgang_bot')
    if data["referralCode"] is not None:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="join"),
            platform='android',
            write_allowed=True,
            start_param=data["referralCode"]
        ))
    else:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="join"),
            platform='android',
            write_allowed=True,
        ))
    auth_url = web_view.url
    tg_web_app_data = unquote(
        string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
    return tg_web_app_data, auth_url


async def _get_major(client, data):
    chat = await client.get_input_entity('major')
    if data["referralCode"] is not None:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="start"),
            platform='android',
            write_allowed=True,
            start_param=data["referralCode"]
        ))
    else:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="start"),
            platform='android',
            write_allowed=True,
        ))
    auth_url = web_view.url
    tg_web_app_data = unquote(
        string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
    return tg_web_app_data, auth_url


async def _get_tonstation(client, data):
    chat = await client.get_input_entity('tonstationgames_bot')
    if data["referralCode"] is not None:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="app"),
            platform='android',
            write_allowed=True,
            start_param=data["referralCode"]
        ))
    else:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="app"),
            platform='android',
            write_allowed=True,
        ))
    auth_url = web_view.url
    tg_web_app_data = unquote(
        string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
    return tg_web_app_data, auth_url


async def _get_horizon(client, data):
    chat = await client.get_input_entity('HorizonLaunch_bot')
    if data["referralCode"] is not None:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="HorizonLaunch"),
            platform='android',
            write_allowed=True,
            start_param=data["referralCode"]
        ))
    else:
        web_view = await client(functions.messages.RequestAppWebViewRequest(
            peer='me',
            app=InputBotAppShortName(bot_id=chat, short_name="HorizonLaunch"),
            platform='android',
            write_allowed=True,
        ))
    auth_url = web_view.url
    tg_web_app_data = unquote(
        string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
    return tg_web_app_data, auth_url


async def _get_tg_web_app_data(data, proxy_dict):
    client = None
    service_map = {
        "blum": _get_blum,
        "iceberg": _get_iceberg,
        "tapswap": _get_tapswap,
        "onewin": _get_onewin,
        "banana": _get_banana,
        "clayton": _get_clayton,
        "cats": _get_cats,
        "major": _get_major,
        "tonstation": _get_tonstation,
        "horizon": _get_horizon
    }
    try:
        client = await _get_client(data, proxy_dict)
        await client.start(phone='0')
        if data["isUpload"] and data["sessionType"] == "telethon":
            tdata = await client.ToTDesktop(flag=UseCurrentSession)
            tdata.SaveTData(os.path.join(data['pathDirectory'], data["id"]))
        await set_username_if_not_exists(client)
        me = await client.get_me()

        service_func = service_map.get(data["service"])
        if service_func:
            tg_web_app_data, auth_url = await service_func(client, data)
        else:
            tg_web_app_data, auth_url = None, None

        await client.disconnect()
        return JSONResponse(
            {
                "status": "success",
                "tgWebAppData": tg_web_app_data,
                'authUrl': auth_url,
                "number": me.phone,
                "apiJson": json.dumps(data['apiJson']),
                'username': me.username
            })
    except Exception as e:
        with open("error.txt", "a") as f:
            f.write(str(e) + "\n")
        handle_exceptions(e)
    finally:
        if client:
            try:
                if client is not None:
                    await client.disconnect()
            except Exception as e:
                handle_exceptions(e)    

@app.post("/api/getTgWebAppData")
async def get_tg_web_app_data(request: Request):
    data = await request.json()
    if data['apiJson'] is not None:
        data['apiJson'] = proccess_api_json(json.loads(data['apiJson']))
    split_proxy = data['proxy'].split(':')
    proxy_dict = {
        "proxy_type": python_socks.ProxyType.SOCKS5 if split_proxy[0] == 'socks5' else python_socks.ProxyType.HTTP,
        "addr": split_proxy[1],
        "port": int(split_proxy[2]),
        "username": split_proxy[3],
        "password": split_proxy[4],
        'rdns': True
    }
    try:
        return await asyncio.wait_for(_get_tg_web_app_data(data, proxy_dict), timeout=20)
    except (TDesktopUnauthorized, OpenTeleException, PhoneNumberInvalidError, ApiJsonError) as e:
        logger.error(f"Session invalid error: {str(e)}")
        raise SessionInvalidError(str(e))
    except Exception as e:
        handle_exceptions(e)


@app.post("/api/joinChannels")
async def join_channels(request: Request):
    client = None
    try:
        data = await request.json()
        if data['apiJson'] is not None:
            data['apiJson'] = proccess_api_json(json.loads(data['apiJson']))
        split_proxy = data['proxy'].split(':')
        proxy_dict = {
            "proxy_type": python_socks.ProxyType.SOCKS5 if split_proxy[0] == 'socks5' else python_socks.ProxyType.HTTP,
            "addr": split_proxy[1],
            "port": int(split_proxy[2]),
            "username": split_proxy[3],
            "password": split_proxy[4],
            'rdns': True
        }
        client = await _get_client(data, proxy_dict)
        await client.start(phone='0')
        me = await client.get_me()
        for channel in data['channels']:
            channel = await client.get_entity(channel)
            try:
                await client(GetParticipantRequest(channel, me.id))
            except:
                await client(functions.channels.JoinChannelRequest(channel))
                await client(UpdateNotifySettingsRequest(
                    peer=channel,
                    settings=DEFAULT_MUTE_SETTINGS
                ))
                await client.edit_folder(channel, 1)
        await client.disconnect()
        return JSONResponse({"status": "success"})
    except (TDesktopUnauthorized, OpenTeleException, PhoneNumberInvalidError, ApiJsonError) as e:
        logger.error(f"Session invalid error: {str(e)}")
        raise SessionInvalidError(str(e))
    except Exception as e:
        with open("error.txt", "a") as f:
            f.write(str(e) + "\n")
        handle_exceptions(e)
    finally:
        if client:
            try:
                if client is not None:
                    await client.disconnect()
                    client = None
            except Exception as e:
                handle_exceptions(e)    

@app.post("/api/createTData")
async def save_tdata(request: Request):
    client = None
    try:
        try:
            data = await request.json()
            if data['apiJson'] is not None:
                data['apiJson'] = proccess_api_json(json.loads(data['apiJson']))
            split_proxy = data['proxy'].split(':')
            proxy_dict = {
                "proxy_type": python_socks.ProxyType.SOCKS5 if split_proxy[0] == 'socks5' else python_socks.ProxyType.HTTP,
                "addr": split_proxy[1],
                "port": int(split_proxy[2]),
                "username": split_proxy[3],
                "password": split_proxy[4],
                'rdns': True
            }
            client = await _get_client(data, proxy_dict)
            tdata = await client.ToTDesktop(flag=UseCurrentSession)
            tdata.save(data['pathDirectory'])
            return JSONResponse({"status": "success"})
        except (TDesktopUnauthorized, OpenTeleException, PhoneNumberInvalidError, ApiJsonError) as e:
            logger.error(f"Session invalid error: {str(e)}")
            raise SessionInvalidError(str(e))
        except Exception as e:
            handle_exceptions(e)
    finally:
        if client:
            try:
                if client is not None:
                    await client.disconnect()
            except Exception as e:
                handle_exceptions(e)

def generate_username(first_name=None, last_name=None):
    base_username = "_".join(
        part.lower().replace(" ", "_") for part in (first_name, last_name) if part
    )

    if not base_username:
        base_username = ''.join(random.choices(string.ascii_lowercase, k=8))

    base_username = unidecode(base_username)
    username = base_username + str(random.randint(100, 2000))

    username = re.sub(r'[^a-zA-Z0-9_]', '', username)[:30]

    return username


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5000)
