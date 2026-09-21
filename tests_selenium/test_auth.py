"""
Login, for every seeded role, driven through the real form (not a raw
POST) — proves the login page renders, the CSRF hidden field + cookie
round-trip works in an actual browser, and each role lands somewhere
that isn't the login page again.
"""
from conftest import BASE_URL, EMAILS, PASSWORD, login_as


def test_login_page_renders(driver):
    driver.get(f"{BASE_URL}/login")
    assert driver.find_element("id", "email")
    assert driver.find_element("id", "password")


def test_wrong_password_shows_error(driver, wait):
    driver.get(f"{BASE_URL}/login")
    driver.find_element("id", "email").send_keys(EMAILS["admin"])
    driver.find_element("id", "password").send_keys("wrong-password-123")
    driver.find_element("css selector", "button[type=submit]").click()
    wait.until(lambda d: d.find_elements("css selector", ".alert-danger"))
    assert "/login" in driver.current_url


def test_each_role_can_log_in(driver, wait):
    for role in ("admin", "seller", "buyer", "lab"):
        login_as(driver, wait, role)
        assert "/login" not in driver.current_url, f"{role} login did not redirect away from /login"
        driver.delete_all_cookies()


def test_logout_returns_to_login(as_admin, wait):
    driver = as_admin
    driver.get(f"{BASE_URL}/logout")
    wait.until(lambda d: "/login" in d.current_url)
    # and a protected page now bounces back to /login
    driver.get(f"{BASE_URL}/admin/companies")
    wait.until(lambda d: "/login" in d.current_url)
