"""
app/core/visual_polish.py
"""

_PALETTE_SIZE = 8

def initials(name: str | None) -> str:
    if not name or not name.strip():
        return "?"
    parts = ["".join(ch for ch in w if ch.isalnum()) for w in name.strip().split()]
    parts = [w for w in parts if w] or [name.strip()]
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def avatar_class(seed: str | None) -> str:
    if not seed:
        seed = "?"
    bucket = sum(ord(ch) for ch in seed) % _PALETTE_SIZE
    return f"mc-avatar-c{bucket}"
