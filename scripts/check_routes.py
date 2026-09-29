"""
scripts/check_routes.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app

SEED_IDS_PATH = Path(__file__).parent / "seed_ids.json"
PASSWORD = "admin123"

ROLE_LOGINS = {
    "admin": "admin@mineralstest.com",
    "seller": "seller@mineralstest.com",
    "buyer": "buyer@mineralstest.com",
    "lab": "lab@mineralstest.com",
}

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
    return _augment_from_db(json.loads(SEED_IDS_PATH.read_text()))


def _augment_from_db(seed: dict) -> dict:
    from app.database.base import SessionLocal
    from app.models.dispute import Dispute
    from app.models.data_request import DataRequest
    db = SessionLocal()
    try:
        for key, model in (("dispute_id", Dispute), ("data_request_id", DataRequest)):
            if not seed.get(key):
                row = db.query(model).first()
                if row is not None:
                    seed[key] = str(row.id)
    finally:
        db.close()
    return seed


PARAM_TO_SEED_KEY = {
    "company_id": "seller_company_id",  
    "user_id": "seller_user_id",
    "product_id": "product_id",
    "rfq_id": "rfq_id",
    "quotation_id": "quotation_id",
    "order_id": "order_id",
    "passport_id": "passport_id",
    "request_id": "pending_verification_request_id",
    "batch_id": "batch_id", 
    "dispute_id": "dispute_id",  
}

ROUTE_PARAM_OVERRIDES = {
    "admin_passport_review": {"passport_id": "pending_passport_id"},
    "admin_company_detail": {"company_id": "pending_company_id"},  
    "buyer_browse_detail": {"product_id": "product_id"},
    "seller_listing_detail": {"product_id": "product_id"},
    "lab_verification_detail": {"request_id": "pending_verification_request_id"},
    "buyer_rfq_detail": {"rfq_id": "rfq_id"},
    "seller_rfq_inbox_detail": {"rfq_id": "rfq_id"},
    "buyer_order_detail": {"order_id": "order_id"},
    "seller_order_detail": {"order_id": "order_id"},
    "admin_user_detail": {"user_id": "seller_user_id"},
    "admin_data_request_detail": {"request_id": "data_request_id"},
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


def expand_urls(route, seed_ids: dict) -> list[str] | None:
    path = route.path
    if "{entity_key}" in path:
        rows = seed_ids.get("master_row_ids") or {}
        urls = []
        for key, row_id in rows.items():
            u = path.replace("{entity_key}", key)
            if "{row_id}" in u:
                if not row_id:
                    continue
                u = u.replace("{row_id}", row_id)
            urls.append(u)
        return urls or None
    if "{kind}" in path:
        company_id = seed_ids.get("seller_company_id")
        return [path.replace("{company_id}", company_id).replace("{kind}", "cr")] if company_id else None
    url = build_url(route, seed_ids)
    return [url] if url else None


def login(client: TestClient, email: str) -> bool:
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

    results = []  
    failures = []

    print(f"Discovered {len(routes)} routes ({len(get_routes)} GET, {len(other_routes)} other-method).\n")

    anon_client = TestClient(app)
    for route in get_routes:
        urls = expand_urls(route, seed_ids)
        if urls is None:
            results.append(("GET", route.path, route.name, "anon", "SKIP (no seed id)"))
            continue
        for url in urls:
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
            urls = expand_urls(route, seed_ids)
            if urls is None:
                results.append(("GET", route.path, route.name, role, "SKIP (no seed id)"))
                continue
            for url in urls:
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
        results.append((methods, route.path, route.name, "-", "SKIPPED (mutating — covered by tests/)"))

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
