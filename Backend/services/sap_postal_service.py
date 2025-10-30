import os
import logging
import base64
import requests
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Setup & Config
# -----------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("sap_postal_service")

SAP_BASE_URL = os.getenv("SAP_BASE_URL", "").rstrip("/")
SAP_USERNAME = os.getenv("SAP_USERNAME")
SAP_PASSWORD = os.getenv("SAP_PASSWORD")
SAP_CLIENT = os.getenv("SAP_CLIENT", "").strip()

if not all([SAP_BASE_URL, SAP_USERNAME, SAP_PASSWORD]):
    raise RuntimeError("Missing SAP_BASE_URL, SAP_USERNAME, or SAP_PASSWORD in environment")

# Prepare basic auth header value
auth_bytes = f"{SAP_USERNAME}:{SAP_PASSWORD}".encode("utf-8")
auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

# Create a session for connection reuse
session = requests.Session()
session.headers.update({
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Basic {auth_base64}"
})

DEFAULT_TIMEOUT = 30
ENTITY_SET = "POSTADDRSet"  # <-- adjust to your SAP OData entity set name

# -----------------------------------------------------------------------------
# CSRF Token Helper
# -----------------------------------------------------------------------------
def fetch_csrf_token():
    """Fetch CSRF token and cookies from the service root."""
    url = f"{SAP_BASE_URL}/"
    if SAP_CLIENT:
        url += f"?sap-client={SAP_CLIENT}"

    headers = {
        "X-CSRF-Token": "Fetch",
        "X-Requested-With": "XMLHttpRequest"
    }
    logger.info(f"[GET] Fetching CSRF token from: {url}")
    resp = session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    if resp.status_code != 200:
        logger.error(f"Failed to fetch CSRF token: {resp.status_code} {resp.text}")
        raise RuntimeError(f"Failed to fetch CSRF token: {resp.text}")

    token = resp.headers.get("X-CSRF-Token")
    cookies = resp.cookies.get_dict()
    return token, cookies

# -----------------------------------------------------------------------------
# GET all Postal Addresses
# -----------------------------------------------------------------------------
def get_postal_address() -> list:
    """Fetch all postal address records (no filter)."""
    url = f"{SAP_BASE_URL}/{ENTITY_SET}"
    if SAP_CLIENT:
        url += f"?sap-client={SAP_CLIENT}"

    logger.info(f"[GET] Fetching Postal Addresses from: {url}")
    resp = session.get(url, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 200 and resp.headers.get("Content-Type", "").startswith("application/json"):
        data = resp.json()
        return data.get("d", {}).get("results", [])

    logger.error(f"GET failed: {resp.status_code} {resp.text}")
    raise RuntimeError(f"Failed to fetch Postal Addresses: {resp.text}")

# -----------------------------------------------------------------------------
# CREATE or UPDATE (upsert-like)
# -----------------------------------------------------------------------------
def create_update_postal_address(entities: dict) -> dict:
    """
    Create or update a Postal Address record (with CSRF).
    Accepts all SAP OData fields dynamically.
    Uses only PLANT as the unique identifier.
    """
    # Filter out empty values so we don’t send blank strings
    clean_entities = {k: v for k, v in entities.items() if v not in (None, "", [])}
    if not clean_entities.get("PLANT"):
        raise ValueError("PLANT must be provided to identify the record")

    # Base URLs
    post_url = f"{SAP_BASE_URL}/{ENTITY_SET}"
    if SAP_CLIENT:
        post_url += f"?sap-client={SAP_CLIENT}"

    # For update, build key predicate using only PLANT
    plant = clean_entities.get("PLANT")
    put_url = f"{SAP_BASE_URL}/{ENTITY_SET}(PLANT='{plant}')"
    if SAP_CLIENT:
        put_url += f"?sap-client={SAP_CLIENT}"

    csrf_token, cookies = fetch_csrf_token()
    payload = {"d": clean_entities}
    common_headers = {
        "X-CSRF-Token": csrf_token,
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": "; ".join([f"{k}={v}" for k, v in cookies.items()])
    }

    # --- Try POST (create) ---
    logger.info(f"[POST] Creating Postal Address at: {post_url} | Payload: {payload}")
    resp = session.post(post_url, headers=common_headers, json=payload, timeout=DEFAULT_TIMEOUT)
    if resp.status_code in (200, 201):
        return resp.json() if resp.text else {"status": "success", "message": "Record created"}

    # If record already exists, try update
    if resp.status_code in (400, 403, 409):
        logger.warning(f"POST failed ({resp.status_code}), trying UPDATE instead...")
        logger.info(f"[PUT] Updating Postal Address at: {put_url} | Payload: {payload}")
        resp_put = session.put(put_url, headers=common_headers, json=payload, timeout=DEFAULT_TIMEOUT)
        if resp_put.status_code in (200, 204):
            return {"status": "success", "message": f"Plant {plant} postal address updated"}

        logger.error(f"PUT failed: {resp_put.status_code} {resp_put.text}")
        raise RuntimeError(f"Failed to update Postal Address {plant}: {resp_put.text}")

    # If neither create nor update worked
    logger.error(f"POST failed: {resp.status_code} {resp.text}")
    raise RuntimeError(f"Failed to create Postal Address: {resp.text}")
