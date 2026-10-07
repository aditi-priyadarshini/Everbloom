# Repository audit

Existing tables: artisans, auth_tokens, back_in_stock_alerts, broadcasts, categories, component_bom, components, coupons, custom_requests, email_log, email_templates, expenditures, faqs, gift_cards, manufacture_log, notifications, order_items, order_requirements, orders, product_bom, product_costs, product_materials, products, raw_materials, returns, reviews, settings, tracking, users, variants, wishlists

Critical findings: non-atomic checkout; product-only cart keys; repeated inventory deduction; unsafe image uploads; public tracebacks; missing order_requirements template; settings update cannot insert keys; incomplete schema; duplicate routes/models.py; arbitrary purchase reviews; GET quote acceptance; destructive order deletion.

Implementation order: security, commerce services, additive database migrations, storefront components, operations UI, regression tests and setup documentation.

Live Supabase schema and credentials are not available locally; legacy compatibility must be verified against a staging backup before production migration.
