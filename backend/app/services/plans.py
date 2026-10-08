from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy import select
from ..models import Subscription

@dataclass(frozen=True)
class PlanLimits:
    name:str; messages_per_day:int; max_file_bytes:int; web_search:bool; memory:bool; voice:bool; images:bool; priority:int
PLANS={
 "free":PlanLimits("free",30,0,False,False,True,False,0),
 "pro":PlanLimits("pro",500,15728640,True,True,True,True,1),
 "premium":PlanLimits("premium",3000,52428800,True,True,True,True,2),
}

def active_plan(db,user_id:int):
    now=datetime.now(timezone.utc)
    rows=db.scalars(select(Subscription).where(Subscription.user_id==user_id).order_by(Subscription.updated_at.desc())).all()
    for s in rows:
        exp=s.expires_at
        if s.state in {"SUBSCRIPTION_STATE_ACTIVE","SUBSCRIPTION_STATE_IN_GRACE_PERIOD","SUBSCRIPTION_STATE_CANCELED","active","grace"} and (exp is None or (exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp)>now): return s.plan
    return "free"

def limits(db,user_id:int): return PLANS.get(active_plan(db,user_id),PLANS["free"])
