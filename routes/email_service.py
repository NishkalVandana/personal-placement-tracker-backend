
import os
import html
import resend
from dotenv import load_dotenv

load_dotenv()


def send_email(to_email, subject, message):
    resend.api_key = os.environ["RESEND_API_KEY"]

    response = resend.Emails.send({
        "from": os.environ["EMAIL_FROM"],
        "to": [to_email],
        "subject": subject,
        "html": f"<p>{html.escape(message)}</p>"
    })

    return response
