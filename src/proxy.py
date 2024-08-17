from typing import Annotated, Optional
from fastapi import APIRouter, Header, responses, status
import httpx
from pydantic import BaseModel, Field, HttpUrl

from .static import sessions, default_headers

router = APIRouter(
    prefix="/proxy",
    responses={401: {"description": "Please login first"}},
)


class ProxyTextBody(BaseModel):
    method: str = Field(pattern=r"^[A-Z]{1,10}$")
    url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    body: Optional[str] = Field(default=None)


@router.post("/text")
async def text_proxy(
    az_token: Annotated[str, Header()],
    body: ProxyTextBody,
):
    """代理纯文本请求。适用于JSON/XML/HTML等格式API"""
    session_cookies = sessions.get(az_token)
    if session_cookies is None:
        return responses.Response(status_code=status.HTTP_401_UNAUTHORIZED)

    async with httpx.AsyncClient(
        cookies=session_cookies, headers=default_headers
    ) as client:
        response = await client.request(
            method=body.method,
            url=str(body.url),
            headers=body.headers,
            content=body.body,
            cookies=session_cookies,
        )
        return responses.Response(
            status_code=response.status_code,
            content=response.content,
            headers=response.headers,
        )
