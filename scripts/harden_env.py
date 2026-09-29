"""
scripts/harden_env.py

    python scripts/harden_env.py --profile local
    python scripts/harden_env.py --profile production --redis redis://localhost:6379/0
    python scripts/harden_env.py --check
"""
import argparse
import base64
import os
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
PLACEHOLDERS = ("CHANGE_ME", "GENERATE")

PROFILES = {
    "local": {"APP_ENV": "development", "DEBUG": "false", "COOKIE_SECURE": "false", "CSP_MODE": "report-only"},
    "staging": {"APP_ENV": "staging", "DEBUG": "false", "COOKIE_SECURE": "true", "CSP_MODE": "enforce"},
    "production": {"APP_ENV": "production", "DEBUG": "false", "COOKIE_SECURE": "true", "CSP_MODE": "enforce",
                   "FORWARDED_ALLOW_IPS": "127.0.0.1", "LOG_LEVEL": "INFO"},
}


def read_env(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def parse(lines: list[str]) -> dict:
    out = {}
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def write_env(path: Path, lines: list[str], updates: dict) -> list[str]:
    changed, seen, out = [], set(), []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in updates:
            seen.add(key)
            new = f"{key}={updates[key]}"
            if new != line:
                changed.append(key)
            out.append(new)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
            changed.append(key)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def check(values: dict) -> int:
    problems, notes = [], []
    live = values.get("APP_ENV") in ("production", "staging")
    key = values.get("SECRET_KEY", "")
    if not key or key.startswith(PLACEHOLDERS) or len(key) < 32:
        problems.append("SECRET_KEY is missing or weak")
    if values.get("DEBUG", "true").lower() != "false":
        problems.append("DEBUG is not false")
    if values.get("APP_ENV") == "production" and values.get("COOKIE_SECURE", "false").lower() != "true":
        problems.append("COOKIE_SECURE must be true in production")
    if not values.get("REDIS_URL"):
        (problems if live else notes).append("REDIS_URL not set (rate limits are per process)")
    if values.get("EMAIL_MODE", "console") != "smtp":
        (problems if live else notes).append("EMAIL_MODE is not smtp (emails are printed in the terminal)")
    if not values.get("FILE_ENCRYPTION_KEY") or values["FILE_ENCRYPTION_KEY"].startswith(PLACEHOLDERS):
        problems.append("FILE_ENCRYPTION_KEY not set (uploads stored unencrypted)")
    for p in problems:
        print(f"  ✗ {p}")
    for n in notes:
        print(f"  · {n} — fine for local development")
    if not problems:
        print("  ✓ environment hardened")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=PROFILES, default="local")
    ap.add_argument("--redis", default=None)
    ap.add_argument("--rotate-secret", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    lines = read_env(ENV)
    values = parse(lines)
    if args.check:
        return check(values)
    if not lines:
        print(".env not found — create it with DATABASE_URL first.")
        return 1

    updates = dict(PROFILES[args.profile])
    key = values.get("SECRET_KEY", "")
    if args.rotate_secret or not key or key.startswith(PLACEHOLDERS) or len(key) < 32:
        updates["SECRET_KEY"] = secrets.token_urlsafe(64)
    if not values.get("FILE_ENCRYPTION_KEY") or values["FILE_ENCRYPTION_KEY"].startswith(PLACEHOLDERS):
        updates["FILE_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(os.urandom(32)).decode()
    if args.redis:
        updates["REDIS_URL"] = args.redis

    backup = ENV.with_name(f".env.bak-{datetime.now():%Y%m%d%H%M%S}")
    shutil.copy2(ENV, backup)
    changed = write_env(ENV, lines, updates)
    print(f"Backup: {backup.name}")
    print("Updated: " + (", ".join(changed) if changed else "nothing"))
    if "SECRET_KEY" in changed:
        print("Note: a new SECRET_KEY signs everyone out once.")
    print("Restart the application to apply.")
    return check(parse(read_env(ENV)))


if __name__ == "__main__":
    sys.exit(main())
