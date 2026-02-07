from loguru import logger
from redis.asyncio import Redis

from backend.config import redis_settings


class RedisProvider:
    _redis: Redis | None = None

    @classmethod
    async def init_redis(cls):
        """
        Initialize the Redis connection.

        This method is used to initialize the Redis connection. It
        checks if the connection is already initialized, and if not,
        creates a new connection with the Redis settings.

        If the connection is successful, it logs a "Connected to Redis"
        message. If the connection fails, it logs a "Failed to connect to Redis"
        message and raises a RuntimeError.

        Usage:

            await RedisProvider.init_redis()
        """
        if cls._redis is None:
            cls._redis = Redis(
                protocol=3,
                host=redis_settings.host,
                port=redis_settings.port,
                password=redis_settings.password,
                decode_responses=True,
            )
        try:
            result = await cls._redis.ping()
        except Exception:
            logger.exception("Failed to connect to Redis")
        else:
            if result:
                logger.debug("Connected to Redis")
            else:
                error_msg = "Failed to connect to Redis"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

    @classmethod
    async def close_redis(cls):
        """
        Close the Redis connection.

        This method is used to close the Redis connection. It
        checks if the connection is not None, and if so, closes
        the connection and sets the connection to None. It also logs
        a "Redis connection closed" message.

        Usage:

            await RedisProvider.close_redis()
        """
        if cls._redis is not None:
            await cls._redis.aclose()
            cls._redis = None
            logger.debug("Redis connection closed")

    @classmethod
    def get_redis(cls) -> Redis:
        """
        Get the Redis connection.

        This method is used to get the Redis connection. It
        checks if the connection is not None, and if so, returns
        the connection. If the connection is None, it raises a
        RuntimeError with a message indicating that the Redis connection is
        not initialized.

        Usage:

            redis = RedisProvider.get_redis()

        Raises:

            RuntimeError: If the Redis connection is not initialized.
        """
        if cls._redis is None:
            raise RuntimeError("Redis is not initialized. Call init_redis() at app startup.")
        return cls._redis
