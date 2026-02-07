from backend.api.exceptions.base import ApiBaseException, ErrorCode


class SecurityIncorrectOldPasswordException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=403,
            error_code=ErrorCode.SECURITY_INCORRECT_OLD_PASSWORD,
            message="Неверный старый пароль",
            description="Occurs when the old password is incorrect.",
        )


class SecuritySamePasswordException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=400,
            error_code=ErrorCode.SECURITY_SAME_PASSWORD,
            message="Новый пароль совпадает со старым",
            description="Occurs when the new password is the same as the old password.",
        )


class SecurityInvalidPasswordException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=422,
            error_code=ErrorCode.SECURITY_INVALID_PASSWORD,
            message="Длина пароля должна быть не менее 6 и не более 72 символов",
            description="Occurs when the password is invalid.",
        )

    @classmethod
    def validate_password(cls, password: str) -> str:
        """
        Validates a password.

        Raises:
            SecurityInvalidPasswordException: If the password length is not between 6 and 72 characters.
        Returns:
            str: The validated password.
        """
        if not (6 <= len(password) <= 72):
            raise cls()
        return password
