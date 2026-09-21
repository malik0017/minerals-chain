"""
app/core/localization.py

BRD §6.10: "All user-facing interfaces, documents, and notifications
shall be available in both Arabic and English... Arabic-language
interfaces shall render with correct right-to-left layout."

Deliberately a plain nested dict, not a full i18n framework (gettext/
Babel/etc.) — this project has stayed dependency-light throughout, and
a framework's .po/.mo compilation pipeline is real infrastructure
overhead that isn't justified for a two-language, no-pluralization-
rules-needed system. If this ever needs a third language or real
plural/gender rules, that's the point to reconsider.

Scope of THIS batch: the global chrome (header, sidebar, footer — every
page extends one of these, so translating them covers the whole app's
navigation and structure) plus the auth pages (login, register,
account status). Deeper per-portal pages (listings, RFQs, orders,
admin tables...) are NOT translated yet — t() below falls back to
English automatically for any key it doesn't have an Arabic string
for, so nothing breaks or shows blank, it just isn't Arabic yet. See
temp.txt's WHAT'S NEXT for the plan to extend coverage.

Usage: t("nav.dashboard", lang) or, in a template, the "t" global
function registered in main.py: {{ t('nav.dashboard') }} (lang is
read from the request-scoped "lang" template variable already present
in every page's context via portal_nav.build_portal_context / the
auth pages' own context).
"""

SUPPORTED_LANGUAGES = ("en", "ar")
DEFAULT_LANGUAGE = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    # --- Sidebar navigation (shared labels across portals) ---
    "nav.main_menu": {"en": "Main Menu", "ar": "القائمة الرئيسية"},
    "nav.quick_links": {"en": "Quick Links", "ar": "روابط سريعة"},
    "nav.coming_soon": {"en": "Coming Soon", "ar": "قريبًا"},
    "nav.admin_view_portals": {"en": "Admin: View Portals", "ar": "المشرف: عرض البوابات"},
    "nav.dashboard": {"en": "Dashboard", "ar": "لوحة التحكم"},
    "nav.my_listings": {"en": "My Listings", "ar": "إعلاناتي"},
    "nav.rfq_inbox": {"en": "RFQ Inbox", "ar": "صندوق طلبات التسعير"},
    "nav.my_quotations": {"en": "My Quotations", "ar": "عروض أسعاري"},
    "nav.orders": {"en": "Orders", "ar": "الطلبات"},
    "nav.browse_minerals": {"en": "Browse Minerals", "ar": "تصفح المعادن"},
    "nav.my_rfqs": {"en": "My RFQs", "ar": "طلبات التسعير الخاصة بي"},
    "nav.verification_requests": {"en": "Verification Requests", "ar": "طلبات التحقق"},
    "nav.pending_approvals": {"en": "Pending Approvals", "ar": "الموافقات المعلقة"},
    "nav.all_companies": {"en": "All Companies", "ar": "جميع الشركات"},
    "nav.users": {"en": "Users", "ar": "المستخدمون"},
    "nav.mineral_passports": {"en": "Mineral Passports", "ar": "جوازات المعادن"},
    "nav.audit_log": {"en": "Audit Log", "ar": "سجل التدقيق"},
    "audit_log.title": {"en": "Audit Log", "ar": "سجل التدقيق"},
    "audit_log.filter_actor": {"en": "Admin", "ar": "المسؤول"},
    "audit_log.filter_action": {"en": "Action", "ar": "الإجراء"},
    "audit_log.all_admins": {"en": "All admins", "ar": "كل المسؤولين"},
    "audit_log.all_actions": {"en": "All actions", "ar": "كل الإجراءات"},
    "audit_log.col_when": {"en": "When", "ar": "الوقت"},
    "audit_log.col_actor": {"en": "Admin", "ar": "المسؤول"},
    "audit_log.col_action": {"en": "Action", "ar": "الإجراء"},
    "audit_log.col_target": {"en": "Target", "ar": "الهدف"},
    "audit_log.col_details": {"en": "Details", "ar": "التفاصيل"},
    "audit_log.empty": {"en": "No audit log entries yet.", "ar": "لا توجد إدخالات في سجل التدقيق بعد."},
    "audit_log.filter": {"en": "Filter", "ar": "تصفية"},
    "nav.settings": {"en": "Settings", "ar": "الإعدادات"},
    "settings.title": {"en": "Platform Settings", "ar": "إعدادات المنصة"},
    "settings.registration_heading": {"en": "Self-registration", "ar": "التسجيل الذاتي"},
    "settings.registration_desc": {"en": "Turn off any role's ability to create a new account on /register. Existing accounts are never affected.", "ar": "أوقف قدرة أي دور على إنشاء حساب جديد عبر صفحة التسجيل. لا يتأثر أي حساب موجود."},
    "settings.otp_heading": {"en": "Email verification (OTP)", "ar": "التحقق من البريد الإلكتروني"},
    "settings.otp_desc": {"en": "When off, /register no longer requires proving control of the email address before submitting. Dev/staging convenience only — keep this on in production.", "ar": "عند الإيقاف، لن تتطلب صفحة التسجيل إثبات ملكية البريد الإلكتروني قبل الإرسال. للتطوير فقط - أبقِ هذا الخيار مفعلاً في الإنتاج."},
    "settings.save": {"en": "Save changes", "ar": "حفظ التغييرات"},
    "settings.saved": {"en": "Settings saved.", "ar": "تم حفظ الإعدادات."},
    "nav.disputes": {"en": "Disputes", "ar": "النزاعات"},
    "nav.reports": {"en": "Reports", "ar": "التقارير"},
    "nav.quotations": {"en": "Quotations", "ar": "عروض الأسعار"},
    "nav.personalize": {"en": "Personalize", "ar": "التخصيص"},
    "nav.coming_soon_heading": {"en": "Coming soon", "ar": "قريبًا"},
    "nav.admin_view_portals_heading": {"en": "Admin: view portals", "ar": "المشرف: عرض البوابات"},

    # --- Personalize page (Batch D) ---
    "personalize.title": {"en": "Personalization", "ar": "التخصيص"},
    "personalize.subtitle": {"en": "Make the platform look the way you want it to.", "ar": "اجعل المنصة تبدو بالشكل الذي تريده."},
    "personalize.theme_color": {"en": "Choose your theme color", "ar": "اختر لون السمة"},
    "personalize.background": {"en": "Background", "ar": "الخلفية"},
    "personalize.sidebar_fill": {"en": "Sidebar fill color", "ar": "لون تعبئة الشريط الجانبي"},
    "personalize.header_fill": {"en": "Header fill color", "ar": "لون تعبئة الرأس"},
    "personalize.color_mode": {"en": "Color mode", "ar": "وضع الألوان"},
    "personalize.color_mode_desc": {"en": "Switch between light and dark mode.", "ar": "التبديل بين الوضع الفاتح والداكن."},
    "personalize.dark_mode": {"en": "Dark mode", "ar": "الوضع الداكن"},
    "personalize.direction_mode": {"en": "Text direction", "ar": "اتجاه النص"},
    "personalize.direction_mode_desc": {"en": "This is tied to your language setting.", "ar": "هذا مرتبط بإعداد اللغة لديك."},
    "personalize.default": {"en": "Default", "ar": "افتراضي"},
    "personalize.white": {"en": "White", "ar": "أبيض"},
    "personalize.black": {"en": "Black", "ar": "أسود"},
    "personalize.accent": {"en": "Accent", "ar": "لون مميز"},
    "personalize.bg_theme": {"en": "Theme", "ar": "السمة"},
    "personalize.background_option": {"en": "Background", "ar": "الخلفية"},
    "personalize.gradient": {"en": "Gradient", "ar": "تدرج"},
    "personalize.background_images": {"en": "Background images", "ar": "صور الخلفية"},
    "personalize.sidebar_layout": {"en": "Sidebar layout", "ar": "تخطيط الشريط الجانبي"},
    "personalize.header_layout": {"en": "Header layout", "ar": "تخطيط الرأس"},
    "personalize.layout_standard": {"en": "Standard", "ar": "قياسي"},
    "personalize.layout_iconic": {"en": "Iconic", "ar": "رمزي"},
    "personalize.layout_boxed": {"en": "Boxed", "ar": "محاط بإطار"},
    "personalize.layout_iconic_boxed": {"en": "Iconic + Boxed", "ar": "رمزي ومحاط بإطار"},
    "personalize.language": {"en": "Language & text direction", "ar": "اللغة واتجاه النص"},
    "personalize.language_desc": {"en": "Switching language also switches text direction — Arabic reads right-to-left.", "ar": "تبديل اللغة يبدل أيضًا اتجاه النص — العربية تُقرأ من اليمين إلى اليسار."},
    "personalize.lang_english": {"en": "English", "ar": "الإنجليزية"},
    "personalize.lang_arabic": {"en": "العربية", "ar": "العربية"},

    # --- Portal labels + admin preview ---
    "portal.seller": {"en": "Seller Portal", "ar": "بوابة البائع"},
    "portal.buyer": {"en": "Buyer Portal", "ar": "بوابة المشتري"},
    "portal.lab": {"en": "Lab Portal", "ar": "بوابة المختبر"},
    "portal.admin": {"en": "Admin Portal", "ar": "بوابة المشرف"},
    "portal.previewing": {"en": "Previewing", "ar": "معاينة"},
    "nav.seller_dashboard": {"en": "Seller Dashboard", "ar": "لوحة تحكم البائع"},
    "nav.buyer_dashboard": {"en": "Buyer Dashboard", "ar": "لوحة تحكم المشتري"},
    "nav.lab_dashboard": {"en": "Lab Dashboard", "ar": "لوحة تحكم المختبر"},

    # --- Header ---
    "header.my_profile": {"en": "My Profile", "ar": "ملفي الشخصي"},
    "header.account_setting": {"en": "Account Setting", "ar": "إعدادات الحساب"},
    "header.logout": {"en": "Logout", "ar": "تسجيل الخروج"},
    "header.notifications": {"en": "Notifications", "ar": "الإشعارات"},
    "header.language": {"en": "Language", "ar": "اللغة"},
    "header.subscription": {"en": "Subscription", "ar": "الاشتراك"},
    "header.upgrade": {"en": "Upgrade", "ar": "ترقية"},

    # --- Footer ---
    "footer.copyright": {"en": "Copyright @2026, Creatively designed by", "ar": "حقوق النشر @2026، تصميم إبداعي من قبل"},
    "footer.on_earth": {"en": "on Earth", "ar": "على الأرض"},
    "footer.help": {"en": "Help", "ar": "المساعدة"},
    "footer.terms": {"en": "Terms of Use", "ar": "شروط الاستخدام"},
    "footer.privacy": {"en": "Privacy Policy", "ar": "سياسة الخصوصية"},

    # --- Auth: login ---
    "auth.login.title": {"en": "Log in", "ar": "تسجيل الدخول"},
    "auth.login.subtitle": {"en": "Welcome back to Minerals Chain", "ar": "مرحبًا بعودتك إلى سلاسل التعدين"},
    "auth.login.email": {"en": "Email", "ar": "البريد الإلكتروني"},
    "auth.login.password": {"en": "Password", "ar": "كلمة المرور"},
    "auth.login.submit": {"en": "Log in", "ar": "تسجيل الدخول"},
    "auth.login.no_account": {"en": "Don't have an account?", "ar": "ليس لديك حساب؟"},
    "auth.login.register_link": {"en": "Register", "ar": "إنشاء حساب"},

    # --- Auth: register ---
    "auth.register.title": {"en": "Create your account", "ar": "إنشاء حسابك"},
    "auth.register.subtitle": {"en": "Register as a mine operator, buyer, or testing lab", "ar": "سجّل كمشغّل منجم أو مشترٍ أو مختبر فحص"},
    "auth.register.role_label": {"en": "I am registering as a...", "ar": "أنا أسجل بصفتي..."},
    "auth.register.role_seller": {"en": "Mine Operator", "ar": "مشغّل منجم"},
    "auth.register.role_buyer": {"en": "Buyer", "ar": "مشترٍ"},
    "auth.register.role_lab": {"en": "Testing Lab", "ar": "مختبر فحص"},
    "auth.register.verify_email_heading": {"en": "Verify your email first", "ar": "تحقّق من بريدك الإلكتروني أولاً"},
    "auth.register.full_name": {"en": "Your full name", "ar": "الاسم الكامل"},
    "auth.register.email": {"en": "Email", "ar": "البريد الإلكتروني"},
    "auth.register.send_code": {"en": "Send code", "ar": "إرسال الرمز"},
    "auth.register.resend_code": {"en": "Resend code", "ar": "إعادة إرسال الرمز"},
    "auth.register.verify": {"en": "Verify", "ar": "تحقّق"},
    "auth.register.email_verified": {"en": "Email verified — you're all set to fill in the rest below.", "ar": "تم التحقق من البريد الإلكتروني — يمكنك الآن إكمال باقي البيانات أدناه."},
    "auth.register.company_details": {"en": "Company details", "ar": "بيانات الشركة"},
    "auth.register.company_name": {"en": "Company name", "ar": "اسم الشركة"},
    "auth.register.cr_number": {"en": "Commercial Registration (CR) number", "ar": "رقم السجل التجاري"},
    "auth.register.cr_document": {"en": "CR document", "ar": "مستند السجل التجاري"},
    "auth.register.license_number": {"en": "Licence / accreditation number", "ar": "رقم الترخيص / الاعتماد"},
    "auth.register.license_document": {"en": "Licence / accreditation document", "ar": "مستند الترخيص / الاعتماد"},
    "auth.register.contact_phone": {"en": "Contact phone", "ar": "رقم الهاتف"},
    "auth.register.password": {"en": "Password", "ar": "كلمة المرور"},
    "auth.register.confirm_password": {"en": "Confirm password", "ar": "تأكيد كلمة المرور"},
    "auth.register.submit": {"en": "Submit registration", "ar": "إرسال التسجيل"},
    "auth.register.verify_first_notice": {"en": "Verify your email above before submitting.", "ar": "يرجى التحقق من بريدك الإلكتروني أعلاه قبل الإرسال."},
    "auth.register.have_account": {"en": "Already have an account?", "ar": "لديك حساب بالفعل؟"},
    "auth.register.login_link": {"en": "Log in", "ar": "تسجيل الدخول"},

    # --- Auth: account status (pending/rejected/suspended landing page) ---
    "auth.status.pending_title": {"en": "Registration pending review", "ar": "التسجيل قيد المراجعة"},
    "auth.status.rejected_title": {"en": "Registration not approved", "ar": "لم تتم الموافقة على التسجيل"},
    "auth.status.suspended_title": {"en": "Account suspended", "ar": "الحساب موقوف"},

    # --- Common buttons/labels reused across many pages ---
    "common.save": {"en": "Save", "ar": "حفظ"},
    "common.save_changes": {"en": "Save changes", "ar": "حفظ التغييرات"},
    "common.cancel": {"en": "Cancel", "ar": "إلغاء"},
    "common.submit": {"en": "Submit", "ar": "إرسال"},
    "common.edit": {"en": "Edit", "ar": "تعديل"},
    "common.view": {"en": "View", "ar": "عرض"},
    "common.back": {"en": "Back", "ar": "رجوع"},
    "common.approve": {"en": "Approve", "ar": "موافقة"},
    "common.reject": {"en": "Reject", "ar": "رفض"},
    "common.status": {"en": "Status", "ar": "الحالة"},
    "common.approved": {"en": "Approved", "ar": "مقبول"},
    "common.pending": {"en": "Pending", "ar": "قيد الانتظار"},
    "common.rejected": {"en": "Rejected", "ar": "مرفوض"},
    "common.welcome": {"en": "Welcome", "ar": "مرحبًا"},
}


def t(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Looks up `key` in TRANSLATIONS for `lang`. Falls back to English
    if the key exists but has no translation for this language, and to
    the raw key itself (wrapped for visibility) if the key doesn't
    exist at all — so a missing/typo'd key is obviously wrong in the
    UI during development rather than silently blank."""
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return f"[{key}]"
    return entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or f"[{key}]"


def is_rtl(lang: str) -> bool:
    return lang == "ar"
