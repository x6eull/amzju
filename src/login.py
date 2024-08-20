from asyncio import gather
import hashlib
import re
import secrets
from typing import Annotated, Literal
from urllib.parse import urlencode
from fastapi import Body, HTTPException, status
import httpx
from pydantic import BaseModel, BeforeValidator, Field, HttpUrl
import pydantic_core

from .utils import config, sessions, default_headers


class ServiceParamsBase(BaseModel):
    def get_entry(self) -> str:
        raise NotImplementedError


class ServiceParamsWithClientId(ServiceParamsBase):
    """
    通过client_id、redirect_uri标识的服务
    """

    response_type: Literal["code"]
    client_id: str = Field(pattern=r"^[a-zA-Z0-9]{1,32}$")
    redirect_uri: HttpUrl

    def get_entry(self) -> str:
        return f"https://zjuam.zju.edu.cn/cas/oauth2.0/authorize?{urlencode({
            'response_type': self.response_type,
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            })}"


class ServiceParamsWithService(ServiceParamsBase):
    """
    通过service标识的服务
    """

    service: HttpUrl

    def get_entry(self) -> str:
        return (
            f"https://zjuam.zju.edu.cn/cas/login?{urlencode({'service': self.service})}"
        )


class UsernamePasswordCredential(BaseModel):
    username: str = Field(pattern=r"^[0-9]{1,10}$")
    password: str = Field(min_length=1, max_length=32)


def __convert_int_from_hex(x: str) -> int:
    assert isinstance(x, str)
    return int(x, 16)


IntFromHex = Annotated[int, BeforeValidator(__convert_int_from_hex)]


class PublicKey(BaseModel):
    modulus: IntFromHex
    exponent: IntFromHex


async def get_public_key(client: httpx.AsyncClient, referer: str):
    """
    获取公钥。不会关闭client
    """
    resp = await client.get(
        "https://zjuam.zju.edu.cn/cas/v2/getPubKey", headers={"referer": referer}
    )
    json = resp.json()
    return PublicKey(**json)


def is_under_zjuam_domain(url: str | httpx.URL | pydantic_core.Url) -> bool:
    # 如果字符串 开头 的零个或多个字符与此正则表达式匹配，则返回相应的 Match。 如果字符串与模式不匹配则返回 None
    return re.match(r"https?://zjuam\.zju\.edu\.cn(/|$)", str(url)) is not None


async def login(
    service_params: Annotated[
        ServiceParamsWithClientId | ServiceParamsWithService, Body(embed=True)
    ],
    credential: Annotated[UsernamePasswordCredential, Body(embed=True)],
) -> tuple[bytes, httpx.Cookies]:
    try:
        entry = service_params.get_entry()
        async with httpx.AsyncClient(
            headers=default_headers, cookies=httpx.Cookies(None)
        ) as client:
            login_page_resp = await client.get(
                url=entry,
                follow_redirects=True,
            )
            login_page = login_page_resp.text
            match = re.search(
                r'<input type="hidden" name="execution" value="(?P<execution>[a-zA-Z0-9_=-]+)"',
                login_page,
            )
            if match is None:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY)
            execution = match.group("execution")
            if not isinstance(execution, str):
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY)
            final_url = (
                login_page_resp.url
            )  # 根据service_params获得入口，再重定向后最终POST的URL

            assert is_under_zjuam_domain(final_url)

            pubkey = await get_public_key(client, str(final_url))

            username = credential.username
            password = credential.password

            encrypted_password = hex(
                pow(
                    int.from_bytes(password.encode("utf-8"), "big"),
                    pubkey.exponent,
                    pubkey.modulus,
                )
            )[2:]

            login_result = await client.post(
                final_url,
                data={
                    "username": username,
                    "password": encrypted_password,
                    "authcode": "",
                    "execution": execution,
                    "_eventId": "submit",
                },
                follow_redirects=True,  # 跟随重定向。登录成功判定：最终请求url不在zjuam域名下
            )
            login_result_url = str(login_result.url)

            if is_under_zjuam_domain(login_result_url):  # 登录失败
                raise HTTPException(
                    status_code=status.HTTP_407_PROXY_AUTHENTICATION_REQUIRED
                )

            # token = sha256(instance_id + sha256(username) + sha256(password))
            token_bytes = generate_token_bytes(username, password)

            # 登录成功
            current_cookies = client.cookies
            sessions.set(token_bytes, current_cookies, config.session_duration)
            return (token_bytes, current_cookies)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Gateway Timeout",
        )
    except:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 参与token生成的随机数，每次启动都会变化
instance_id = secrets.token_bytes(32)


def generate_token_bytes(username: str, password: str) -> bytes:
    hash_instance = hashlib.sha256(instance_id)
    hash_instance.update(hashlib.sha256(username.encode("utf-8")).digest())
    hash_instance.update(hashlib.sha256(password.encode("utf-8")).digest())
    return hash_instance.digest()
