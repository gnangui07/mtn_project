import os
import django
from django.conf import settings
from django.core.mail import send_mail
import traceback

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reports.settings')
django.setup()

print(f"DEBUG: EMAIL_HOST = {settings.EMAIL_HOST}")
print(f"DEBUG: EMAIL_PORT = {settings.EMAIL_PORT}")
print(f"DEBUG: EMAIL_USE_TLS = {settings.EMAIL_USE_TLS}")
print(f"DEBUG: EMAIL_HOST_USER = {settings.EMAIL_HOST_USER}")

try:
    print("Attempting to send email...")
    send_mail(
        'Test SMTP Connection',
        'This is a test email to verify SMTP configuration.',
        settings.DEFAULT_FROM_EMAIL,
        ['gaoussou.traore@mtn.com'],
        fail_silently=False,
    )
    print("SUCCESS: Email sent successfully!")
except Exception as e:
    print("\nFAILURE: Could not send email.")
    print(f"Error Type: {type(e).__name__}")
    print(f"Error Message: {str(e)}")
    print("\nFull Traceback:")
    traceback.print_exc()
