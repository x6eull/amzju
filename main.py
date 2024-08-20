from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.proxy import router as proxy_router
from src.utils import config
import uvicorn

print("doc_enabled: ", config.doc_enabled)
app = FastAPI(
    title="amzju",
    version="0.1.2",
    docs_url="/docs" if config.doc_enabled else None,
    redoc_url="/redoc" if config.doc_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        [config.cors_allow_origins]
        if isinstance(config.cors_allow_origins, str)
        else config.cors_allow_origins
    ),
    allow_credentials=False,
    allow_methods="*",
    allow_headers="*",
    expose_headers="*",
)


app.include_router(proxy_router)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        date_header=False,
        server_header=False,
        proxy_headers=False,
    )
