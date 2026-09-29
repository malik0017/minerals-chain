"""
app/services/master_data/starter_content.py

Batch Q1 — starter text for the admin-editable content pages. It is a
reasonable baseline aligned with PDPL principles (purpose, minimisation,
rights, retention, breach notification, contact), NOT legal advice: have it
reviewed by Saudi data-protection counsel before go-live (BRD §11.5), then
edit it in Master Data → Content Pages and raise the version.
"""

PRIVACY_EN = """# Who we are
Minerals Chain operates a B2B marketplace for industrial minerals in the Kingdom of Saudi Arabia. This notice explains what personal data we process, why, and your rights under the Personal Data Protection Law (PDPL).

# What we collect
- Account data: your name, business email, phone number, job title and password (stored only as a secure hash).
- Company data: legal name, Commercial Registration number, VAT number, licence or accreditation number, National Address and the documents you upload to prove them.
- Activity data: listings, RFQs, quotations, orders, disputes, notifications, and a security log of logins and administrative actions.

# Why we use it
- To verify that every participant is a legitimate licensed business (registration review).
- To run the marketplace: listings, lab verification, RFQs, orders, documents and disputes.
- To meet legal obligations, including tax (ZATCA) record keeping and security logging.
We do not sell personal data and we collect only what these purposes need.

# Identity protection
Buyer and seller identities are hidden from each other until an order is confirmed. Administrators can see identities to run the platform and resolve disputes.

# How long we keep it
Transaction, certificate, invoice and dispute records are kept for the period required by Saudi law (tax records for at least six years). Account data is kept while your account is active and then deleted or anonymised, unless the law requires us to keep it.

# Your rights
You can access your data, ask us to correct it, ask us to delete it, restrict or object to processing. Use My Profile → Privacy & my data to download your data or submit a request. We respond within 30 days.

# Security and breaches
Data is protected with access controls, encryption in transit, private document storage and audit logging. If a breach may harm you, we notify the Saudi Data & AI Authority (SDAIA) within 72 hours and inform affected users.

# Contact
Data protection contact: privacy@mineralschain.com"""

PRIVACY_AR = """# من نحن
تدير منصة سلاسل التعدين سوقاً إلكترونياً بين الشركات للمعادن الصناعية في المملكة العربية السعودية. يوضح هذا الإشعار البيانات الشخصية التي نعالجها وأسباب ذلك وحقوقك وفق نظام حماية البيانات الشخصية.

# ما الذي نجمعه
- بيانات الحساب: الاسم والبريد الإلكتروني للعمل ورقم الجوال والمسمى الوظيفي وكلمة المرور (تُحفظ بشكل مشفّر فقط).
- بيانات الشركة: الاسم القانوني ورقم السجل التجاري والرقم الضريبي ورقم الترخيص أو الاعتماد والعنوان الوطني والمستندات المرفوعة لإثباتها.
- بيانات النشاط: المنتجات وطلبات التسعير وعروض الأسعار والطلبات والنزاعات والإشعارات وسجل أمني لعمليات الدخول والإجراءات الإدارية.

# لماذا نستخدمها
- للتحقق من أن كل مشارك منشأة مرخّصة ونظامية (مراجعة التسجيل).
- لتشغيل السوق: المنتجات والتحقق المخبري وطلبات التسعير والطلبات والمستندات والنزاعات.
- للوفاء بالالتزامات النظامية ومنها حفظ السجلات الضريبية (هيئة الزكاة والضريبة والجمارك) والسجلات الأمنية.
لا نبيع البيانات الشخصية ولا نجمع إلا ما تتطلبه هذه الأغراض.

# حماية الهوية
تبقى هوية المشتري والبائع مخفية عن بعضهما حتى تأكيد الطلب. يطّلع المسؤولون على الهويات لتشغيل المنصة وحل النزاعات.

# مدة الاحتفاظ
نحتفظ بسجلات المعاملات والشهادات والفواتير والنزاعات للمدة التي يفرضها النظام السعودي (السجلات الضريبية ست سنوات على الأقل). ونحتفظ ببيانات الحساب طوال فترة نشاطه ثم تُحذف أو تُجعل مجهولة الهوية ما لم يُلزمنا النظام بالاحتفاظ بها.

# حقوقك
يحق لك الاطلاع على بياناتك وطلب تصحيحها أو حذفها أو تقييد معالجتها أو الاعتراض عليها. استخدم: ملفي الشخصي ← الخصوصية وبياناتي لتنزيل بياناتك أو تقديم طلب. نرد خلال 30 يوماً.

# الأمان وحوادث التسرب
نحمي البيانات بضوابط الوصول والتشفير أثناء النقل والتخزين الخاص للمستندات وسجلات التدقيق. وإذا وقع تسرب قد يضرك نبلغ الهيئة السعودية للبيانات والذكاء الاصطناعي (سدايا) خلال 72 ساعة ونُعلم المستخدمين المتأثرين.

# التواصل
مسؤول حماية البيانات: privacy@mineralschain.com"""

TERMS_EN = """# Use of the platform
Only approved companies holding a valid Commercial Registration (and a mining licence or lab accreditation where applicable) may trade on Minerals Chain.

# Verification before trade
No product is visible to buyers until an accredited laboratory has verified it and issued a Certificate of Analysis.

# Identity protection
Parties must not try to identify or contact each other outside the platform before an order is confirmed.

# Fees
Settlement fees are published in advance and charged to both parties when an order is confirmed. Fees are subject to 15% VAT.

# Disputes
Either party may raise a dispute on an order. The platform administrator records a formal decision. Financial settlement of a decision is handled outside the platform in the initial release.

# Records
Certificates, passports, invoices and dispute decisions are permanent records and cannot be edited after issue."""

TERMS_AR = """# استخدام المنصة
لا يحق التداول في سلاسل التعدين إلا للشركات المعتمدة التي تملك سجلاً تجارياً سارياً (وترخيص تعدين أو اعتماد مختبر حسب الحال).

# التحقق قبل التداول
لا يظهر أي منتج للمشترين حتى يتحقق منه مختبر معتمد ويصدر شهادة تحليل.

# حماية الهوية
لا يجوز للأطراف محاولة التعرف على بعضها أو التواصل خارج المنصة قبل تأكيد الطلب.

# الرسوم
تُنشر رسوم التسوية مسبقاً وتُحتسب على الطرفين عند تأكيد الطلب، وتخضع لضريبة القيمة المضافة 15%.

# النزاعات
يحق لأي طرف رفع نزاع على الطلب، ويسجّل مسؤول المنصة قراراً رسمياً. وتتم التسوية المالية للقرار خارج المنصة في الإصدار الأول.

# السجلات
الشهادات والجوازات والفواتير وقرارات النزاعات سجلات دائمة لا يمكن تعديلها بعد إصدارها."""

HELP_EN = """# Getting started
- **Sellers:** create a listing, add its specification, request lab verification, then answer RFQs in your RFQ inbox.
- **Buyers:** create an RFQ with the specification you need, compare anonymous quotations side by side, and accept the best one.
- **Labs:** schedule the sample, record results for each parameter, and the system issues the Certificate of Analysis.

# Language
Use the language button in the header (or the LTR/RTL switch in Personalize) to change between English and Arabic. The whole interface switches language and direction together.

# Need help?
Email support@mineralschain.com."""

HELP_AR = """# البدء
- **البائعون:** أنشئ منتجاً وأضف مواصفاته واطلب التحقق المخبري ثم أجب على طلبات التسعير.
- **المشترون:** أنشئ طلب تسعير بالمواصفات المطلوبة وقارن العروض المجهولة جنباً إلى جنب واقبل الأفضل.
- **المختبرات:** جدول أخذ العينة وسجّل نتيجة كل معيار ليصدر النظام شهادة التحليل.

# اللغة
استخدم زر اللغة في الأعلى (أو مفتاح الاتجاه في صفحة التخصيص) للتبديل بين العربية والإنجليزية، ويتغير النص والاتجاه معاً.

# تحتاج مساعدة؟
راسلنا على support@mineralschain.com."""

CONTENT_PAGES = [
    {"slug": "privacy", "title_en": "Privacy Notice", "title_ar": "إشعار الخصوصية", "body_en": PRIVACY_EN,
     "body_ar": PRIVACY_AR, "version": "1.0", "is_published": "true"},
    {"slug": "terms", "title_en": "Terms of Use", "title_ar": "شروط الاستخدام", "body_en": TERMS_EN,
     "body_ar": TERMS_AR, "version": "1.0", "is_published": "true"},
    {"slug": "help", "title_en": "Help Center", "title_ar": "مركز المساعدة", "body_en": HELP_EN,
     "body_ar": HELP_AR, "version": "1.0", "is_published": "true"},
]
