"""
app/services/master_data/registry.py

Declarative registry behind /admin/master-data. Each Entity describes one
table well enough for the generic service + templates to list, search,
create, edit, (de)activate, delete, export and import it.

Field types: text | textarea | int | decimal | bool | date | choice | fk
  fk      — `fk` names another registry key; the form renders a <select>
            of that entity's active rows, CSV import/export use its
            natural key (usually `code`) instead of the UUID.
  choice  — fixed list validated here (see md_base.py docstring for why
            these are not PG enums).
"""
from dataclasses import dataclass, field

from app.models.batch import Batch, BatchQualityResult, BatchStage, BatchStatus, QCStatus
from app.models.company import Company
from app.models.md_classification import Grade, MineralGroup, MineralType
from app.models.md_commercial import (
    Application, CustomerSegment, HSCode, Incoterm, PaymentTerm, SubscriptionPlan,
)
from app.models.md_locations import MineSource, Region, Warehouse, WarehouseBin
from app.models.md_product import ProductMaster, ProductMasterApplication, ProductMasterPackaging
from app.models.md_quality import QualityParameter, QualitySpecification, TestMethod
from app.models.md_units import PackagingType, ParticleSize, UnitOfMeasure
from app.models.product import Product
from app.models.ui_translation import UITranslation
from app.models.content_page import ContentPage


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    type: str = "text"
    required: bool = False
    fk: str | None = None
    choices: tuple[str, ...] = ()
    help: str = ""
    readonly: bool = False       # shown, never written from the form (e.g. computed)
    col: int = 6                 # bootstrap column width in the form grid


@dataclass(frozen=True)
class Entity:
    key: str
    model: type
    title: str
    title_ar: str
    icon: str
    section: str
    description: str
    fields: tuple[Field, ...]
    list_fields: tuple[str, ...]
    search_fields: tuple[str, ...] = ("code", "name_en", "name_ar")
    natural_key: tuple[str, ...] = ("code",)
    order_by: tuple[str, ...] = ("sort_order", "code")
    has_active: bool = True
    hidden: bool = False          # FK source only, not listed/editable here
    label_attr: str | None = None  # attribute used as the FK dropdown label (default str(obj))
    detail_route: str | None = None  # custom page (e.g. batch QC) linked from the list
    audit_target: str = "master_data"


# Common master columns (MasterDataMixin) — prepended to every standard master.
def _std(*extra: Field, code_help: str = "") -> tuple[Field, ...]:
    return (
        Field("code", "Code", required=True, help=code_help or "Short unique business key, e.g. LIM-95.", col=3),
        Field("name_en", "Name (English)", required=True, col=5),
        Field("name_ar", "Name (Arabic)", col=4),
        *extra,
        Field("sort_order", "Sort order", "int", col=3),
        Field("is_active", "Active", "bool", col=3),
        Field("notes", "Notes", "textarea", col=12),
    )


SECTIONS = [
    ("classification", "Mineral Classification", "bi-diagram-3"),
    ("catalog", "Product Catalog", "bi-box-seam"),
    ("quality", "Quality & Specifications", "bi-clipboard2-check"),
    ("units", "Units & Packaging", "bi-rulers"),
    ("sources", "Sources & Logistics", "bi-geo-alt"),
    ("commercial", "Commercial & Regulatory", "bi-briefcase"),
    ("traceability", "Batch / Lot Traceability", "bi-upc-scan"),
    ("localization", "Localization & Content", "bi-translate"),
]

ENTITIES: list[Entity] = [
    # ---------------- Classification ----------------
    Entity("mineral-groups", MineralGroup, "Mineral Groups", "مجموعات المعادن", "bi-collection", "classification",
           "Top of the hierarchy: Industrial, Metallic, Construction, Processed, By-products.",
           _std(), ("code", "name_en", "name_ar", "is_active")),
    Entity("mineral-types", MineralType, "Mineral Types", "أنواع المعادن", "bi-gem", "classification",
           "Limestone, Silica Sand, Kaolin, Iron Ore … each under one group.",
           _std(Field("group_id", "Mineral group", "fk", required=True, fk="mineral-groups"),
                Field("chemical_formula", "Chemical formula", help="e.g. CaCO3")),
           ("code", "name_en", "group_id", "chemical_formula", "is_active")),
    Entity("grades", Grade, "Grades", "الدرجات", "bi-award", "classification",
           "Commercial specification per mineral type (PDF §6). Limits live in Quality Specifications.",
           _std(Field("mineral_type_id", "Mineral type", "fk", required=True, fk="mineral-types"),
                Field("application_id", "Main application", "fk", fk="applications"),
                Field("purity_min_pct", "Min purity (%)", "decimal", col=3),
                Field("quality_level", "Quality level", "choice", choices=("A", "B", "C"), col=3),
                Field("spec_version", "Spec version", col=3),
                Field("effective_date", "Effective date", "date", col=3)),
           ("code", "name_en", "mineral_type_id", "purity_min_pct", "quality_level", "spec_version", "is_active")),
    Entity("particle-sizes", ParticleSize, "Particle Sizes", "أحجام الحبيبات", "bi-grid-3x3-gap", "classification",
           "Mesh / micron / mm size classes (PDF §7).",
           _std(Field("mesh", "Mesh", "int", col=3), Field("micron_min", "Min (µm)", "decimal", col=3),
                Field("micron_max", "Max (µm)", "decimal", col=3), Field("d50_micron", "D50 (µm)", "decimal", col=3),
                Field("d90_micron", "D90 (µm)", "decimal", col=3)),
           ("code", "name_en", "mesh", "micron_min", "micron_max", "d50_micron", "is_active")),

    # ---------------- Catalog ----------------
    Entity("product-masters", ProductMaster, "Product Master", "بيانات المنتج الرئيسية", "bi-box-seam", "catalog",
           "The catalog item: Mineral → Grade → Particle size → UOM → regulatory flags (PDF §1, §3). "
           "Leave Code blank to auto-generate (e.g. MIN-CACO3-95-25UM).",
           (
               Field("code", "Product code", help="Blank = auto: MIN-<formula/type>-<grade>-<size>", col=3),
               Field("name_en", "Product name (English)", required=True, col=5),
               Field("name_ar", "Product name (Arabic)", col=4),
               Field("short_name", "Short name", col=3),
               Field("product_type", "Product type", "choice", required=True,
                     choices=("raw_material", "processed", "finished_product", "by_product"), col=3),
               Field("status", "Status", "choice", required=True, choices=("active", "inactive", "blocked", "discontinued"), col=3),
               Field("quality_class", "Quality class", "choice", choices=("A", "B", "C"), col=3),
               Field("mineral_type_id", "Mineral type", "fk", required=True, fk="mineral-types", col=4),
               Field("grade_id", "Grade", "fk", fk="grades", col=4),
               Field("particle_size_id", "Particle size", "fk", fk="particle-sizes", col=4),
               Field("chemical_formula", "Chemical formula", col=3),
               Field("color", "Color", col=3),
               Field("processing_method", "Processing method", col=6),
               Field("origin_country", "Country of origin (ISO-2)", col=3),
               Field("default_source_id", "Default mine / source", "fk", fk="mine-sources", col=5),
               Field("hs_code_id", "HS code", "fk", fk="hs-codes", col=4),
               Field("base_uom_id", "Base UOM", "fk", fk="uoms", col=4),
               Field("purchase_uom_id", "Purchase UOM", "fk", fk="uoms", col=4),
               Field("sales_uom_id", "Sales UOM", "fk", fk="uoms", col=4),
               Field("default_warehouse_id", "Default warehouse", "fk", fk="warehouses", col=4),
               Field("standard_cost", "Standard cost", "decimal", col=3),
               Field("selling_price", "Selling price", "decimal", col=3),
               Field("currency", "Currency", col=2),
               Field("bulk_density_t_m3", "Bulk density (t/m³)", "decimal", col=3),
               Field("loading_type", "Loading type", col=4),
               Field("transport_requirements", "Transport requirements", col=8),
               Field("hazard_class", "Hazard class", col=4),
               Field("is_sales_item", "Sales item", "bool", col=2),
               Field("is_purchase_item", "Purchase item", "bool", col=2),
               Field("is_inventory_item", "Inventory item", "bool", col=2),
               Field("batch_managed", "Batch managed", "bool", col=2),
               Field("coa_required", "COA required", "bool", col=2),
               Field("inspection_required", "Inspection required", "bool", col=2),
               Field("sds_required", "SDS required", "bool", col=2),
               Field("sort_order", "Sort order", "int", col=2),
               Field("is_active", "Active", "bool", col=2),
               Field("description", "Description", "textarea", col=12),
           ),
           ("code", "name_en", "mineral_type_id", "grade_id", "particle_size_id", "hs_code_id", "status"),
           search_fields=("code", "name_en", "name_ar", "short_name")),
    Entity("product-packagings", ProductMasterPackaging, "Product ↔ Packaging", "المنتج والتعبئة", "bi-bag", "catalog",
           "Which packaging each catalog product is sold in (PDF §8 — no duplicate products per pack size).",
           (Field("product_master_id", "Product", "fk", required=True, fk="product-masters"),
            Field("packaging_type_id", "Packaging", "fk", required=True, fk="packaging-types"),
            Field("is_default", "Default packaging", "bool", col=3)),
           ("product_master_id", "packaging_type_id", "is_default"),
           search_fields=(), natural_key=("product_master_id", "packaging_type_id"), order_by=("created_at",), has_active=False),
    Entity("product-applications", ProductMasterApplication, "Product ↔ Application", "المنتج والاستخدام", "bi-diagram-2", "catalog",
           "End uses of each catalog product (cement, glass, ceramics …).",
           (Field("product_master_id", "Product", "fk", required=True, fk="product-masters"),
            Field("application_id", "Application", "fk", required=True, fk="applications")),
           ("product_master_id", "application_id"),
           search_fields=(), natural_key=("product_master_id", "application_id"), order_by=("created_at",), has_active=False),

    # ---------------- Quality ----------------
    Entity("quality-parameters", QualityParameter, "Quality Parameters", "معايير الجودة", "bi-activity", "quality",
           "Chemical, physical and particle-size parameters (PDF §4, §5).",
           _std(Field("parameter_type", "Type", "choice", required=True, choices=("chemical", "physical", "particle_size"), col=3),
                Field("symbol", "Display symbol", col=3, help="e.g. SiO₂"),
                Field("default_uom_id", "Default unit", "fk", fk="uoms", col=3),
                Field("default_test_method_id", "Default test method", "fk", fk="test-methods"),
                Field("decimal_places", "Decimals", "int", col=3)),
           ("code", "name_en", "parameter_type", "symbol", "default_uom_id", "is_active")),
    Entity("test-methods", TestMethod, "Test Methods", "طرق الاختبار", "bi-eyedropper", "quality",
           "Laboratory tests / standards (Quality Test Master, PDF §13 #13).",
           _std(Field("standard_ref", "Standard reference", help="e.g. ASTM C25, ISO 13320"),
                Field("default_fee_sar", "Default fee (SAR)", "decimal", col=3),
                Field("turnaround_days", "Turnaround (days)", "int", col=3)),
           ("code", "name_en", "standard_ref", "default_fee_sar", "turnaround_days", "is_active")),
    Entity("specifications", QualitySpecification, "Quality Specifications", "مواصفات الجودة", "bi-clipboard2-check", "quality",
           "Acceptable min/max per parameter for a GRADE (default) or a specific PRODUCT (override). Set exactly one of the two.",
           (Field("grade_id", "Grade", "fk", fk="grades", col=4),
            Field("product_master_id", "…or Product (override)", "fk", fk="product-masters", col=4),
            Field("parameter_id", "Parameter", "fk", required=True, fk="quality-parameters", col=4),
            Field("min_value", "Min", "decimal", col=2), Field("max_value", "Max", "decimal", col=2),
            Field("target_value", "Target", "decimal", col=2),
            Field("uom_id", "Unit", "fk", fk="uoms", col=3),
            Field("test_method_id", "Test method", "fk", fk="test-methods", col=3),
            Field("is_mandatory", "Mandatory", "bool", col=2), Field("spec_version", "Version", col=2),
            Field("effective_date", "Effective date", "date", col=3), Field("is_active", "Active", "bool", col=2)),
           ("grade_id", "product_master_id", "parameter_id", "min_value", "max_value", "target_value", "uom_id", "is_mandatory"),
           search_fields=(), natural_key=("grade_id", "product_master_id", "parameter_id"), order_by=("created_at",)),

    # ---------------- Units & packaging ----------------
    Entity("uoms", UnitOfMeasure, "Units of Measure", "وحدات القياس", "bi-rulers", "units",
           "Conversion = factor to the base unit of the same type (mass base KG: MT = 1000).",
           _std(Field("uom_type", "Type", "choice", required=True,
                      choices=("mass", "volume", "length", "percentage", "density", "hardness", "count", "other"), col=3),
                Field("symbol", "Symbol", col=3), Field("factor_to_base", "Factor to base", "decimal", required=True, col=3),
                Field("is_base", "Base unit of its type", "bool", col=3)),
           ("code", "name_en", "uom_type", "symbol", "factor_to_base", "is_base", "is_active")),
    Entity("packaging-types", PackagingType, "Packaging Types", "أنواع التعبئة", "bi-bag", "units",
           "BULK, jumbo bags, PP bags, pallets (PDF §8).",
           _std(Field("capacity_value", "Capacity", "decimal", col=3), Field("capacity_uom_id", "Capacity unit", "fk", fk="uoms", col=3),
                Field("material", "Material", col=3), Field("is_bulk", "Bulk (unpacked)", "bool", col=3)),
           ("code", "name_en", "capacity_value", "capacity_uom_id", "is_bulk", "is_active")),

    # ---------------- Sources & logistics ----------------
    Entity("regions", Region, "Regions", "المناطق", "bi-map", "sources",
           "Saudi administrative regions.", _std(Field("country_code", "Country (ISO-2)", col=3)),
           ("code", "name_en", "name_ar", "is_active")),
    Entity("mine-sources", MineSource, "Mines / Quarries", "المناجم والمحاجر", "bi-minecart-loaded", "sources",
           "Source traceability (PDF §9). Licence = MIM mining licence reference.",
           _std(Field("mineral_type_id", "Main mineral", "fk", fk="mineral-types"),
                Field("region_id", "Region", "fk", fk="regions"),
                Field("owner_company_id", "Operator (platform company)", "fk", fk="companies"),
                Field("owner_name", "Owner name (if not on platform)"),
                Field("location", "Location"), Field("extraction_method", "Extraction method", "choice",
                      choices=("open_pit", "underground", "quarry", "placer", "processing_plant")),
                Field("latitude", "Latitude", "decimal", col=3), Field("longitude", "Longitude", "decimal", col=3),
                Field("license_number", "Licence no.", col=3), Field("license_expiry", "Licence expiry", "date", col=3),
                Field("country_of_origin", "Country of origin", col=3)),
           ("code", "name_en", "mineral_type_id", "region_id", "license_number", "license_expiry", "extraction_method", "is_active")),
    Entity("warehouses", Warehouse, "Warehouses", "المستودعات", "bi-building", "sources",
           "Storage locations (PDF §13 #16). National address = Saudi short address code.",
           _std(Field("company_id", "Owner company (blank = platform/3PL)", "fk", fk="companies"),
                Field("region_id", "Region", "fk", fk="regions"), Field("city", "City", col=3),
                Field("national_address", "National address", col=3), Field("address", "Address", col=6),
                Field("capacity_mt", "Capacity (MT)", "decimal", col=3)),
           ("code", "name_en", "region_id", "city", "company_id", "capacity_mt", "is_active")),
    Entity("warehouse-bins", WarehouseBin, "Warehouse Bins", "مواقع التخزين", "bi-grid", "sources",
           "Detailed location inside a warehouse (PDF §13 #17). Code is unique per warehouse.",
           (Field("warehouse_id", "Warehouse", "fk", required=True, fk="warehouses"),
            Field("code", "Bin code", required=True, col=3), Field("name_en", "Description", required=True),
            Field("capacity_mt", "Capacity (MT)", "decimal", col=3), Field("is_active", "Active", "bool", col=3)),
           ("warehouse_id", "code", "name_en", "capacity_mt", "is_active"),
           search_fields=("code", "name_en"), natural_key=("warehouse_id", "code"), order_by=("code",)),

    # ---------------- Commercial & regulatory ----------------
    Entity("applications", Application, "Applications", "الاستخدامات", "bi-diagram-2", "commercial",
           "End-use industries: cement, glass, ceramics, paint …", _std(), ("code", "name_en", "name_ar", "is_active")),
    Entity("customer-segments", CustomerSegment, "Customer Segments", "شرائح العملاء", "bi-people", "commercial",
           "Industry / customer classification.", _std(), ("code", "name_en", "name_ar", "is_active")),
    Entity("hs-codes", HSCode, "HS Codes (Regulatory)", "رموز النظام المنسق", "bi-upc", "commercial",
           "Customs / regulatory attributes (PDF §13 #20). Verify codes against the ZATCA integrated tariff before export use.",
           _std(Field("national_tariff_code", "Saudi tariff code", col=3), Field("customs_duty_pct", "Duty (%)", "decimal", col=3),
                Field("hazard_class", "Hazard class", col=3), Field("sds_required", "SDS required", "bool", col=3),
                Field("export_license_required", "Export licence required", "bool", col=3),
                code_help="HS heading, e.g. 2521.00"),
           ("code", "name_en", "national_tariff_code", "customs_duty_pct", "sds_required", "is_active")),
    Entity("incoterms", Incoterm, "Incoterms", "شروط التجارة الدولية", "bi-truck", "commercial",
           "ICC Incoterms® rules.", _std(Field("edition", "Edition", col=3)), ("code", "name_en", "edition", "is_active")),
    Entity("payment-terms", PaymentTerm, "Payment Terms", "شروط الدفع", "bi-calendar-check", "commercial",
           "Standard credit terms.", _std(Field("days", "Days", "int", required=True, col=3)), ("code", "name_en", "days", "is_active")),
    Entity("subscription-plans", SubscriptionPlan, "Subscription Plans", "خطط الاشتراك", "bi-stars", "commercial",
           "BRD §6.11 tiers. Code must be entry / mid / premium; names, prices and limits are yours to set. Blank limit = unlimited.",
           _std(Field("annual_price_sar", "Annual price (SAR)", "decimal", required=True, col=3),
                Field("max_active_listings", "Max active listings", "int", col=3),
                Field("max_active_rfqs", "Max active RFQs", "int", col=3),
                Field("search_priority", "Search priority", "int", col=3),
                Field("analytics_level", "Analytics", "choice", choices=("basic", "extended", "full"), col=3),
                Field("grace_period_days", "Grace period (days)", "int", col=3),
                Field("expedited_passport_review", "Expedited passport review", "bool", col=3),
                Field("priority_lab_scheduling", "Priority lab scheduling", "bool", col=3),
                Field("dedicated_support", "Dedicated support", "bool", col=3),
                code_help="entry | mid | premium"),
           ("code", "name_en", "annual_price_sar", "max_active_listings", "max_active_rfqs", "is_active")),

    # ---------------- Traceability ----------------
    Entity("batches", Batch, "Batches / Lots", "الدفعات", "bi-upc-scan", "traceability",
           "Lot traceability (PDF §9) with QC release (PDF §10). Leave batch number blank to auto-number (LOT-2026-00001). "
           "Open a batch's QC page to enter lab results and auto-evaluate PASS/FAIL.",
           (
               Field("batch_number", "Batch number", help="Blank = auto", col=3),
               Field("lot_number", "Lot number", col=3),
               Field("source_batch_ref", "Mine's batch ref", col=3),
               Field("stage", "Stage", "choice", required=True, choices=tuple(s.value for s in BatchStage), col=3),
               Field("product_master_id", "Product", "fk", required=True, fk="product-masters", col=6),
               Field("company_id", "Owner company", "fk", fk="companies", col=6),
               Field("mine_source_id", "Mine / source", "fk", fk="mine-sources", col=4),
               Field("parent_batch_id", "Parent batch", "fk", fk="batches", col=4),
               Field("listing_product_id", "Marketplace listing", "fk", fk="listings", col=4),
               Field("production_date", "Production date", "date", col=3),
               Field("quantity", "Quantity", "decimal", required=True, col=3),
               Field("uom_id", "Unit", "fk", fk="uoms", col=3),
               Field("warehouse_id", "Warehouse", "fk", fk="warehouses", col=3),
               Field("bin_id", "Bin", "fk", fk="warehouse-bins", col=3),
               Field("status", "Status", "choice", required=True, choices=tuple(s.value for s in BatchStatus), col=3),
               Field("qc_status", "QC status", "choice", choices=tuple(s.value for s in QCStatus), readonly=True, col=3),
               Field("notes", "Notes", "textarea", col=12),
           ),
           ("batch_number", "product_master_id", "stage", "quantity", "uom_id", "warehouse_id", "qc_status", "status"),
           search_fields=("batch_number", "lot_number", "source_batch_ref"), natural_key=("batch_number",),
           order_by=("created_at",), has_active=False, label_attr="batch_number", detail_route="admin_batch_qc"),
    Entity("batch-results", BatchQualityResult, "Batch Quality Results", "نتائج جودة الدفعات", "bi-clipboard-data", "traceability",
           "Measured values per batch. PASS/FAIL is computed automatically against the specification on save.",
           (Field("batch_id", "Batch", "fk", required=True, fk="batches", col=4),
            Field("parameter_id", "Parameter", "fk", required=True, fk="quality-parameters", col=4),
            Field("measured_value", "Measured value", "decimal", required=True, col=4),
            Field("test_method_id", "Test method", "fk", fk="test-methods", col=4),
            Field("tested_at", "Tested on", "date", col=4),
            Field("spec_min", "Spec min (auto)", "decimal", readonly=True, col=2),
            Field("spec_max", "Spec max (auto)", "decimal", readonly=True, col=2),
            Field("passed", "Passed (auto)", "bool", readonly=True, col=2)),
           ("batch_id", "parameter_id", "measured_value", "spec_min", "spec_max", "passed"),
           search_fields=(), natural_key=("batch_id", "parameter_id"), order_by=("created_at",), has_active=False),

    # ---------------- Localization (Batch R1) ----------------
    Entity("translations", UITranslation, "Arabic Translations", "الترجمة العربية", "bi-translate", "localization",
           "Every English phrase in the interface and its Arabic text. Arabic pages are translated from this list. "
           "Use {} for a changing value, e.g. \"Created {}.\" → \"تم إنشاء {}.\"",
           (Field("source_text", "English text", "textarea", required=True, col=6),
            Field("text_ar", "Arabic text", "textarea", required=True, col=6),
            Field("context", "Context", col=4, help="Optional: admin, seller, buyer, lab, status…"),
            Field("is_active", "Active", "bool", col=3)),
           ("source_text", "text_ar", "context", "is_active"),
           search_fields=("source_text", "text_ar", "context"), natural_key=("source_text",), order_by=("source_text",)),

    Entity("content-pages", ContentPage, "Content Pages", "صفحات المحتوى", "bi-file-richtext", "localization",
           "Privacy Notice, Terms of Use, Help — English and Arabic, shown at /privacy, /terms, /help and /pages/<slug>. "
           "Formatting: \"# \" heading, \"- \" bullet, blank line = new paragraph, **bold**, [link](/path). "
           "Raise the version when the privacy notice changes materially.",
           (Field("slug", "Slug (URL)", required=True, col=3, help="privacy, terms, help, …"),
            Field("title_en", "Title (English)", required=True, col=5), Field("title_ar", "Title (Arabic)", col=4),
            Field("body_en", "Body (English)", "textarea", required=True, col=12),
            Field("body_ar", "Body (Arabic)", "textarea", col=12),
            Field("version", "Version", col=3), Field("is_published", "Published", "bool", col=3)),
           ("slug", "title_en", "version", "is_published"),
           search_fields=("slug", "title_en", "title_ar"), natural_key=("slug",), order_by=("slug",), has_active=False),

    # ---------------- FK-only sources (not editable here) ----------------
    Entity("companies", Company, "Companies", "الشركات", "bi-building", "commercial", "", (), (),
           search_fields=("company_name",), natural_key=("cr_number",), order_by=("company_name",),
           has_active=False, hidden=True, label_attr="company_name"),
    Entity("listings", Product, "Marketplace listings", "الإعلانات", "bi-shop", "catalog", "", (), (),
           search_fields=("mineral_type",), natural_key=("id",), order_by=("created_at",),
           has_active=False, hidden=True, label_attr="mineral_type"),
]

BY_KEY: dict[str, Entity] = {e.key: e for e in ENTITIES}


def get_entity(key: str) -> Entity | None:
    e = BY_KEY.get(key)
    return None if e is None else e


def visible_entities() -> list[Entity]:
    return [e for e in ENTITIES if not e.hidden]
