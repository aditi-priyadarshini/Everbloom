# Vercel startup notes

Everbloom now uses Vercel's native Flask detection. Do not restore the legacy `builds` / catch-all `routes` configuration unless Vercel's current Flask documentation explicitly requires it.

The root `app.py` exposes `app` and `application` at module scope. `/healthz` returns a small JSON response when the Flask application factory has completed successfully.

Required production environment variables:

- `SECRET_KEY` (32+ characters)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (preferred; legacy anon key is only a temporary compatibility fallback)

Optional:

- `RATELIMIT_STORAGE_URI` (shared Redis recommended; memory fallback is allowed)
- mail and OAuth settings documented in `.env.example`
