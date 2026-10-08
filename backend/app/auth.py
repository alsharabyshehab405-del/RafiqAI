from datetime import datetime,timedelta,timezone
import hashlib,secrets,jwt
from fastapi import Depends,HTTPException
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User,RefreshToken,now
ph=PasswordHash.recommended();bearer=HTTPBearer()
def hash_password(p): return ph.hash(p)
def verify_password(p,h): return ph.verify(p,h)
def access_token(uid:int): return jwt.encode({"sub":str(uid),"type":"access","exp":datetime.now(timezone.utc)+timedelta(minutes=settings.access_token_minutes)},settings.jwt_secret,algorithm="HS256")
def new_refresh(db,user,device_name="Android"):
    raw=secrets.token_urlsafe(48);row=RefreshToken(user_id=user.id,token_hash=hashlib.sha256(raw.encode()).hexdigest(),device_name=device_name[:120],expires_at=datetime.now(timezone.utc)+timedelta(days=settings.refresh_token_days));db.add(row);db.flush();return raw
def current_user(c:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
    try:
        p=jwt.decode(c.credentials,settings.jwt_secret,algorithms=["HS256"]);
        if p.get("type")!="access": raise ValueError()
        uid=int(p["sub"])
    except Exception: raise HTTPException(401,"جلسة غير صالحة")
    u=db.get(User,uid)
    if not u or u.disabled_at: raise HTTPException(401,"الحساب غير متاح")
    return u
def require_admin(user=Depends(current_user)):
    if not user.is_admin: raise HTTPException(403,"صلاحية الإدارة مطلوبة")
    return user
