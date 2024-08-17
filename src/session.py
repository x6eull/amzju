import asyncio
from datetime import datetime, timedelta
import secrets
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


class Session(Generic[T]):
    value: T
    not_after: datetime

    def __init__(self, value: T, valid_duration: int):
        """新建一个session。有效期单位为秒"""
        self.value = value
        self.not_after = datetime.now() + timedelta(seconds=valid_duration)

    def is_expired(self) -> bool:
        return datetime.now() > self.not_after


class SessionJar(Generic[T]):
    __inner: dict[str, Session[T]] = dict()

    def insert(self, value: T, valid_duration: int = 3600) -> str:
        """新建一个session，返回一个随机串作为id。
        session默认有效时间为3600s，随机串为64bytes，按URL安全的base64编码。"""
        key = secrets.token_urlsafe(64)
        self.__inner[key] = Session(value, valid_duration)
        return key

    def get(self, key: str) -> Optional[T]:
        if key not in self.__inner:
            return None
        return self.__inner[key].value

    def __init__(self):
        self.task = asyncio.get_event_loop().create_task(self.__cleanup())

    def __del__(self):
        self.task.cancel()

    async def __cleanup(self):
        while True:
            await asyncio.sleep(60)
            self.__inner = {k: v for k, v in self.__inner.items() if not v.is_expired()}
