"""
app/services/registration_otp_service.py
"""
import random

from app.core.security import (
    create_email_verified_token,
    create_registration_otp_token,
    decode_registration_otp_token,
    hash_password,
    verify_password,
)
from app.services.email_service import send_email


class RegistrationOTPError(ValueError):
    pass


def request_otp(email: str) -> str:
    """Returns the token to store in the mc_reg_otp_pending cookie."""
    code = f"{random.randint(0, 999999):06d}"
    otp_hash = hash_password(code)  
    token = create_registration_otp_token(email=email, otp_hash=otp_hash)

    send_email(
        to=email,
        subject="Verify your email — Minerals Chain",
        body=(
            f"Your verification code is: {code}\n\n"
            f"This code expires in 10 minutes. If you didn't request this, "
            f"you can safely ignore this email."
        ),
    )
    return token


def verify_otp(pending_token: str | None, submitted_code: str) -> str:
    if not pending_token:
        raise RegistrationOTPError("Request a verification code first.")

    payload = decode_registration_otp_token(pending_token)
    if payload is None:
        raise RegistrationOTPError("Your verification code has expired. Request a new one.")

    if not verify_password(submitted_code.strip(), payload["otp_hash"]):
        raise RegistrationOTPError("That code didn't match. Check your email and try again.")

    return create_email_verified_token(email=payload["email"])
