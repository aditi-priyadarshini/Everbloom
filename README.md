# Everbloom

Everbloom is a Flask/Jinja handmade-commerce application with a Supabase PostgreSQL and Storage backend. The existing authentication, UPI advance workflow, products, custom requests, customer orders, costing, material recipes and component manufacturing remain in the same application.

The redesign introduces a fixed parchment/espresso/terracotta identity, editorial storefront, responsive product cards, option-aware cart lines, guest checkout and private tracking links, working newsletter subscriptions, merchandising controls, review eligibility, private payment receipts, inventory movements and transactional commerce operations.

## Architecture

- `app.py`: application factory, CSRF, OAuth, rate limits, security headers and safe errors.
- `routes/`: customer, authentication, orders and admin HTTP handlers.
- `models.py`: existing persistence API retained for compatibility.
- `services/commerce.py`: availability, Decimal pricing, coupon rules, quantity and preparation-date calculations.
- `services/cart.py`: legacy-cart migration, option validation and cart-line identities.
- `services/uploads.py`: actual image decoding, size checks, orientation normalization, resizing and WebP conversion.
- `supa.py`: server-only REST/RPC and Storage requests with timeouts.
- `supabase/migrations/`: canonical database setup and atomic PostgreSQL operations.
- `templates/`, `static/`: server-rendered pages with progressive JavaScript enhancement.

No frontend framework or payment gateway has been introduced.

## Local setup

Use Python 3.11 or newer in a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set a strong `SECRET_KEY`, `SUPABASE_URL`, backend `SUPABASE_SERVICE_ROLE_KEY`, and `SITE_URL`. `.env` is loaded automatically and ignored by Git. Generate a secret with `python -c "import secrets; print(secrets.token_hex(32))"`.

```sh
flask --app app run --debug
```

Without database configuration, public catalog pages render an empty state; business writes require Supabase. Never use debug mode in production.

## Supabase database setup

Back up an existing database first. Test migrations against a staging copy: the original repository did not contain a reliable schema, so local tests cannot establish compatibility with an unknown deployed schema. The baseline expects UUID customer/product/order/request identifiers and bigint category/material/component/variant identifiers. Existing tables are retained; existing schemas with different identifier types require an explicit adaptation before migration.

Run each file **once**, in order, using the Supabase SQL editor or `psql` with `ON_ERROR_STOP=1`:

1. `001_legacy_baseline.sql`: complete baseline for tables already referenced by the application.
2. `002_commerce.sql`: additive availability, guest order, option snapshots, promotions, ledger and RLS changes; legacy product availability is backfilled.
3. `003_transactions.sql`: atomic order placement, coupon/gift-card redemption, material allocation, cancellation and newsletter functions.
4. `004_inventory_operations.sql`: atomic purchasing and component production; stock balance audit triggers.
5. `005_merchandising.sql`: collections, occasions, testimonials, review moderation and compatibility columns.
6. `006_custom_conversion.sql`: locked, repeat-safe custom-request conversion.
7. `007_order_states.sql`: legacy status synchronization with independent payment and fulfilment states.
8. `008_order_validation.sql`: status constraints and forward-only fulfilment transitions.
9. `009_order_updates.sql`: transactional status/amount updates and production allocation.
10. `010_backend_permissions.sql`: explicit service-role table and sequence permissions.

From the repository root, `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f schema.sql` executes the same files using psql include directives. For the Supabase browser SQL editor, paste individual migration contents; `\ir` is a psql command.

The migration files are versioned, not a script to rerun on every application startup. Trigger/constraint creation intentionally exposes an accidentally repeated migration rather than silently ignoring an unexpected schema state.

### Backend credential and RLS decision

All business data access occurs on the Flask server with the service-role key. RLS is enabled and access revoked from `anon` and `authenticated` on application tables. Commerce RPCs are executable only by `service_role`. The application does its own authentication using password hashes and server-signed sessions; it does not use Supabase Auth JWTs. Never expose the service key to the browser. Existing permissive policies should be reviewed during staging migration. Storage uses separate bucket permissions.

### Storage

Create:

- `everbloom`: public product/artisan/custom-reference imagery; uploads allowed only to the backend service role.
- `payment-receipts`: **private**; uploads and signed reads allowed only to the backend service role.

New receipts store a private object reference. Authorized admin order pages obtain five-minute signed URLs. Existing public receipt URLs are preserved for compatibility; migrate historical receipts into private storage and remove their public objects before launch. Custom reference images remain in the public image bucket; customers should not upload sensitive documents.

Uploads accept actual JPEG/PNG/WebP data only, at most 8 MB per image and 12 images per product. Images are orientation-normalized, bounded to 2000 px and converted to WebP under generated filenames. Requests are capped at 32 MB.

## Email and Google OAuth

`MAIL_USERNAME` and `MAIL_PASSWORD` configure the existing Zoho India SMTP connection (`smtp.zoho.in`, port 465, SSL). Use an application password. When absent, email sending returns failure and logs a skip; orders still persist. Messages include a plain-text fallback. Set the sender and DNS SPF/DKIM/DMARC correctly for your domain. No SMTP secrets are shown in admin settings.

For Google sign-in set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Register `${SITE_URL}/auth/google/callback` as the OAuth callback. Enable the Google consent screen and add the exact deployed origin. Use HTTPS in production.

Create an account and verify its email. In the Supabase SQL editor, grant the first owner access explicitly:

```sql
update public.users set is_admin=true, email_verified=true
where email='owner@example.com';
```

Admin requests recheck the database role server-side. Signing up never grants admin privileges.

## Availability and inventory policy

Products retain legacy `stock`, `allow_preorder`, `discount_percent`, `images` and `is_listed` columns.

- `READY_TO_SHIP` and `ONE_OF_ONE`: finished quantity is atomically decremented when checkout succeeds; cancellation restores recorded allocations once.
- `MADE_TO_ORDER`: zero finished stock is valid. Required raw materials/components are allocated when crafting begins or the owner explicitly allocates production materials.
- `PREORDER`: opening/closing dates are enforced by the transaction.
- `CUSTOM_ONLY`, `UNAVAILABLE`, `DRAFT`, `ARCHIVED`: cannot be purchased normally. Hidden/draft/archived products cannot be opened publicly.

Production allocation locks the order and inventory rows, rejects shortages, writes movements and sets a one-time consumption marker. Cancellation does not automatically return already-consumed glue, ribbon or manufactured components; recovered materials need an explicit adjustment. Stock updates have a balance ledger, while explicit order movements carry the order reference. Do not sum balance-change and contextual movements as if they were independent physical consumption.

Component manufacture and purchasing run as database transactions. Product recipes and costing retain the existing admin editors. Current material calculation uses product-level recipes, not per-combination BOM overrides.

## Orders, payment and custom requests

Payment and fulfilment are independent columns. Legacy `status` remains synchronized for existing screens and transactional email functions. Manual UPI proofs are submissions, never automatic proof of payment. The owner verifies payments and manages crafting/shipping separately. No automatic refunds, courier tracking or gateway processing is implied.

Guest orders receive a high-entropy private tracking link with payment-proof submission when an advance is requested. Treat these links as bearer credentials. Registered customers retain their account order pages. Review submission requires a delivered purchase associated with that account, and admin moderation controls visibility.

Cart keys include product, option IDs and personalisation. Checkout recalculates prices from database rows and stores option/personalisation snapshots in order items and confirmation emails. Legacy group-based options remain supported. The signed-cookie cart is bounded to prevent cookie overflow; large orders should be split. Full SKU-combination inventory and per-variant BOM overrides are not implemented.

Custom requests accept guests, reference images, occasion, size, colours, budget and desired date. Quote acceptance uses CSRF-protected POST. Conversion locks the request, creates an order and its item together, and returns the same order for repeat conversions. Private conversion notes remain internal.

## Owner setup

Use admin settings for announcement, hero text/images, story, business/contact details, policies, UPI QR and processing buffer. Add categories, collections, occasions and approved testimonials through the catalog controls; assign collections/occasions from product edit. Add product options after saving a product. Personalisation fields currently use a validated JSON editor, for example:

```json
[{"name":"recipient_name","label":"Recipient name","required":true}]
```

Publish actual policy content and product photographs before launch. Empty image states are neutral placeholders; there are no invented reviews, customer counts or social feeds.

## Tests

```sh
pip install -r requirements-dev.txt
python -m compileall -q app.py models.py routes services
python -m pytest -q
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f tests/transactions.sql
```

The SQL regression suite requires a disposable migrated database and rolls back test data. It checks atomic allocation, checkout idempotency, oversell rollback, one-time production deduction, cancellation restoration and retained history. Python tests cover guards, CSRF, pricing, availability, cart identity/options, guest checkout payloads, dates, coupons, image validation, template compilation and page smoke tests.

Live SMTP, Google consent, Supabase REST/Storage and deployment require configured services and are not covered by mocked page tests. See `docs/AUDIT.md` for initial findings and `docs/LAUNCH_CHECKLIST.md` for remaining launch requirements.

## Vercel deployment

1. Back up the current database and Storage. Rehearse all migrations on staging and verify identifier/column compatibility.
2. Apply migrations in order; create the public image and private receipt buckets.
3. Configure `SECRET_KEY` (at least 32 random characters), `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SITE_URL` and SMTP/OAuth variables. Configure a shared `RATELIMIT_STORAGE_URI` (`rediss://...`) for distributed production rate limiting; the application temporarily falls back to per-instance memory limiting if Redis is not yet configured.
4. Deploy this existing repository using its `vercel.json` Python/static configuration. Production startup fails when the strong session secret or all Supabase backend credentials are absent. Missing shared Redis logs a warning instead of taking the storefront offline.
5. Add the deployed Google callback, verify sender authentication, create the first admin, fill business/policy content and upload real products.
6. Execute guest, registered, custom-order and admin production journeys on staging, including receipt upload and actual email delivery; inspect logs and database movements before promoting the release.

Production cookies are Secure/HttpOnly/SameSite=Lax. Local HTTP development omits Secure. Exceptions are logged server-side and never returned as tracebacks. CSRF remains active on state-changing forms. Rate limits protect auth and high-value submission endpoints; shared Redis is necessary for distributed enforcement.

## October 2026 admin/performance patch

The admin save/error handling and Supabase performance patch includes a new **System health** page at `/admin/system-health`, batch settings updates, public-catalogue caching, more reliable upload/CRUD feedback and lower-query inventory costing.

See [docs/ADMIN_PERFORMANCE_FIXES.md](docs/ADMIN_PERFORMANCE_FIXES.md) for exact changes, migration prerequisites, deployment verification, and known limitations. Deploying just the Python code does **not** run the Supabase migrations.
