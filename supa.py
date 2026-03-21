"""
supa.py — Supabase REST API client.
All database calls go through here. No SQL, no drivers, just HTTP.
Env vars are read lazily (inside functions) so Vercel can inject them at runtime.
"""
import os, requests


def _base():
    return os.environ.get("SUPABASE_URL", "").rstrip("/")

def _key():
    # prefer service role (bypasses RLS), fall back to anon
    return os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

def _headers():
    k = _key()
    return {
        "apikey": k,
        "Authorization": f"Bearer {k}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def _url(table):
    return f"{_base()}/rest/v1/{table}"


# ── Core operations ───────────────────────────────────────────

def select(table, filters=None, order="", limit=None, single=False):
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
    if r.status_code == 406 and single:
        return None
    return [] if not single else None


def select_one(table, filters):
    result = select(table, filters=filters, single=True)
    return result


def insert(table, data):
    r = requests.post(_url(table), headers=_headers(), json=data)
    if r.status_code in (200, 201):
        rows = r.json()
        return rows[0] if isinstance(rows, list) and rows else rows
    raise Exception(f"Insert failed {r.status_code}: {r.text}")


def update(table, filters, data):
    r = requests.patch(_url(table), headers=_headers(), json=data, params=filters)
    if r.status_code in (200, 204):
        return True
    raise Exception(f"Update failed {r.status_code}: {r.text}")


def delete(table, filters):
    r = requests.delete(_url(table), headers=_headers(), params=filters)
    return r.status_code in (200, 204)


# ── Storage ───────────────────────────────────────────────────

def upload_file(bucket, path, file_bytes, content_type="image/jpeg"):
    k = _key()
    r = requests.post(
        f"{_base()}/storage/v1/object/{bucket}/{path}",
        headers={
            "apikey": k,
            "Authorization": f"Bearer {k}",
            "Content-Type": content_type,
        },
        data=file_bytes,
    )
    if r.status_code in (200, 201):
        return f"{_base()}/storage/v1/object/public/{bucket}/{path}"
    return None


def upload_image(file_storage, bucket, path):
    import time
    ext = (file_storage.filename or "jpg").rsplit(".", 1)[-1].lower()
    full_path = f"{path}.{ext}"
    data = file_storage.read()
    ct = f"image/{ext}".replace("image/jpg", "image/jpeg")
    return upload_file(bucket, full_path, data, ct)


# ── Helpers ───────────────────────────────────────────────────

def eq(col, val):
    return {col: f"eq.{val}"}

def get_by_id(table, id):
    return select_one(table, {"id": f"eq.{id}"})

def count(table, filters=None):
    params = {"select": "id"}
    if filters:
        params.update(filters)
    k = _key()
    headers = {
        "apikey": k,
        "Authorization": f"Bearer {k}",
        "Prefer": "count=exact",
        "Range-Unit": "items",
        "Range": "0-0",
    }
    r = requests.get(_url(table), headers=headers, params=params)
    cr = r.headers.get("Content-Range", "0/0")
    try:
        return int(cr.split("/")[1])
    except Exception:
        return 0
