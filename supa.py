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
    """Backend returned a failure. Never treat a failed query as an empty table."""


def _get_url():
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def _get_key():
    return (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or
            os.environ.get("SUPABASE_SERVICE_KEY") or
            os.environ.get("SUPABASE_KEY") or
            os.environ.get("SUPABASE_ANON_KEY", ""))


def _get_service_key():
    return (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or
            os.environ.get("SUPABASE_SERVICE_KEY") or _get_key())


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
        # Do not log request bodies or Authorization headers.
        log.error('Supabase %s %s returned HTTP %s: %.280s', method, scope,
                  response.status_code, response.text)
        raise SupabaseError(f'Backend rejected {scope} (HTTP {response.status_code}); check migrations and service-role permissions')
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
