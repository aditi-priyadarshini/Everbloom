# Rosewood Bloom UI pass

## Design audit and decisions

Applied the installed `ui-ux-pro-max`, `frontend-design`, and `webapp-testing` skills. The audit identified a muted, repetitive storefront palette; decorative admin typography; public merchandising without publication checks; a category-by-category homepage query loop; mobile navigation without focus containment; a mobile admin menu rendered as a permanent grid; redundant product table columns; and an unimplemented newest sort branch.

The storefront uses warm ivory, deep berry, coral details, restrained sage, and Fraunces with Manrope. Photography comes from existing uploaded products/settings. With no photography, CSS brand artwork replaces the image. Category layouts adapt to one, two, three, and larger catalogues. The admin uses Manrope, neutral surfaces, a dark sidebar, operational status labels, and mobile cards derived from the same tables.

## Implementation

- Sticky storefront header; real category/occasion dropdowns; native mobile, search, and filter dialogs with keyboard dismissal, focus restoration, scrims, and scroll locking.
- Editorial homepage, real product image composition, conditional content sections, adaptive category/collection layouts, product crossfades, saved-product actions, and dark footer.
- Shop search, explicit newest/price sorting, removable filter chips, mobile filter/sort controls, and a useful empty state.
- Product disclosures, gallery alternative text, scrollable thumbnails, sticky purchase controls, and preserved variants/personalisation.
- Cart preparation hints and labelled quantities; grouped checkout with preserved form values after validation; custom requests organised around the idea before contact details.
- Separate admin CSS foundation, grouped sidebar, mobile drawer, real search destinations, attention-first dashboard, product filters, responsive tables, contextual fulfilment actions, and grouped settings.
- Product media ordering, cover-image indicators, editable image descriptions, previews, structured personalisation fields, section navigation, persistent save controls, and unsaved-change protection.
- Category/collection/occasion counts and edit/archive/restore controls. Archives preserve records and product associations.
- Inventory counts/value, material search, low-stock filtering, accessible receive/edit dialogs, and movement-history links.
- Native analytics charts using existing metrics. Removed the external Chart.js request and speculative future-feature suggestions.

## Backend boundaries

`models.get_public_merchandising()` builds one request-local snapshot with six batch queries, independent of category/collection/occasion count. It reuses the existing commerce `availability(...).published` rule. A group appears only if active and linked to at least one published product; ready-stock quantity does not determine whether a made-to-order product is published. Admin counts include unpublished products separately. The homepage reuses the snapshot for category photographs.

Other backend changes are limited to explicit newest sorting, admin product/customer filters, safe media ordering/alternative text, and merchandising edit/archive/restore. Authentication, order transitions/RPCs, checkout transactions, and inventory mutation code retain their existing contracts.

## Database and deployment

Apply **only** `supabase/migrations/011_ui_metadata.sql` before deploying this change. It adds:

- `categories.active boolean not null default true` for archive/restore.
- `products.image_alt_texts jsonb not null default '[]'` for editable image descriptions.

Existing rows, product images, memberships, and transactions are preserved. No migration is executed automatically by this work. Existing migrations are unchanged. Publication-derived empty-group hiding does not require stored product counts.

No production dependency was added. Existing Authlib, Flask-Limiter, and Playwright tooling was installed in `/tmp` for local validation because the machine lacked working test tools. Dependency manifests, startup, secrets/environment validation, Vercel entrypoint, and ignore configuration are unchanged.

Commit the modified templates, CSS/JS/favicon, `models.py`, `routes/shop.py`, `routes/admin.py`, new shared partials/styles, regression tests, this document, and migration 011. Deploy through the existing Vercel workflow after applying the migration. No environment-variable changes are required.

## Verification boundaries

Python tests use mocked Supabase calls. Browser verification uses isolated, clearly labelled QA fixtures outside production, including empty and populated catalogues. No fake catalogue data or stock photography is added to the application. External font requests are blocked in deterministic browser checks, so screenshots exercise font fallbacks as well as local layout. Live Google OAuth, SMTP delivery, production payment processing, and a Vercel deployment require configured external services and are not exercised against real accounts here.

## Final checks

- `python -m compileall .`: passed.
- Existing suite plus publication/media/checkout regressions: **74 passed**.
- `python tests/ui_qa.py --empty` and `python tests/ui_qa.py`: **231 page/viewport checks**, at 360, 390, 430, 768, 1024, 1280, and 1440px; no page overflow or JavaScript errors. A further seven-width order-detail check also passed.
- Browser interactions covered mobile storefront/admin drawers, Escape/focus restoration, mobile sort sheet, gallery alt updates, media reordering, the personalisation editor, material search, and stock receive/edit dialogs.
- All **83** literal template endpoint references resolve.
- `git diff --check`: passed.
- `app.py`, `pyproject.toml`, `requirements.txt`, `.vercelignore`, `vercel.json`, and existing migrations: unchanged.

The browser harness uses `/usr/bin/chromium`; adjust its executable path if Chromium is installed elsewhere. Screenshots and JSON results are written to `/tmp/everbloom-qa` by default.

## Changed files

- `docs/rosewood-bloom-ui.md`
- `models.py`
- `routes/admin.py`
- `routes/shop.py`
- `static/css/admin.css`
- `static/css/main.css`
- `static/css/shared.css`
- `static/favicon.svg`
- `static/js/main.js`
- `supabase/migrations/011_ui_metadata.sql`
- `templates/admin/_metric_bars.html`
- `templates/admin/analytics.html`
- `templates/admin/base_admin.html`
- `templates/admin/custom_request_detail.html`
- `templates/admin/customers.html`
- `templates/admin/dashboard.html`
- `templates/admin/email_template_edit.html`
- `templates/admin/inventory.html`
- `templates/admin/merchandising.html`
- `templates/admin/order_detail.html`
- `templates/admin/orders.html`
- `templates/admin/product_form.html`
- `templates/admin/products.html`
- `templates/admin/settings.html`
- `templates/base.html`
- `templates/shared/icon.html`
- `templates/shared/search_icon.html`
- `templates/shop/_product_card.html`
- `templates/shop/cart.html`
- `templates/shop/checkout.html`
- `templates/shop/custom_order.html`
- `templates/shop/custom_order_track.html`
- `templates/shop/index.html`
- `templates/shop/product.html`
- `templates/shop/shop.html`
- `tests/test_merchandising.py`
- `tests/ui_qa.py`

## Commit and deploy

After applying migration 011 in Supabase, commit the UI changes on the existing `main` branch:

```sh
git add models.py routes/shop.py routes/admin.py static templates \
  tests/test_merchandising.py tests/ui_qa.py docs/rosewood-bloom-ui.md \
  supabase/migrations/011_ui_metadata.sql
git commit -m "Polish Rosewood Bloom storefront and studio admin"
git push origin main
```

Use the existing Vercel deployment attached to `main`; no entrypoint, dependency discovery, Python version, or environment settings should change. No commit, push, migration execution, or deployment was performed by this UI pass.
