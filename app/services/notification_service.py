"""
app/services/notification_service.py
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.notification import Notification
from app.models.user import User, UserRole

AR_TEMPLATES: dict[str, tuple[str, str]] = {
    "registration_submitted": ("طلب تسجيل جديد", "سجّلت {company} ({role}) وتنتظر المراجعة."),
    "registration_approved": ("تمت الموافقة على التسجيل", "تمت الموافقة على {company}. لديك الآن وصول كامل إلى بوابتك."),
    "registration_rejected": ("لم تتم الموافقة على التسجيل", "لم تتم الموافقة على تسجيل {company}. السبب: {reason}"),
    "verification_requested": ("طلب تحقق جديد", "طلب أحد البائعين التحقق من منتج {mineral}."),
    "verification_scheduled": ("تمت جدولة أخذ العينة", "جدول المختبر أخذ عينة منتج {mineral} بتاريخ {date}."),
    "verification_testing": ("بدأ الاختبار", "بدأ المختبر اختبار عينة منتج {mineral}."),
    "verification_passed": ("اجتاز التحقق", "تم التحقق من منتج {mineral}. صدرت الشهادة {certificate}."),
    "verification_failed": ("لم يجتز التحقق", "لم يجتز منتج {mineral} التحقق. السبب: {reason}"),
    "passport_requested": ("طلب جواز معدني جديد", "طلب بائع جواز معدني لمنتج {mineral}."),
    "passport_approved": ("صدر الجواز المعدني", "صدر جواز منتج {mineral}: {certificate} (ساري حتى {until})."),
    "passport_rejected": ("لم تتم الموافقة على طلب الجواز", "لم تتم الموافقة على طلب جواز منتج {mineral}. السبب: {reason}"),
    "passport_expiring": ("الجواز المعدني قارب على الانتهاء", "ينتهي الجواز {certificate} بتاريخ {until}. اطلب التجديد."),
    "rfq_new": ("طلب تسعير جديد", "طلب تسعير جديد لـ {mineral} ({quantity})."),
    "rfq_cancelled": ("أُلغي طلب التسعير", "ألغى المشتري طلب التسعير {rfq} الخاص بـ {mineral}."),
    "quotation_received": ("عرض سعر جديد", "تلقيت عرض سعر جديداً على طلب التسعير {rfq} ({mineral})."),
    "quotation_revised": ("تم تعديل عرض سعر", "عدّل أحد البائعين عرضه على طلب التسعير {rfq}."),
    "quotation_accepted": ("تم قبول عرض السعر", "قبل مشترٍ عرضك على طلب {mineral}. أكّد الطلب للمتابعة وستظهر لك هوية المشتري."),
    "quotation_not_selected": ("لم يتم اختيار عرض السعر", "أُغلق طلب التسعير {rfq} باختيار عرض آخر."),
    "order_confirmed": ("تم تأكيد الطلب — كُشفت هوية البائع", "أكّد البائع طلب {mineral}. يمكنك الآن رؤية الطرف الآخر."),
    "order_shipped": ("الطلب قيد الشحن", "طلب {mineral} الآن قيد الشحن."),
    "order_delivered": ("تم تسليم الطلب", "تم تسليم طلب {mineral}. أكّد الاستلام لإكماله."),
    "order_invoiced": ("صدرت فاتورة الطلب", "أصدر البائع الفاتورة {invoice} لطلب {mineral}."),
    "order_completed": ("اكتمل الطلب", "أكّد المشتري استلام طلب {mineral}. اكتمل الطلب."),
    "order_document": ("مستند جديد على الطلب", "أُضيف مستند ({doc_type}) إلى الطلب {order}."),
    "dispute_raised": ("تم رفع نزاع", "رُفع النزاع {dispute} على الطلب {order}: {category}."),
    "dispute_message": ("رسالة جديدة في النزاع", "رسالة جديدة في النزاع {dispute}."),
    "dispute_status": ("تحديث حالة النزاع", "النزاع {dispute} الآن: {status}."),
    "dispute_resolved": ("صدر قرار النزاع", "صدر قرار النزاع {dispute} لصالح {party}."),
    "dispute_corrected": ("تصحيح قرار النزاع", "صُحح قرار النزاع {dispute} بشكل رسمي."),
    "dispute_withdrawn": ("سُحب النزاع", "سُحب النزاع {dispute}."),
    "subscription_changed": ("تم تغيير الاشتراك", "خطة اشتراكك الآن {plan}."),
    "subscription_expiring": ("الاشتراك قارب على الانتهاء", "ينتهي اشتراك {plan} بتاريخ {until}. جدّد لتجنب الانتقال إلى الخطة الأساسية."),
    "subscription_grace": ("الاشتراك في فترة السماح", "انتهى اشتراك {plan}. لديك فترة سماح حتى {until}."),
    "subscription_expired": ("انتهى الاشتراك", "انتهى اشتراك {plan} وتم نقلك إلى الخطة الأساسية."),
    "data_request_submitted": ("طلب بيانات شخصية جديد", "قدّم {user} طلب {type} ({reference})."),
    "data_request_updated": ("تحديث طلب البيانات", "طلبك {reference} الآن: {status}."),
    "product_suspended": ("تم تعليق المنتج", "علّقت الإدارة منتج {mineral}. السبب: {reason}"),
    "product_reactivated": ("تمت إعادة تفعيل المنتج", "أعادت الإدارة تفعيل منتج {mineral}."),
    "document_uploaded": ("مستند شركة بانتظار المراجعة", "رفعت {company} مستند {doc_type}."),
    "document_reviewed": ("مراجعة المستند: {doc_type}", "تمت مراجعة {doc_type}: {status}. {note}"),
    "document_expiring": ("مستند قارب على الانتهاء: {doc_type}", "ارفع النسخة المجددة من {doc_type} قبل {until} لمواصلة التداول."),
    "documents_expiring": ("مستندات شركات قاربت على الانتهاء", "أُرسل {count} تذكير إلى الشركات."),
    "shipment_late": ("الشحنة {shipment} تجاوزت موعد الوصول", "أضف تحديث تتبع أو موعد وصول جديد للمشتري."),
    "shipment_update": ("تحديث الشحنة {shipment}", "الشحنة {shipment}: {status_ar} {where}"),
}

ICONS = {
    "registration": "bi-building-check", "verification": "bi-eyedropper", "passport": "bi-shield-check",
    "rfq": "bi-file-earmark-text", "quotation": "bi-tags", "order": "bi-box-seam", "dispute": "bi-flag",
    "subscription": "bi-stars", "data": "bi-person-lock", "product": "bi-diagram-3", "shipment": "bi-truck", "document": "bi-folder2-open", "documents": "bi-folder2-open",
}


def icon_for(type_: str) -> str:
    return ICONS.get(type_.split("_")[0], "bi-bell")


class _SafeDict(dict):
    def __missing__(self, key):
        return "…"


def _arabic(type_: str, title: str, params: dict) -> tuple[str | None, str | None]:
    tpl = AR_TEMPLATES.get(type_)
    if tpl is None:
        from app.core.translation import translate_text
        t = translate_text(title)
        return (t if t != title else None), None
    p = _SafeDict({k: ("" if v is None else str(v)) for k, v in params.items()})
    return tpl[0].format_map(p), tpl[1].format_map(p)


def notify_user(db: Session, user: User, type_: str, title: str, body: str, /, *,
                action_url: str | None = None, **params) -> Notification:
    title_ar, body_ar = _arabic(type_, title, params)
    n = Notification(
        user_id=user.id, company_id=user.company_id, type=type_, title=title[:200], body=body,
        title_ar=title_ar[:200] if title_ar else None, body_ar=body_ar, action_url=action_url,
    )
    db.add(n)
    return n


def notify_company(db: Session, company: Company | None, type_: str, title: str, body: str, /, *,
                   action_url: str | None = None, **params) -> int:
    if company is None:
        return 0
    count = 0
    for user in company.users:
        if user.is_active:
            notify_user(db, user, type_, title, body, action_url=action_url, **params)
            count += 1
    return count


def notify_admins(db: Session, area: str, type_: str, title: str, body: str, /, *,
                  action_url: str | None = None, **params) -> int:
    from app.core.permissions import admin_can
    count = 0
    for admin in db.query(User).filter(User.role == UserRole.ADMIN, User.is_active.is_(True)).all():
        if admin_can(admin, area):
            notify_user(db, admin, type_, title, body, action_url=action_url, **params)
            count += 1
    return count


def localized(n: Notification, lang: str) -> tuple[str, str]:
    if lang == "ar":
        return (n.title_ar or n.title), (n.body_ar or n.body)
    return n.title, n.body


def time_ago(dt: datetime) -> str:
    delta = datetime.now(timezone.utc) - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60} min ago"
    if secs < 86400:
        return f"{secs // 3600} h ago"
    return dt.strftime("%Y-%m-%d")


def header_summary(db: Session, user_id: uuid.UUID, lang: str, limit: int = 6) -> dict:
    q = db.query(Notification).filter(Notification.user_id == user_id)
    unread = q.filter(Notification.is_read.is_(False)).count()
    items = []
    for n in q.order_by(Notification.created_at.desc()).limit(limit):
        title, body = localized(n, lang)
        items.append({"title": title, "body": body, "is_read": n.is_read, "action_url": n.action_url,
                      "icon": icon_for(n.type), "when": time_ago(n.created_at)})
    return {"unread": unread, "entries": items}
