import os
import json
import secrets
import urllib.parse
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import requests

from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("HUBSPOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET")
if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError("Missing HUBSPOT_CLIENT_ID or HUBSPOT_CLIENT_SECRET in environment variables")

REDIRECT_URI = os.getenv(
    "HUBSPOT_REDIRECT_URI",
    "http://localhost:8000/integrations/hubspot/oauth2callback"
)

SCOPES_RAW = os.getenv(
    "HUBSPOT_SCOPES",
    "crm.objects.appointments.read crm.objects.courses.read crm.objects.companies.read crm.objects.contacts.read"
    # "crm.objects.appointments.read%20crm.objects.courses.read%20crm.objects.companies.read%20crm.objects.contacts.read"
)
# https://app-na2.hubspot.com/oauth/authorize?client_id=06cace6e-ca22-4d22-a869-532bc2bbb69a&redirect_uri=http://localhost:8000/integrations/hubspot/oauth2callback&scope=crm.objects.appointments.read%20oauth%20crm.objects.courses.read%20crm.objects.companies.read%20crm.objects.contacts.read
# URL‑encode once
ENCODED_REDIRECT_URI = urllib.parse.quote_plus(REDIRECT_URI)
ENCODED_SCOPES      = urllib.parse.quote_plus(SCOPES_RAW)

# Build the base authorization URL
AUTHORIZATION_URL = (
    "https://app.hubspot.com/oauth/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={ENCODED_REDIRECT_URI}"
    r"&scope="+ENCODED_SCOPES
)

async def authorize_hubspot(user_id, org_id):
    """
    Generate the HubSpot OAuth2 URL (with state) and store the state in Redis.
    """
    state_data = {
        "state":   secrets.token_urlsafe(32),
        "user_id": user_id,
        "org_id":  org_id,
    }
    encoded_state = urllib.parse.quote_plus(json.dumps(state_data))
    # TTL = 10 minutes
    await add_key_value_redis(
        f"hubspot_state:{org_id}:{user_id}",
        json.dumps(state_data),
        expire=600,
    )
    return f"{AUTHORIZATION_URL}&state={encoded_state}"

async def oauth2callback_hubspot(request: Request):
    """
    Callback handler: validate state, exchange code for tokens, store tokens.
    """
    if request.query_params.get("error"):
        raise HTTPException(400, request.query_params.get("error"))

    code  = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(400, "Missing code or state in callback.")

    # Decode and validate state
    state_json = json.loads(urllib.parse.unquote_plus(state))
    orig_state = state_json["state"]
    user_id    = state_json["user_id"]
    org_id     = state_json["org_id"]

    saved = await get_value_redis(f"hubspot_state:{org_id}:{user_id}")
    if not saved or orig_state != json.loads(saved).get("state"):
        raise HTTPException(400, "State validation failed.")

    # Exchange code for tokens
    token_url = "https://api.hubapi.com/oauth/v1/token"
    data = {
        "grant_type":    "authorization_code",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri":  REDIRECT_URI,
        "code":          code,
    }

    async with httpx.AsyncClient() as client:
        resp, _ = await asyncio.gather(
            client.post(token_url, data=data, headers={
                "Content-Type": "application/x-www-form-urlencoded"
            }),
            delete_key_redis(f"hubspot_state:{org_id}:{user_id}")
        )

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"HubSpot token exchange failed: {resp.text}")

    creds = resp.json()
    await add_key_value_redis(
        f"hubspot_credentials:{org_id}:{user_id}",
        json.dumps(creds),
        expire=600,
    )

    # Close the popup
    return HTMLResponse("""
    <html><body><script>window.close();</script></body></html>
    """)

async def get_hubspot_credentials(user_id, org_id):
    """
    Retrieve (and delete) one‑time credentials from Redis.
    """
    raw = await get_value_redis(f"hubspot_credentials:{org_id}:{user_id}")
    if not raw:
        raise HTTPException(400, "No HubSpot credentials found.")
    await delete_key_redis(f"hubspot_credentials:{org_id}:{user_id}")
    return json.loads(raw)

def create_integration_item_metadata_object(response_json) -> IntegrationItem:
    """
    Map a HubSpot CRM object into our IntegrationItem.
    """
    obj_id = response_json.get("id")
    props  = response_json.get("properties", {})

    # Derive a human‑readable name
    name = props.get("name") or \
           f"{props.get('firstname','')} {props.get('lastname','')}".strip() or \
           None

    # If 'archived' is False, use the object type; else mark as 'archived'
    obj_type = response_json.get("archived") is False and \
               response_json.get("type", "object") or "archived"

    return IntegrationItem(
        id=obj_id,
        name=name,
        type=obj_type,
        parent_id=None
    )

async def get_items_hubspot(credentials) -> list[IntegrationItem]:
    """
    Example: paginate through Contacts and return them as IntegrationItems.
    """
    creds = credentials if isinstance(credentials, dict) else json.loads(credentials)
    token = creds.get("access_token")
    if not token:
        raise HTTPException(400, "Invalid HubSpot credentials.")

    headers = {"Authorization": f"Bearer {token}"}
    url     = "https://api.hubapi.com/crm/v3/objects/contacts"
    params  = {"limit": 100, "properties": "firstname,lastname,email"}

    items: list[IntegrationItem] = []
    while url:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, f"Error fetching HubSpot items: {resp.text}")

        data = resp.json()
        for obj in data.get("results", []):
            items.append(create_integration_item_metadata_object(obj))

        # follow pagination link if present
        url     = data.get("paging", {}).get("next", {}).get("link")
        params  = None

    return items




# # slack.py

# from fastapi import Request

# async def authorize_hubspot(user_id, org_id):
#     # TODO
#     pass

# async def oauth2callback_hubspot(request: Request):
#     # TODO
#     pass

# async def get_hubspot_credentials(user_id, org_id):
#     # TODO
#     pass

# async def create_integration_item_metadata_object(response_json):
#     # TODO
#     pass

# async def get_items_hubspot(credentials):
#     # TODO
#     pass