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

## PHASE 3 — Payments & Compliance: ⬜ NOT STARTED
ZATCA e-invoicing, escrow/settlement, subscription billing
enforcement, disputes, audit logging expansion.

## PHASE 4 — Scale & Optimization: ⬜ NOT STARTED
Inventory management, logistics/shipping, document management,
advanced reporting, admin monitoring, mobile responsiveness pass.

---

## Reference documents from other batches
- **`DATA_DICTIONARY.md`** (Batch A) — full table-by-table database reference
- Each batch's own README (`BATCH_A_README.md`, `BATCH_B_README.md`,
  `BATCH_C_README.md`, ...) — step-by-step testing instructions and
  the specific design decisions made in that batch

---

## Known cleanup pending (low priority, doesn't block anything)
- Delete `app/templates/layouts/base_app.html` and `base_portal.html` (unused)
- Delete `app/modules/seller/routes.py` (stray unused duplicate)
- Wire `users.last_login_at` — currently a dead column, never written to

## Deliberate scope boundaries
Noted here so they don't get re-litigated by accident — these are
considered decisions, not oversights:

- Email is not editable from `/my-profile` or `/admin/users`
- Company role is not editable anywhere after registration
- Passport validity period (365 days) is a hardcoded constant, no
  admin-configurable policy UI yet
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

## Operational reminder
Every delivery that includes a new file under `alembic/versions/`
needs `alembic upgrade head` run against the actual database after
copying the files in. Copying the migration file alone does NOT apply
it — a "column ... does not exist" error right after applying a batch
almost always means this step was missed. Check `alembic current`
against the latest filename in `alembic/versions/` to confirm.
