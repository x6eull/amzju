import asyncio
from datetime import datetime, timedelta
from typing import Generic, Optional, TypeVar

K = TypeVar("K")
T = TypeVar("T")


class Session(Generic[T]):
    value: T
    not_after: datetime

    def __init__(self, value: T, valid_duration: int):
        """新建一个session。有效期单位为秒"""
        self.value = value
        self.not_after = datetime.now() + timedelta(seconds=valid_duration)

    def is_expired(self, reserved: int = 0) -> bool:
        if reserved == 0:
            return datetime.now() > self.not_after
        return datetime.now() + timedelta(seconds=reserved) > self.not_after


class SessionJar(Generic[K, T]):
    __inner: dict[K, Session[T]] = dict()

    def set(self, key: K, value: T, valid_duration: int):
        """新建(覆盖相同key)session。有效期单位为秒"""
        self.__inner[key] = Session(value, valid_duration)

    def get(
        self, key: K, expire_reserved_seconds: int = 0
    ) -> Optional[tuple[T, datetime]]:
        if key not in self.__inner:
            return None
        result = self.__inner[key]
        if result.is_expired(expire_reserved_seconds):
            return None
        return (self.__inner[key].value, self.__inner[key].not_after)

    def __init__(self, cleanup_interval: int):
        self.task = asyncio.get_event_loop().create_task(
            self.__cleanup(cleanup_interval)
        )

    def __del__(self):
        self.task.cancel()

    async def __cleanup(self, cleanup_interval: int):
        try:
            while True:
                await asyncio.sleep(cleanup_interval)
                self.__inner = {
                    k: v for k, v in self.__inner.items() if not v.is_expired()
                }

        except asyncio.CancelledError:
            pass
