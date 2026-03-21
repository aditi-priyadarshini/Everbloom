import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def _url(table):
    return f"{SUPABASE_URL}/rest/v1/{table}"


def select(table, filters=None, order=None, limit=None, single=False):
    params = {"select": "*"}
    if filters:
        params.update(filters)
    if order:
        params["order"] = order
    if limit:
        params["limit"] = limit
    headers = {**HEADERS}
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
    r = requests.get(_url(table), headers=HEADERS, params=params)
    if r.status_code in (200, 206):
        return r.json()
    return []


def insert(table, data):
    r = requests.post(_url(table), headers=HEADERS, json=data)
    if r.status_code in (200, 201):
        result = r.json()
        return result[0] if isinstance(result, list) else result
    return None


def update(table, filters, data):
    params = {}
    if filters:
        params.update(filters)
    r = requests.patch(_url(table), headers=HEADERS, json=data, params=params)
    if r.status_code in (200, 204):
        try:
            return r.json()
        except Exception:
            return True
    return None


def delete(table, filters):
    params = {}
    if filters:
        params.update(filters)
    r = requests.delete(_url(table), headers=HEADERS, params=params)
    return r.status_code in (200, 204)


def rpc(func_name, params=None):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{func_name}",
        headers=HEADERS,
        json=params or {},
    )
    if r.status_code == 200:
        return r.json()
    return None


# ── Storage ──────────────────────────────────────────────

def upload_file(bucket, path, file_bytes, content_type="image/jpeg"):
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type,
    }
    r = requests.post(url, headers=headers, data=file_bytes)
    if r.status_code in (200, 201):
        return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"
    return None


def public_url(bucket, path):
    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"
