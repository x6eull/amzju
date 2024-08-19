import base64
from typing import Annotated
from fastapi import APIRouter, Body, Depends, HTTPException, Header, responses, status
import httpx
from pydantic import Base64Bytes, HttpUrl

from .login import (
    SESSION_DURATION,
    ServiceParamsWithClientId,
    ServiceParamsWithService,
    UsernamePasswordCredential,
    generate_token_bytes,
    login,
)
from .utils import sessions, default_headers

router = APIRouter(prefix="/proxy")


async def ensure_session(
    az_token: Annotated[Base64Bytes | None, Header()] = None,
    service_params: Annotated[
        ServiceParamsWithClientId | ServiceParamsWithService | None, Body(embed=True)
    ] = None,
    credential: Annotated[UsernamePasswordCredential | None, Body(embed=True)] = None,
    refresh_after: Annotated[
        int, Body(embed=True, ge=0, le=60 * 60 * 24 * 365 * 10)
    ] = SESSION_DURATION,  # 要求已有的会话持续时间不能超过多久，若为0，表明每次代理请求均登录(不推荐)
) -> tuple[bytes, httpx.Cookies]:
    # 如果没有提供token且允许使用之前的会话，尝试从username/password获取token
    if not az_token and refresh_after > 0:
        if service_params is None or credential is None:
            raise HTTPException(status.HTTP_407_PROXY_AUTHENTICATION_REQUIRED)
        az_token = generate_token_bytes(credential.username, credential.password)

    if az_token is not None:
        result = sessions.get(az_token, SESSION_DURATION - refresh_after)
        if result is not None:
            return (az_token, result[0])

    # 会话已过期（或不存在，继续尝试登录）
    if service_params is None or credential is None:
        raise HTTPException(status.HTTP_407_PROXY_AUTHENTICATION_REQUIRED)
    login_result = await login(service_params, credential)
    return login_result


@router.post("/text")
async def text_proxy(
    session: Annotated[tuple[bytes, httpx.Cookies], Depends(ensure_session)],
    method: Annotated[str, Body(embed=True, pattern=r"^[A-Z]{1,10}$")],
    url: Annotated[HttpUrl, Body(embed=True)],
    headers: Annotated[dict[str, str], Body(embed=True, default_factory=dict)],
    body: Annotated[str | None, Body(embed=True)] = None,
):
    """代理纯文本请求。适用于JSON/XML/HTML等格式API"""
    (token_bytes, cookies) = session
    async with httpx.AsyncClient(cookies=cookies, headers=default_headers) as client:
        response = await client.request(
            method=method,
            url=str(url),
            headers=headers,
            content=body,
        )
        response.headers["az-token"] = base64.standard_b64encode(token_bytes).decode(
            "utf-8"
        )
        return responses.Response(
            status_code=response.status_code,
            content=response.content,
            headers=response.headers,
        )
