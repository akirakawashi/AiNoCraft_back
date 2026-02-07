import httpx
from loguru import logger

from backend.config.http_client import http_client_config


class HTTPClient:
    _client: httpx.AsyncClient | None = None

    @classmethod
    async def init(cls) -> None:
        """Initialize the HTTP client.

        This method sets up the HTTP client with the given configuration.
        The client is initialized with the given limits, timeout, and headers.
        The client is also configured to follow redirects and trust the environment.
        """
        limits = httpx.Limits(
            max_connections=http_client_config.max_connections,
            max_keepalive_connections=http_client_config.max_keepalive_connections,
        )
        timeout = httpx.Timeout(http_client_config.timeout)
        headers = {
            "User-Agent": http_client_config.user_agent,
        }

        cls._client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
            trust_env=True,
        )
        logger.debug("HTTP client initialized")

    @classmethod
    async def close(cls) -> None:
        """
        Close the HTTP client.

        This method closes the HTTP client and releases any resources
        associated with it. It is safe to call this method multiple
        times, as it will only close the client once it has been
        initialized.

        After calling this method, the client will be set to None and
        calling any methods on it will result in a RuntimeError being
        raised.
        """
        if cls._client:
            await cls._client.aclose()
            cls._client = None
            logger.debug("HTTP client closed")

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        """
        Get the HTTP client instance.

        This property returns the underlying HTTP client instance,
        which is an instance of httpx.AsyncClient.

        If the client is not initialized, a RuntimeError will be raised.
        """
        if not cls._client:
            raise RuntimeError("HTTP client is not initialized, call HTTPClient.init() first")
        return cls._client
