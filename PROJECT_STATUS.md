# Minerals Chain — Project Status

This file tracks what's done, what's in progress, and what's next.
`temp.txt` is the structural reference (folders/files only); this is
where the "is it actually finished, and what did we decide along the
way" content lives.

---

## PHASE 1 — Core Foundation: ✅ COMPLETE
Registration/login/2FA/lockout, admin approval workflow, seller
listing CRUD, lab verification, Mineral Passport, admin oversight
(companies/users/passports), profile management, notifications.

## PHASE 2 — Marketplace Trading Engine: ✅ COMPLETE
Buyer browse (identity-concealed) → RFQ creation → seller quotations
→ order lifecycle with identity reveal on seller confirmation (BRD
§6.6). The full BRD §6.5–6.6 trading loop is built and tested
end-to-end, including the two-competing-sellers identity-isolation
scenario.

## Cross-cutting work (post-Phase-2, lettered batches A/B/C/...)

| Batch | Scope | Status |
|---|---|---|
| A | Schema evolution: VAT Registration Number, real Subscription table, `Certificate`+`MineralPassport` consolidated into a generalized `Certification`+`CertificationScope` pair, email service (console/SMTP dual-mode) | ✅ Done |
| B | Registration overhaul: mandatory CR + licence documents (all roles), phone country-code picker, email OTP gating final submission | ✅ Done |
| C | Localization: AR/EN language switcher (actually wired up — it wasn't before), RTL layout, global chrome + auth pages translated | ✅ Done |
| D | Personalization page — port the real InvestmentUX theme JS (current widget is a non-functional mockup) | ✅ Done |
| E | Dashboard redesign (seller/buyer/lab) in the InvestmentUX visual pattern | ✅ Done |
| F | Visual polish: company detail page background, multi-color data styling, profile picture card | ✅ Done |
| G | Security & user management: CSRF tokens, cookie `secure` flag, login/OTP rate-limiting, expanded audit log coverage | ✅ Done |
| H | RTL layout fix, personalize page rewiring, phone country flags, user-detail redesign, admin audit-log viewer, per-role registration toggle + OTP dev-mode toggle | ✅ Done |
| H-fix | Restored 4 files that never landed on the dev machine after Batch H (`app.core.portal_nav` etc. `ModuleNotFoundError`s), + new testing tooling: `scripts/seed_test_data.py`, `scripts/check_routes.py`, `tests_selenium/` | ✅ Done |
| I | ERP Master Data (all 20 masters from Minerals_ERP_Master_Data.pdf): mineral group/type/grade, specs, parameters, test methods, particle size, UOM, packaging, mines, warehouses/bins, applications, segments, HS codes, incoterms, payment terms, subscription plans, Product Master catalog, Batch/Lot + QC gate; generic `/admin/master-data` engine with CSV import/export + starter data | ✅ Done |
| J | Schema V1 alignment (Minerals_DB_Schema_V1): bilingual/regulatory company fields, user profile fields, listing↔catalog link, product/RFQ specs, COA results, lab/passport fees, business references, frozen order financials + VAT, reveal log, settlement fees, order documents, bilingual notifications | ✅ Done |
| K | Admin Control Center: typed system settings (fees, VAT, policies, numbering, security, dev tools), security checklist, company edit/suspend, user creation, impersonation, order override console, fee ledger, admin-2FA enforcement, private document storage, security headers, subscription limits | ✅ Done |

## BRD completion release (this delivery) — see docs/BRD_COVERAGE.md

| Batch | Scope | Status |
|---|---|---|
| R1 | One language button → language + RTL/LTR together (server-driven, theme switch captured); Arabic UI catalogue (1,600+ phrases, `app/services/master_data/i18n/*.tsv`, admin-editable); chart labels translated; test banner off by default | ✅ Done |
| Q1 | Admin permission levels (super_admin / operations / finance / compliance / support), users list with filters + bulk actions, admin "New company", PDPL consent + privacy centre + data-subject request queue + anonymisation, public Privacy/Terms/Help pages (admin-editable content) | ✅ Done |
| M6 | Real bilingual notifications (bell, page, deep links, admin alerts by area) | ✅ Done |
| M4 | Subscription lifecycle: plan page, upgrade/downgrade rules, renew, grace → expire → downgrade, charges with VAT, admin subscriptions + charges | ✅ Done |
| M1 | Disputes: raise with evidence (SHA-256), thread, internal notes, withdraw, admin status/assign, immutable decision, logged correction, order RESOLVED + completed_via_dispute | ✅ Done |
| M2 | Lab workflow: schedule → testing → per-parameter results → auto PASS/FAIL → COA with fingerprint + printable view; `/lab/certificates`; Admin → Lab Partners (fee, turnaround, accreditation, pause, preferred); premium priority | ✅ Done |
| M3 | Seller spec editor (catalogue pre-fill), specs required before verification, buyer browse with specs + COA results + passport badges + plan-priority ordering, structured RFQ, spec match score, quote revision/expiry, comparison table, RFQ cancel, Admin → Products (suspend/reactivate) + Admin → RFQs, passport renewal (expedited for premium) | ✅ Done |
| P1 | Order documents (upload after reveal, share toggle, integrity-checked download), commercial invoice (INV-, not ZATCA), INVOICED step, order progress stepper | ✅ Done |
| R2 | Visual Control Center (ECharts: KPIs, combo, donuts, stacked bars, gauge), Admin → Reports (revenue streams, normal vs dispute orders, disputes, lab pass rates, top minerals, CSV) | ✅ Done |
| D | `scripts/generate_demo_data.py` — 100+ records per module over 12 months, every password `admin123` | ✅ Done |

## Pending by decision

| Batch | Scope | Status |
|---|---|---|
| L | ZATCA Fatoora Phase 2 e-invoicing (clearance/reporting, QR, hash chain, CSID, credit notes) | ⏸ Later — needs tax-advisor decision on invoice issuer |
| N | Payment gateway (SAMA-licensed: mada / Apple Pay / SADAD), subscription billing | ⏸ Later |
| O | Inventory ledger, Odoo/SAP B1 export | ⬜ |
| Q | Infra hardening before go-live: encryption at rest, backups, Redis rate limiting, strict CSP, pen test | ⬜ Before go-live |
| R | Wathq CR / MIM licence API checks (BRD §13: future enhancement), native mobile | ⬜ |

## PHASE 3 — Payments & Compliance: 🟡 FOUNDATIONS LAID (Batches J/K: VAT snapshot, settlement fees, references)
ZATCA e-invoicing, escrow/settlement, subscription billing
enforcement, disputes, audit logging expansion.

## PHASE 4 — Scale & Optimization: ⬜ NOT STARTED
Inventory management, logistics/shipping, document management,
advanced reporting, admin monitoring, mobile responsiveness pass.


## Known cleanup pending (low priority, doesn't block anything)
- Delete `app/modules/seller/routes_old.py` (stray unused duplicate)
- Delete legacy `app/models/certificate.py`, `app/models/passport.py`, `app/services/passport_service.py` (pre-Batch-A, no longer imported)
- ~~Wire `users.last_login_at`~~ — done in Batch K
- Pre-existing autogenerate drift on `users.email` (unique constraint vs unique index) — cosmetic, reconcile in a later migration
- Delete `app/static/uploads/company_documents/` after running Control Center → "Secure legacy uploads"

## Deliberate scope boundaries
Noted here so they don't get re-litigated by accident — these are
considered decisions, not oversights:

- Email is not editable from `/my-profile` or `/admin/users`
- Company role is not editable anywhere after registration
- ~~Passport validity period hardcoded~~ — now System Settings → Policies (Batch K)
- No 2FA backup codes — recovery path is admin disabling 2FA for a
  locked-out user
- Buyer browse search is mineral-type match only, no other filters
- RFQ inbox is a broadcast feed, not an automated matching engine
- No RFQ cancellation (enum has room for it when needed)
- No quotation revision — one shot per seller per RFQ
- No "verification status" comparison column on quotations (quotations
  respond to a general RFQ, not one specific listing — no clean 1:1
  mapping to attach a meaningful signal to)
- No "invoiced" order status — real invoicing is Phase 3; 5 stages
  instead of BRD's example 6
- No seller "reject" path for an order after quoting — deferred with
  disputes (Phase 3), needs cancellation/refund logic thought through
  properly rather than bolted on
- `certification_scopes`' attribute-range/geo-region columns exist but
  nothing populates them yet — deliberate forward capacity
- No subscription-limit enforcement, upgrade/downgrade UI, or billing
  yet — the table is real and populated, enforcement logic is future work
- Login/2FA/OTP rate limiting (Batch G) is in-memory and per-process —
  correct for the current single-process deployment, but each worker
  process would keep its own counters if the app is ever run with
  multiple workers; a shared store (Redis) is the natural upgrade then
- File inputs can't survive a page reload (HTML limitation) —
  documents need reattaching if the registration OTP round-trip or a
  validation error sends the form back
- Localization coverage is global chrome + auth pages only so far —
  deeper per-portal pages (listings, RFQs, orders, admin tables) fall
  back to English cleanly; extending coverage is incremental work, not
  an architecture gap
- `platform_settings` (Batch H) is a deliberate single-row table (id
  always 1), not a generic key/value store — see the model's own
  docstring. Fine for a handful of booleans; revisit only if the
  number of platform-wide toggles grows a lot
- Audit log (Batch H) now also records every completed login
  (`action="login"`), not just admin actions — but only for a fully
  completed login (password step, or the second half of the 2FA
  flow), not the auto-login right after registration
- The registration-role toggle (Batch H) hides/disables the role in
  the UI AND re-checks it server-side on submit — but it does not
  retroactively touch any account that already registered under a
  role that's since been disabled

## Operational reminder
Every delivery that includes a new file under `alembic/versions/`
needs `alembic upgrade head` run against the actual database after
copying the files in. Copying the migration file alone does NOT apply
it — a "column ... does not exist" error right after applying a batch
almost always means this step was missed. Check `alembic current`
against the latest filename in `alembic/versions/` to confirm.

## Post-batch routine — updated for Batch I+
1. `alembic upgrade head`   2. `python scripts/load_master_data.py`   3. `python scripts/seed_test_data.py`
4. `python scripts/check_routes.py` (now expands every master-data screen)   5. `pytest tests/ -q`


