"""
app/core/visual_polish.py

Batch F: small, dependency-free helpers that back the "multi-color,
professional, not plain/simple text" visual pass requested against the
admin data tables and detail pages (Company Shares-style presentation
in the InvestmentUX reference, applied to Minerals Chain's own real
data — no new JS library, no chart dependency, same philosophy as
core/donut_chart.py in Batch E).

Two pure functions, registered as Jinja globals in core/templates.py:

- initials(name)            -> "AB" style initials for an avatar chip
- avatar_class(seed)        -> one of a fixed palette of CSS classes,
                                deterministically hashed from `seed` so
                                the SAME company/user always gets the
                                SAME color across pages and reloads,
                                without persisting anything to the DB.

The actual colors live in app/static/css/batch-f-polish.css as
`.mc-avatar-c0` .. `.mc-avatar-c7`; this module only ever returns the
class name, never a hex value, so the palette can be retuned in one
CSS file without touching Python or templates.
"""

_PALETTE_SIZE = 8


def initials(name: str | None) -> str:
    """First letter of up to the first two words of `name`, uppercased.
    Falls back to '?' for missing/blank names rather than raising —
    this runs inside template rendering, where an exception would take
    down the whole page over a cosmetic detail."""
    if not name or not name.strip():
        return "?"
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def avatar_class(seed: str | None) -> str:
    """Deterministic (not random) mapping from an identifying string —
    a company name, a user email, whatever is stable for that row — to
    one of the fixed palette classes. Same seed always yields the same
    class, so a company's color stays consistent between the list page
    and its detail page without storing a color anywhere."""
    if not seed:
        seed = "?"
    bucket = sum(ord(ch) for ch in seed) % _PALETTE_SIZE
    return f"mc-avatar-c{bucket}"
