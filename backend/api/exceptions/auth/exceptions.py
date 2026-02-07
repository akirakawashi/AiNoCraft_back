from backend.api.exceptions.base import ApiBaseException, ErrorCode


class AuthInvalidCredentialsException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=401,
            error_code=ErrorCode.AUTH_INVALID_CREDENTIALS,
            message="Неверный логин или пароль",
            description="Occurs when trying to log in with incorrect credentials.",
        )


class AuthForbiddenException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=403,
            error_code=ErrorCode.AUTH_FORBIDDEN,
            message="Доступ запрещен",
            description="Occurs when trying to access a resource without required permissions.",
        )


class AuthRefreshTokenNotFoundException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=401,
            error_code=ErrorCode.AUTH_REFRESH_TOKEN_NOT_FOUND,
            message="Refresh token не найден",
            description="Occurs when the refresh_token cookie is missing.",
        )


class AuthInvalidTokenTypeException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=401,
            error_code=ErrorCode.AUTH_INVALID_TOKEN_TYPE,
            message="Неверный тип токена",
            description="Occurs when a token of the wrong type is provided (e.g., access instead of refresh).",
        )


class AuthRefreshTokenRevokedException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=401,
            error_code=ErrorCode.AUTH_REFRESH_TOKEN_REVOKED,
            message="Refresh token отозван или истек",
            description="Occurs when the refresh token is invalid in the database.",
        )


class AuthTokenExpiredException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=401,
            error_code=ErrorCode.AUTH_TOKEN_EXPIRED,
            message="Токен истек",
            description="Occurs when the JWT token has expired.",
        )


class AuthTokenInvalidException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=401,
            error_code=ErrorCode.AUTH_TOKEN_INVALID,
            message="Недействительный токен",
            description="Occurs when the JWT token is invalid or an unexpected error occurs during validation.",
        )


class AuthAccessTokenNotFoundException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=401,
            error_code=ErrorCode.AUTH_ACCESS_TOKEN_NOT_FOUND,
            message="Access token не найден",
            description="Occurs when the access token is missing from the Authorization header.",
        )


class AuthPasswordResetTokenNotFoundException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=401,
            error_code=ErrorCode.AUTH_PASSWORD_RESET_TOKEN_NOT_FOUND,
            message="Password reset token не найден",
            description="Occurs when the password_reset_token cookie is missing.",
        )
