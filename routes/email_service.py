
import os
import html
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()


def send_email(to_email, subject, message):
    sender_email = os.environ["SMTP_EMAIL"]
    app_password = os.environ["SMTP_APP_PASSWORD"]

    email = EmailMessage()
    email["From"] = sender_email
    email["To"] = to_email
    email["Subject"] = subject

    email.set_content(message)
    email.add_alternative(
        f"<p>{html.escape(message)}</p>",
        subtype="html"
    )

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(email)

    return {"message": "Email sent successfully"}
