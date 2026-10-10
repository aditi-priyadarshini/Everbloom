"""Minimal Supabase PostgREST adapter with pooled HTTP connections and visible failures."""
import logging
import os
import uuid
import requests
from requests.adapters import HTTPAdapter

log = logging.getLogger(__name__)
_http = requests.Session()
_http.mount("https://", HTTPAdapter(pool_connections=8, pool_maxsize=16))
_TIMEOUT = (4, 12)  # connect, read; fail rather than hang for 15 seconds per call


class SupabaseError(RuntimeError):
    """A database failure with an administrator-only diagnostic.

    The public exception message stays generic because this adapter is also
    called from storefront routes. Only authenticated admin views should expose
    the server-provided PostgREST reason.
    """

    def __init__(self, message, *, status=None, code=None, backend_message=None, hint=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.backend_message = backend_message
        self.hint = hint

    @property
    def admin_detail(self):
        detail = str(self)
        if self.code:
            detail += f' [code: {self.code}]'
        if self.backend_message:
            detail += f' — {self.backend_message}'
        if self.hint:
            detail += f' — {self.hint}'
        return detail


def _one_line(value, limit=240):
    """Keep untrusted PostgREST message content bounded and single-line."""
    return ' '.join(str(value or '').split())[:limit]


def _backend_hint(status, code, scope=""):
    if code in ("42703", "PGRST204") and scope in ("probe categories", "probe custom_requests"):
        return ("Missing column in the deployed Supabase project. Run migration "
                "016_missing_columns_repair.sql against the database targeted by "
                "Vercel SUPABASE_URL, then NOTIFY pgrst to reload schema.")
    if scope == "RPC convert_custom_request":
        if code in ("42883", "PGRST202"):
            return ("Custom-order RPC or its dependencies are missing. Review migration "
                    "013_custom_conversion_repair.sql; reload PostgREST schema cache.")
        if code in ("42703", "42P01", "PGRST204", "PGRST205"):
            return ("Custom-order conversion needs database columns from commerce migrations. "
                    "Review migration 013_custom_conversion_repair.sql and reload schema cache.")
        if code in ("22023", "P0001", "55000"):
            return "The conversion RPC rejected this request or quote. Read its reason above; verify the request state."
        if code in ("23502", "23503", "23505", "23514"):
            return "Conversion violates a database constraint. Check the request, linked product and order schema."
    if code in ('PGRST204', 'PGRST205', '42703', '42P01'):
        return ('Database schema is missing or PostgREST has stale metadata. '
                'Check supabase/migrations/012_product_insert_repair.sql and reload the schema cache.')
    if code in ('42501',) or status in (401, 403):
        return ('Check that Vercel has SUPABASE_SERVICE_ROLE_KEY for the correct Supabase project; '
                'also verify the service_role SQL grants. Never paste the key into this page.')
    if code == '23503':
        return 'A selected category or linked record does not exist. Refresh the form and select a valid entry.'
    if code == '23514':
        return 'A product value violates a database CHECK constraint (such as stock, price or discount).'
    if code == '23505':
        return 'A value that must be unique already exists in the database.'
    if code == '22P02':
        return 'A submitted field has the wrong data type (often a category ID or date).'
    return 'Inspect the PostgREST error code and the affected column in the server logs.'


def _get_url():
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def _get_key():
    return (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or
            os.environ.get("SUPABASE_SERVICE_KEY") or
            os.environ.get("SUPABASE_KEY") or
            os.environ.get("SUPABASE_ANON_KEY", ""))


def _get_service_key():
    return (os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or
            os.environ.get('SUPABASE_SERVICE_KEY'))


def _headers(prefer="return=representation"):
    key = _get_key()
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": prefer}


def _url(table):
    return f"{_get_url()}/rest/v1/{table}"


def _request(method, url, *, scope, **kwargs):
    if not _get_url() or not _get_key():
        # Preserve the repository's offline-development behavior when Supabase
        # has not been configured; production already validates credentials.
        if os.environ.get('VERCEL') or os.environ.get('APP_ENV') == 'production':
            raise SupabaseError('Supabase backend configuration is incomplete')
        return None
    try:
        response = _http.request(method, url, timeout=_TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        log.error('Supabase %s %s transport error: %s', method, scope, type(exc).__name__)
        raise SupabaseError(f'Backend connection failed during {scope}') from exc
    if not 200 <= response.status_code < 300:
        # Parse PostgREST's JSON error so admins can distinguish missing schema,
        # constraint violations and permissions. Never log request data or keys.
        try:
            payload = response.json()
        except (ValueError, TypeError, AttributeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        code = _one_line(payload.get('code'), 40)
        reason = _one_line(payload.get('message'))
        details = _one_line(payload.get('details'), 160)
        backend_message = ' — '.join(p for p in (reason, details) if p)
        log.error('Supabase %s %s returned HTTP %s code=%s reason=%s',
                  method, scope, response.status_code, code or 'unknown', backend_message)
        raise SupabaseError(
            f'Backend rejected {scope} (HTTP {response.status_code})',
            status=response.status_code, code=code,
            backend_message=backend_message,
            hint=_backend_hint(response.status_code, code, scope),
        )
    return response


def select(table, filters=None, order=None, limit=None, single=False):
    if not _get_url():
        return None if single else []
    params = {'select': '*'}
    if filters: params.update(filters)
    if order: params['order'] = order
    if limit is not None: params['limit'] = limit
    headers = _headers()
    if single: headers['Accept'] = 'application/vnd.pgrst.object+json'
    response = _request('GET', _url(table), scope=f'select {table}', headers=headers, params=params)
    return response.json() if response is not None else (None if single else [])


def select_join(table, select_cols, filters=None, order=None, limit=None):
    params = {'select': select_cols}
    if filters: params.update(filters)
    if order: params['order'] = order
    if limit is not None: params['limit'] = limit
    response = _request('GET', _url(table), scope=f'select {table}', headers=_headers(), params=params)
    return response.json() if response is not None else []



def probe_table(table, columns):
    """Read-only, zero-row schema/permission probe for authenticated admins."""
    response = _request('GET', _url(table), scope=f'probe {table}',
                        headers=_headers(), params={'select': columns, 'limit': 0})
    if response is None: raise SupabaseError('Database URL or key is not configured')
    return True


def probe_bucket(bucket, *, expected_public):
    """Read-only Storage API check; never tries to upload test data."""
    key = _get_service_key()
    if not key:
        raise SupabaseError('A service-role credential is required to inspect Storage')
    response = _request('GET', f'{_get_url()}/storage/v1/bucket/{bucket}',
                        scope=f'probe storage bucket {bucket}',
                        headers={'apikey': key, 'Authorization': f'Bearer {key}'})
    if response is None:
        raise SupabaseError('Storage backend is not configured')
    info = response.json()
    if not isinstance(info, dict) or bool(info.get('public')) != expected_public:
        visibility = 'public' if expected_public else 'private'
        raise SupabaseError(f'Storage bucket {bucket} must be {visibility}')
    return True


def insert(table, data):
    response = _request('POST', _url(table), scope=f'insert {table}', headers=_headers(), json=data)
    if response is None: return None
    rows = response.json() if response.content else []
    return rows[0] if isinstance(rows, list) and rows else rows or None


def upsert(table, data, on_conflict):
    """Batch insert/update in one database round-trip."""
    response = _request('POST', _url(table), scope=f'upsert {table}',
                        headers=_headers('resolution=merge-duplicates,return=representation'),
                        params={'on_conflict': on_conflict}, json=data)
    return response.json() if response is not None and response.content else None


def update(table, filters, data):
    response = _request('PATCH', _url(table), scope=f'update {table}',
                        headers=_headers(), json=data, params=filters or {})
    if response is None: return None
    return response.json() if response.content else True


def delete(table, filters):
    response = _request('DELETE', _url(table), scope=f'delete {table}',
                        headers=_headers(), params=filters or {})
    return response is not None


def rpc(func_name, params=None):
    if func_name == "convert_custom_request" and not (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")):
        raise SupabaseError("A server-side Supabase service-role credential is required for custom-order conversion")
    response = _request('POST', f'{_get_url()}/rest/v1/rpc/{func_name}',
                        scope=f'RPC {func_name}', headers=_headers(), json=params or {})
    return response.json() if response is not None and response.content else None


def upload_file(bucket, path, file_bytes, content_type='image/jpeg'):
    from services.uploads import optimize_image
    file_bytes = optimize_image(file_bytes)
    path = path.rsplit('/', 1)[0] + '/' + str(uuid.uuid4()) + '.webp'
    private_receipt = path.startswith('payments/')
    if private_receipt: bucket = 'payment-receipts'
    key = _get_service_key()
    if not key: raise SupabaseError('Storage service-role credential missing')
    headers = {'apikey': key, 'Authorization': f'Bearer {key}',
               'Content-Type': 'image/webp', 'x-upsert': 'false'}
    response = _request('POST', f'{_get_url()}/storage/v1/object/{bucket}/{path}',
                        scope='storage upload', headers=headers, data=file_bytes,
                        )
    if response is None: return None
    return (f'private:{bucket}/{path}' if private_receipt else
            f'{_get_url()}/storage/v1/object/public/{bucket}/{path}')


def public_url(bucket, path):
    return f'{_get_url()}/storage/v1/object/public/{bucket}/{path}'


def receipt_url(value):
    """Sign private receipts only inside authorized order views."""
    if not value or not value.startswith('private:'): return value
    path = value[len('private:'):]
    key = _get_service_key()
    response = _request('POST', f'{_get_url()}/storage/v1/object/sign/{path}',
                        scope='receipt signing',
                        headers={'apikey': key, 'Authorization': f'Bearer {key}'},
                        json={'expiresIn': 300})
    if response is None: return None
    signed = response.json().get('signedURL') or response.json().get('signedUrl')
    return _get_url() + '/storage/v1' + signed if signed else None
