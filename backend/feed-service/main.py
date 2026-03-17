"""Feed service entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from broadcaster import feed_broadcaster
from websocket import router as websocket_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await feed_broadcaster.start()
    try:
        yield
    finally:
        await feed_broadcaster.stop()


app = FastAPI(title="CLAWSEUM Feed Service", version="0.1.0", lifespan=lifespan)
app.include_router(websocket_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "feed-service"}
