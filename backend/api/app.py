from asyncio.exceptions import CancelledError
from contextlib import asynccontextmanager

from cashews import cache
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter

from backend.api.exceptions.base import ApiBaseException
from backend.api.routers.avatar import router as avatar_router
from backend.api.routers.balance import router as balance_router
from backend.api.routers.change_password import router as change_password_router
from backend.api.routers.check_user import router as check_user
from backend.api.routers.health import router as health_router
from backend.api.routers.login import router as login_router
from backend.api.routers.logout import router as logout_router
from backend.api.routers.minecraft_auth import router as minecraft_auth_router
from backend.api.routers.minecraft_root import router as minecraft_root_router
from backend.api.routers.minecraft_session import router as minecraft_session_router
from backend.api.routers.refresh import router as refresh_router
from backend.api.routers.register import router as register_router
from backend.api.routers.reset_password import router as reset_password_router
from backend.config.api import api_config
from backend.config.redis import redis_settings
from backend.database.provider import DatabaseProvider
from backend.minio.provider import MinioProvider
from backend.redis.provider import RedisProvider
from backend.smtp.provider import SmtpProvider
from backend.utils.http_client import HTTPClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache.setup(redis_settings.url, pickle_type="sqlalchemy")
    ping_result = await cache.ping(message=None)
    if not ping_result:
        raise RuntimeError("Redis connection failed")
    await RedisProvider.init_redis()

    await FastAPILimiter.init(
        redis=RedisProvider.get_redis(), http_callback=api_config.rate_limit_http_callback
    )
    await DatabaseProvider.init_engine()

    await MinioProvider.init()

    await HTTPClient.init()

    await SmtpProvider.init()
    try:
        yield

    except CancelledError:
        pass

    finally:
        await RedisProvider.close_redis()
        await DatabaseProvider.dispose_engine()
        await HTTPClient.close()
        await SmtpProvider.close()


app = FastAPI(title="AiNoCraft API", version="1.0.3", lifespan=lifespan)

origins = [
    "https://ainocraft.com",
    "https://www.ainocraft.com",
]

if api_config.dev_mode:
    origins.extend(["http://localhost:3000", "http://127.0.0.1:3000"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiBaseException)
async def app_exception_handler(request: Request, exc: ApiBaseException):
    return JSONResponse(status_code=exc.status_code, content=exc.to_response())


app.include_router(register_router, prefix=api_config.path)  # /api/v1/register
app.include_router(login_router, prefix=api_config.path)  # /api/v1/login
app.include_router(logout_router, prefix=api_config.path)  # /api/v1/logout
app.include_router(refresh_router, prefix=api_config.path)  # /api/v1/refresh
app.include_router(balance_router, prefix=api_config.path)  # /api/v1/balance
app.include_router(change_password_router, prefix=api_config.path)  # /api/v1/change-password
app.include_router(avatar_router, prefix=api_config.path)  # /api/v1/avatars
app.include_router(check_user, prefix=api_config.path)  # /api/v1/check
app.include_router(reset_password_router, prefix=api_config.path)  # /api/v1/reset_password
app.include_router(health_router)  # /health
app.include_router(
    minecraft_root_router, prefix=api_config.minecraft_path
)  # /minecraft-server-api/
app.include_router(
    minecraft_auth_router, prefix=api_config.minecraft_path
)  # /minecraft-server-api/authserver/*
app.include_router(
    minecraft_session_router, prefix=api_config.minecraft_path
)  # /minecraft-server-api/sessionserver/session/minecraft/*


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, loop="uvloop", http="httptools")
