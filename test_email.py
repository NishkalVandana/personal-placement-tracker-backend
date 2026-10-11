from routes.email_service import send_email

result = send_email(
    "nsp0801@gmail.com",
    "My First Flask Email",
    "Hello! My Flask email service is working."
)

print(result)