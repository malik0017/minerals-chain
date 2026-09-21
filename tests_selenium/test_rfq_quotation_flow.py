"""
Seller submitting a quotation, and buyer accepting one — the two
mutating steps of the RFQ flow check_routes.py can't safely fire.

Uses the seed's SECOND rfq (rfq2_id), which seed_test_data.py leaves
deliberately open with no quotation, specifically so this test always
has something fresh to act on. Each half is naturally idempotent
because the app's own templates are conditional on state (a seller who
already quoted sees "Submitted" instead of the form; a buyer sees
"accepted" instead of the Accept button) — so re-running this file
against the same un-reseeded DB skips rather than fails.
"""
import pytest
from conftest import BASE_URL


def test_seller_can_submit_quotation(as_seller, wait, seed_ids):
    """Test seller can submit a quotation to an RFQ.
    
    This tests the complete flow:
    1. Navigate to RFQ inbox
    2. Open a specific RFQ
    3. Fill quotation form
    4. Submit with validation
    5. Verify success response
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    import time
    
    driver = as_seller
    rfq_id = seed_ids["rfq2_id"]
    
    # Navigate to RFQ
    driver.get(f"{BASE_URL}/seller/rfq-inbox/{rfq_id}")
    
    # Skip if already quoted
    if "Submitted" in driver.page_source:
        pytest.skip("Seller already quoted this RFQ in an earlier run — re-seed to reset.")
    
    # Skip if form not present
    price_field = driver.find_elements("id", "price_value")
    if not price_field:
        pytest.skip("Quotation form not present (RFQ may already be closed/quoted).")
    
    # BATCH 2A: Wait for form to be ready
    print("DEBUG: Waiting for form to be ready...")
    wait.until(EC.presence_of_element_located((By.ID, "price_value")))
    wait.until(EC.element_to_be_clickable((By.ID, "price_value")))
    
    # BATCH 2B: Fill form fields with logging
    print("DEBUG: Filling quotation form...")
    price_input = driver.find_element("id", "price_value")
    lead_time_input = driver.find_element("id", "lead_time_days")
    terms_input = driver.find_element("id", "terms_notes")
    
    # Clear fields first (important if form retains old values)
    price_input.clear()
    lead_time_input.clear()
    terms_input.clear()
    
    # Fill with test values
    price_input.send_keys("450.00")
    lead_time_input.send_keys("14")
    terms_input.send_keys("FOB Jubail, seeded via Selenium test.")
    
    # BATCH 2C: Wait for submit button to be ready
    print("DEBUG: Waiting for submit button to be clickable...")
    submit_button = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type=submit]"))
    )
    
    # Log button state
    print(f"DEBUG: Button visible={submit_button.is_displayed()}, enabled={submit_button.is_enabled()}")
    
    # BATCH 2D: Submit using JavaScript (more reliable)
    print("DEBUG: Submitting form via JavaScript...")
    driver.execute_script("arguments[0].click();", submit_button)
    
    # BATCH 2E: Wait for server response
    print("DEBUG: Waiting for server response and page update...")
    time.sleep(0.5)  # Brief pause for form submission to reach server
    
    # BATCH 2F: Verify success message appears
    try:
        wait.until(lambda d: "Submitted" in d.page_source)
        print("DEBUG: ✓ 'Submitted' message found in page")
    except TimeoutException:
        print(f"DEBUG: ✗ 'Submitted' not found")
        print(f"DEBUG: Current URL: {driver.current_url}")
        print(f"DEBUG: Page title: {driver.title}")
        # Print last 1000 chars of page source for debugging
        page_html = driver.page_source[-1000:]
        print(f"DEBUG: Page source (last 1000 chars):\n{page_html}")
        raise AssertionError("Quotation did not submit successfully")


def test_buyer_can_accept_quotation(as_buyer, wait, seed_ids):
    driver = as_buyer
    rfq_id = seed_ids["rfq2_id"]
    driver.get(f"{BASE_URL}/buyer/rfqs/{rfq_id}")

    accept_buttons = driver.find_elements("css selector", "form[action*='/accept'] button[type=submit]")
    if not accept_buttons:
        if "accepted" in driver.page_source.lower():
            pytest.skip("A quotation on this RFQ was already accepted in an earlier run.")
        pytest.skip("No quotation available yet to accept — run test_seller_can_submit_quotation first.")

    driver.execute_script("arguments[0].click();", accept_buttons[0])
    # accepting a quotation is guarded by a native confirm() dialog
    wait.until(lambda d: d.switch_to.alert)
    driver.switch_to.alert.accept()
    wait.until(lambda d: "accepted" in d.page_source.lower() or "/buyer/orders" in d.current_url)
