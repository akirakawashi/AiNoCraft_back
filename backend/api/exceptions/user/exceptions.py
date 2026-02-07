from backend.api.exceptions.base import ApiBaseException, ErrorCode
from backend.config import avatar_config


class UserLoginAlreadyExistsException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=409,
            error_code=ErrorCode.USER_LOGIN_ALREADY_EXISTS,
            message="Пользователь с таким логином уже существует",
            description="Occurs when trying to register with an already taken login.",
        )


class UserEmailAlreadyExistsException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=409,
            error_code=ErrorCode.USER_EMAIL_ALREADY_EXISTS,
            message="Пользователь с таким email уже существует",
            description="Occurs when trying to register with an already taken email address.",
        )


class UserPhoneAlreadyExistsException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=409,
            error_code=ErrorCode.USER_PHONE_ALREADY_EXISTS,
            message="Пользователь с таким номером телефона уже существует",
            description="Occurs when trying to register with an already taken phone number.",
        )


class UserNotFoundException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=404,
            error_code=ErrorCode.USER_NOT_FOUND,
            message="Пользователь не найден",
            description="Occurs when trying to get information about a non-existent user.",
        )


class UserAvatarUnsupportedTypeException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=400,
            error_code=ErrorCode.USER_AVATAR_UNSUPPORTED_FILE_TYPE,
            message="Формат загруженного файла не поддерживается, загрузите файл в формате JPEG, PNG, WebP!",
            description="Occurs when the uploaded avatar file type is not supported.",
        )


class UserAvatarTooLargeException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=413,
            error_code=ErrorCode.USER_AVATAR_FILE_TOO_LARGE,
            message=f"Размер загруженного файла слишком большой. Максимальный размер файла {avatar_config.max_size} МБ!",
            description="Occurs when the uploaded avatar file exceeds the maximum allowed size.",
        )


class UserAvatarFailedException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=502,
            error_code=ErrorCode.USER_AVATAR_FAILED_EXCEPTION,
            message="Ошибка при загрузке фото! Попробуйте позже!",
            description="Failed to upload avatar to file server.",
        )
