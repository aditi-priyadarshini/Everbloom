# Verification record

- Python: 64 pytest cases passed. Includes public/admin page rendering, template compilation, guards, CSRF, availability, Decimal pricing, options/personalisation through guest checkout payloads, coupons, delivered-purchase eligibility, image validation and stale-cart removal.
- PostgreSQL 18: all ten ordered migrations applied to a fresh disposable local database. Both SQL regression blocks passed, covering ready inventory, idempotency, cancellation/restock, oversell rollback, made-to-order allocation, duplicate deduction prevention, variant/personalisation snapshots, coupon limits, gift-card redemption, custom conversion and transactional state changes.
- Browser: public pages at 360, 390, 768, 1024 and 1440px returned 200 without document horizontal overflow; mobile navigation open/Escape behavior passed.
- Browser commerce/admin: product option selection, required personalisation, cart, checkout, admin overview, orders and new-product editor passed layout checks at all five widths using temporary local fixtures. The mobile admin sidebar visibility issue found during QA was fixed.
- Python syntax compilation and literal Jinja endpoint checks passed. No undefined literal template endpoints remain.
- Removed session-random palette code, numeric category-name branching and publicly returned traceback handlers. CSRF remains enabled.

The temporary browser fixtures and local PostgreSQL test records were not added to storefront content or sent to external services. This is not end-to-end verification of real SMTP/OAuth/Supabase Storage or the unknown production schema. See LAUNCH_CHECKLIST.md for unimplemented scope and required staging checks.
