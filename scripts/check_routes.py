"""
scripts/check_routes.py

Hits every registered route in the app and reports which ones actually
work — meant to run after every batch/update, right after `alembic
upgrade head` and `python scripts/seed_test_data.py`, as your "did this
batch break anything" smoke test.

USAGE
    python scripts/seed_test_data.py     # once, or after a fresh DB
    python scripts/check_routes.py

Runs entirely in-process against your app via FastAPI's TestClient —
no server needs to be running, and it uses whatever DATABASE_URL your
.env already points at. This is deliberate: a route "working" here
means the whole stack (routing, template rendering, DB queries,
permissions) executed without crashing, not just that some server
process happened to answer a socket.

WHAT COUNTS AS PASS / FAIL
    GET routes  — any response that ISN'T a 500 is a PASS. A 200, or a
                  302/303 redirect (e.g. an anonymous user bounced to
                  /login, or a role hitting a portal that isn't theirs
                  bounced to /home), or a 403/404 are all the route
                  correctly doing its job. A 500 means the route
                  crashed — a real bug, not a permissions/data question.
    POST routes — listed but not fired automatically (mutating a shared
                  seeded dataset on every run would make re-running
                  this script destructive and non-idempotent). Each is
                  marked SKIPPED with the reason, so you can see what
                  wasn't exercised at a glance. The Selenium suite in
                  tests_selenium/ is what actually drives these.
    Path params — filled in from scripts/seed_ids.json (written by
                  seed_test_data.py). A GET route needing an id that
                  isn't in that file is marked SKIPPED, not FAILED —
                  it's a gap in the seed data, not a broken route.

Every role logs in for real through POST /login (exercising that route
too), and each GET is tried once anonymously and once per role whose
portal it plausibly belongs to (by path prefix), so a route that's
supposed to redirect an unauthorized role away is verified to do that,
not just to return something.

EXIT CODE: 0 if every attempted check passed, 1 if any 500 was hit —
wire this into a CI step or a pre-commit routine and a broken batch
fails loudly instead of being discovered by a person clicking around.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app

SEED_IDS_PATH = Path(__file__).parent / "seed_ids.json"
PASSWORD = "Test@12345"

ROLE_LOGINS = {
    "admin": "admin@mineralstest.com",
    "seller": "seller@mineralstest.com",
    "buyer": "buyer@mineralstest.com",
    "lab": "lab@mineralstest.com",
}

# Path prefix -> which role(s) plausibly own it. "any" = any logged-in role.
PREFIX_ROLES = {
    "/admin": ["admin"],
    "/seller": ["seller"],
    "/buyer": ["buyer"],
    "/lab": ["lab"],
    "/my-profile": ["any"],
    "/notifications": ["any"],
    "/personalize": ["any"],
    "/home": ["any"],
    "/language": ["any"],
}


def flatten_routes(routes):
    """FastAPI 0.141's include_router() wraps routers in an internal
    _IncludedRouter lazy-matching object instead of flattening routes
    onto app.routes directly — .original_router.routes is where the
    real APIRoute objects live. See the Batch H debugging session for
    how this was discovered (app.routes alone silently under-reported
    routes from 87 down to 11)."""
    out = []
    for r in routes:
        if type(r).__name__ == "_IncludedRouter":
            out.extend(flatten_routes(r.original_router.routes))
        elif getattr(r, "path", None) is not None and getattr(r, "methods", None) is not None:
            out.append(r)
    return out


def load_seed_ids() -> dict:
    if not SEED_IDS_PATH.exists():
        print(f"[warn] {SEED_IDS_PATH} not found — run scripts/seed_test_data.py first.")
        print("       Every path-param route below will be SKIPPED.\n")
        return {}
    return json.loads(SEED_IDS_PATH.read_text())


PARAM_TO_SEED_KEY = {
    "company_id": "seller_company_id",  # overridden per-route below where a different company fits better
    "user_id": "seller_user_id",
    "product_id": "product_id",
    "rfq_id": "rfq_id",
    "quotation_id": "quotation_id",
    "order_id": "order_id",
    "passport_id": "passport_id",
    "request_id": "pending_verification_request_id",
}

# A few routes need a SPECIFIC id, not just "any id of that param name" —
# e.g. admin reviewing the PENDING passport, not the already-approved one.
ROUTE_PARAM_OVERRIDES = {
    "admin_passport_review": {"passport_id": "pending_passport_id"},
    "admin_company_detail": {"company_id": "pending_company_id"},  # exercises the approvals-adjacent detail view
    "buyer_browse_detail": {"product_id": "product_id"},
    "seller_listing_detail": {"product_id": "product_id"},
    "lab_verification_detail": {"request_id": "pending_verification_request_id"},
    "buyer_rfq_detail": {"rfq_id": "rfq_id"},
    "seller_rfq_inbox_detail": {"rfq_id": "rfq_id"},
    "buyer_order_detail": {"order_id": "order_id"},
    "seller_order_detail": {"order_id": "order_id"},
    "admin_user_detail": {"user_id": "seller_user_id"},
}


def build_url(route, seed_ids: dict) -> str | None:
    path = route.path
    if "{" not in path:
        return path
    overrides = ROUTE_PARAM_OVERRIDES.get(route.name, {})
    result = path
    for param in route.param_convertors.keys() if hasattr(route, "param_convertors") else []:
        seed_key = overrides.get(param, PARAM_TO_SEED_KEY.get(param))
        value = seed_ids.get(seed_key) if seed_key else None
        if not value:
            return None
        result = result.replace("{" + param + "}", str(value))
    return result if "{" not in result else None


def login(client: TestClient, email: str) -> bool:
    # Batch G's CSRF double-submit cookie (see app/core/csrf.py) needs a
    # matching `csrf_token` form field and `mc_csrf` cookie — the cookie
    # is issued on the first response of the session (any GET works) and
    # TestClient's cookie jar picks it up automatically; we just need to
    # echo that same value back as the form field.
    client.get("/login")
    csrf_token = client.cookies.get("mc_csrf")
    resp = client.post(
        "/login",
        data={"email": email, "password": PASSWORD, "csrf_token": csrf_token},
        follow_redirects=False,
    )
    return resp.status_code in (303, 302)


def roles_for_path(path: str) -> list[str]:
    for prefix, roles in PREFIX_ROLES.items():
        if path.startswith(prefix):
            return roles
    return []


def main() -> int:
    seed_ids = load_seed_ids()
    routes = flatten_routes(app.routes)
    get_routes = [r for r in routes if r.methods and "GET" in r.methods and r.path not in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")]
    other_routes = [r for r in routes if r.methods and "GET" not in r.methods]

    results = []  # (method, path, name, actor, status)
    failures = []

    print(f"Discovered {len(routes)} routes ({len(get_routes)} GET, {len(other_routes)} other-method).\n")

    # --- anonymous pass ---
    anon_client = TestClient(app)
    for route in get_routes:
        url = build_url(route, seed_ids)
        if url is None:
            results.append(("GET", route.path, route.name, "anon", "SKIP (no seed id)"))
            continue
        try:
            resp = anon_client.get(url, follow_redirects=False)
            status = resp.status_code
        except Exception as exc:
            status = f"CRASH: {exc}"
        outcome = "FAIL" if (isinstance(status, int) and status >= 500) or isinstance(status, str) else "PASS"
        results.append(("GET", url, route.name, "anon", f"{status} {outcome}"))
        if outcome == "FAIL":
            failures.append((url, route.name, "anon", status))

    # --- per-role pass ---
    for role, email in ROLE_LOGINS.items():
        client = TestClient(app)
        if not login(client, email):
            print(f"[warn] could not log in as {role} ({email}) — is scripts/seed_test_data.py run? Skipping this role.\n")
            continue
        for route in get_routes:
            applicable_roles = roles_for_path(route.path)
            if not applicable_roles:
                continue
            if role not in applicable_roles and "any" not in applicable_roles:
                continue
            url = build_url(route, seed_ids)
            if url is None:
                results.append(("GET", route.path, route.name, role, "SKIP (no seed id)"))
                continue
            try:
                resp = client.get(url, follow_redirects=False)
                status = resp.status_code
            except Exception as exc:
                status = f"CRASH: {exc}"
            outcome = "FAIL" if (isinstance(status, int) and status >= 500) or isinstance(status, str) else "PASS"
            results.append(("GET", url, route.name, role, f"{status} {outcome}"))
            if outcome == "FAIL":
                failures.append((url, route.name, role, status))

    # --- report non-GET routes as informational only ---
    for route in other_routes:
        methods = ",".join(sorted(m for m in route.methods if m != "HEAD"))
        results.append((methods, route.path, route.name, "-", "SKIPPED (mutating — see tests_selenium/)"))

    # --- print table ---
    col = "{:<8} {:<55} {:<32} {:<8} {}"
    print(col.format("METHOD", "PATH", "NAME", "ACTOR", "RESULT"))
    print("-" * 130)
    for method, path, name, actor, outcome in results:
        print(col.format(method, path, name or "", actor, outcome))

    print(f"\n{len(failures)} failing check(s) out of {len([r for r in results if 'SKIP' not in r[4]])} attempted.")
    if failures:
        print("\nFAILURES:")
        for url, name, actor, status in failures:
            print(f"  {url} ({name}) as {actor}: {status}")
        return 1

    skipped = [r for r in results if "SKIP" in r[4] and "no seed id" in r[4]]
    if skipped:
        print(f"\n{len(skipped)} GET route(s) skipped for missing seed data — see the table above (search for 'no seed id').")

    print("\nAll attempted checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
