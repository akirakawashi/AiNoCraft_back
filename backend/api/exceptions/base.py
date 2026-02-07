from enum import StrEnum
from typing import Any, Type


class ErrorCode(StrEnum):
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_FORBIDDEN = "AUTH_FORBIDDEN"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_REFRESH_TOKEN_NOT_FOUND = "AUTH_REFRESH_TOKEN_NOT_FOUND"
    AUTH_ACCESS_TOKEN_NOT_FOUND = "AUTH_ACCESS_TOKEN_NOT_FOUND"
    AUTH_INVALID_TOKEN_TYPE = "AUTH_INVALID_TOKEN_TYPE"
    AUTH_REFRESH_TOKEN_REVOKED = "AUTH_REFRESH_TOKEN_REVOKED"
    AUTH_PASSWORD_RESET_TOKEN_NOT_FOUND = "AUTH_PASSWORD_RESET_TOKEN_NOT_FOUND"

    USER_LOGIN_ALREADY_EXISTS = "USER_LOGIN_ALREADY_EXISTS"
    USER_EMAIL_ALREADY_EXISTS = "USER_EMAIL_ALREADY_EXISTS"
    USER_PHONE_ALREADY_EXISTS = "USER_PHONE_ALREADY_EXISTS"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_AVATAR_UNSUPPORTED_FILE_TYPE = "USER_AVATAR_UNSUPPORTED_FILE_TYPE"
    USER_AVATAR_FILE_TOO_LARGE = "USER_AVATAR_FILE_TOO_LARGE"
    USER_AVATAR_FAILED_EXCEPTION = "USER_AVATAR_FAILED_EXCEPTION"

    LIMIT_TOO_MANY_REQUESTS = "LIMIT_TOO_MANY_REQUESTS"

    SECURITY_INVALID_PASSWORD = "SECURITY_INVALID_PASSWORD"
    SECURITY_INCORRECT_OLD_PASSWORD = "SECURITY_INCORRECT_OLD_PASSWORD"
    SECURITY_SAME_PASSWORD = "SECURITY_SAME_PASSWORD"

    EMAIL_TEMPLATE_NOT_FOUND = "EMAIL_TEMPLATE_NOT_FOUND"
    EMAIL_SENDING_FAILED = "EMAIL_SENDING_FAILED"
    EMAIL_INVALID_CODE = "EMAIL_INVALID_CODE"
    EMAIL_CODE_EXPIRED = "EMAIL_CODE_EXPIRED"


class ApiBaseException(Exception):
    """
    Base exception class for API errors.

    All custom exceptions should inherit from this class.
    Each exception automatically provides OpenAPI documentation for Swagger UI.
    """

    status_code: int
    error_code: ErrorCode
    message: str
    description: str = ""

    def __init__(
        self,
        status_code: int | None = None,
        error_code: ErrorCode | None = None,
        message: str | None = None,
        description: str = "",
    ) -> None:
        """
        Initializes an ApiExceptionBase object.

        Args:
            status_code (int): HTTP status code.
            error_code (ErrorCode): Error code.
            message (str): Error message.
            description (str): Detailed description for documentation (optional).
        """
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        if message is not None:
            self.message = message
        self.description = description or self.message
        super().__init__(self.message)

    def to_response(self) -> dict[str, dict[str, str]]:
        """Convert exception to JSON response format."""
        return {"error": {"code": self.error_code.value, "message": self.message}}

    @staticmethod
    def _create_error_schema(
        code_value: str | list[str] | None = None,
        message_example: str | None = None,
    ) -> dict[str, Any]:
        """
        Create the nested error schema structure.

        Args:
            code_value: Example value or enum list for error code
            message_example: Example value for message

        Returns:
            dict: Error schema structure
        """
        code_schema: dict[str, Any] = {"type": "string"}
        if isinstance(code_value, list):
            code_schema["enum"] = code_value
        elif code_value:
            code_schema["example"] = code_value

        message_schema: dict[str, Any] = {"type": "string"}
        if message_example:
            message_schema["example"] = message_example

        return {
            "type": "object",
            "properties": {
                "error": {
                    "type": "object",
                    "properties": {
                        "code": code_schema,
                        "message": message_schema,
                    },
                }
            },
        }

    @classmethod
    def get_openapi_response(cls) -> dict[str, Any]:
        """
        Generate OpenAPI response schema for this exception.
        Used for automatic Swagger UI documentation.

        Returns:
            dict: OpenAPI response schema
        """
        temp_instance = cls()

        return {
            "description": temp_instance.description,
            "content": {
                "application/json": {
                    "schema": cls._create_error_schema(
                        code_value=temp_instance.error_code.value,
                        message_example=temp_instance.message,
                    ),
                    "example": temp_instance.to_response(),
                }
            },
        }


def build_error_responses(*exception_classes: Type[ApiBaseException]) -> dict[int | str, dict]:
    """
    Generate a dictionary of error responses for manual use.

    This function groups multiple exceptions with the same status code together,
    showing all possible error codes and messages in the documentation.

    Usage:
        @router.post(
            "/endpoint",
            responses=build_error_responses(
                UserNotFoundException,
                AuthForbiddenException,
            )
        )
        async def my_endpoint():
            ...

    Args:
        *exception_classes: Exception classes that inherit from ApiBaseException

    Returns:
        dict: OpenAPI responses dictionary keyed by status code
    """
    # Group exceptions by status code
    grouped_by_status: dict[int, list[ApiBaseException]] = {}

    for exc_class in exception_classes:
        if not issubclass(exc_class, ApiBaseException):
            raise TypeError(f"{exc_class.__name__} must inherit from ApiBaseException")

        temp_instance = exc_class()
        status_code = temp_instance.status_code

        if status_code not in grouped_by_status:
            grouped_by_status[status_code] = []
        grouped_by_status[status_code].append(temp_instance)

    # Build responses for each status code
    responses: dict[int | str, dict] = {}
    for status_code, instances in grouped_by_status.items():
        if len(instances) == 1:
            # Single error for this status code - use simple format
            responses[status_code] = instances[0].__class__.get_openapi_response()
        else:
            # Multiple errors for this status code - combine them
            combined_description = " || ".join(
                f"{inst.error_code.value}: {inst.description}" for inst in instances
            )

            # Create examples for all possible errors
            examples = {}
            for inst in instances:
                examples[inst.error_code.value] = {
                    "summary": inst.error_code.value,
                    "value": inst.to_response(),
                }

            responses[status_code] = {
                "description": combined_description,
                "content": {
                    "application/json": {
                        "schema": ApiBaseException._create_error_schema(
                            code_value=[inst.error_code.value for inst in instances],
                        ),
                        "examples": examples,
                    }
                },
            }

    return responses
