/**
 * Minerals Chain - Advanced Language Switcher
 * Professional RTL/LTR Support with Dynamic Layout Switching
 * Supports: Arabic, English (RTL/LTR)
 * Version: 1.0.0
 */

class LanguageSwitcher {
  constructor(options = {}) {
    this.currentLanguage = localStorage.getItem('language') || 'en';
    this.currentDirection = localStorage.getItem('direction') || 'ltr';
    
    this.options = {
      defaultLanguage: 'en',
      defaultDirection: 'ltr',
      supportedLanguages: ['en', 'ar'],
      directions: { en: 'ltr', ar: 'rtl' },
      animationDuration: 300,
      storageKey: 'language',
      directionKey: 'direction',
      ...options
    };

    this.translations = {};
    this.isInitialized = false;
    
    this.init();
  }

  /**
   * Initialize language switcher
   */
  init() {
    console.log('🔄 Initializing Language Switcher...');
    
    // Set initial direction
    this.setDirection(this.currentLanguage);
    
    // Bind event listeners
    this.bindEventListeners();
    
    // Initialize translations
    this.loadTranslations();
    
    this.isInitialized = true;
    console.log('✅ Language Switcher initialized');
  }

  /**
   * Load language translations
   */
  loadTranslations() {
    this.translations = {
      en: {
        language: 'English',
        direction: 'ltr',
        'nav.dashboard': 'Dashboard',
        'nav.companies': 'Companies',
        'nav.users': 'Users',
        'nav.minerals': 'Minerals',
        'nav.rfq': 'RFQ',
        'nav.quotations': 'Quotations',
        'nav.settings': 'Settings',
        'nav.logout': 'Logout',
        'btn.save': 'Save',
        'btn.cancel': 'Cancel',
        'btn.delete': 'Delete',
        'btn.edit': 'Edit',
        'btn.add': 'Add New',
        'page.title': 'Minerals Chain Admin Portal'
      },
      ar: {
        language: 'العربية',
        direction: 'rtl',
        'nav.dashboard': 'لوحة التحكم',
        'nav.companies': 'الشركات',
        'nav.users': 'المستخدمون',
        'nav.minerals': 'المعادن',
        'nav.rfq': 'طلبات الأسعار',
        'nav.quotations': 'الفواتير',
        'nav.settings': 'الإعدادات',
        'nav.logout': 'تسجيل الخروج',
        'btn.save': 'حفظ',
        'btn.cancel': 'إلغاء',
        'btn.delete': 'حذف',
        'btn.edit': 'تعديل',
        'btn.add': 'إضافة جديد',
        'page.title': 'بوابة إدارة سلسلة المعادن'
      }
    };
  }

  /**
   * Bind event listeners to language switcher buttons
   */
  bindEventListeners() {
    // Find all language switcher buttons
    const langButtons = document.querySelectorAll('[data-lang]');
    
    langButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        e.preventDefault();
        const lang = button.getAttribute('data-lang');
        this.switchLanguage(lang);
      });
    });

    // Listen for language change events from other tabs
    window.addEventListener('storage', (e) => {
      if (e.key === this.options.storageKey) {
        location.reload();
      }
    });
  }

  /**
   * Switch language and update entire document
   * @param {string} language - Language code (e.g., 'en', 'ar')
   */
  switchLanguage(language) {
    if (!this.options.supportedLanguages.includes(language)) {
      console.error(`Unsupported language: ${language}`);
      return;
    }

    console.log(`🔄 Switching language to: ${language}`);

    // Start transition animation
    this.startTransition();

    // Update current language
    this.currentLanguage = language;
    localStorage.setItem(this.options.storageKey, language);

    // Set direction based on language
    this.setDirection(language);

    // Update document language
    document.documentElement.lang = language;

    // Update all text elements
    this.updateTextContent();

    // Update all input placeholders
    this.updatePlaceholders();

    // Dispatch custom event
    window.dispatchEvent(new CustomEvent('languageChanged', {
      detail: { language, direction: this.currentDirection }
    }));

    // End transition
    this.endTransition();

    console.log(`✅ Language switched to: ${language}`);
  }

  /**
   * Set document direction (RTL/LTR)
   * @param {string} language - Language code
   */
  setDirection(language) {
    const direction = this.options.directions[language] || this.options.defaultDirection;
    this.currentDirection = direction;

    // Save to localStorage
    localStorage.setItem(this.options.directionKey, direction);

    // Set document direction
    document.documentElement.setAttribute('dir', direction);
    document.documentElement.style.direction = direction;
    document.body.style.direction = direction;

    // Update text alignment
    this.updateTextAlignment(direction);

    // Update transform scale for RTL
    if (direction === 'rtl') {
      document.documentElement.style.transformOrigin = 'right center';
    } else {
      document.documentElement.style.transformOrigin = 'left center';
    }

    console.log(`📝 Direction set to: ${direction}`);
  }

  /**
   * Update text alignment throughout document
   * @param {string} direction - 'rtl' or 'ltr'
   */
  updateTextAlignment(direction) {
    const elements = document.querySelectorAll('[data-align-auto]');
    
    elements.forEach(el => {
      if (direction === 'rtl') {
        el.style.textAlign = 'right';
        el.style.direction = 'rtl';
      } else {
        el.style.textAlign = 'left';
        el.style.direction = 'ltr';
      }
    });

    // Update margin/padding for RTL
    const margin_elements = document.querySelectorAll('[data-margin-auto]');
    margin_elements.forEach(el => {
      if (direction === 'rtl') {
        // Swap margin left/right
        const mleft = el.style.marginLeft;
        const mright = el.style.marginRight;
        el.style.marginLeft = mright;
        el.style.marginRight = mleft;
      }
    });
  }

  /**
   * Update all text content with translations
   */
  updateTextContent() {
    const language = this.currentLanguage;
    const trans = this.translations[language] || {};

    // Update elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (trans[key]) {
        el.textContent = trans[key];
      }
    });

    // Update page title
    document.title = trans['page.title'] || document.title;

    // Update button texts
    document.querySelectorAll('[data-i18n-btn]').forEach(btn => {
      const key = btn.getAttribute('data-i18n-btn');
      if (trans[key]) {
        btn.textContent = trans[key];
      }
    });
  }

  /**
   * Update input placeholders
   */
  updatePlaceholders() {
    const language = this.currentLanguage;
    const trans = this.translations[language] || {};

    document.querySelectorAll('[data-i18n-placeholder]').forEach(input => {
      const key = input.getAttribute('data-i18n-placeholder');
      if (trans[key]) {
        input.placeholder = trans[key];
      }
    });
  }

  /**
   * Start transition animation
   */
  startTransition() {
    document.body.style.opacity = '0.7';
    document.body.style.transition = `opacity ${this.options.animationDuration}ms ease`;
  }

  /**
   * End transition animation
   */
  endTransition() {
    setTimeout(() => {
      document.body.style.opacity = '1';
    }, this.options.animationDuration);
  }

  /**
   * Get current language
   */
  getLanguage() {
    return this.currentLanguage;
  }

  /**
   * Get current direction
   */
  getDirection() {
    return this.currentDirection;
  }

  /**
   * Get translation for a key
   * @param {string} key - Translation key
   * @param {string} language - Optional language code
   */
  t(key, language = null) {
    const lang = language || this.currentLanguage;
    const trans = this.translations[lang] || {};
    return trans[key] || key;
  }

  /**
   * Add custom translations
   * @param {string} language - Language code
   * @param {object} translations - Translation object
   */
  addTranslations(language, translations) {
    if (!this.translations[language]) {
      this.translations[language] = {};
    }
    this.translations[language] = {
      ...this.translations[language],
      ...translations
    };
  }

  /**
   * Detect user's browser language
   */
  detectBrowserLanguage() {
    const browserLang = navigator.language || navigator.userLanguage;
    const langCode = browserLang.split('-')[0];
    return this.options.supportedLanguages.includes(langCode) ? langCode : this.options.defaultLanguage;
  }

  /**
   * Initialize with browser language
   */
  initWithBrowserLanguage() {
    const browserLang = this.detectBrowserLanguage();
    this.switchLanguage(browserLang);
  }
}

/**
 * Create CSS for RTL/LTR support
 */
function injectRTLStyles() {
  const style = document.createElement('style');
  style.innerHTML = `
    /* RTL/LTR Support */
    [dir="rtl"] {
      direction: rtl;
      text-align: right;
    }

    [dir="ltr"] {
      direction: ltr;
      text-align: left;
    }

    /* Sidebar RTL */
    [dir="rtl"] .sidebar {
      right: 0;
      left: auto;
      border-right: none;
      border-left: 1px solid var(--gray-300);
    }

    [dir="rtl"] .main-content {
      margin-right: 250px;
      margin-left: 0;
    }

    /* Navigation RTL */
    [dir="rtl"] .navbar {
      flex-direction: row-reverse;
    }

    [dir="rtl"] .nav-links {
      flex-direction: row-reverse;
    }

    /* Buttons RTL */
    [dir="rtl"] .btn {
      flex-direction: row-reverse;
    }

    /* Forms RTL */
    [dir="rtl"] .form-group label {
      text-align: right;
    }

    /* Table RTL */
    [dir="rtl"] table {
      text-align: right;
    }

    [dir="rtl"] th,
    [dir="rtl"] td {
      text-align: right;
    }

    /* Modals RTL */
    [dir="rtl"] .modal-content {
      text-align: right;
    }

    /* Dropdowns RTL */
    [dir="rtl"] .dropdown-menu {
      left: auto;
      right: 0;
    }

    /* Language Switcher */
    .language-switcher {
      display: flex;
      gap: 0.5rem;
      align-items: center;
    }

    .language-switcher button {
      padding: 0.5rem 1rem;
      border: none;
      background-color: var(--gray-200);
      color: var(--text-primary);
      border-radius: var(--radius-lg);
      cursor: pointer;
      font-weight: 500;
      transition: all var(--transition-base);
    }

    .language-switcher button.active {
      background-color: var(--primary-color);
      color: white;
    }

    .language-switcher button:hover {
      background-color: var(--primary-dark);
      color: white;
    }

    /* Smooth Language Switch Animation */
    body {
      transition: direction 300ms ease, opacity 300ms ease;
    }
  `;
  document.head.appendChild(style);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  injectRTLStyles();
  
  // Create global instance
  window.languageSwitcher = new LanguageSwitcher({
    supportedLanguages: ['en', 'ar'],
    directions: { en: 'ltr', ar: 'rtl' }
  });

  console.log('✅ Language Switcher ready');
});

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = LanguageSwitcher;
}
