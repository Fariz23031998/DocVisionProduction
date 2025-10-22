# import resend
# from typing import Dict
# from random import randint
#
# from src.core.conf import APP_NAME, RESEND_API_KEY
# from src.utils.helper import format_message_from_template
#
# resend.api_key = RESEND_API_KEY
#
#
# def send_verification_code() -> Dict:
#     code = randint(100000, 999999)
#     html_body = format_message_from_template(verification_code=code, app_name=APP_NAME)
#     print(html_body)
    # params: resend.Emails.SendParams = {
    #     "from": "onboarding@resend.dev",
    #     "to": ["delivered@resend.dev"],
    #     "subject": "Verification code",
    #     "html": html_body,
    # }
    # email: resend.Email = resend.Emails.send(params)
    # return email


# send_verification_code()