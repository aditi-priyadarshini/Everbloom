# End-to-end journeys

`journeys.py` drives the **real Flask app** over real HTTP into **PostgREST and Postgres** (the same
layers Supabase uses). Only e-mail delivery (captured) and file storage (stubbed) are substituted.
It covers 36 journeys: admin set-up, browsing, signup/verification/password reset, cart, checkout with
coupon + gift card, oversell and double-submit protection, advance payment with real image validation,
the whole fulfilment chain, cancellation/restock, returns and reviews, both custom-order flows
(admin converts / customer accepts by e-mailed link), components, recipes, inventory, reporting.

    sudo bash tests/e2e/run.sh fresh     # new project, uuid ids
    sudo bash tests/e2e/run.sh legacy    # older database, integer custom_requests.id

It builds a throw-away Postgres cluster in /tmp and never touches Supabase or production.
Requires Ubuntu/Debian `postgresql-16` and the PostgREST binary at `/tmp/pgrst/postgrest`
(https://github.com/PostgREST/postgrest/releases). Set `E2E_REPAIR=<sql file>` to test an older repair script.

Not covered: real SMTP, Google OAuth, real Supabase Storage, payment gateways, browsers/JavaScript.
