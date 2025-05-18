from django.core.mail import send_mail

from island_bali.settings import EMAIL_HOST_USER

def send_reset_password(text: str):
    
    send_mail(
        subject="Заявка на франшизу",
        message=f"""
        {text}
        """,
        from_email=EMAIL_HOST_USER,
        recipient_list=["tima.j.zh@gmail.com"],
        fail_silently=False,
    )