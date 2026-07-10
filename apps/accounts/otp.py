import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status

from .models import EmailOTP, OTPPurpose


class OTPError(Exception):
    def __init__(self, message, status_code=status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def generate_and_send_otp(user, purpose=OTPPurpose.EMAIL_VERIFICATION):
    """Invalidates any prior pending code for this (user, purpose) and emails a fresh one."""
    EmailOTP.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)

    code = f'{secrets.randbelow(10_000):04d}'
    otp = EmailOTP.objects.create(
        user=user,
        code=code,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
    )

    send_mail(
        subject='Your NetGrove verification code',
        message=(
            f'Your NetGrove verification code is {code}.\n\n'
            f'It expires in {settings.OTP_EXPIRY_MINUTES} minutes. '
            "If you didn't request this, you can safely ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return otp


def verify_otp(user, submitted_code, purpose=OTPPurpose.EMAIL_VERIFICATION):
    """Raises OTPError with a user-facing message on any failure; returns the spent OTP on success."""
    otp = EmailOTP.objects.filter(user=user, purpose=purpose, is_used=False).order_by('-created_at').first()
    if not otp:
        raise OTPError('No pending verification code found. Please request a new one.')

    if otp.is_expired():
        otp.is_used = True
        otp.save(update_fields=['is_used'])
        raise OTPError('This verification code has expired. Please request a new one.')

    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        otp.is_used = True
        otp.save(update_fields=['is_used'])
        raise OTPError('Too many incorrect attempts. Please request a new code.')

    if otp.code != submitted_code:
        otp.attempts += 1
        remaining = settings.OTP_MAX_ATTEMPTS - otp.attempts
        if remaining <= 0:
            otp.is_used = True
            otp.save(update_fields=['attempts', 'is_used'])
            raise OTPError('Too many incorrect attempts. Please request a new code.')
        otp.save(update_fields=['attempts'])
        raise OTPError(f'Incorrect code. {remaining} attempt(s) remaining.')

    otp.is_used = True
    otp.save(update_fields=['is_used'])
    return otp


def resend_cooldown_remaining(user, purpose=OTPPurpose.EMAIL_VERIFICATION):
    """Seconds left before another OTP may be sent, or 0 if none is pending."""
    last_otp = EmailOTP.objects.filter(user=user, purpose=purpose).order_by('-created_at').first()
    if not last_otp:
        return 0
    elapsed = (timezone.now() - last_otp.created_at).total_seconds()
    remaining = settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed
    return max(0, int(remaining))
