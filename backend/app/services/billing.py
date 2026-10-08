import hashlib
from datetime import datetime,timezone
from ..config import settings

def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()
def product_plan(product):
    if product in [x.strip() for x in settings.pro_product_ids.split(",") if x.strip()]: return "pro"
    if product in [x.strip() for x in settings.premium_product_ids.split(",") if x.strip()]: return "premium"
    return None

def verify_google_subscription(product_id,purchase_token):
    if not settings.google_play_service_account_json: raise RuntimeError("Google Play verification is not configured")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    import json
    creds=service_account.Credentials.from_service_account_info(json.loads(settings.google_play_service_account_json),scopes=["https://www.googleapis.com/auth/androidpublisher"])
    api=build("androidpublisher","v3",credentials=creds,cache_discovery=False)
    return api.purchases().subscriptionsv2().get(packageName=settings.google_play_package_name,token=purchase_token).execute()

def expiry_from_payload(payload):
    items=payload.get("lineItems",[])
    vals=[]
    for item in items:
        if item.get("expiryTime"):
            vals.append(datetime.fromisoformat(item["expiryTime"].replace("Z","+00:00")))
    return max(vals) if vals else None
