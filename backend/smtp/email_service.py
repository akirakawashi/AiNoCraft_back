from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from backend.api.exceptions.email import EmailTemplateNotFoundException
from backend.config.smtp import smtp_settings
from backend.smtp.provider import SmtpProvider


class EmailService:
    _TEMPLATE_ENV = Environment(
        loader=FileSystemLoader(searchpath=Path(smtp_settings.template_dir))
    )

    @classmethod
    def _render_template(
        cls,
        filename: str,
        context: dict,
    ) -> str:
        try:
            return cls._TEMPLATE_ENV.get_template(filename).render(**context)
        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            raise EmailTemplateNotFoundException()

    @classmethod
    async def send_verification(cls, email: str, username: str, code: str) -> None:
        html = cls._render_template("verification.html", {"username": username, "code": code})

        return await SmtpProvider.send_email(
            to_email=email, subject="Код подтверждения", html_content=html
        )

    @classmethod
    async def send_welcome(
        cls,
        email: str,
        username: str,
    ) -> None:
        html = cls._render_template("welcome.html", {"username": username})

        return await SmtpProvider.send_email(
            to_email=email,
            subject="Welcome AiNoCraft!",
            html_content=html,
        )

    @classmethod
    async def send_password_changed(cls, email: str, username: str) -> None:
        html = cls._render_template("password_changed.html", {"username": username})

        return await SmtpProvider.send_email(
            to_email=email,
            subject="Пароль успешно изменён",
            html_content=html,
        )

    @classmethod
    async def send_password_reset_code(cls, email: str, username: str, code: str) -> None:
        html = cls._render_template(
            "password_reset_code.html", {"username": username, "code": code}
        )

        return await SmtpProvider.send_email(
            to_email=email,
            subject="Код подтверждения для смены пароля",
            html_content=html,
        )

    @classmethod
    async def send_phone_added(cls, email: str, username: str, phone: str) -> None:
        html = cls._render_template("phone_added.html", {"username": username, "phone": phone})

        return await SmtpProvider.send_email(
            to_email=email,
            subject="Телефон добавлен",
            html_content=html,
        )

    @classmethod
    async def send_account_blocked(
        cls,
        email: str,
        username: str,
        blocked_at: str,
        unblock_date: str,
        duration: str,
        reason: str,
    ) -> None:
        html = cls._render_template(
            "account_blocked.html",
            {
                "username": username,
                "blocked_at": blocked_at,
                "unblock_date": unblock_date,
                "duration": duration,
                "reason": reason,
            },
        )

        return await SmtpProvider.send_email(
            to_email=email,
            subject="Ваш аккаунт заблокирован",
            html_content=html,
        )
