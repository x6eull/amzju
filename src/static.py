import os
from httpx import Cookies
from src.session import SessionJar


sessions: SessionJar[Cookies] = SessionJar()


default_headers = {
    "User-Agent": os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "*/*",
}


def before_sep(text: str, sep: str) -> str:
    result = text.split(sep, 1)[0]
    assert result is not None
    return result
