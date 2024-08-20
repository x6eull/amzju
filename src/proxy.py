import asyncio
import base64
from typing import Annotated
from fastapi import APIRouter, Body, Depends, HTTPException, Header, responses, status
import httpx
from pydantic import Base64Bytes, HttpUrl


from .login import (
    ServiceParamsWithClientId,
    ServiceParamsWithService,
    UsernamePasswordCredential,
    generate_token_bytes,
    login,
)
from .utils import config, sessions, default_headers
from .approve import get_credential_from_passphrase

router = APIRouter(prefix="/proxy")


async def ensure_session(
    az_token: Annotated[
        Base64Bytes | None,
        Header(
            description="上次成功登录返回的az-token。用户名密码/token/passphrase三者至少提供一项，都提供时先尝试token。"
        ),
    ] = None,
    service_params: Annotated[
        ServiceParamsWithClientId | ServiceParamsWithService | None,
        Body(
            embed=True,
            description="统一认证使用的服务回调信息。可跟踪正常访问统一认证时的URL，Query中即包含这些参数。如需进行登录(即没有先前的会话)，必须提供此参数",
        ),
    ] = None,
    credential: Annotated[UsernamePasswordCredential | None, Body(embed=True)] = None,
    passphrase: Annotated[
        str | None, Body(embed=True, description="用于Approve模式的通行密钥")
    ] = None,
    max_age: Annotated[
        int | None,
        Body(
            embed=True,
            ge=0,
            le=60 * 60 * 24,
            description="要求已有会话的持续时间不能超过多久(单位: 秒)，若为0，表明每次代理请求均重新登录(不推荐)；不提供则遵循默认的会话持续时间",
        ),
    ] = None,
) -> tuple[bytes, httpx.Cookies]:
    from_passphrase = False
    if passphrase:
        private_cred = get_credential_from_passphrase(passphrase)
        if private_cred is not None:
            credential = UsernamePasswordCredential(**private_cred.model_dump())
            from_passphrase = True

    # 如果没有提供token且允许使用之前的会话，尝试从username/password获取token
    if max_age is None:
        # 不放在参数默认值，防止从文档中看到配置
        max_age = config.session_duration
    if max_age > 0:  # 会话持续时间为0时不使用会话
        if not az_token:
            if service_params is None or credential is None:
                raise HTTPException(status.HTTP_407_PROXY_AUTHENTICATION_REQUIRED)
            az_token = generate_token_bytes(credential.username, credential.password)

        result = sessions.get(az_token, config.session_duration - max_age)
        if result is not None:
            return (az_token, result[0])

    # 会话已过期（或不存在，继续尝试登录）
    if service_params is None or credential is None:
        raise HTTPException(status.HTTP_407_PROXY_AUTHENTICATION_REQUIRED)
    if (
        not from_passphrase
        and config.username_filter.search(credential.username) is None
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, {"message": "Username not allowed"}
        )
    login_result = await login(service_params, credential)
    return login_result


@router.post(
    "/text",
    name="代理纯文本请求",
    response_model=None,
    responses={
        200: {
            "description": "将上游的响应原样返回(将跟随重定向)，包括状态码、headers、body",
            "headers": {
                "az-token": {
                    "description": "可用于代替用户名密码的会话id。amzju不使用cookie，客户端可以保存不同用户的会话id。",
                    "schema": {"type": "string", "format": "password"},
                }
            },
            "content": {
                "application/json": None,
                "*/*": {
                    "schema": {"const": "上游响应的body。Content-Type同样由上游决定。"}
                },
            },
        },
        407: {"description": "登录失败"},
        422: {"description": "参数错误，或实例不允许此用户名登录"},
        500: {"description": "其他内部错误"},
        502: {"description": "登录逻辑错误"},
        504: {"description": "请求上游超时"},
    },
)
async def text_proxy(
    session: Annotated[tuple[bytes, httpx.Cookies], Depends(ensure_session)],
    method: Annotated[str, Body(embed=True, pattern=r"^[A-Z]{1,10}$")],
    url: Annotated[HttpUrl, Body(embed=True)],
    headers: Annotated[dict[str, str] | None, Body(embed=True)] = None,
    body: Annotated[str | None, Body(embed=True)] = None,
):
    """代理纯文本请求。适用于JSON/XML/HTML等格式API"""
    (token_bytes, cookies) = session
    token_dict = {"az-token": base64.standard_b64encode(token_bytes).decode("utf-8")}
    async with httpx.AsyncClient(cookies=cookies, headers=default_headers) as client:
        try:
            response = await client.request(
                method=method,
                url=str(url),
                headers=headers,
                content=body,
                follow_redirects=True,
            )
            response.headers.update(token_dict)
            return responses.Response(
                status_code=response.status_code,
                content=response.content,
                headers=response.headers,
            )
        except httpx.TimeoutException:
            return responses.Response(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content="Gateway Timeout",
                headers=token_dict,
            )
        # 其它Exception直接500
