from backend.api.exceptions.base import ApiBaseException, ErrorCode


class LimitTooManyRequestsException(ApiBaseException):
    def __init__(self, retry_after: int = 0):
        super().__init__(
            status_code=429,
            error_code=ErrorCode.LIMIT_TOO_MANY_REQUESTS,
            message=f"Слишком много запросов, повторите попытку через {retry_after} секунд(-ы)",
            description="Occurs when the rate limit is exceeded.",
        )
