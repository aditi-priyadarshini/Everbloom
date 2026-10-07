import os
import requests


def _get_url():
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def _get_key():
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")


def _get_service_key():
    # Service role key bypasses RLS — needed for Storage uploads
    return (os.environ.get("SUPABASE_SERVICE_KEY")
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or _get_key())


def _headers():
    key = _get_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _url(table):
    return f"{_get_url()}/rest/v1/{table}"


def select(table, filters=None, order=None, limit=None, single=False):
    if not _get_url(): return None if single else []
    params = {"select": "*"}
    if filters:
        params.update(filters)
    if order:
        params["order"] = order
    if limit:
        params["limit"] = limit
    headers = _headers()
    if single:
        headers["Accept"] = "application/vnd.pgrst.object+json"
    r = requests.get(_url(table), headers=headers, params=params, timeout=15)
    if r.status_code in (200, 206):
        return r.json()
    return [] if not single else None


def select_join(table, select_cols, filters=None, order=None, limit=None):
    params = {"select": select_cols}
    if filters:
        params.update(filters)
    if order:
        params["order"] = order
    if limit:
        params["limit"] = limit
    r = requests.get(_url(table), headers=_headers(), params=params, timeout=15)
    if r.status_code in (200, 206):
        return r.json()
    return []


def insert(table, data):
    r = requests.post(_url(table), headers=_headers(), json=data, timeout=15)
    if r.status_code in (200, 201):
        result = r.json()
        return result[0] if isinstance(result, list) else result
    import sys
    print(f"[supa.insert ERROR] table={table} status={r.status_code}", file=sys.stderr)
    return None


def update(table, filters, data):
    params = {}
    if filters:
        params.update(filters)
    r = requests.patch(_url(table), headers=_headers(), json=data, params=params, timeout=15)
    if r.status_code in (200, 204):
        try:
            return r.json()
        except Exception:
            return True
    import sys
    print(f"[supa.update ERROR] table={table} status={r.status_code}", file=sys.stderr)
    return None


def delete(table, filters):
    params = {}
    if filters:
        params.update(filters)
    r = requests.delete(_url(table), headers=_headers(), params=params, timeout=15)
    return r.status_code in (200, 204)


def rpc(func_name, params=None):
    r = requests.post(
        f"{_get_url()}/rest/v1/rpc/{func_name}",
        headers=_headers(),
        json=params or {}, timeout=15,
    )
    if r.status_code == 200:
        return r.json()
    return None


# ── Storage ──────────────────────────────────────────────

def upload_file(bucket, path, file_bytes, content_type="image/jpeg"):
    import sys
    from services.uploads import optimize_image
    import uuid
    file_bytes = optimize_image(file_bytes)
    path = path.rsplit('/', 1)[0] + '/' + str(uuid.uuid4()) + '.webp'
    content_type = 'image/webp'
    private_receipt = path.startswith('payments/')
    if private_receipt: bucket = 'payment-receipts'
    key = _get_service_key()
    base_url = _get_url()
    url = f"{base_url}/storage/v1/object/{bucket}/{path}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    r = requests.post(url, headers=headers, data=file_bytes, timeout=30)
    if r.status_code in (200, 201):
        return f"private:{bucket}/{path}" if private_receipt else f"{base_url}/storage/v1/object/public/{bucket}/{path}"
    print(f"[supa.upload_file ERROR] status={r.status_code}", file=sys.stderr)
    return None


def public_url(bucket, path):
    return f"{_get_url()}/storage/v1/object/public/{bucket}/{path}"


def receipt_url(value):
    """Sign private receipts only inside authorized order views."""
    if not value or not value.startswith('private:'): return value
    path=value[len('private:'):]
    key=_get_service_key()
    response=requests.post(f'{_get_url()}/storage/v1/object/sign/{path}',headers={'apikey':key,'Authorization':f'Bearer {key}'},json={'expiresIn':300},timeout=15)
    if response.status_code!=200: return None
    signed=response.json().get('signedURL') or response.json().get('signedUrl')
    return _get_url()+'/storage/v1'+signed if signed else None
