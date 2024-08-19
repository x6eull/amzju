import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.proxy import router as proxy_router
from src.utils import before_sep

app = FastAPI()

if os.path.exists("cors_allow_origins.txt"):
    cors_allow_origins = []

    with open("cors_allow_origins.txt", "rt", encoding="utf-8") as f:
        for line in f:
            line = before_sep(line, "#")
            line = line.strip()
            if len(line) == 0:
                continue
            cors_allow_origins.append(line)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["az-token"],
        expose_headers=["az-token"],
    )


app.include_router(proxy_router)
