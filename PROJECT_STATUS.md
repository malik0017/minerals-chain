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

## NEW: post-batch routine (`scripts/`, `tests_selenium/`)
Every batch from now on should end with this three-step routine before
you consider it "done" on your machine:

1. `alembic upgrade head`
2. `python scripts/seed_test_data.py` — idempotent; safe to run after
   every batch, creates/repairs a full set of known test accounts,
   companies, products, RFQs, quotations and an order at every stage
   of its lifecycle. Writes `scripts/seed_ids.json`.
3. `python scripts/check_routes.py` — in-process route smoke test (no
   server needs to be running separately); hits every GET route
   anonymously and as each seeded role, exits non-zero if anything
   500s. This is what would have caught the `ModuleNotFoundError`s
   that triggered H-fix, instantly, at import time.

`tests_selenium/` is the companion real-browser suite for the handful
of mutating (POST) flows `check_routes.py` deliberately never fires —
run it with `pytest tests_selenium/` once `seed_test_data.py` has been
run. See `TESTING_TOOLS_README.md` for full setup and details on all
three.
