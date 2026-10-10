# Everbloom — operation and acceptance checklist

**Important:** This is a test PLAN and dependency map, not a claim that live Supabase works. No production credentials or live browser access were available. Only the offline static scan and isolated mocked tests were run.

| Feature / route group | Tables/RPC/other dependency | Offline status | Required live acceptance test |
|---|---|---|---|
| Homepage, shop, search, collections, occasions, product detail | products, categories, collections, occasions, linkage | Route and templates parsed | Browse home, empty shop, multiple categories, search, sorting, hidden/draft products |
| Product creation, edit, archive, photos, variants | products, variants, membership tables, `everbloom` public bucket | Product insert error handling unit-tested | Create/edit product, upload/remove/reorder image, add variant, assign category, archive and verify hidden |
| Admin dashboard / analytics | orders, order_items, inventory, custom requests | Route parsed | Load with actual historic orders, compare totals, test slow pages on mobile |
| Cart / checkout / order placement | `place_commerce_order`, orders, order_items, tracking, inventory_movements, coupons, gift_cards | RPC name accounted for; local code guards present | Guest and logged-in checkout; invalid quantity, deleted product, oversell, coupon limit, double click |
| Order management / statuses / cancellation | `update_commerce_order`, `cancel_commerce_order`, `consume_order_inventory` | RPC name accounted for | Confirm allowed transitions, blocked invalid transitions, status emails, single inventory decrement and cancellation restock |
| Custom request / quote / convert / linked product | custom_requests, `convert_custom_request`, orders, order_items, tracking | Idempotency and error handling unit-tested | Quote a request, convert once, click twice, link product, verify only one order and line item |
| Materials / receipt / component production / recipes | raw_materials, components, product_bom, component_bom, `receive_material`, `produce_component` | RPC name accounted for | Buy material, manufacture, insufficient-stock rejection, ledger reconciliation |
| Product costs / BOM | product_costs, product_bom, product_materials | Route parsed | Create/edit cost and recipe, compare estimated vs actual stock movement |
| Customers / authentication / Google sign-in | users, auth_tokens, Google OAuth, SMTP | Routes and CSRF scanned | Sign up, verify, log in/out, reset password, bad password, OAuth callback |
| Reviews / returns / wishlists | reviews, returns, wishlists | Routes parsed | Verify purchased-only review, return eligibility, denied unauthorized access |
| Payment receipt upload | `payment-receipts` private bucket, orders, tracking | Upload/order update failure path hardened | Upload JPEG/PNG, verify private receipt cannot be accessed anonymously, authorized signed URL works |
| Newsletter / campaigns / email templates | `subscribe_newsletter`, newsletter_subscribers, broadcasts, email_templates, email_log, SMTP | RPC name accounted for | Subscribe twice, send actual SMTP, detect failed sends, audit log record |
| Artisans / testimonials / FAQ / settings | artisans, testimonials, faqs, settings | Templates parsed; no live CRUD | Add/edit/archive, verify public visibility, save & reload settings |
| Coupons / gift cards | coupons, gift_cards, checkout RPC | Coupon RLS gap fixed in migration 015 | Make coupon, redeem exactly once per checkout, reject exhausted/expired, verify no public table access |
| System health | key table probes, `everbloom`, `payment-receipts` | Read-only probes unit-tested | Verify all rows green using deployed service-role project |

## Definition of a passing live flow

For **each mutation**, check: request returns success, row changes in Supabase, fresh-page reload reflects it, object access is correctly authorized, related tables remain consistent, an invalid input is rejected without partial mutations, and refresh/retry does not create duplicates. Server logs must have no 400/403/500 responses. HTML form CSRF tokens must remain enabled. For order/email workflows, a failed SMTP send must never roll back a committed database order or lead to a duplicate retry.

## Not proven in this container

Full Flask integration suite was blocked by missing packages (Flask and its extensions; network package install unavailable). There was no configured live Supabase, SMTP, Google OAuth, Redis, Vercel deployment URL, or real Storage files. Postgres service and psql were also unavailable, so the new SQL scripts were not executed against even a disposable PostgreSQL server. The static template/route scan is not the same as live operation testing.
