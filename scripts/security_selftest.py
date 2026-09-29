"""
scripts/security_selftest.py — automated pre-pen-test checks (OWASP ASVS L1 subset)

    python scripts/seed_test_data.py
    python scripts/security_selftest.py [--out reports/]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import check_routes as cr  # noqa: E402
from app.database.base import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402

PORTALS = ("/admin", "/seller", "/buyer", "/lab")
results: list[dict] = []


def record(area: str, name: str, ok: bool, detail: str = "") -> None:
    results.append({"area": area, "check": name, "ok": bool(ok), "detail": detail})


def client_for(role: str | None) -> TestClient:
    c = TestClient(app)
    if role:
        cr.login(c, cr.ROLE_LOGINS[role])
    else:
        c.get("/login")
    return c


def get_urls(seed: dict) -> list[str]:
    urls = []
    for r in cr.flatten_routes(app.routes):
        if r.methods and "GET" in r.methods and r.path.startswith(PORTALS):
            urls += cr.expand_urls(r, seed) or []
    return [u for u in dict.fromkeys(urls) if not any(x in u for x in ("logout", "export", ".csv", ".json"))]


def check_headers() -> None:
    r = TestClient(app).get("/login")
    h = {k.lower(): v for k, v in r.headers.items()}
    for name in ("x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy"):
        record("Headers", name, name in h, h.get(name, "missing"))
    csp = h.get("content-security-policy") or h.get("content-security-policy-report-only")
    record("Headers", "content-security-policy", bool(csp), "enforced" if "content-security-policy" in h else "report-only")
    cookies = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else [r.headers.get("set-cookie", "")]
    cookies = [c for c in cookies if c]
    record("Session", "CSRF cookie HttpOnly + SameSite", bool(cookies) and all("httponly" in c.lower() and "samesite" in c.lower() for c in cookies),
           "; ".join(c.split(";")[0] for c in cookies if c))
    st = TestClient(app).get("/static/../storage/.gitkeep")
    record("Storage", "private storage not reachable via /static", st.status_code != 200, str(st.status_code))


def check_login_cookie() -> None:
    c = TestClient(app)
    c.get("/login")
    r = c.post("/login", data={"email": cr.ROLE_LOGINS["admin"], "password": cr.PASSWORD,
                               "csrf_token": c.cookies.get("mc_csrf")}, follow_redirects=False)
    raw = [v for k, v in r.headers.multi_items() if k.lower() == "set-cookie" and v.startswith("mc_session")]
    record("Session", "session cookie HttpOnly", bool(raw) and "httponly" in raw[0].lower(), raw[0].split(";")[0][:24] + "…" if raw else "none")
    record("Session", "session cookie SameSite", bool(raw) and "samesite" in raw[0].lower())


def check_anonymous(urls: list[str]) -> None:
    anon = client_for(None)
    leaks = [u for u in urls if anon.get(u, follow_redirects=False).status_code == 200]
    record("Access control", f"anonymous blocked on {len(urls)} portal pages", not leaks, ", ".join(leaks[:5]))


def check_role_isolation(urls: list[str]) -> None:
    for role in ("seller", "buyer", "lab"):
        c = client_for(role)
        foreign = [u for u in urls if u.startswith(PORTALS) and not u.startswith("/" + role)]
        leaks = [u for u in foreign if c.get(u, follow_redirects=False).status_code == 200]
        record("Access control", f"{role} cannot open other portals ({len(foreign)} pages)", not leaks, ", ".join(leaks[:5]))


def check_idor() -> None:
    db = SessionLocal()
    try:
        buyer_cid = db.execute(text("SELECT company_id FROM users WHERE email=:e"), {"e": cr.ROLE_LOGINS["buyer"]}).scalar()
        seller_cid = db.execute(text("SELECT company_id FROM users WHERE email=:e"), {"e": cr.ROLE_LOGINS["seller"]}).scalar()
        foreign_order = db.execute(text("SELECT id FROM orders WHERE buyer_company_id <> :b LIMIT 1"), {"b": buyer_cid}).scalar()
        foreign_sorder = db.execute(text("SELECT id FROM orders WHERE seller_company_id <> :s LIMIT 1"), {"s": seller_cid}).scalar()
        foreign_rfq = db.execute(text("SELECT id FROM rfqs WHERE buyer_company_id <> :b LIMIT 1"), {"b": buyer_cid}).scalar()
        foreign_dispute = db.execute(text("""SELECT d.id FROM disputes d JOIN orders o ON o.id=d.order_id
                                            WHERE o.buyer_company_id <> :b LIMIT 1"""), {"b": buyer_cid}).scalar()
        pending = db.execute(text("""SELECT o.id, c.company_name FROM orders o JOIN companies c ON c.id=o.seller_company_id
                                     WHERE o.buyer_company_id=:b AND o.confirmed_at IS NULL LIMIT 1"""), {"b": buyer_cid}).first()
    finally:
        db.close()
    buyer, seller = client_for("buyer"), client_for("seller")
    for label, c, url in (("buyer → another buyer's order", buyer, f"/buyer/orders/{foreign_order}"),
                          ("seller → another seller's order", seller, f"/seller/orders/{foreign_sorder}"),
                          ("buyer → another buyer's RFQ", buyer, f"/buyer/rfqs/{foreign_rfq}"),
                          ("buyer → another company's dispute", buyer, f"/buyer/disputes/{foreign_dispute}")):
        if "None" in url:
            record("IDOR", label, True, "no data to test")
            continue
        r = c.get(url, follow_redirects=False)
        record("IDOR", label, r.status_code != 200, str(r.status_code))
    if pending:
        page = buyer.get(f"/buyer/orders/{pending[0]}").text
        record("Identity protection", "seller name hidden before confirmation", pending[1] not in page)
    else:
        record("Identity protection", "seller name hidden before confirmation", True, "no pending order to test")


def check_csrf() -> None:
    c = client_for("admin")
    r = c.post("/admin/control-center/security/fix", data={"item": "dev_banner"}, follow_redirects=False)
    record("CSRF", "POST without token rejected", r.status_code == 400, str(r.status_code))


def check_rate_limit() -> None:
    c = TestClient(app)
    c.get("/login")
    token = c.cookies.get("mc_csrf")
    codes = [c.post("/login", data={"email": "nobody@example.com", "password": "x", "csrf_token": token},
                    headers={"x-forwarded-for": "203.0.113.9"}, follow_redirects=False).status_code for _ in range(15)]
    record("Brute force", "login rate limit engages", 429 in codes, f"codes: {sorted(set(codes))}")


def check_api() -> None:
    c = TestClient(app)
    codes = {p: c.get(p).status_code for p in ("/api/v1/me", "/api/v1/orders", "/api/v1/shipments")}
    record("API", "API rejects requests without a token", all(v == 401 for v in codes.values()), str(sorted(set(codes.values()))))
    bad = c.get("/api/v1/me", headers={"Authorization": "Bearer mc_deadbeef_not-a-real-token"}).status_code
    record("API", "API rejects forged tokens", bad == 401, str(bad))
    browser = client_for("seller")
    record("API", "session cookie does not authenticate the API", browser.get("/api/v1/me").status_code == 401)
    r = client_for("admin").post("/admin/api-tokens/00000000-0000-0000-0000-000000000000/revoke", follow_redirects=False)
    record("CSRF", "CSRF still enforced outside /api/v1", r.status_code == 400, str(r.status_code))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()
    seed = cr.load_seed_ids()
    urls = get_urls(seed)
    check_headers()
    check_login_cookie()
    check_anonymous(urls)
    check_role_isolation(urls)
    check_idor()
    check_csrf()
    check_rate_limit()
    check_api()

    passed = sum(r["ok"] for r in results)
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    (out / f"security-selftest-{stamp}.json").write_text(json.dumps(results, indent=2))
    lines = [f"# Security self-test — {stamp}", "", f"**{passed}/{len(results)} checks passed**", "",
             "| Area | Check | Result | Detail |", "|---|---|---|---|"]
    lines += [f"| {r['area']} | {r['check']} | {'✅' if r['ok'] else '❌'} | {r['detail']} |" for r in results]
    (out / f"security-selftest-{stamp}.md").write_text("\n".join(lines) + "\n")
    for r in results:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['area']:<20} {r['check']}  {r['detail'][:80]}")
    print(f"\n{passed}/{len(results)} passed · report: {out / f'security-selftest-{stamp}.md'}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
