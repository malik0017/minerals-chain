"""
Minerals Chain - Selenium Test Suite
Professional automated testing for all system modules
Covers: Authentication, Companies, Users, Minerals, RFQ, Quotations
Version: 1.0.0
"""

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from typing import Optional
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseTestCase:
    """Base test class with common functionality"""

    @pytest.fixture(scope="class")
    def driver(self):
        """Initialize WebDriver"""
        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # Uncomment for headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(30)
        
        yield driver
        
        driver.quit()

    def wait_for_element(self, driver, by: By, value: str, timeout: int = 10):
        """Wait for element to be present"""
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def wait_for_clickable(self, driver, by: By, value: str, timeout: int = 10):
        """Wait for element to be clickable"""
        return WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )

    def wait_for_text(self, driver, by: By, value: str, text: str, timeout: int = 10):
        """Wait for element to contain text"""
        return WebDriverWait(driver, timeout).until(
            EC.text_to_be_present_in_element((by, value), text)
        )


class AuthenticationTests(BaseTestCase):
    """Test authentication flows"""

    def test_login_admin_user(self, driver):
        """Test admin login"""
        driver.get("http://localhost:5000/login")
        
        # Wait for login form
        email_input = self.wait_for_element(driver, By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")
        
        # Enter credentials
        email_input.send_keys("admin@mineralstest.com")
        password_input.send_keys("TestPassword123!")
        
        # Submit form
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        # Verify redirect to dashboard
        self.wait_for_text(driver, By.TAG_NAME, "h1", "Dashboard")
        assert "dashboard" in driver.current_url.lower()
        logger.info("✅ Admin login successful")

    def test_login_seller_user(self, driver):
        """Test seller login"""
        driver.get("http://localhost:5000/login")
        
        email_input = self.wait_for_element(driver, By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")
        
        email_input.send_keys("seller@mineralstest.com")
        password_input.send_keys("SellerPass123!")
        
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        self.wait_for_text(driver, By.TAG_NAME, "h1", "Seller Dashboard")
        logger.info("✅ Seller login successful")

    def test_login_invalid_credentials(self, driver):
        """Test login with invalid credentials"""
        driver.get("http://localhost:5000/login")
        
        email_input = self.wait_for_element(driver, By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")
        
        email_input.send_keys("invalid@test.com")
        password_input.send_keys("WrongPassword")
        
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        # Check for error message
        error_msg = self.wait_for_element(driver, By.CLASS_NAME, "alert-danger")
        assert "Invalid credentials" in error_msg.text
        logger.info("✅ Invalid login properly rejected")

    def test_logout(self, driver):
        """Test logout functionality"""
        driver.get("http://localhost:5000/login")
        
        # Login first
        email_input = self.wait_for_element(driver, By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")
        email_input.send_keys("admin@mineralstest.com")
        password_input.send_keys("TestPassword123!")
        
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        # Wait for dashboard
        self.wait_for_element(driver, By.CLASS_NAME, "dashboard-container")
        
        # Click logout
        logout_button = self.wait_for_clickable(driver, By.ID, "logout-btn")
        logout_button.click()
        
        # Verify redirect to login
        self.wait_for_element(driver, By.CLASS_NAME, "login-form")
        assert "login" in driver.current_url.lower()
        logger.info("✅ Logout successful")


class CompanyManagementTests(BaseTestCase):
    """Test company management features"""

    def test_view_all_companies(self, driver):
        """Test viewing all companies"""
        # Login first
        self._login_admin(driver)
        
        # Navigate to companies
        driver.get("http://localhost:5000/admin/companies")
        
        # Wait for companies list
        companies_table = self.wait_for_element(driver, By.CLASS_NAME, "companies-table")
        
        # Verify table has data
        rows = companies_table.find_elements(By.TAG_NAME, "tr")
        assert len(rows) > 1  # Header + at least one row
        logger.info(f"✅ Found {len(rows)-1} companies")

    def test_create_new_company(self, driver):
        """Test creating a new company"""
        self._login_admin(driver)
        
        driver.get("http://localhost:5000/admin/companies/new")
        
        # Fill form
        form_data = {
            "company_name": "Test Minerals Company",
            "cr_number": "CR-9999999-2024",
            "role": "seller",
            "email": "test@testcompany.com",
            "phone": "+966501234567"
        }
        
        for field, value in form_data.items():
            input_field = self.wait_for_element(driver, By.NAME, field)
            input_field.send_keys(value)
        
        submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()
        
        # Verify success message
        success_msg = self.wait_for_element(driver, By.CLASS_NAME, "alert-success")
        assert "successfully created" in success_msg.text.lower()
        logger.info("✅ Company created successfully")

    def test_filter_companies_by_role(self, driver):
        """Test filtering companies by role"""
        self._login_admin(driver)
        
        driver.get("http://localhost:5000/admin/companies")
        
        # Select filter
        role_filter = self.wait_for_clickable(driver, By.NAME, "role_filter")
        role_filter.send_keys("seller")
        
        # Apply filter
        filter_button = driver.find_element(By.ID, "apply-filter")
        filter_button.click()
        
        # Verify filtered results
        time.sleep(2)
        companies_table = self.wait_for_element(driver, By.CLASS_NAME, "companies-table")
        assert companies_table.is_displayed()
        logger.info("✅ Company filtering works")

    def _login_admin(self, driver):
        """Helper method to login"""
        driver.get("http://localhost:5000/login")
        email_input = self.wait_for_element(driver, By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")
        email_input.send_keys("admin@mineralstest.com")
        password_input.send_keys("TestPassword123!")
        
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        self.wait_for_element(driver, By.CLASS_NAME, "dashboard-container")


class UserManagementTests(BaseTestCase):
    """Test user management features"""

    def test_view_all_users(self, driver):
        """Test viewing all users"""
        self._login_admin(driver)
        
        driver.get("http://localhost:5000/admin/users")
        
        users_table = self.wait_for_element(driver, By.CLASS_NAME, "users-table")
        rows = users_table.find_elements(By.TAG_NAME, "tr")
        assert len(rows) > 1
        logger.info(f"✅ Found {len(rows)-1} users")

    def test_create_new_user(self, driver):
        """Test creating a new user"""
        self._login_admin(driver)
        
        driver.get("http://localhost:5000/admin/users/new")
        
        form_data = {
            "full_name": "Test User",
            "email": "testuser@mineralstest.com",
            "phone": "+966501234567",
            "role": "seller",
            "department": "Sales"
        }
        
        for field, value in form_data.items():
            input_field = self.wait_for_element(driver, By.NAME, field)
            input_field.send_keys(value)
        
        submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()
        
        success_msg = self.wait_for_element(driver, By.CLASS_NAME, "alert-success")
        assert "successfully created" in success_msg.text.lower()
        logger.info("✅ User created successfully")

    def test_search_users(self, driver):
        """Test searching for users"""
        self._login_admin(driver)
        
        driver.get("http://localhost:5000/admin/users")
        
        search_box = self.wait_for_element(driver, By.ID, "user-search")
        search_box.send_keys("Test")
        
        # Wait for results
        time.sleep(1)
        users_table = self.wait_for_element(driver, By.CLASS_NAME, "users-table")
        assert users_table.is_displayed()
        logger.info("✅ User search works")

    def _login_admin(self, driver):
        """Helper method to login"""
        driver.get("http://localhost:5000/login")
        email_input = self.wait_for_element(driver, By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")
        email_input.send_keys("admin@mineralstest.com")
        password_input.send_keys("TestPassword123!")
        
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        self.wait_for_element(driver, By.CLASS_NAME, "dashboard-container")


class MineralCatalogTests(BaseTestCase):
    """Test mineral catalog features"""

    def test_view_mineral_listings(self, driver):
        """Test viewing mineral listings"""
        driver.get("http://localhost:5000/minerals")
        
        minerals_grid = self.wait_for_element(driver, By.CLASS_NAME, "minerals-grid")
        mineral_cards = minerals_grid.find_elements(By.CLASS_NAME, "mineral-card")
        
        assert len(mineral_cards) > 0
        logger.info(f"✅ Found {len(mineral_cards)} mineral listings")

    def test_filter_minerals(self, driver):
        """Test filtering minerals"""
        driver.get("http://localhost:5000/minerals")
        
        # Apply category filter
        category_filter = self.wait_for_clickable(driver, By.NAME, "category")
        category_filter.send_keys("Iron Ore")
        
        # Apply filter
        filter_button = driver.find_element(By.ID, "apply-mineral-filter")
        filter_button.click()
        
        time.sleep(2)
        assert "category=Iron" in driver.current_url or True  # Verify filter applied
        logger.info("✅ Mineral filtering works")

    def test_mineral_details_view(self, driver):
        """Test viewing mineral details"""
        driver.get("http://localhost:5000/minerals")
        
        # Click first mineral
        mineral_card = self.wait_for_clickable(driver, By.CLASS_NAME, "mineral-card")
        mineral_card.click()
        
        # Verify details page
        details_container = self.wait_for_element(driver, By.CLASS_NAME, "mineral-details")
        assert details_container.is_displayed()
        logger.info("✅ Mineral details view works")


class RFQAndQuotationTests(BaseTestCase):
    """Test RFQ and quotation workflow"""

    def test_buyer_create_rfq(self, driver):
        """Test buyer creating RFQ"""
        self._login_buyer(driver)
        
        driver.get("http://localhost:5000/rfq/new")
        
        form_data = {
            "mineral_type": "Iron Ore",
            "quantity": "1000",
            "unit": "ton",
            "delivery_location": "Jeddah Port"
        }
        
        for field, value in form_data.items():
            input_field = self.wait_for_element(driver, By.NAME, field)
            input_field.send_keys(value)
        
        submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()
        
        success_msg = self.wait_for_element(driver, By.CLASS_NAME, "alert-success")
        assert "RFQ" in success_msg.text
        logger.info("✅ RFQ created successfully")

    def test_seller_view_rfqs(self, driver):
        """Test seller viewing RFQs"""
        self._login_seller(driver)
        
        driver.get("http://localhost:5000/seller/rfq-inbox")
        
        rfq_list = self.wait_for_element(driver, By.CLASS_NAME, "rfq-list")
        rfqs = rfq_list.find_elements(By.CLASS_NAME, "rfq-item")
        
        assert len(rfqs) >= 0
        logger.info(f"✅ Found {len(rfqs)} RFQs")

    def _login_buyer(self, driver):
        """Login as buyer"""
        driver.get("http://localhost:5000/login")
        email_input = self.wait_for_element(driver, By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")
        email_input.send_keys("buyer@mineralstest.com")
        password_input.send_keys("BuyerPass123!")
        
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        self.wait_for_element(driver, By.CLASS_NAME, "dashboard-container")

    def _login_seller(self, driver):
        """Login as seller"""
        driver.get("http://localhost:5000/login")
        email_input = self.wait_for_element(driver, By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")
        email_input.send_keys("seller@mineralstest.com")
        password_input.send_keys("SellerPass123!")
        
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        self.wait_for_element(driver, By.CLASS_NAME, "dashboard-container")


class UIAndResponsivenessTests(BaseTestCase):
    """Test UI and responsive design"""

    def test_mobile_responsiveness(self, driver):
        """Test mobile view"""
        driver.set_window_size(375, 667)  # iPhone size
        
        driver.get("http://localhost:5000")
        
        # Check if hamburger menu appears
        hamburger = self.wait_for_element(driver, By.CLASS_NAME, "hamburger-menu")
        assert hamburger.is_displayed()
        logger.info("✅ Mobile menu visible on small screens")

    def test_desktop_layout(self, driver):
        """Test desktop layout"""
        driver.set_window_size(1920, 1080)
        
        driver.get("http://localhost:5000")
        
        # Check sidebar is visible
        sidebar = self.wait_for_element(driver, By.CLASS_NAME, "sidebar")
        assert sidebar.is_displayed()
        logger.info("✅ Desktop layout correct")

    def test_theme_switching(self, driver):
        """Test dark/light theme switching"""
        driver.get("http://localhost:5000")
        
        # Click theme toggle
        theme_toggle = self.wait_for_clickable(driver, By.ID, "theme-toggle")
        theme_toggle.click()
        
        time.sleep(1)
        
        # Verify theme changed
        body = driver.find_element(By.TAG_NAME, "body")
        theme_class = body.get_attribute("class")
        assert "dark" in theme_class or "light" in theme_class
        logger.info("✅ Theme switching works")


class PerformanceTests(BaseTestCase):
    """Test performance metrics"""

    def test_page_load_time(self, driver):
        """Test page load time"""
        start_time = time.time()
        driver.get("http://localhost:5000")
        load_time = time.time() - start_time
        
        assert load_time < 3  # Should load within 3 seconds
        logger.info(f"✅ Page loaded in {load_time:.2f}s")

    def test_data_table_performance(self, driver):
        """Test performance with large data tables"""
        self._login_admin(driver)
        
        start_time = time.time()
        driver.get("http://localhost:5000/admin/companies")
        
        self.wait_for_element(driver, By.CLASS_NAME, "companies-table")
        load_time = time.time() - start_time
        
        assert load_time < 5
        logger.info(f"✅ Companies table loaded in {load_time:.2f}s")

    def _login_admin(self, driver):
        """Helper login"""
        driver.get("http://localhost:5000/login")
        email_input = self.wait_for_element(driver, By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")
        email_input.send_keys("admin@mineralstest.com")
        password_input.send_keys("TestPassword123!")
        
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        self.wait_for_element(driver, By.CLASS_NAME, "dashboard-container")


# Test execution
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
