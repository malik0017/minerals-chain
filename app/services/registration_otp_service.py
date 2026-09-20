"""
app/services/registration_otp_service.py

Batch B: gates final registration submission on proving the person
controls the email address they're registering with. Two steps:

  1. request_otp(email) — generates a 6-digit code, hashes it (never
     stored or transmitted in plain form except in the email itself),
     packages the hash into a signed, 10-minute token
     (core/security.create_registration_otp_token), and sends the
     plain code via email_service.send_email(). The token is what the
     route puts in a cookie — the server never needs to remember the
     code anywhere else (no OTP table), the token IS the memory.

  2. verify_otp(token, submitted_code) — re-hashes the submitted code
     and compares against the hash inside the token. On success,
     issues a SEPARATE 30-minute "email_verified" token (also just a
     cookie) that the final registration submission checks against.

No database table for OTPs, by design — matches the same pattern
already used for 2FA login (core/security.py's pending-2FA token):
a short-lived signed token IS the state, nothing to clean up, nothing
that outlives its own expiry.
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
    """Raised for any invalid OTP action. Routes catch this and show
    the message."""
    pass


def request_otp(email: str) -> str:
    """Returns the token to store in the mc_reg_otp_pending cookie."""
    code = f"{random.randint(0, 999999):06d}"
    otp_hash = hash_password(code)  # Argon2 hash — fine for a short-lived 6-digit code too
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
    """Returns a NEW token (for mc_reg_email_verified) on success.
    Raises RegistrationOTPError otherwise."""
    if not pending_token:
        raise RegistrationOTPError("Request a verification code first.")

    payload = decode_registration_otp_token(pending_token)
    if payload is None:
        raise RegistrationOTPError("Your verification code has expired. Request a new one.")

    if not verify_password(submitted_code.strip(), payload["otp_hash"]):
        raise RegistrationOTPError("That code didn't match. Check your email and try again.")

    return create_email_verified_token(email=payload["email"])
