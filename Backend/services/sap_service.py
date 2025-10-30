import os
import logging
import requests
from urllib.parse import quote
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Setup & Config
# -----------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("sap_service")

SAP_BASE_URL = os.getenv("SAP_BASE_URL", "").rstrip("/")
SAP_USERNAME = os.getenv("SAP_USERNAME")
SAP_PASSWORD = os.getenv("SAP_PASSWORD")
SAP_CLIENT   = os.getenv("SAP_CLIENT", "").strip()

if not all([SAP_BASE_URL, SAP_USERNAME, SAP_PASSWORD]):
    raise RuntimeError("Missing SAP_BASE_URL, SAP_USERNAME, or SAP_PASSWORD in environment")

DEFAULT_TIMEOUT = 30
ENTITY_SET = "TELEPHONEADDRSet"

# Single session for reuse; let it manage cookies and auth.
session = requests.Session()
session.auth = (SAP_USERNAME, SAP_PASSWORD)
session.headers.update({
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json",
})

def _with_query(base: str) -> str:
    """Append sap-client and $format=json consistently."""
    parts = []
    if SAP_CLIENT:
        parts.append(f"sap-client={SAP_CLIENT}")
    parts.append("$format=json")
    return base + ("?" + "&".join(parts) if parts else "")

# -----------------------------------------------------------------------------
# CSRF Token Helper
# -----------------------------------------------------------------------------
def fetch_csrf_token(fetch_path: str = ""):
    """
    Fetch CSRF token from the service. Many SAP systems require you to hit the
    service or an entity set (not just '/').
    """
    url = _with_query(f"{SAP_BASE_URL}/{fetch_path}".rstrip("/"))
    headers = {"X-CSRF-Token": "Fetch", "X-Requested-With": "XMLHttpRequest"}
    logger.info(f"[GET] Fetching CSRF token from: {url}")
    resp = session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    if resp.status_code != 200:
        logger.error(f"Failed to fetch CSRF token: {resp.status_code} {resp.text}")
        raise RuntimeError(f"Failed to fetch CSRF token: {resp.text}")
    token = resp.headers.get("X-CSRF-Token")
    if not token:
        raise RuntimeError("CSRF token not returned by server")
    return token

# -----------------------------------------------------------------------------
# GET all Telephone Addresses
# -----------------------------------------------------------------------------
def get_telephone_address() -> list:
    url = _with_query(f"{SAP_BASE_URL}/{ENTITY_SET}")
    logger.info(f"[GET] Fetching Telephone Addresses from: {url}")
    resp = session.get(url, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 200 and "application/json" in resp.headers.get("Content-Type", ""):
        data = resp.json()
        # SAP OData v2 responses are wrapped in {"d":{"results":[...]}}
        return data.get("d", {}).get("results", []) or data.get("value", [])
    logger.error(f"GET failed: {resp.status_code} {resp.text}")
    raise RuntimeError(f"Failed to fetch Telephone Addresses: {resp.text}")

# -----------------------------------------------------------------------------
# Helper: GET by key (PLANT)
# -----------------------------------------------------------------------------
def get_telephone_address_by_plant(plant: str) -> dict | None:
    if not plant:
        raise ValueError("plant is required")
    key = f"(PLANT='{quote(plant)}')"
    url = _with_query(f"{SAP_BASE_URL}/{ENTITY_SET}{key}")
    logger.info(f"[GET] Fetching Telephone Address by PLANT from: {url}")
    resp = session.get(url, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("d") or data  # d/object
    if resp.status_code == 404:
        return None
    logger.error(f"Key GET failed: {resp.status_code} {resp.text}")
    raise RuntimeError(f"Failed to fetch Telephone Address for PLANT {plant}: {resp.text}")

# -----------------------------------------------------------------------------
# CREATE or UPDATE (Upsert)
# -----------------------------------------------------------------------------
def create_update_telephone_address(entities: dict) -> dict:
    """
    Upsert a Telephone Address identified uniquely by PLANT.
    - If PLANT exists -> PATCH with If-Match: *
    - Else -> POST to the entity set
    """
    if not isinstance(entities, dict):
        raise TypeError("entities must be a dict")

    clean_entities = {k: v for k, v in entities.items() if v not in (None, "", [])}
    plant = clean_entities.get("PLANT")
    if not plant:
        raise ValueError("PLANT must be provided to identify the record")

    # Check existence first (clearer than relying on POST error codes)
    exists = get_telephone_address_by_plant(plant) is not None

    token = fetch_csrf_token(fetch_path=ENTITY_SET)
    write_headers = {
        "X-CSRF-Token": token,
        "X-Requested-With": "XMLHttpRequest",
        "If-Match": "*",  # allow overwrite for updates
    }

    if exists:
        # PATCH to update only provided fields
        key = f"(PLANT='{quote(plant)}')"
        url = _with_query(f"{SAP_BASE_URL}/{ENTITY_SET}{key}")
        logger.info(f"[PATCH] Updating Telephone Address at: {url}")
        resp = session.patch(url, headers=write_headers, json=clean_entities, timeout=DEFAULT_TIMEOUT)
        if resp.status_code in (204, 200):  # 204 typical; 200 if representation returned
            return {"status": "success", "message": f"Plant {plant} telephone address updated"}
        logger.error(f"PATCH failed: {resp.status_code} {resp.text}")
        raise RuntimeError(f"Failed to update Telephone Address {plant}: {resp.text}")
    else:
        # POST to create
        url = _with_query(f"{SAP_BASE_URL}/{ENTITY_SET}")
        logger.info(f"[POST] Creating Telephone Address at: {url}")
        resp = session.post(url, headers=write_headers, json=clean_entities, timeout=DEFAULT_TIMEOUT)
        if resp.status_code in (201, 200):  # 201 typical
            try:
                data = resp.json()
                return data.get("d") or data or {"status": "success", "message": "Record created"}
            except Exception:
                return {"status": "success", "message": "Record created"}
        logger.error(f"POST failed: {resp.status_code} {resp.text}")
        raise RuntimeError(f"Failed to create Telephone Address: {resp.text}")
