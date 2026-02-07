import json
from urllib.parse import urlparse

from loguru import logger
from minio import Minio
from minio.error import S3Error

from backend.config.minio import minio_settings
from backend.config.minio_buckets import MINIO_BUCKETS


class MinioProvider:
    _client: Minio | None = None
    _signing_client: Minio | None = None

    @classmethod
    async def init(cls):
        """
        Initialize the MinIO client.

        This method is used to initialize the MinIO client. It creates a
        MinIO client with the MinIO settings and checks if the connection
        is successful. If the connection fails, it logs a "Minio connection
        error" message and exits the program with status code 1. If the
        connection is successful, it logs a "MinIO client initialized" message.

        Usage:

            await MinioProvider.init()
        """
        if cls._signing_client is None:
            parsed = urlparse(minio_settings.public_url)
            netloc = parsed.netloc or parsed.path
            scheme = parsed.scheme or "http"
            cls._signing_client = Minio(
                endpoint=netloc,
                access_key=minio_settings.access_key,
                secret_key=minio_settings.secret_key,
                secure=(scheme == "https"),
            )
            logger.debug("MinIO signing client initialized")

        if cls._client is None:
            cls._client = Minio(
                endpoint=minio_settings.endpoint,
                access_key=minio_settings.access_key,
                secret_key=minio_settings.secret_key,
                secure=minio_settings.secure,
            )
        try:
            cls._client.bucket_exists("test")
        except S3Error:
            logger.exception("Minio connection error")
            exit(1)
        else:
            logger.debug("MinIO client initialized")

        # Initialize configured buckets and set their policies
        for bucket_config in MINIO_BUCKETS:
            if not cls._client.bucket_exists(bucket_config.name):
                cls._client.make_bucket(bucket_config.name)
                logger.debug(f"Bucket '{bucket_config.name}' created")

                # Set bucket policy
                if bucket_config.policy:
                    policy_doc = bucket_config.get_policy_document()
                    if policy_doc.get("Statement"):
                        cls._client.set_bucket_policy(bucket_config.name, json.dumps(policy_doc))
                        get_access = "Allow" if bucket_config.policy.allow_anonymous_get else "Deny"
                        put_access = "Allow" if bucket_config.policy.allow_anonymous_put else "Deny"
                        logger.debug(
                            f"Bucket '{bucket_config.name}' policy set: "
                            f"GET={get_access}, PUT/DELETE={put_access}"
                        )

    @classmethod
    def get_client(cls) -> Minio:
        """
        Get the MinIO client.

        This method is used to get the MinIO client. It checks if the
        MinIO client is not initialized, and if so, raises a RuntimeError
        with a message indicating that the MinIO client is not initialized.

        Usage:

            minio_client = MinioProvider.get_client()

        Raises:

            RuntimeError: If the MinIO client is not initialized.
        """
        if cls._client is None:
            raise RuntimeError(
                "MinIO client is not initialized. Call 'await MinioProvider.init()' first."
            )

        return cls._client

    @classmethod
    def get_signing_client(cls) -> Minio:
        """
        Get the MinIO signing client.

        This method is used to get the MinIO client that is used for generating
        pre-signed URLs. It checks if the MinIO signing client is not initialized,
        and if so, raises a RuntimeError with a message indicating that the MinIO
        signing client is not initialized.

        Usage:

            minio_signing_client = MinioProvider.get_signing_client()

        Raises:

            RuntimeError: If the MinIO signing client is not initialized.
        """
        if cls._signing_client is None:
            raise RuntimeError(
                "MinIO signing client is not initialized. Call 'await MinioClient.init()' first."
            )
        return cls._signing_client
