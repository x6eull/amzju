import json
import os
import re
from typing import Annotated, Literal
from httpx import Cookies
from pydantic import BaseModel, Field
from src.session import SessionJar


class Config(BaseModel):
    # 设置可跨域访问的域名。对其将不限制Method和Header。
    # 空列表则不允许跨域访问。为'*'或['*']则允许所有域名跨域访问。
    cors_allow_origins: list[str] | str
    user_agent: str
    # 会话清理间隔，单位为秒
    session_cleanup_interval: Annotated[int, Field(gt=0)]
    # 会话持续时间，单位为秒
    session_duration: Annotated[int, Field(gt=0)]
    host: str
    # 监听端口，0为随机端口(0传递给uvicorn)
    port: Annotated[int, Field(ge=0, le=65535)]
    username_filter: re.Pattern
    doc_enabled: bool


config_paths = ["config.json", "local.config.json"]
config_combined = dict()
for cpath in config_paths:
    if os.path.exists(cpath):
        with open(cpath, "rb") as f:
            config = json.load(f)
            if isinstance(config, dict):
                config_combined.update(config)
        print(f"Loaded config file: '{cpath}'")
    else:
        print(f"Config file '{cpath}' not found.")


config = Config(**config_combined)
sessions: SessionJar[bytes, Cookies] = SessionJar(config.session_cleanup_interval)


default_headers = {
    "User-Agent": os.getenv(
        "USER_AGENT",
        config.user_agent,
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "*/*",
}
