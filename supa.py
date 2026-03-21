import os
import requests

def _get_url():
    return os.environ.get("SUPABASE_URL", "").rstrip("/")

def _get_key():
    # Support both SUPABASE_KEY and SUPABASE_ANON_KEY
    return os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")

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
    r = requests.get(_url(table), headers=headers, params=params)
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
    r = requests.get(_url(table), headers=_headers(), params=params)
    if r.status_code in (200, 206):
        return r.json()
    return []


def insert(table, data):
    r = requests.post(_url(table), headers=_headers(), json=data)
    if r.status_code in (200, 201):
        result = r.json()
        return result[0] if isinstance(result, list) else result
    # Log the actual Supabase error so you can debug
    try:
        import sys
        print(f"[supa.insert ERROR] table={table} status={r.status_code} body={r.text}", file=sys.stderr)
    except Exception:
        pass
    return None


def update(table, filters, data):
    params = {}
    if filters:
        params.update(filters)
    r = requests.patch(_url(table), headers=_headers(), json=data, params=params)
    if r.status_code in (200, 204):
        try:
            return r.json()
        except Exception:
            return True
    try:
        import sys
        print(f"[supa.update ERROR] table={table} status={r.status_code} body={r.text}", file=sys.stderr)
    except Exception:
        pass
    return None


def delete(table, filters):
    params = {}
    if filters:
        params.update(filters)
    r = requests.delete(_url(table), headers=_headers(), params=params)
    return r.status_code in (200, 204)


def rpc(func_name, params=None):
    r = requests.post(
        f"{_get_url()}/rest/v1/rpc/{func_name}",
        headers=_headers(),
        json=params or {},
    )
    if r.status_code == 200:
        return r.json()
    return None


# ── Storage ──────────────────────────────────────────────

def upload_file(bucket, path, file_bytes, content_type="image/jpeg"):
    import sys
    key = _get_key()
    base_url = _get_url()

    # Try POST first (new file)
    url = f"{base_url}/storage/v1/object/{bucket}/{path}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
        "x-upsert": "true",   # overwrite if exists
    }
    r = requests.post(url, headers=headers, data=file_bytes)
    if r.status_code in (200, 201):
        return f"{base_url}/storage/v1/object/public/{bucket}/{path}"

    print(f"[supa.upload_file ERROR] bucket={bucket} path={path} status={r.status_code} body={r.text}", file=sys.stderr)
    return None


def public_url(bucket, path):
    return f"{_get_url()}/storage/v1/object/public/{bucket}/{path}"
