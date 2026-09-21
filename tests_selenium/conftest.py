"""
tests_selenium/conftest.py

Real-browser end-to-end tests, complementing scripts/check_routes.py.

check_routes.py proves every GET route renders without crashing. It
deliberately never fires a POST (mutating a shared seeded dataset on
every run would make it destructive). These Selenium tests are what
actually DRIVE the mutating flows a real user performs — logging in,
approving a company, submitting a quotation, accepting an order — by
clicking real buttons in a real Chrome, exactly like a person would.

SETUP (once)
    1. Your app must be running (uvicorn) against a DB that has been
       seeded with scripts/seed_test_data.py — these tests log in as
       the seeded admin/seller/buyer/lab accounts and rely on the
       fixed seed data (a still-OPEN rfq2, a PENDING passport, etc).
    2. pip install selenium
    3. You need a Chrome/Chromium binary AND a matching chromedriver.
       - If you already have Google Chrome installed on Windows, just
         install chromedriver: pip install selenium already brings in
         Selenium Manager, which auto-downloads a matching driver the
         first time you run pytest — nothing else to do on most setups.
       - If Selenium Manager can't reach the internet in your network,
         download chromedriver yourself from
         https://googlechromelabs.github.io/chrome-for-testing/
         matching your installed Chrome's version, and set
         CHROMEDRIVER_PATH below (env var) to point at it.

RUNNING
    set BASE_URL=http://127.0.0.1:8000   (or your dev server's URL)
    pytest tests_selenium/ -v

    Headless by default. Set HEADLESS=0 to watch the browser drive
    itself (useful the first time, to see it's really doing this).

WHAT THESE TESTS ASSUME
    - scripts/seed_test_data.py has been run against the DB the app
      under test is using, so scripts/seed_ids.json exists.
    - The fixed seed credentials (see PASSWORD below) haven't been
      changed by hand in the DB.
    - Each test is independent and safe to re-run: tests either only
      READ, or they drive a flow using the specific seed record set
      aside for that flow (e.g. rfq2_id is deliberately left OPEN with
      no quotation, specifically so the "submit a quotation" test has
      something to act on every time you re-seed).
"""
import json
import os
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
HEADLESS = os.environ.get("HEADLESS", "1") != "0"
CHROMEDRIVER_PATH = os.environ.get("CHROMEDRIVER_PATH")  # optional override
CHROME_BINARY = os.environ.get("CHROME_BINARY")  # optional override

PASSWORD = "Test@12345"
EMAILS = {
    "admin": "admin@mineralstest.com",
    "seller": "seller@mineralstest.com",
    "buyer": "buyer@mineralstest.com",
    "lab": "lab@mineralstest.com",
}

SEED_IDS_PATH = Path(__file__).parent.parent / "scripts" / "seed_ids.json"


@pytest.fixture(scope="session")
def seed_ids() -> dict:
    if not SEED_IDS_PATH.exists():
        pytest.exit(
            f"{SEED_IDS_PATH} not found — run `python scripts/seed_test_data.py` "
            "against the DB your app is using before running these tests."
        )
    return json.loads(SEED_IDS_PATH.read_text())


@pytest.fixture
def driver():
    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1000")
    if CHROME_BINARY:
        opts.binary_location = CHROME_BINARY

    service = Service(executable_path=CHROMEDRIVER_PATH) if CHROMEDRIVER_PATH else Service()
    drv = webdriver.Chrome(service=service, options=opts)
    drv.implicitly_wait(2)
    yield drv
    drv.quit()


@pytest.fixture
def wait(driver):
    return WebDriverWait(driver, 10)


def login_as(driver, wait, role: str):
    """Drives the real login form with complete session reset.
    
    This ensures:
    1. No cookies bleed between role logins
    2. Each role gets a fresh browser session
    3. Test data isolation is maintained
    """
    email = EMAILS[role]
    
    # CRITICAL FIX: Completely clear browser state
    driver.delete_all_cookies()
    driver.execute_script("window.sessionStorage.clear();")
    driver.execute_script("window.localStorage.clear();")
    
    # Navigate to login
    driver.get(f"{BASE_URL}/login")
    
    # Fill and submit login form
    driver.find_element("id", "email").clear()
    driver.find_element("id", "email").send_keys(email)
    driver.find_element("id", "password").clear()
    driver.find_element("id", "password").send_keys(PASSWORD)
    driver.find_element("css selector", "button[type=submit]").click()
    
    # Wait for redirect away from login
    wait.until(lambda d: "/login" not in d.current_url)
    return driver


@pytest.fixture
def as_admin(driver, wait):
    return login_as(driver, wait, "admin")


@pytest.fixture
def as_seller(driver, wait):
    return login_as(driver, wait, "seller")


@pytest.fixture
def as_buyer(driver, wait):
    return login_as(driver, wait, "buyer")


@pytest.fixture
def as_lab(driver, wait):
    return login_as(driver, wait, "lab")
