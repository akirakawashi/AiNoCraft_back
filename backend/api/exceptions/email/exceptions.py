# backend/api/exceptions/email.py
from backend.api.exceptions.base import ApiBaseException, ErrorCode


class EmailTemplateNotFoundException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=500,
            error_code=ErrorCode.EMAIL_TEMPLATE_NOT_FOUND,
            message="Ошибка шаблона email",
            description="The requested email template file does not exist.",
        )


class EmailSendingException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=503,
            error_code=ErrorCode.EMAIL_SENDING_FAILED,
            message="Не удалось отправить письмо",
            description="Failed to send email via SMTP provider after retries.",
        )


class EmailInvalidCodeException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=400,
            error_code=ErrorCode.EMAIL_INVALID_CODE,
            message="Неверный код подтверждения",
            description="The provided email verification code is invalid or has expired.",
        )


class EmailCodeExpiredException(ApiBaseException):
    def __init__(self):
        super().__init__(
            status_code=400,
            error_code=ErrorCode.EMAIL_CODE_EXPIRED,
            message="Код подтверждения истек, заполните форму регистрации заново",
            description="The provided email verification code has expired.",
        )
