"""
Admin approving a pending seller company — the flow check_routes.py
can only reach as a GET (the review page), never fires.

Safe to re-run: if a previous run already approved the seed's pending
company, it's no longer in the approvals queue, and this test skips
itself instead of failing (re-seeding from a fresh DB restores the
pending company for the next full run).
"""
import pytest
from conftest import BASE_URL


def test_admin_can_approve_pending_company(as_admin, wait, seed_ids):
    driver = as_admin
    pending_id = seed_ids["pending_company_id"]

    driver.get(f"{BASE_URL}/admin/approvals")
    rows = driver.find_elements(
        "css selector", f"a[href*='/admin/approvals/{pending_id}']"
    )
    if not rows:
        pytest.skip(
            "Seed's pending company is no longer in the queue — already "
            "approved by an earlier run of this test. Re-run "
            "scripts/seed_test_data.py against a fresh DB to reset it."
        )

    driver.execute_script("arguments[0].click();", rows[0])
    wait.until(lambda d: "/admin/approvals/" in d.current_url)

    approve_button = driver.find_element("css selector", "button.btn-success")
    driver.execute_script("arguments[0].click();", approve_button)

    wait.until(lambda d: d.current_url.rstrip("/").endswith("/admin/approvals"))

    # company no longer appears in the pending queue
    remaining = driver.find_elements(
        "css selector", f"a[href*='/admin/approvals/{pending_id}']"
    )
    assert not remaining, "Approved company still showing in the pending queue"

    # and its audit-log entry exists
    driver.get(f"{BASE_URL}/admin/audit-log")
    assert "company_approved" in driver.page_source or "Approved" in driver.page_source
