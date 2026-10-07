# Vercel startup troubleshooting

The application pins Python 3.12 for predictable dependency compatibility.

Required production variables:

- `SECRET_KEY` — at least 32 characters
- `SUPABASE_URL`
- one backend credential: preferably `SUPABASE_SERVICE_ROLE_KEY`; legacy `SUPABASE_ANON_KEY` can boot older/non-RLS-hardened deployments

Recommended:

- `SITE_URL`
- `RATELIMIT_STORAGE_URI` (`rediss://...`) for distributed rate limiting
- mail/OAuth variables for those features

Rate limiting is fail-open for application availability: if Flask-Limiter or Redis cannot initialize, the storefront still boots and logs the problem.

If Flask application creation itself fails, the Vercel WSGI module now exposes a minimal HTTP 503 response containing only the exception type/message. It does not expose a Python traceback or secret values. This converts opaque `FUNCTION_INVOCATION_FAILED` startup crashes into an actionable configuration error.
