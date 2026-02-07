import asyncio
from asyncio.exceptions import CancelledError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from aiosmtplib import SMTP
from loguru import logger

from backend.api.exceptions.email import EmailSendingException
from backend.config.smtp import smtp_settings


class SmtpProvider:
    _QUEUE: asyncio.Queue[tuple[int, SMTP]] = asyncio.Queue(maxsize=smtp_settings.pool_size)
    _KEEP_ALIVE_TASK: asyncio.Task | None = None

    @classmethod
    async def init(cls):
        """
        Initialize the SMTP pool with the given settings.

        Creates a specified number of SMTP clients and connects them to the
        SMTP server. After that, starts a keep alive task to keep
        the connections alive.
        """
        for i in range(smtp_settings.pool_size):
            smtp_client = SMTP(
                hostname=smtp_settings.host,
                port=smtp_settings.port,
                username=smtp_settings.username,
                password=smtp_settings.password,
                use_tls=smtp_settings.use_tls,
            )
            await smtp_client.connect()
            await cls._QUEUE.put((i, smtp_client))

        cls._KEEP_ALIVE_TASK = asyncio.create_task(cls._keep_alive_manager())
        logger.debug(f"SMTP pool initialized with {smtp_settings.pool_size} clients")

    @classmethod
    async def close(cls):
        """
        Close the SMTP pool.
        """
        if cls._KEEP_ALIVE_TASK:
            cls._KEEP_ALIVE_TASK.cancel()

            try:
                await cls._KEEP_ALIVE_TASK

            except (CancelledError, Exception):
                pass

            cls._KEEP_ALIVE_TASK = None

        while not cls._QUEUE.empty():
            _, smtp_client = await cls._QUEUE.get()

            try:
                await smtp_client.quit()

            except Exception as e:
                logger.warning(f"Error quitting SMTP client during close: {repr(e)}")

        logger.debug("SMTP pool closed")

    @classmethod
    async def _keep_alive_manager(cls):
        """
        Keep-alive manager for SMTP clients.

        This function is responsible for periodically sending a NOOP command
        to idle SMTP clients to keep the connection alive. If the NOOP
        command fails, it will attempt to reconnect the SMTP client.
        If the reconnection fails, it will log an error and stop.

        The function will run indefinitely until it is cancelled.

        The function will:

        1. Get the idle count of SMTP clients from the queue.
        2. If the idle count is 0, continue to the next iteration.
        3. For each idle SMTP client, attempt to send a NOOP command.
        4. If the NOOP command fails, attempt to reconnect the SMTP client.
        5. If the reconnection fails, log an error and stop.
        6. Put the SMTP client back into the queue.
        7. Sleep for the specified keep-alive interval before the next iteration.

        The function will log warnings for failed NOOP commands and errors
        during reconnection attempts. It will log an error if an unexpected
        exception occurs.

        The function will be cancelled if the SMTP pool is closed.
        """
        while True:
            try:
                idle_count = cls._QUEUE.qsize()

                if idle_count == 0:
                    await asyncio.sleep(smtp_settings.keep_alive_interval)
                    continue

                for _ in range(idle_count):
                    try:
                        i, smtp_client = cls._QUEUE.get_nowait()

                    except asyncio.QueueEmpty:
                        break

                    try:
                        try:
                            await asyncio.wait_for(
                                smtp_client.noop(), timeout=smtp_settings.noop_timeout
                            )
                            logger.debug(f"SMTP client #{i} NOOP successful")

                        except (Exception, asyncio.CancelledError) as e:
                            if isinstance(e, asyncio.CancelledError):
                                raise e
                            logger.warning(
                                f"Failed NOOP for SMTP client #{i} due to {repr(e)}, reconnecting..."
                            )

                            try:
                                await smtp_client.quit()

                            except Exception as e:
                                logger.warning(
                                    f"Error quitting SMTP client #{i} during NOOP reconnect: {repr(e)}"
                                )

                            reconnected = False
                            for attempt in range(smtp_settings.max_retries):
                                try:
                                    await smtp_client.connect()
                                    reconnected = True
                                    break

                                except Exception as connect_exception:
                                    logger.warning(
                                        f"Reconnect attempt {attempt + 1} failed for #{i}: {connect_exception}"
                                    )
                                    await asyncio.sleep(1)

                            if reconnected:
                                logger.debug(f"SMTP client #{i} reconnected successfully")

                            else:
                                logger.error(f"Failed to reconnect SMTP client #{i}.")

                    finally:
                        await cls._QUEUE.put((i, smtp_client))

                await asyncio.sleep(smtp_settings.keep_alive_interval)

            except CancelledError:
                logger.debug("Keep-alive task cancelled")
                raise

            except Exception:
                logger.exception("Unexpected error in keep-alive manager")
                await asyncio.sleep(
                    30
                )  # Sleep before retrying on unexpected errors to avoid tight loop

    @classmethod
    async def send_email(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
    ) -> None:
        """
        Send an email using a SMTP client from the pool.

        If the message cannot be sent after the maximum number of retries,
        an EmailSendingException is raised.

        :param to_email: The recipient's email address
        :param subject: The email subject
        :param html_content: The HTML content of the email
        :param text_content: The text content of the email (optional)
        :return: None
        """
        msg = MIMEMultipart("alternative")
        msg["subject"] = subject
        msg["from"] = f"{smtp_settings.from_name} <{smtp_settings.from_email}>"
        msg["to"] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        for attempt in range(smtp_settings.max_retries):
            i, smtp_client = await cls._QUEUE.get()

            try:
                await smtp_client.send_message(msg)
                logger.debug(f"Email sent to {to_email} using SMTP client #{i}")
                await cls._QUEUE.put((i, smtp_client))
                break

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1} failed to send to {to_email} (client #{i}): {repr(e)}",
                )

                try:
                    try:
                        await smtp_client.quit()

                    except Exception as e:
                        logger.warning(
                            f"Error quitting SMTP client #{i} during send_email: {repr(e)}"
                        )

                    await smtp_client.connect()
                    logger.debug(f"SMTP client #{i} reconnected successfully after error")

                except Exception as reconnect_error:
                    logger.warning(
                        f"Failed to reconnect client #{i} immediately: {repr(reconnect_error)}"
                    )

                else:
                    logger.debug(f"SMTP client #{i} reconnected successfully after error")

                finally:
                    await cls._QUEUE.put((i, smtp_client))

                    if attempt == smtp_settings.max_retries - 1:
                        raise EmailSendingException()

                    await asyncio.sleep(1)
