from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from random import randint

from starlette.background import BackgroundTask

from src.core.conf import SMTP_SERVER, SMTP_PORT, SMTP_EMAIL_PASSWORD, SMTP_EMAIL_FROM
from src.utils.helper import load_template_from_txt, format_message_from_template

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=SMTP_EMAIL_FROM,
    MAIL_PASSWORD=SMTP_EMAIL_PASSWORD,
    MAIL_FROM=SMTP_EMAIL_FROM,
    MAIL_PORT=SMTP_PORT,
    MAIL_SERVER=SMTP_SERVER,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

html_template = load_template_from_txt("email_verification_template.txt")


async def send_verification_code(recipient_email: str, background_task: BackgroundTask):
    fast_mail = FastMail(conf)
    code = randint(100000, 999999)
    html_body = format_message_from_template(
        template_content=html_template,
        verification_code=code
    )
    message = MessageSchema(
        subject="Verification code",
        recipients=recipient_email,
        body=html_body,
        subtype=MessageType.html
    )

    await fast_mail.send_message(message)