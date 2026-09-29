"""
app/services/master_data/starter_data.py

Starter reference data, loaded through service.upsert_records() — the same
code path as a CSV import — so it is idempotent (upsert by natural key)
and safe to re-run: it never duplicates rows, and it overwrites only the
columns listed here (an admin's extra edits to other columns survive).

Sources:
  * Minerals_ERP_Master_Data.pdf — hierarchy (§2), limestone example
    product (§3), spec examples (§4, §10), physical parameters (§5),
    grades (§6), particle sizes (§7), packaging (§8), mine example (§9),
    batch/COA example LOT-2026-00125 (§11).
  * Saudi administrative regions (13), ICC Incoterms® 2020.
  * HS headings are the international 6-digit Harmonized System headings
    commonly used for these minerals — ILLUSTRATIVE ONLY. Confirm each
    against the ZATCA integrated customs tariff before using them on an
    export document.
  * Subscription plan prices/limits are PLACEHOLDERS for testing
    (BRD §6.11: pricing is a commercial decision) — edit them in the UI.
"""
from sqlalchemy.orm import Session

from app.services.master_data.registry import BY_KEY
from app.services.master_data.service import ImportResult, upsert_records


def _std(code, en, ar="", **extra):
    return {"code": code, "name_en": en, "name_ar": ar, **{k: str(v) for k, v in extra.items()}}


STARTER: list[tuple[str, list[dict]]] = [
    ("regions", [
        _std("RIY", "Riyadh", "الرياض", sort_order=1), _std("MKK", "Makkah", "مكة المكرمة", sort_order=2),
        _std("MDN", "Madinah", "المدينة المنورة", sort_order=3), _std("EST", "Eastern Province", "المنطقة الشرقية", sort_order=4),
        _std("QSM", "Al-Qassim", "القصيم", sort_order=5), _std("ASR", "Asir", "عسير", sort_order=6),
        _std("TBK", "Tabuk", "تبوك", sort_order=7), _std("HAL", "Hail", "حائل", sort_order=8),
        _std("NBR", "Northern Borders", "الحدود الشمالية", sort_order=9), _std("JZN", "Jazan", "جازان", sort_order=10),
        _std("NJN", "Najran", "نجران", sort_order=11), _std("BAH", "Al-Bahah", "الباحة", sort_order=12),
        _std("JOF", "Al-Jouf", "الجوف", sort_order=13),
    ]),
    ("uoms", [
        _std("KG", "Kilogram", "كيلوغرام", uom_type="mass", symbol="kg", factor_to_base=1, is_base="true", sort_order=1),
        _std("MT", "Metric tonne", "طن متري", uom_type="mass", symbol="t", factor_to_base=1000, sort_order=2),
        _std("G", "Gram", "غرام", uom_type="mass", symbol="g", factor_to_base="0.001", sort_order=3),
        _std("TON", "Short ton (US)", "طن قصير", uom_type="mass", symbol="ton", factor_to_base="907.18474", sort_order=4),
        _std("LB", "Pound", "رطل", uom_type="mass", symbol="lb", factor_to_base="0.45359237", sort_order=5),
        _std("M3", "Cubic metre", "متر مكعب", uom_type="volume", symbol="m³", factor_to_base=1, is_base="true", sort_order=10),
        _std("L", "Litre", "لتر", uom_type="volume", symbol="L", factor_to_base="0.001", sort_order=11),
        _std("MM", "Millimetre", "مليمتر", uom_type="length", symbol="mm", factor_to_base=1, is_base="true", sort_order=20),
        _std("UM", "Micrometre", "ميكرومتر", uom_type="length", symbol="µm", factor_to_base="0.001", sort_order=21),
        _std("PCT", "Percent", "نسبة مئوية", uom_type="percentage", symbol="%", factor_to_base=1, is_base="true", sort_order=30),
        _std("PPM", "Parts per million", "جزء في المليون", uom_type="percentage", symbol="ppm", factor_to_base="0.0001", sort_order=31),
        _std("GCM3", "Gram per cm³", "غرام/سم³", uom_type="density", symbol="g/cm³", factor_to_base=1, is_base="true", sort_order=40),
        _std("MOHS", "Mohs hardness", "صلادة موس", uom_type="hardness", symbol="Mohs", factor_to_base=1, is_base="true", sort_order=50),
        _std("MESH", "Mesh", "مش", uom_type="other", symbol="mesh", factor_to_base=1, sort_order=60),
        _std("PH", "pH", "الأس الهيدروجيني", uom_type="other", symbol="pH", factor_to_base=1, sort_order=61),
        _std("G100G", "g / 100 g", "غ/100غ", uom_type="other", symbol="g/100g", factor_to_base=1, sort_order=62),
        _std("EA", "Each", "وحدة", uom_type="count", symbol="ea", factor_to_base=1, is_base="true", sort_order=70),
    ]),
    ("applications", [
        _std("CEMENT", "Cement", "الأسمنت"), _std("GLASS", "Glass", "الزجاج"), _std("CERAMICS", "Ceramics", "السيراميك"),
        _std("PAINT", "Paint & coatings", "الدهانات"), _std("PLASTICS", "Plastics", "البلاستيك"), _std("PAPER", "Paper", "الورق"),
        _std("STEEL", "Steel & metallurgy", "الصلب والتعدين"), _std("CONSTRUCTION", "Construction", "البناء"),
        _std("AGRI", "Agriculture", "الزراعة"), _std("DRILLING", "Oil & gas drilling", "حفر النفط والغاز"),
        _std("WATER", "Water treatment", "معالجة المياه"),
    ]),
    ("customer-segments", [
        _std("CEM-MFR", "Cement manufacturer", "مصنع أسمنت"), _std("GLS-MFR", "Glass manufacturer", "مصنع زجاج"),
        _std("CER-MFR", "Ceramics manufacturer", "مصنع سيراميك"), _std("STL-MFR", "Steel producer", "منتج صلب"),
        _std("CONTRACTOR", "Construction contractor", "مقاول بناء"), _std("TRADER", "Trader / distributor", "تاجر / موزع"),
        _std("EXPORTER", "Exporter", "مصدر"), _std("GOV", "Government entity", "جهة حكومية"),
    ]),
    ("incoterms", [
        _std("EXW", "Ex Works", "تسليم أرض المصنع", sort_order=1), _std("FCA", "Free Carrier", "تسليم الناقل", sort_order=2),
        _std("CPT", "Carriage Paid To", "أجور النقل مدفوعة إلى", sort_order=3),
        _std("CIP", "Carriage and Insurance Paid To", "أجور النقل والتأمين مدفوعة إلى", sort_order=4),
        _std("DAP", "Delivered at Place", "التسليم في المكان", sort_order=5),
        _std("DPU", "Delivered at Place Unloaded", "التسليم في المكان مفرغة", sort_order=6),
        _std("DDP", "Delivered Duty Paid", "التسليم مع دفع الرسوم", sort_order=7),
        _std("FAS", "Free Alongside Ship", "التسليم بجانب السفينة", sort_order=8),
        _std("FOB", "Free on Board", "التسليم على ظهر السفينة", sort_order=9),
        _std("CFR", "Cost and Freight", "التكلفة والشحن", sort_order=10),
        _std("CIF", "Cost, Insurance and Freight", "التكلفة والتأمين والشحن", sort_order=11),
    ]),
    ("payment-terms", [
        _std("CIA", "Cash in advance", "الدفع المسبق", days=0, sort_order=1), _std("NET15", "Net 15 days", "صافي 15 يوم", days=15, sort_order=2),
        _std("NET30", "Net 30 days", "صافي 30 يوم", days=30, sort_order=3), _std("NET60", "Net 60 days", "صافي 60 يوم", days=60, sort_order=4),
        _std("NET90", "Net 90 days", "صافي 90 يوم", days=90, sort_order=5), _std("LC", "Letter of credit", "اعتماد مستندي", days=0, sort_order=6),
    ]),
    ("hs-codes", [
        _std("2521.00", "Limestone flux; limestone for lime/cement", "حجر الجير", sds_required="false"),
        _std("2505.10", "Silica sands and quartz sands", "رمال السيليكا", sds_required="true"),
        _std("2505.90", "Natural sands (other)", "رمال طبيعية أخرى"),
        _std("2507.00", "Kaolin and other kaolinic clays", "الكاولين"),
        _std("2508.10", "Bentonite", "البنتونايت"),
        _std("2518.10", "Dolomite, not calcined", "الدولوميت"),
        _std("2529.10", "Feldspar", "الفلسبار"),
        _std("2517.10", "Pebbles, gravel, crushed stone", "الحصى والحجر المكسر"),
        _std("2517.41", "Marble granules, chippings and powder", "مسحوق الرخام"),
        _std("2836.50", "Calcium carbonate (precipitated)", "كربونات الكالسيوم المرسبة"),
        _std("2601.11", "Iron ores, non-agglomerated", "خامات الحديد"),
        _std("2603.00", "Copper ores and concentrates", "خامات النحاس"),
        _std("2602.00", "Manganese ores and concentrates", "خامات المنغنيز"),
        _std("2610.00", "Chromium ores and concentrates", "خامات الكروم"),
    ]),
    ("mineral-groups", [
        _std("IND", "Industrial Minerals", "المعادن الصناعية", sort_order=1),
        _std("MET", "Metallic Minerals", "المعادن الفلزية", sort_order=2),
        _std("CON", "Construction Minerals", "معادن البناء", sort_order=3),
        _std("PRC", "Processed Minerals", "المعادن المعالجة", sort_order=4),
        _std("BYP", "By-Products / Waste", "المنتجات الثانوية", sort_order=5),
    ]),
    ("mineral-types", [
        _std("LIM", "Limestone", "الحجر الجيري", group_id="IND", chemical_formula="CaCO3"),
        _std("DOL", "Dolomite", "الدولوميت", group_id="IND", chemical_formula="CaMg(CO3)2"),
        _std("SIL", "Silica Sand", "رمل السيليكا", group_id="IND", chemical_formula="SiO2"),
        _std("FEL", "Feldspar", "الفلسبار", group_id="IND"),
        _std("KAO", "Kaolin", "الكاولين", group_id="IND", chemical_formula="Al2Si2O5(OH)4"),
        _std("BEN", "Bentonite", "البنتونايت", group_id="IND"),
        _std("FEO", "Iron Ore", "خام الحديد", group_id="MET", chemical_formula="Fe2O3"),
        _std("CUO", "Copper Ore", "خام النحاس", group_id="MET"),
        _std("MNO", "Manganese Ore", "خام المنغنيز", group_id="MET"),
        _std("CHR", "Chromite", "الكروميت", group_id="MET", chemical_formula="FeCr2O4"),
        _std("AGG", "Aggregate", "الركام", group_id="CON"),
        _std("GRV", "Gravel", "الحصى", group_id="CON"),
        _std("CRS", "Crushed Stone", "الحجر المكسر", group_id="CON"),
        _std("SND", "Sand", "الرمل", group_id="CON"),
        _std("GCC", "Ground Calcium Carbonate", "كربونات الكالسيوم المطحونة", group_id="PRC", chemical_formula="CaCO3"),
        _std("PCC", "Precipitated Calcium Carbonate", "كربونات الكالسيوم المرسبة", group_id="PRC", chemical_formula="CaCO3"),
        _std("MLS", "Micronized Limestone", "الحجر الجيري الميكروني", group_id="PRC", chemical_formula="CaCO3"),
        _std("PSI", "Processed Silica", "السيليكا المعالجة", group_id="PRC", chemical_formula="SiO2"),
        _std("FIN", "Mineral Fines", "الناعم المعدني", group_id="BYP"),
        _std("DST", "Dust", "الغبار", group_id="BYP"),
    ]),
    ("test-methods", [
        _std("XRF", "X-ray fluorescence (XRF) chemical analysis", "تحليل الأشعة السينية الفلورية", standard_ref="ISO 12677", turnaround_days=3),
        _std("ASTM-C25", "Chemical analysis of limestone, quicklime and hydrated lime", "التحليل الكيميائي للحجر الجيري", standard_ref="ASTM C25", turnaround_days=5),
        _std("LOD-105", "Moisture — oven drying at 105 °C", "الرطوبة - التجفيف عند 105", standard_ref="ISO 787-2", turnaround_days=1),
        _std("LASER-PSD", "Particle size — laser diffraction", "حجم الحبيبات - حيود الليزر", standard_ref="ISO 13320", turnaround_days=2),
        _std("SIEVE", "Particle size — sieve analysis", "التحليل بالمناخل", standard_ref="ASTM C136", turnaround_days=2),
        _std("WHITENESS", "Whiteness / brightness (colorimetry)", "درجة البياض", standard_ref="Colorimeter", turnaround_days=1),
        _std("BULK-DENS", "Bulk / tamped density", "الكثافة الظاهرية", standard_ref="ISO 787-11", turnaround_days=1),
        _std("PH-SUSP", "pH of aqueous suspension", "الأس الهيدروجيني للمعلق", standard_ref="ISO 787-9", turnaround_days=1),
        _std("OIL-ABS", "Oil absorption value", "امتصاص الزيت", standard_ref="ISO 787-5", turnaround_days=1),
    ]),
    ("quality-parameters", [
        _std("CACO3", "Calcium carbonate", "كربونات الكالسيوم", parameter_type="chemical", symbol="CaCO₃", default_uom_id="PCT", default_test_method_id="XRF"),
        _std("SIO2", "Silica", "السيليكا", parameter_type="chemical", symbol="SiO₂", default_uom_id="PCT", default_test_method_id="XRF"),
        _std("AL2O3", "Alumina", "الألومينا", parameter_type="chemical", symbol="Al₂O₃", default_uom_id="PCT", default_test_method_id="XRF"),
        _std("FE2O3", "Iron oxide", "أكسيد الحديد", parameter_type="chemical", symbol="Fe₂O₃", default_uom_id="PCT", default_test_method_id="XRF"),
        _std("CAO", "Calcium oxide", "أكسيد الكالسيوم", parameter_type="chemical", symbol="CaO", default_uom_id="PCT", default_test_method_id="XRF"),
        _std("MGO", "Magnesium oxide", "أكسيد المغنيسيوم", parameter_type="chemical", symbol="MgO", default_uom_id="PCT", default_test_method_id="XRF"),
        _std("TIO2", "Titanium dioxide", "ثاني أكسيد التيتانيوم", parameter_type="chemical", symbol="TiO₂", default_uom_id="PCT", default_test_method_id="XRF"),
        _std("LOI", "Loss on ignition", "الفقد بالحرق", parameter_type="chemical", symbol="LOI", default_uom_id="PCT", default_test_method_id="ASTM-C25"),
        _std("MOISTURE", "Moisture", "الرطوبة", parameter_type="physical", symbol="H₂O", default_uom_id="PCT", default_test_method_id="LOD-105"),
        _std("WHITENESS", "Whiteness", "البياض", parameter_type="physical", symbol="W", default_uom_id="PCT", default_test_method_id="WHITENESS"),
        _std("BULK-DENS", "Bulk density", "الكثافة الظاهرية", parameter_type="physical", symbol="ρb", default_uom_id="GCM3", default_test_method_id="BULK-DENS"),
        _std("SG", "Specific gravity", "الوزن النوعي", parameter_type="physical", symbol="SG", default_uom_id="GCM3"),
        _std("HARDNESS", "Hardness", "الصلادة", parameter_type="physical", symbol="Mohs", default_uom_id="MOHS"),
        _std("PH", "pH", "الأس الهيدروجيني", parameter_type="physical", symbol="pH", default_uom_id="PH", default_test_method_id="PH-SUSP"),
        _std("OIL-ABS", "Oil absorption", "امتصاص الزيت", parameter_type="physical", symbol="OA", default_uom_id="G100G", default_test_method_id="OIL-ABS"),
        _std("PSIZE-MAX", "Top particle size", "أكبر حجم حبيبي", parameter_type="particle_size", symbol="Dmax", default_uom_id="MM", default_test_method_id="SIEVE"),
        _std("D50", "Median particle size D50", "الحجم الوسيط D50", parameter_type="particle_size", symbol="D50", default_uom_id="UM", default_test_method_id="LASER-PSD"),
        _std("D90", "Particle size D90", "الحجم D90", parameter_type="particle_size", symbol="D90", default_uom_id="UM", default_test_method_id="LASER-PSD"),
        _std("MESH", "Mesh size", "رقم المنخل", parameter_type="particle_size", symbol="mesh", default_uom_id="MESH", default_test_method_id="SIEVE"),
    ]),
    ("particle-sizes", [
        _std("PS-0-5MM", "0–5 mm", "0-5 مم", micron_min=0, micron_max=5000, sort_order=1),
        _std("PS-10UM", "10 µm", "10 ميكرون", d50_micron=10, sort_order=2),
        _std("PS-20UM", "20 µm", "20 ميكرون", d50_micron=20, sort_order=3),
        _std("PS-25UM", "25 µm", "25 ميكرون", d50_micron=25, d90_micron=45, sort_order=4),
        _std("PS-45UM", "45 µm (325 mesh)", "45 ميكرون", mesh=325, micron_max=45, sort_order=5),
        _std("PS-75UM", "75 µm (200 mesh)", "75 ميكرون", mesh=200, micron_max=75, sort_order=6),
    ]),
    ("packaging-types", [
        _std("BULK", "Bulk truck", "شاحنة سائبة", capacity_value=25, capacity_uom_id="MT", is_bulk="true", sort_order=1),
        _std("BB-1000", "Jumbo bag", "كيس جامبو", capacity_value=1, capacity_uom_id="MT", material="PP woven", sort_order=2),
        _std("BAG-25", "PP bag 25 kg", "كيس 25 كغ", capacity_value=25, capacity_uom_id="KG", material="PP", sort_order=3),
        _std("BAG-50", "PP bag 50 kg", "كيس 50 كغ", capacity_value=50, capacity_uom_id="KG", material="PP", sort_order=4),
        _std("PALLET", "Palletized bags", "أكياس على منصات", capacity_value=1, capacity_uom_id="MT", sort_order=5),
        _std("DRUM", "Drum", "برميل", capacity_value=200, capacity_uom_id="KG", material="Steel/HDPE", sort_order=6),
    ]),
    ("grades", [
        _std("LIM-90", "Limestone 90", "حجر جيري 90", mineral_type_id="LIM", purity_min_pct=90, quality_level="C", spec_version="V1.0", effective_date="2026-01-01", application_id="CEMENT"),
        _std("LIM-95", "Limestone 95", "حجر جيري 95", mineral_type_id="LIM", purity_min_pct=95, quality_level="A", spec_version="V1.0", effective_date="2026-01-01", application_id="CEMENT"),
        _std("LIM-97", "Limestone 97", "حجر جيري 97", mineral_type_id="LIM", purity_min_pct=97, quality_level="A", spec_version="V1.0", effective_date="2026-01-01"),
        _std("LIM-99", "Limestone 99", "حجر جيري 99", mineral_type_id="LIM", purity_min_pct=99, quality_level="A", spec_version="V1.0", effective_date="2026-01-01"),
        _std("SIL-FDY", "Silica Sand — Foundry Grade", "رمل سيليكا - درجة المسابك", mineral_type_id="SIL", quality_level="B", spec_version="V1.0"),
        _std("SIL-GLS", "Silica Sand — Glass Grade", "رمل سيليكا - درجة الزجاج", mineral_type_id="SIL", purity_min_pct=98, quality_level="A", spec_version="V1.0", application_id="GLASS"),
        _std("SIL-CON", "Silica Sand — Construction Grade", "رمل سيليكا - درجة البناء", mineral_type_id="SIL", quality_level="C", spec_version="V1.0", application_id="CONSTRUCTION"),
        _std("SIL-IND", "Silica Sand — Industrial Grade", "رمل سيليكا - درجة صناعية", mineral_type_id="SIL", quality_level="B", spec_version="V1.0"),
        _std("KAO-CER", "Kaolin — Ceramic Grade", "كاولين - درجة السيراميك", mineral_type_id="KAO", quality_level="A", spec_version="V1.0", application_id="CERAMICS"),
        _std("GCC-95", "Calcium Carbonate 95", "كربونات الكالسيوم 95", mineral_type_id="GCC", purity_min_pct=95, quality_level="A", spec_version="V1.0", application_id="PAINT"),
    ]),
    ("specifications", [
        # PDF §4 / §10 — Limestone 95
        {"grade_id": "LIM-95", "parameter_id": "CACO3", "min_value": "95", "max_value": "99", "target_value": "97", "uom_id": "PCT", "test_method_id": "XRF", "is_mandatory": "true"},
        {"grade_id": "LIM-95", "parameter_id": "SIO2", "min_value": "0", "max_value": "2", "uom_id": "PCT", "test_method_id": "XRF", "is_mandatory": "true"},
        {"grade_id": "LIM-95", "parameter_id": "MGO", "min_value": "0", "max_value": "1.5", "uom_id": "PCT", "test_method_id": "XRF", "is_mandatory": "true"},
        {"grade_id": "LIM-95", "parameter_id": "FE2O3", "min_value": "0", "max_value": "0.5", "uom_id": "PCT", "test_method_id": "XRF", "is_mandatory": "true"},
        {"grade_id": "LIM-95", "parameter_id": "MOISTURE", "min_value": "0", "max_value": "1", "uom_id": "PCT", "test_method_id": "LOD-105", "is_mandatory": "true"},
        {"grade_id": "LIM-95", "parameter_id": "PSIZE-MAX", "min_value": "0", "max_value": "5", "uom_id": "MM", "test_method_id": "SIEVE", "is_mandatory": "false"},
        {"grade_id": "LIM-95", "parameter_id": "WHITENESS", "min_value": "90", "uom_id": "PCT", "test_method_id": "WHITENESS", "is_mandatory": "false"},
        # PDF §4 — Silica sand (glass) and Kaolin
        {"grade_id": "SIL-GLS", "parameter_id": "SIO2", "min_value": "98", "max_value": "99.8", "uom_id": "PCT", "test_method_id": "XRF", "is_mandatory": "true"},
        {"grade_id": "SIL-GLS", "parameter_id": "FE2O3", "min_value": "0", "max_value": "0.05", "uom_id": "PCT", "test_method_id": "XRF", "is_mandatory": "true"},
        {"grade_id": "KAO-CER", "parameter_id": "AL2O3", "min_value": "35", "max_value": "40", "uom_id": "PCT", "test_method_id": "XRF", "is_mandatory": "true"},
        {"grade_id": "KAO-CER", "parameter_id": "FE2O3", "min_value": "0", "max_value": "1.5", "uom_id": "PCT", "test_method_id": "XRF", "is_mandatory": "true"},
        # PDF §5 — physical example for calcium carbonate 95
        {"grade_id": "GCC-95", "parameter_id": "CACO3", "min_value": "95", "uom_id": "PCT", "test_method_id": "XRF", "is_mandatory": "true"},
        {"grade_id": "GCC-95", "parameter_id": "MOISTURE", "max_value": "1", "uom_id": "PCT", "test_method_id": "LOD-105", "is_mandatory": "true"},
        {"grade_id": "GCC-95", "parameter_id": "D50", "min_value": "20", "max_value": "30", "target_value": "25", "uom_id": "UM", "test_method_id": "LASER-PSD", "is_mandatory": "true"},
        {"grade_id": "GCC-95", "parameter_id": "D90", "max_value": "45", "uom_id": "UM", "test_method_id": "LASER-PSD", "is_mandatory": "false"},
        {"grade_id": "GCC-95", "parameter_id": "WHITENESS", "min_value": "90", "uom_id": "PCT", "test_method_id": "WHITENESS", "is_mandatory": "true"},
        {"grade_id": "GCC-95", "parameter_id": "BULK-DENS", "min_value": "1.2", "max_value": "1.5", "uom_id": "GCM3", "test_method_id": "BULK-DENS", "is_mandatory": "false"},
        {"grade_id": "GCC-95", "parameter_id": "OIL-ABS", "max_value": "20", "uom_id": "G100G", "test_method_id": "OIL-ABS", "is_mandatory": "false"},
        {"grade_id": "GCC-95", "parameter_id": "PH", "min_value": "8", "max_value": "9", "uom_id": "PH", "test_method_id": "PH-SUSP", "is_mandatory": "false"},
    ]),
    ("mine-sources", [
        _std("MINE-001", "Quarry A", "المحجر أ", mineral_type_id="LIM", region_id="RIY", location="Riyadh region",
             license_number="XXXXX", extraction_method="open_pit", country_of_origin="SA", owner_name="(set operator company)"),
    ]),
    ("warehouses", [
        _std("WH-RUH-01", "Riyadh 2nd Industrial City yard", "ساحة المدينة الصناعية الثانية بالرياض", region_id="RIY", city="Riyadh", capacity_mt=20000),
        _std("WH-DMM-01", "Dammam port logistics yard", "ساحة ميناء الدمام", region_id="EST", city="Dammam", capacity_mt=50000),
    ]),
    ("warehouse-bins", [
        {"warehouse_id": "WH-RUH-01", "code": "A-01", "name_en": "Open stockpile A-01", "capacity_mt": "5000"},
        {"warehouse_id": "WH-RUH-01", "code": "B-01", "name_en": "Covered bay B-01 (bagged)", "capacity_mt": "1500"},
        {"warehouse_id": "WH-DMM-01", "code": "EXP-01", "name_en": "Export staging EXP-01", "capacity_mt": "10000"},
    ]),
    ("product-masters", [
        {"code": "MIN-LIM-001", "name_en": "Limestone 95% CaCO₃", "name_ar": "حجر جيري 95% كربونات كالسيوم", "short_name": "LIM95",
         "product_type": "raw_material", "status": "active", "quality_class": "A", "mineral_type_id": "LIM", "grade_id": "LIM-95",
         "particle_size_id": "PS-0-5MM", "chemical_formula": "CaCO3", "color": "White", "origin_country": "SA",
         "default_source_id": "MINE-001", "hs_code_id": "2521.00", "base_uom_id": "MT", "purchase_uom_id": "MT", "sales_uom_id": "MT",
         "default_warehouse_id": "WH-RUH-01", "is_sales_item": "true", "is_purchase_item": "true", "is_inventory_item": "true",
         "batch_managed": "true", "coa_required": "true", "inspection_required": "true", "sds_required": "false", "currency": "SAR"},
        {"code": "MIN-CACO3-95-25UM", "name_en": "Calcium Carbonate 95% – 25 µm", "name_ar": "كربونات الكالسيوم 95% - 25 ميكرون",
         "product_type": "processed", "status": "active", "quality_class": "A", "mineral_type_id": "GCC", "grade_id": "GCC-95",
         "particle_size_id": "PS-25UM", "chemical_formula": "CaCO3", "color": "White", "origin_country": "SA", "hs_code_id": "2517.41",
         "base_uom_id": "MT", "purchase_uom_id": "MT", "sales_uom_id": "MT", "processing_method": "Dry grinding and air classification",
         "batch_managed": "true", "coa_required": "true", "inspection_required": "true", "currency": "SAR"},
        {"code": "MIN-SIO2-GLS", "name_en": "Silica Sand — Glass Grade", "name_ar": "رمل سيليكا - درجة الزجاج",
         "product_type": "raw_material", "status": "active", "mineral_type_id": "SIL", "grade_id": "SIL-GLS", "chemical_formula": "SiO2",
         "origin_country": "SA", "hs_code_id": "2505.10", "base_uom_id": "MT", "sales_uom_id": "MT", "purchase_uom_id": "MT",
         "sds_required": "true", "currency": "SAR"},
        {"code": "MIN-KAO-CER", "name_en": "Kaolin — Ceramic Grade", "name_ar": "كاولين - درجة السيراميك",
         "product_type": "raw_material", "status": "active", "mineral_type_id": "KAO", "grade_id": "KAO-CER",
         "origin_country": "SA", "hs_code_id": "2507.00", "base_uom_id": "MT", "sales_uom_id": "MT", "purchase_uom_id": "MT", "currency": "SAR"},
    ]),
    ("product-packagings", [
        {"product_master_id": "MIN-CACO3-95-25UM", "packaging_type_id": p, "is_default": "true" if p == "BULK" else "false"}
        for p in ("BULK", "BB-1000", "BAG-25", "BAG-50")
    ] + [{"product_master_id": "MIN-LIM-001", "packaging_type_id": "BULK", "is_default": "true"}]),
    ("product-applications", [
        {"product_master_id": "MIN-LIM-001", "application_id": "CEMENT"},
        {"product_master_id": "MIN-CACO3-95-25UM", "application_id": "PAINT"},
        {"product_master_id": "MIN-CACO3-95-25UM", "application_id": "PLASTICS"},
        {"product_master_id": "MIN-SIO2-GLS", "application_id": "GLASS"},
        {"product_master_id": "MIN-KAO-CER", "application_id": "CERAMICS"},
    ]),
    ("subscription-plans", [
        _std("entry", "Bronze", "برونزي", annual_price_sar=0, max_active_listings=5, max_active_rfqs=5, search_priority=0,
             analytics_level="basic", grace_period_days=14, sort_order=1),
        _std("mid", "Silver", "فضي", annual_price_sar=0, max_active_listings=25, max_active_rfqs=25, search_priority=1,
             analytics_level="extended", grace_period_days=14, sort_order=2),
        _std("premium", "Gold", "ذهبي", annual_price_sar=0, search_priority=2, analytics_level="full", grace_period_days=30,
             expedited_passport_review="true", priority_lab_scheduling="true", dedicated_support="true", sort_order=3),
    ]),
    # PDF §11 example batch: LOT-2026-00125, Limestone Industrial 95, produced 20-Sep-2026, Quarry A
    ("batches", [
        {"batch_number": "LOT-2026-00125", "product_master_id": "MIN-LIM-001", "stage": "finished", "mine_source_id": "MINE-001",
         "production_date": "2026-09-20", "quantity": "500", "uom_id": "MT", "warehouse_id": "WH-RUH-01",
         "bin_id": "WH-RUH-01/A-01", "status": "quarantine", "notes": "Example batch from ERP Master Data PDF §11"},
    ]),
    ("batch-results", [
        {"batch_id": "LOT-2026-00125", "parameter_id": p, "measured_value": v, "tested_at": "2026-09-22"}
        for p, v in (("CACO3", "96.8"), ("SIO2", "1.2"), ("MGO", "0.8"), ("FE2O3", "0.22"), ("MOISTURE", "0.65"), ("PSIZE-MAX", "4"))
    ]),
]


from app.services.master_data.starter_content import CONTENT_PAGES  # noqa: E402

STARTER.append(("content-pages", CONTENT_PAGES))


def load_starter_data(db: Session, actor=None) -> dict[str, ImportResult]:
    results = {}
    for key, records in STARTER:
        results[key] = upsert_records(db, BY_KEY[key], records, actor)
    # Batch R1: Arabic UI catalog — adds missing phrases, never overwrites admin edits
    from app.services.master_data.i18n import load_catalog
    results["translations"] = load_catalog(db)
    return results
