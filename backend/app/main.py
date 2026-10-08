from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import base64, hashlib, json, logging, secrets, time
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse
from sqlalchemy import select, desc, func, or_
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .config import settings
from .db import engine, get_db
from .models import User, RefreshToken, Conversation, Message, Task, Memory, Subscription, FileAsset, DeviceToken, AnalyticsEvent, AuditLog, Project, ProjectMemory, ProjectConversation, AgentRun, AgentStep, ResearchRun, ResearchSource, Artifact, Automation, UsageLedger, VectorChunk, now
from .schemas import *
from .auth import *
from .ai import chat, stream_chat
from .services.memory import safe_memory, memory_context
from .services.plans import active_plan, limits
from .services.search import web_search
from .services.storage import object_key, sha256, validate_upload, put_object, signed_url, extract_text, scan_bytes, delete_object
from .services.billing import token_hash, product_plan, verify_google_subscription, expiry_from_payload
from .services.ai_platform import router
from .services.agents import AgentEngine, AgentStepSpec, AgentLimits
from .services.research import deep_research
from .services.tools import search_tool, fetch_tool
from .services.rag import chunk_text, rank_chunks, source_id, lexical_score, embed, semantic_status, QdrantStore, reindex_file
from .services.cost import usage_from_provider
async def enqueue_worker(function_name, *args):
    from arq import create_pool
    from arq.connections import RedisSettings
    pool=await create_pool(RedisSettings.from_dsn(settings.rate_limit_storage_uri if settings.rate_limit_storage_uri.startswith("redis://") else "redis://redis:6379/1"))
    try: return await pool.enqueue_job(function_name,*args)
    finally: await pool.close()
from .services.safety import inspect_input, validate_tool_url
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    if settings.sentry_dsn: sentry_sdk.init(dsn=settings.sentry_dsn,integrations=[FastApiIntegration()],send_default_pii=False,traces_sample_rate=0.05,environment=settings.app_env)
except ImportError: sentry_sdk=None
logging.basicConfig(level=getattr(logging,settings.log_level.upper(),logging.INFO),format="%(asctime)s %(levelname)s %(name)s %(message)s")
log=logging.getLogger("rafiq")
limiter=Limiter(key_func=get_remote_address,default_limits=[f"{settings.rate_limit_per_minute}/minute"],storage_uri=settings.rate_limit_storage_uri)
@asynccontextmanager
async def lifespan(app): yield
app=FastAPI(title="Rafiq AI API",version="4.0.0",lifespan=lifespan)
app.state.limiter=limiter
origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=["GET","POST","PATCH","PUT","DELETE"],allow_headers=["Authorization","Content-Type","X-Request-ID"])
@app.middleware("http")
async def security_and_observability(request,call_next):
    request_id=request.headers.get("X-Request-ID") or secrets.token_hex(12); started=time.perf_counter()
    try: response=await call_next(request)
    except Exception:
        log.exception("request_failed request_id=%s path=%s",request_id,request.url.path); raise
    if response.status_code >= 500:
        try:
            with Session(engine) as db: db.add(AuditLog(action="http_error",metadata_json=json.dumps({"path":request.url.path,"status":response.status_code}))); db.commit()
        except Exception: pass
    response.headers.update({"X-Request-ID":request_id,"X-Content-Type-Options":"nosniff","X-Frame-Options":"DENY","Referrer-Policy":"no-referrer","Cache-Control":"no-store","Permissions-Policy":"camera=(),geolocation=(),microphone=()","Strict-Transport-Security":"max-age=31536000; includeSubDomains"})
    log.info("request request_id=%s method=%s path=%s status=%s ms=%.1f",request_id,request.method,request.url.path,response.status_code,(time.perf_counter()-started)*1000)
    return response
@app.exception_handler(RateLimitExceeded)
async def rate_handler(request,exc):
    with Session(engine) as db: db.add(AuditLog(action="rate_limit",metadata_json=json.dumps({"path":request.url.path}))); db.commit()
    return JSONResponse(status_code=429,content={"detail":"تم تجاوز حد الطلبات"},headers={"Retry-After":"60"})

@app.get("/ai/models")
def ai_models(user=Depends(current_user)):
    return [{"name":p.name,"provider":p.provider,"context_window":p.context_tokens,"vision":p.vision,"audio":p.audio,"tool_calling":p.tool_calling,"structured_output":p.structured_output,"reasoning":p.reasoning,"streaming":p.streaming,"input_price":p.input_cost_per_1k,"output_price":p.output_cost_per_1k,"quality":p.quality,"speed":p.speed,"reliability":p.reliability} for p in router.profiles]
@app.get("/ai/route")
def ai_route(task:str="chat",plan:str="free",preference:str="balanced",user=Depends(current_user)):
    p,reason=router.route(plan=plan,task=task,preference=preference)
    return {"model":p.name,"provider":p.provider,"reason":reason}

@app.get("/ai/safety")
def ai_safety(user=Depends(current_user)):
    return {"gateway":["input_security","moderation","model","tool_security","output_validation","pii_detection","policy_validation"],"prompt_injection_detection":True,"secret_redaction":True}

@app.get("/eval/status")
def eval_status(user=Depends(current_user)):
    from .services.evaluation import load_golden, evaluate_text, aggregate
    path="evals/golden.json"
    cases=load_golden(path)
    results=[evaluate_text(c,c.expected) for c in cases]
    return aggregate(results)
@app.get("/health")
def health(): return {"status":"ok","service":settings.service_name,"version":"4.0.0"}
@app.get("/ready")
def ready(db:Session=Depends(get_db)):
    db.execute(select(1)); return {"status":"ready"}
@app.get("/metrics",response_class=PlainTextResponse)
def metrics(db:Session=Depends(get_db)):
    vals={"users":db.scalar(select(func.count(User.id))) or 0,"conversations":db.scalar(select(func.count(Conversation.id))) or 0,"messages":db.scalar(select(func.count(Message.id))) or 0,"tasks":db.scalar(select(func.count(Task.id))) or 0,"memories":db.scalar(select(func.count(Memory.id))) or 0,"files":db.scalar(select(func.count(FileAsset.id))) or 0}
    return "\n".join(f"rafiq_{k} {v}" for k,v in vals.items())+"\n"
def audit(db,action,actor=None,target=None,metadata=None): db.add(AuditLog(actor_user_id=actor,target_user_id=target,action=action,metadata_json=json.dumps(metadata or {},ensure_ascii=False)))
def plan_for(db,user): return active_plan(db,user.id)
def profile_out(db,u): return ProfileOut(email=u.email,display_name=u.display_name,locale=u.locale,memory_enabled=u.memory_enabled,analytics_enabled=u.analytics_enabled,plan=plan_for(db,u),created_at=u.created_at.isoformat())
@app.post("/auth/register",response_model=TokenResponse)
@limiter.limit("5/minute")
def register(data:AuthRequest,request:Request,db:Session=Depends(get_db)):
    e=str(data.email).lower()
    if db.scalar(select(User).where(User.email==e)): raise HTTPException(409,"البريد مستخدم بالفعل")
    admin=False
    u=User(email=e,password_hash=hash_password(data.password),is_admin=admin);db.add(u);db.flush();rt=new_refresh(db,u);at=access_token(u.id);audit(db,"register",u.id,u.id);db.commit();return TokenResponse(access_token=at,refresh_token=rt)
@app.post("/auth/login",response_model=TokenResponse)
@limiter.limit("10/minute")
def login(data:AuthRequest,request:Request,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if not u or u.disabled_at or not verify_password(data.password,u.password_hash): raise HTTPException(401,"بيانات الدخول غير صحيحة")
    rt=new_refresh(db,u,request.headers.get("X-Device-Name","Android"));at=access_token(u.id);audit(db,"login",u.id,u.id);db.commit();return TokenResponse(access_token=at,refresh_token=rt)
@app.post("/auth/refresh",response_model=TokenResponse)
@limiter.limit("30/minute")
def refresh(data:RefreshBody,request:Request,db:Session=Depends(get_db)):
    h=hashlib.sha256(data.refresh_token.encode()).hexdigest();row=db.scalar(select(RefreshToken).where(RefreshToken.token_hash==h))
    if not row: raise HTTPException(401,"جلسة منتهية")
    exp=row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at
    if row.revoked_at or exp<=datetime.now(timezone.utc) or row.user.disabled_at: raise HTTPException(401,"جلسة منتهية")
    row.revoked_at=now();rt=new_refresh(db,row.user,row.device_name);at=access_token(row.user_id);db.commit();return TokenResponse(access_token=at,refresh_token=rt)
@app.post("/auth/logout")
def logout(data:RefreshBody,db:Session=Depends(get_db)):
    row=db.scalar(select(RefreshToken).where(RefreshToken.token_hash==hashlib.sha256(data.refresh_token.encode()).hexdigest()))
    if row: row.revoked_at=now();db.commit()
    return {"ok":True}
@app.post("/auth/logout-all")
def logout_all(user=Depends(current_user),db:Session=Depends(get_db)):
    db.query(RefreshToken).filter(RefreshToken.user_id==user.id,RefreshToken.revoked_at.is_(None)).update({RefreshToken.revoked_at:now()});audit(db,"logout_all",user.id,user.id);db.commit();return {"ok":True}
@app.get("/auth/sessions",response_model=list[SessionOut])
def sessions(user=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(RefreshToken).where(RefreshToken.user_id==user.id).order_by(desc(RefreshToken.created_at))).all()
    return [SessionOut(id=x.id,device_name=x.device_name,created_at=x.created_at.isoformat(),expires_at=x.expires_at.isoformat(),revoked=x.revoked_at is not None) for x in rows]
@app.delete("/auth/sessions/{sid}")
def revoke_session(sid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(RefreshToken).where(RefreshToken.id==sid,RefreshToken.user_id==user.id))
    if not row: raise HTTPException(404,"الجلسة غير موجودة")
    row.revoked_at=now();db.commit();return {"ok":True}
@app.patch("/auth/password")
def change_password(data:dict,user=Depends(current_user),db:Session=Depends(get_db)):
    old=str(data.get("old_password",""));new=str(data.get("new_password",""))
    if len(new)<8 or len(new)>128 or not verify_password(old,user.password_hash): raise HTTPException(400,"كلمة المرور غير صحيحة أو غير صالحة")
    user.password_hash=hash_password(new);db.query(RefreshToken).filter(RefreshToken.user_id==user.id).update({RefreshToken.revoked_at:now()});db.commit();return {"ok":True}
@app.patch("/auth/email")
def change_email(data:dict,user=Depends(current_user),db:Session=Depends(get_db)):
    email=str(data.get("email","")).strip().lower();password=str(data.get("password",""))
    if not verify_password(password,user.password_hash): raise HTTPException(400,"بيانات غير صحيحة")
    if db.scalar(select(User).where(User.email==email,User.id!=user.id)): raise HTTPException(409,"البريد مستخدم بالفعل")
    user.email=email;user.updated_at=now();db.commit();return {"ok":True,"email":email}
@app.delete("/auth/me")
async def delete_me(user=Depends(current_user),db:Session=Depends(get_db)):
    files=db.scalars(select(FileAsset).where(FileAsset.user_id==user.id)).all()
    projects=db.scalars(select(Project).where(Project.user_id==user.id)).all()
    for f in files:
        try: delete_object(f.object_key)
        except Exception: log.warning("object_delete_failed file=%s",f.id)
    if settings.qdrant_url:
        store=QdrantStore()
        for project in projects:
            try: await store.delete_collection(f"{settings.qdrant_collection_prefix}_project_{project.id}")
            except Exception: log.warning("vector_project_delete_failed project=%s",project.id)
    audit(db,"delete_account",user.id,user.id,{"files":len(files),"projects":len(projects),"vector_cleanup":bool(settings.qdrant_url)})
    db.delete(user); db.commit()
    return {"deleted":True,"object_storage_processed":True,"vector_cleanup_requested":bool(settings.qdrant_url),"projects_processed":len(projects)}
@app.get("/me",response_model=ProfileOut)
def profile(user=Depends(current_user),db:Session=Depends(get_db)): return profile_out(db,user)
@app.patch("/me",response_model=ProfileOut)
def update_profile(data:ProfileUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    if data.display_name is not None: user.display_name=data.display_name.strip()
    user.locale=data.locale
    if data.memory_enabled is not None:user.memory_enabled=data.memory_enabled
    if data.analytics_enabled is not None:user.analytics_enabled=data.analytics_enabled
    user.updated_at=now();db.commit();db.refresh(user);return profile_out(db,user)
def page_cursor(rows,limit): return base64.urlsafe_b64encode(str(rows[-1].id).encode()).decode() if rows and len(rows)==limit else None
def decode_cursor(cursor):
    try:return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:raise HTTPException(400,"cursor غير صالح")
def conv_out(x): return ConversationOut(id=x.id,title=x.title,pinned=x.pinned,updated_at=x.updated_at.isoformat())
def msg_out(x): return MessageOut(id=x.id,conversation_id=x.conversation_id,role=x.role,content=x.content,created_at=x.created_at.isoformat(),model=x.model,input_tokens=x.input_tokens,output_tokens=x.output_tokens)
def task_out(x): return TaskOut(id=x.id,title=x.title,description=x.description,completed=x.completed,due_at=x.due_at.isoformat() if x.due_at else None,priority=x.priority,recurrence=x.recurrence,updated_at=x.updated_at.isoformat())
def parse_due(value):
    if not value:return None
    try:return datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:raise HTTPException(400,"due_at غير صالح")
@app.get("/conversations",response_model=Page[ConversationOut])
def conversations(limit:int=50,cursor:str|None=None,user=Depends(current_user),db:Session=Depends(get_db)):
    limit=max(1,min(limit,100));q=select(Conversation).where(Conversation.user_id==user.id)
    if cursor:q=q.where(Conversation.id<decode_cursor(cursor))
    q=q.order_by(desc(Conversation.pinned),desc(Conversation.updated_at),desc(Conversation.id)).limit(limit);rows=db.scalars(q).all();return Page(items=[conv_out(x) for x in rows],next_cursor=page_cursor(rows,limit))
@app.post("/conversations",response_model=ConversationOut)
def create_conv(data:ConversationCreate,user=Depends(current_user),db:Session=Depends(get_db)):
    c=Conversation(user_id=user.id,title=data.title.strip(),updated_at=now());db.add(c);db.commit();db.refresh(c);return conv_out(c)
@app.patch("/conversations/{cid}",response_model=ConversationOut)
def rename(cid:int,data:ConversationUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    c=db.scalar(select(Conversation).where(Conversation.id==cid,Conversation.user_id==user.id))
    if not c:raise HTTPException(404,"المحادثة غير موجودة")
    c.title=data.title.strip();
    if data.pinned is not None:c.pinned=data.pinned
    c.updated_at=now();db.commit();return conv_out(c)
@app.delete("/conversations/{cid}")
def del_conv(cid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    c=db.scalar(select(Conversation).where(Conversation.id==cid,Conversation.user_id==user.id))
    if not c:raise HTTPException(404,"المحادثة غير موجودة")
    db.delete(c);db.commit();return {"deleted":True}
@app.get("/conversations/{cid}/messages",response_model=Page[MessageOut])
def msgs(cid:int,limit:int=50,cursor:str|None=None,user=Depends(current_user),db:Session=Depends(get_db)):
    c=db.scalar(select(Conversation).where(Conversation.id==cid,Conversation.user_id==user.id))
    if not c:raise HTTPException(404,"المحادثة غير موجودة")
    mlimit=max(1,min(limit,100));mq=select(Message).where(Message.conversation_id==cid)
    if cursor:mq=mq.where(Message.id>decode_cursor(cursor))
    rows=db.scalars(mq.order_by(Message.id).limit(mlimit)).all();return Page(items=[msg_out(x) for x in rows],next_cursor=page_cursor(rows,mlimit))
@app.get("/search",response_model=list[SearchResult])
@limiter.limit("30/minute")
def search(q:str,request:Request,user=Depends(current_user),db:Session=Depends(get_db)):
    q=q.strip()
    if len(q)<2:raise HTTPException(400,"البحث يحتاج حرفين على الأقل")
    pattern=f"%{q[:120]}%";rows=db.execute(select(Message,Conversation.title).join(Conversation,Conversation.id==Message.conversation_id).where(Conversation.user_id==user.id,Message.content.ilike(pattern)).order_by(desc(Message.id)).limit(50)).all()
    return [SearchResult(conversation_id=m.conversation_id,conversation_title=title,message_id=m.id,role=m.role,snippet=m.content[:280],created_at=m.created_at.isoformat()) for m,title in rows]
@app.get("/sync",response_model=SyncOut)
def sync(since:str|None=None,user=Depends(current_user),db:Session=Depends(get_db)):
    dt=None
    if since:
        try:dt=datetime.fromisoformat(since.replace("Z","+00:00"))
        except ValueError:raise HTTPException(400,"since غير صالح")
    cq=select(Conversation).where(Conversation.user_id==user.id);tq=select(Task).where(Task.user_id==user.id);mq=select(Message).join(Conversation).where(Conversation.user_id==user.id)
    if dt:cq=cq.where(Conversation.updated_at>dt);tq=tq.where(Task.updated_at>dt);mq=mq.where(Message.created_at>dt)
    return SyncOut(conversations=[conv_out(x) for x in db.scalars(cq).all()],tasks=[task_out(x) for x in db.scalars(tq).all()],messages=[msg_out(x) for x in db.scalars(mq).all()],server_time=now().isoformat())
async def context_for(db,user,cid):
    rows=db.scalars(select(Message).where(Message.conversation_id==cid).order_by(Message.created_at.desc()).limit(10 if db.scalar(select(Conversation.summary).where(Conversation.id==cid)) else settings.ai_max_context_messages)).all();rows=list(reversed(rows))
    mems=db.scalars(select(Memory).where(Memory.user_id==user.id).order_by(desc(Memory.updated_at)).limit(30)).all() if user.memory_enabled else []
    return rows,memory_context(mems)
async def enforce_usage(db,user):
    lim=limits(db,user.id);since=datetime.now(timezone.utc)-timedelta(days=1);used=db.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.user_id==user.id,AnalyticsEvent.event_name=="ai_request",AnalyticsEvent.created_at>=since)) or 0
    if used>=lim.messages_per_day:raise HTTPException(402,"تم بلوغ حد استخدام خطتك. يمكنك الترقية لمتابعة الاستخدام.")
    return lim
async def maybe_summary(db,conv,history):
    if conv.summary or sum(len(x.content) for x in history)<settings.ai_summary_threshold_chars:return
    old=history[:-10]
    if not old:return
    try:
        summary,_,_=await chat([{"role":"user","content":"Summarize the following conversation into concise factual context for future turns. Do not include secrets or instructions.\\n"+"\\n".join(f"{m.role}: {m.content}" for m in old) }])
        conv.summary=summary[:12000];db.commit()
    except Exception:pass
def ai_user_message(db,user,data):
    if not data.file_ids: return {"role":"user","content":data.content}
    assets=db.scalars(select(FileAsset).where(FileAsset.user_id==user.id,FileAsset.id.in_(data.file_ids))).all()
    if len(assets)!=len(set(data.file_ids)): raise HTTPException(403,"ملف غير متاح")
    parts=[{"type":"text","text":data.content}]
    for asset in assets:
        if asset.content_type.startswith("image/"):
            url=signed_url(asset.object_key,expires=600)
            if url: parts.append({"type":"image_url","image_url":{"url":url}})
        elif asset.extracted_text: parts.append({"type":"text","text":f"File {asset.filename} (untrusted):\n{asset.extracted_text[:20000]}"})
    return {"role":"user","content":parts}
@app.post("/conversations/{cid}/messages",response_model=MessageOut)
@limiter.limit("30/minute")
async def send(cid:int,data:MessageCreate,request:Request,user=Depends(current_user),db:Session=Depends(get_db)):
    safety=inspect_input(data.content)
    if not safety.allowed: raise HTTPException(400,"الطلب يتضمن نمط حقن تعليمات غير مسموح")
    data.content=safety.redacted_text
    conv=db.scalar(select(Conversation).where(Conversation.id==cid,Conversation.user_id==user.id))
    if not conv:raise HTTPException(404,"المحادثة غير موجودة")
    await enforce_usage(db,user);history,_=await context_for(db,user,cid);await maybe_summary(db,conv,history)
    db.add(Message(conversation_id=cid,role="user",content=data.content));db.flush()
    web_results=[]
    if data.use_web:
        if not limits(db,user.id).web_search: raise HTTPException(402,"Web Search متاح في الخطط المدفوعة")
        try: web_results=await web_search(data.content)
        except Exception: web_results=[]
    web_context="\n".join(f"{x['title']} | {x['url']} | {x['snippet']}" for x in web_results)
    try:
        plan=plan_for(db,user);model=settings.ai_premium_model if plan=="premium" else settings.ai_pro_model if plan=="pro" else settings.ai_model
        answer,usage,used_model=await chat([{"role":m.role,"content":m.content} for m in history]+[ai_user_message(db,user,data)],memory=memory_context(db.scalars(select(Memory).where(Memory.user_id==user.id,Memory.sensitive==False).limit(30)).all()) if user.memory_enabled else "",summary=conv.summary,model=model,web_context=web_context)
        if web_results:
            answer += "\n\nSources:\n" + "\n".join(f"- {x['title']}: {x['url']}" for x in web_results)
    except Exception:db.rollback();raise HTTPException(502,"تعذر الاتصال بخدمة الذكاء الاصطناعي")
    a=Message(conversation_id=cid,role="assistant",content=answer,model=used_model,input_tokens=int(usage.get("prompt_tokens",0) or 0),output_tokens=int(usage.get("completion_tokens",0) or 0))
    db.add(a);conv.updated_at=now();db.add(AnalyticsEvent(user_id=user.id,event_name="ai_request",properties_json=json.dumps({"model":used_model,"input_tokens":a.input_tokens,"output_tokens":a.output_tokens},ensure_ascii=False)))
    u=usage_from_provider(usage);db.add(UsageLedger(user_id=user.id,feature="chat",model=used_model,input_tokens=u.input_tokens,output_tokens=u.output_tokens,cost_usd=u.cost_usd));db.commit();db.refresh(a);return msg_out(a)
@app.post("/conversations/{cid}/messages/stream")
@limiter.limit("15/minute")
async def send_stream(cid:int,data:MessageCreate,request:Request,user=Depends(current_user),db:Session=Depends(get_db)):
    safety=inspect_input(data.content)
    if not safety.allowed: raise HTTPException(400,"الطلب يتضمن نمط حقن تعليمات غير مسموح")
    data.content=safety.redacted_text
    conv=db.scalar(select(Conversation).where(Conversation.id==cid,Conversation.user_id==user.id))
    if not conv:raise HTTPException(404,"المحادثة غير موجودة")
    await enforce_usage(db,user);history,_=await context_for(db,user,cid)
    web_results=[]
    if data.use_web:
        if not limits(db,user.id).web_search: raise HTTPException(402,"Web Search متاح في الخطط المدفوعة")
        try: web_results=await web_search(data.content)
        except Exception: web_results=[]
    web_context="\n".join(f"{x['title']} | {x['url']} | {x['snippet']}" for x in web_results)
    db.add(Message(conversation_id=cid,role="user",content=data.content));db.commit()
    plan=plan_for(db,user);model=settings.ai_premium_model if plan=="premium" else settings.ai_pro_model if plan=="pro" else settings.ai_model
    async def generate():
        chunks=[]
        try:
            async for chunk in stream_chat([{"role":m.role,"content":m.content} for m in history]+[ai_user_message(db,user,data)],memory=memory_context(db.scalars(select(Memory).where(Memory.user_id==user.id,Memory.sensitive==False).limit(30)).all()) if user.memory_enabled else "",summary=conv.summary,model=model,web_context=web_context):
                chunks.append(chunk);yield f"data: {json.dumps({'type':'delta','text':chunk},ensure_ascii=False)}\n\n"
            answer="".join(chunks)
            if web_results:
                answer += "\n\nSources:\n" + "\n".join(f"- {x['title']}: {x['url']}" for x in web_results)
                yield f"data: {json.dumps({'type':'sources','items':web_results},ensure_ascii=False)}\n\n"
            with Session(engine) as s:
                c=s.scalar(select(Conversation).where(Conversation.id==cid,Conversation.user_id==user.id));
                if c:s.add(Message(conversation_id=cid,role="assistant",content=answer,model=model));c.updated_at=now();s.add(AnalyticsEvent(user_id=user.id,event_name="ai_request",properties_json=json.dumps({"stream":True,"output_chars":len(answer),"model":model})));s.add(UsageLedger(user_id=user.id,feature="chat_stream",model=model));s.commit()
            yield 'data: {"type":"done"}\n\n'
        except Exception:yield 'data: {"type":"error"}\n\n'
    return StreamingResponse(generate(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
@app.delete("/conversations/{cid}/messages/{mid}")
def del_msg(cid:int,mid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    m=db.scalar(select(Message).join(Conversation).where(Message.id==mid,Message.conversation_id==cid,Conversation.user_id==user.id))
    if not m:raise HTTPException(404,"الرسالة غير موجودة")
    db.delete(m);db.commit();return {"deleted":True}
@app.post("/memories/suggest")
async def suggest_memories(data:MemorySuggestionRequest,user=Depends(current_user),db:Session=Depends(get_db)):
    if not user.memory_enabled: raise HTTPException(403,"الذاكرة معطلة")
    prompt="Extract at most 3 durable, non-sensitive user preferences/facts from the text. Return JSON array only with objects {key,value,category}. Never extract passwords, tokens, health, financial, political, religious, sexual or identity-sensitive data. If none, return [].\nTEXT:\n"+data.text
    try:
        raw,_,_=await chat([{"role":"user","content":prompt}],model=settings.ai_model)
        parsed=json.loads(raw[raw.find("["):raw.rfind("]")+1])
    except Exception: return {"suggestions":[]}
    safe=[]
    for item in parsed if isinstance(parsed,list) else []:
        if isinstance(item,dict) and item.get("key") and item.get("value") and safe_memory(str(item["key"]),str(item["value"]),str(item.get("category","preference")),False): safe.append({"key":str(item["key"])[:120],"value":str(item["value"])[:3000],"category":str(item.get("category","preference"))[:40]})
    return {"suggestions":safe[:3]}
@app.get("/memories",response_model=list[MemoryOut])
def memories(user=Depends(current_user),db:Session=Depends(get_db)):
    return [MemoryOut(id=m.id,key=m.key,value=m.value,category=m.category,sensitive=m.sensitive,created_at=m.created_at.isoformat(),updated_at=m.updated_at.isoformat()) for m in db.scalars(select(Memory).where(Memory.user_id==user.id).order_by(desc(Memory.updated_at))).all()]
@app.post("/memories",response_model=MemoryOut)
def create_memory(data:MemoryCreate,user=Depends(current_user),db:Session=Depends(get_db)):
    if not user.memory_enabled:raise HTTPException(403,"الذاكرة معطلة")
    if not safe_memory(data.key,data.value,data.category,data.sensitive):raise HTTPException(400,"لا يمكن تخزين هذه المعلومة في الذاكرة")
    m=db.scalar(select(Memory).where(Memory.user_id==user.id,Memory.key==data.key));
    if m:m.value=data.value;m.category=data.category;m.sensitive=False;m.updated_at=now()
    else:m=Memory(user_id=user.id,key=data.key,value=data.value,category=data.category,sensitive=False);db.add(m)
    db.commit();db.refresh(m);return MemoryOut(id=m.id,key=m.key,value=m.value,category=m.category,sensitive=m.sensitive,created_at=m.created_at.isoformat(),updated_at=m.updated_at.isoformat())
@app.patch("/memories/{mid}",response_model=MemoryOut)
def update_memory(mid:int,data:MemoryUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    m=db.scalar(select(Memory).where(Memory.id==mid,Memory.user_id==user.id));
    if not m:raise HTTPException(404,"الذاكرة غير موجودة")
    if not safe_memory(m.key,data.value,data.category,data.sensitive):raise HTTPException(400,"لا يمكن تخزين هذه المعلومة في الذاكرة")
    m.value=data.value;m.category=data.category;m.sensitive=False;m.updated_at=now();db.commit();return MemoryOut(id=m.id,key=m.key,value=m.value,category=m.category,sensitive=m.sensitive,created_at=m.created_at.isoformat(),updated_at=m.updated_at.isoformat())
@app.delete("/memories/{mid}")
def delete_memory(mid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    m=db.scalar(select(Memory).where(Memory.id==mid,Memory.user_id==user.id));
    if not m:raise HTTPException(404,"الذاكرة غير موجودة")
    db.delete(m);db.commit();return {"deleted":True}
@app.put("/memory/settings")
def memory_settings(data:MemorySettings,user=Depends(current_user),db:Session=Depends(get_db)):
    user.memory_enabled=data.enabled;user.updated_at=now();db.commit();return {"enabled":user.memory_enabled}
@app.get("/web-search",response_model=WebSearchOut)
@limiter.limit("10/minute")
async def search_web(q:str,request:Request,user=Depends(current_user),db:Session=Depends(get_db)):
    if not limits(db,user.id).web_search:raise HTTPException(402,"Web Search متاح في الخطط المدفوعة")
    if len(q.strip())<2:raise HTTPException(400,"استعلام قصير")
    try:r=await web_search(q.strip());db.add(AnalyticsEvent(user_id=user.id,event_name="web_search",properties_json=json.dumps({"length":len(q)},ensure_ascii=False)));db.commit();return WebSearchOut(query=q.strip(),results=[SearchWebResult(**x) for x in r])
    except Exception:raise HTTPException(502,"تعذر تنفيذ البحث")
@app.post("/files",response_model=FileOut)
@limiter.limit("10/minute")
async def upload_file(request:Request,file:UploadFile=File(...),user=Depends(current_user),db:Session=Depends(get_db),conversation_id:int|None=None):
    lim=limits(db,user.id)
    if lim.max_file_bytes<=0:raise HTTPException(402,"الملفات متاحة في Pro وPremium")
    data=await file.read()
    try:validate_upload(file.filename or "file",file.content_type or "application/octet-stream",data);scan_bytes(data)
    except ValueError as e:raise HTTPException(400,str(e))
    key=object_key(user.id,file.filename or "file");put_object(key,data,file.content_type or "application/octet-stream");text=extract_text(file.filename or "file",file.content_type or "",data)
    asset=FileAsset(user_id=user.id,conversation_id=conversation_id,object_key=key,filename=(file.filename or "file")[:255],content_type=file.content_type or "application/octet-stream",size_bytes=len(data),sha256=sha256(data),extracted_text=text,status="ready");db.add(asset);db.commit();db.refresh(asset)
    return FileOut(id=asset.id,filename=asset.filename,content_type=asset.content_type,size_bytes=asset.size_bytes,status=asset.status,created_at=asset.created_at.isoformat(),download_url=signed_url(key))
@app.get("/files",response_model=list[FileOut])
def files(user=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(FileAsset).where(FileAsset.user_id==user.id).order_by(desc(FileAsset.created_at))).all();return [FileOut(id=x.id,filename=x.filename,content_type=x.content_type,size_bytes=x.size_bytes,status=x.status,created_at=x.created_at.isoformat(),download_url=signed_url(x.object_key)) for x in rows]
@app.delete("/files/{fid}")
async def delete_file(fid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    x=db.scalar(select(FileAsset).where(FileAsset.id==fid,FileAsset.user_id==user.id));
    if not x: raise HTTPException(404,"الملف غير موجود")
    project_ids=[r[0] for r in db.execute(select(VectorChunk.project_id).where(VectorChunk.file_id==fid,VectorChunk.project_id.is_not(None)).distinct()).all()]
    delete_object(x.object_key)
    if settings.qdrant_url:
        store=QdrantStore()
        for pid in project_ids:
            try: await store.delete_points(f"{settings.qdrant_collection_prefix}_project_{pid}",file_id=fid,project_id=pid)
            except Exception as exc: raise HTTPException(502,"تعذر تنظيف الفهرس المتجهي") from exc
    db.query(VectorChunk).filter(VectorChunk.file_id==fid).delete(synchronize_session=False)
    db.delete(x); db.commit(); return {"deleted":True,"vector_cleanup":bool(settings.qdrant_url)}
@app.get("/tasks",response_model=list[TaskOut])
def tasks(user=Depends(current_user),db:Session=Depends(get_db)): return [task_out(x) for x in db.scalars(select(Task).where(Task.user_id==user.id).order_by(desc(Task.updated_at))).all()]
@app.post("/tasks",response_model=TaskOut)
def add_task(data:TaskCreate,user=Depends(current_user),db:Session=Depends(get_db)):
    if data.priority not in {"low","normal","high","urgent"}:raise HTTPException(400,"أولوية غير صالحة")
    t=Task(user_id=user.id,title=data.title.strip(),description=data.description,due_at=parse_due(data.due_at),priority=data.priority,recurrence=data.recurrence,updated_at=now());db.add(t);db.commit();db.refresh(t);return task_out(t)
@app.patch("/tasks/{tid}",response_model=TaskOut)
def update_task(tid:int,data:TaskUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    t=db.scalar(select(Task).where(Task.id==tid,Task.user_id==user.id));
    if not t:raise HTTPException(404,"المهمة غير موجودة")
    values=data.model_dump(exclude_unset=True)
    if "due_at" in values:values["due_at"]=parse_due(values["due_at"])
    if values.get("priority") and values["priority"] not in {"low","normal","high","urgent"}:raise HTTPException(400,"أولوية غير صالحة")
    for k,v in values.items():setattr(t,k,v)
    t.updated_at=now();db.commit();return task_out(t)
@app.delete("/tasks/{tid}")
def del_task(tid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    t=db.scalar(select(Task).where(Task.id==tid,Task.user_id==user.id));
    if not t:raise HTTPException(404,"المهمة غير موجودة")
    db.delete(t);db.commit();return {"deleted":True}
@app.post("/billing/verify",response_model=EntitlementOut)
@limiter.limit("10/minute")
def verify_purchase(data:PurchaseVerify,request:Request,user=Depends(current_user),db:Session=Depends(get_db)):
    plan=product_plan(data.product_id)
    if not plan:raise HTTPException(400,"منتج غير معروف")
    try:payload=verify_google_subscription(data.product_id,data.purchase_token)
    except Exception:raise HTTPException(502,"تعذر التحقق من Google Play")
    state=payload.get("subscriptionState","");exp=expiry_from_payload(payload);active=state in {"SUBSCRIPTION_STATE_ACTIVE","SUBSCRIPTION_STATE_IN_GRACE_PERIOD","SUBSCRIPTION_STATE_CANCELED"} and exp and exp>datetime.now(timezone.utc)
    products={x.get("productId") for x in payload.get("lineItems",[]) if x.get("productId")}
    if data.product_id not in products: raise HTTPException(400,"المنتج لا يطابق عملية الشراء")
    row=db.scalar(select(Subscription).where(Subscription.purchase_token_hash==token_hash(data.purchase_token)))
    if row and row.user_id!=user.id: raise HTTPException(409,"عملية الشراء مرتبطة بحساب آخر")
    if not row:row=Subscription(user_id=user.id,product_id=data.product_id,purchase_token_hash=token_hash(data.purchase_token));db.add(row)
    row.plan=plan;row.state=state;row.expires_at=exp;row.grace_period=state=="SUBSCRIPTION_STATE_IN_GRACE_PERIOD";row.auto_renew=bool(payload.get("lineItems",[{}])[0].get("autoRenewingPlan"));row.updated_at=now();audit(db,"subscription_verified",user.id,user.id,{"plan":plan,"state":state});db.commit()
    return EntitlementOut(plan=plan if active else "free",active=bool(active),expires_at=exp.isoformat() if exp else None,product_id=data.product_id)
@app.get("/billing/entitlement",response_model=EntitlementOut)
def entitlement(user=Depends(current_user),db:Session=Depends(get_db)):
    p=active_plan(db,user.id);row=db.scalar(select(Subscription).where(Subscription.user_id==user.id,Subscription.plan==p).order_by(desc(Subscription.updated_at))) if p!="free" else None
    return EntitlementOut(plan=p,active=p!="free",expires_at=row.expires_at.isoformat() if row and row.expires_at else None,product_id=row.product_id if row else None)
@app.post("/devices/fcm")
def register_device(data:DeviceTokenBody,user=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(DeviceToken).where(DeviceToken.token==data.token));
    if row:row.user_id=user.id;row.enabled=True;row.platform=data.platform
    else:db.add(DeviceToken(user_id=user.id,token=data.token,platform=data.platform))
    db.commit();return {"ok":True}
@app.delete("/devices/fcm/{token}")
def unregister_device(token:str,user=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(DeviceToken).where(DeviceToken.token==token,DeviceToken.user_id==user.id));
    if row:row.enabled=False;db.commit()
    return {"ok":True}
@app.post("/analytics/events")
def analytics(data:AnalyticsBody,user=Depends(current_user),db:Session=Depends(get_db)):
    if not user.analytics_enabled:return {"accepted":False}
    db.add(AnalyticsEvent(user_id=user.id,event_name=data.event_name,properties_json=json.dumps(data.properties,ensure_ascii=False)[:4000]));db.commit();return {"accepted":True}
@app.get("/export",response_model=ExportOut)
def export_data(user=Depends(current_user),db:Session=Depends(get_db)):
    convs=db.scalars(select(Conversation).where(Conversation.user_id==user.id)).all();msgs=db.scalars(select(Message).join(Conversation).where(Conversation.user_id==user.id)).all();tasks_=db.scalars(select(Task).where(Task.user_id==user.id)).all();mems=db.scalars(select(Memory).where(Memory.user_id==user.id)).all()
    return ExportOut(user_id=user.id,generated_at=now().isoformat(),profile={"email":user.email,"display_name":user.display_name,"locale":user.locale},conversations=[{"id":c.id,"title":c.title,"messages":[{"role":m.role,"content":m.content,"created_at":m.created_at.isoformat()} for m in msgs if m.conversation_id==c.id]} for c in convs],tasks=[task_out(t).model_dump() for t in tasks_],memories=[MemoryOut(id=m.id,key=m.key,value=m.value,category=m.category,sensitive=m.sensitive,created_at=m.created_at.isoformat(),updated_at=m.updated_at.isoformat()).model_dump() for m in mems],projects=[{"id":p.id,"name":p.name,"instructions":p.instructions} for p in db.scalars(select(Project).where(Project.user_id==user.id)).all()],artifacts=[artifact_out(a).model_dump() for a in db.scalars(select(Artifact).where(Artifact.user_id==user.id)).all()],research=[{"id":r.id,"query":r.query,"status":r.status,"result":json.loads(r.result_json or '{}')} for r in db.scalars(select(ResearchRun).where(ResearchRun.user_id==user.id)).all()],agent_runs=[{"id":r.id,"goal":r.goal,"status":r.status,"result":json.loads(r.result_json or '{}')} for r in db.scalars(select(AgentRun).where(AgentRun.user_id==user.id)).all()],automations=[{"id":a.id,"name":a.name,"trigger":json.loads(a.trigger_json),"action":json.loads(a.action_json),"enabled":a.enabled} for a in db.scalars(select(Automation).where(Automation.user_id==user.id)).all()],files=[{"id":f.id,"filename":f.filename,"status":f.status,"size_bytes":f.size_bytes} for f in db.scalars(select(FileAsset).where(FileAsset.user_id==user.id)).all()],usage=[{"feature":u.feature,"model":u.model,"input_tokens":u.input_tokens,"output_tokens":u.output_tokens,"cost_usd":u.cost_usd,"created_at":u.created_at.isoformat()} for u in db.scalars(select(UsageLedger).where(UsageLedger.user_id==user.id)).all()])
@app.post("/admin/bootstrap")
@limiter.limit("3/minute")
def admin_bootstrap(request:Request,user=Depends(current_user),db:Session=Depends(get_db)):
    token=request.headers.get("X-Admin-Bootstrap-Token","")
    if not settings.admin_bootstrap_token or not secrets.compare_digest(token,settings.admin_bootstrap_token): raise HTTPException(403,"غير مصرح")
    user.is_admin=True;user.updated_at=now();audit(db,"admin_bootstrap",user.id,user.id);db.commit();return {"ok":True}

@app.get("/admin/stats",response_model=AdminStats)
def admin_stats(admin=Depends(require_admin),db:Session=Depends(get_db)):
    now_=datetime.now(timezone.utc);week=now_-timedelta(days=7);active_day=now_-timedelta(days=30)
    users=db.scalar(select(func.count(User.id))) or 0;paid=db.scalar(select(func.count(func.distinct(Subscription.user_id))).where(Subscription.expires_at>now_)) or 0
    events=db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.event_name=="ai_request")).all();tokens=0;cost=0.0
    price_map={}
    for pair in settings.product_prices_usd.split(","):
        if "=" in pair:
            k,v=pair.split("=",1)
            try:price_map[k.strip()]=float(v)
            except ValueError:pass
    subs=db.scalars(select(Subscription)).all();revenue=sum(price_map.get(x.product_id,0.0) for x in subs if x.state in {"SUBSCRIPTION_STATE_ACTIVE","SUBSCRIPTION_STATE_CANCELED","SUBSCRIPTION_STATE_IN_GRACE_PERIOD"})
    for e in events:
        try:d=json.loads(e.properties_json);tokens+=int(d.get("input_tokens",0))+int(d.get("output_tokens",0));cost+=(int(d.get("input_tokens",0))/1000)*settings.ai_input_cost_per_1k+(int(d.get("output_tokens",0))/1000)*settings.ai_output_cost_per_1k
        except Exception:pass
    return AdminStats(users=users,active_users=db.scalar(select(func.count(func.distinct(AnalyticsEvent.user_id))).where(AnalyticsEvent.created_at>=active_day,AnalyticsEvent.user_id.is_not(None))) or 0,paid_users=paid,new_users_7d=db.scalar(select(func.count(User.id)).where(User.created_at>=week)) or 0,conversations=db.scalar(select(func.count(Conversation.id))) or 0,messages=db.scalar(select(func.count(Message.id))) or 0,ai_tokens=tokens,ai_cost=cost,revenue_estimate_usd=revenue,errors=db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action=="http_error")) or 0,rate_limit_events=db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action=="rate_limit")) or 0)
@app.get("/admin/analytics")
def admin_analytics(admin=Depends(require_admin),db:Session=Depends(get_db)):
    now_=datetime.now(timezone.utc)
    def distinct(days):
        return db.scalar(select(func.count(func.distinct(AnalyticsEvent.user_id))).where(AnalyticsEvent.created_at>=now_-timedelta(days=days),AnalyticsEvent.user_id.is_not(None))) or 0
    features=db.execute(select(AnalyticsEvent.event_name,func.count(AnalyticsEvent.id)).group_by(AnalyticsEvent.event_name).order_by(desc(func.count(AnalyticsEvent.id))).limit(50)).all()
    return {"dau":distinct(1),"wau":distinct(7),"mau":distinct(30),"feature_usage":{name:int(count) for name,count in features},"paid_users":db.scalar(select(func.count(func.distinct(Subscription.user_id))).where(Subscription.expires_at>now_)) or 0}
@app.get("/admin/users",response_model=list[AdminUserOut])
def admin_users(q:str="",limit:int=100,admin=Depends(require_admin),db:Session=Depends(get_db)):
    query=select(User).order_by(desc(User.created_at)).limit(max(1,min(limit,200)))
    if q.strip():query=query.where(or_(User.email.ilike(f"%{q.strip()[:120]}%"),User.display_name.ilike(f"%{q.strip()[:120]}%")))
    rows=db.scalars(query).all();return [AdminUserOut(id=u.id,email=u.email,display_name=u.display_name,plan=active_plan(db,u.id),disabled=u.disabled_at is not None,created_at=u.created_at.isoformat()) for u in rows]
@app.post("/admin/users/{uid}/disable")
def admin_disable(uid:int,admin=Depends(require_admin),db:Session=Depends(get_db)):
    u=db.get(User,uid)
    if not u:raise HTTPException(404,"المستخدم غير موجود")
    u.disabled_at=now();db.query(RefreshToken).filter(RefreshToken.user_id==uid).update({RefreshToken.revoked_at:now()});audit(db,"admin_disable",admin.id,uid);db.commit();return {"ok":True}
@app.post("/admin/users/{uid}/enable")
def admin_enable(uid:int,admin=Depends(require_admin),db:Session=Depends(get_db)):
    u=db.get(User,uid)
    if not u:raise HTTPException(404,"المستخدم غير موجود")
    u.disabled_at=None;audit(db,"admin_enable",admin.id,uid);db.commit();return {"ok":True}
@app.get("/admin/audit")
def admin_audit(limit:int=100,admin=Depends(require_admin),db:Session=Depends(get_db)):
    rows=db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(max(1,min(limit,500)))).all()
    return [{"id":x.id,"action":x.action,"actor_user_id":x.actor_user_id,"target_user_id":x.target_user_id,"metadata":json.loads(x.metadata_json),"created_at":x.created_at.isoformat()} for x in rows]

# ---------------- Next-generation platform ----------------
def project_out(p): return ProjectOut(id=p.id,name=p.name,instructions=p.instructions,created_at=p.created_at.isoformat(),updated_at=p.updated_at.isoformat())
def artifact_out(a): return ArtifactOut(id=a.id,name=a.name,kind=a.kind,content=a.content,version=a.version,project_id=a.project_id,updated_at=a.updated_at.isoformat())

def require_project(db, user_id, pid):
    p=db.scalar(select(Project).where(Project.id==pid,Project.user_id==user_id))
    if not p: raise HTTPException(404,"المشروع غير موجود")
    return p

@app.get("/projects",response_model=list[ProjectOut])
def list_projects(user=Depends(current_user),db:Session=Depends(get_db)):
    return [project_out(p) for p in db.scalars(select(Project).where(Project.user_id==user.id).order_by(desc(Project.updated_at))).all()]

@app.post("/projects",response_model=ProjectOut)
def create_project(data:ProjectCreate,user=Depends(current_user),db:Session=Depends(get_db)):
    p=Project(user_id=user.id,name=data.name.strip(),instructions=data.instructions.strip(),updated_at=now());db.add(p);db.commit();db.refresh(p);return project_out(p)

@app.patch("/projects/{pid}",response_model=ProjectOut)
def update_project(pid:int,data:ProjectUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    p=require_project(db,user.id,pid)
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(p,k,v.strip() if isinstance(v,str) else v)
    p.updated_at=now();db.commit();return project_out(p)

@app.delete("/projects/{pid}")
async def delete_project(pid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    p=require_project(db,user.id,pid)
    files=db.scalars(select(FileAsset).where(FileAsset.user_id==user.id,FileAsset.id.in_(select(VectorChunk.file_id).where(VectorChunk.project_id==pid)))).all()
    for f in files:
        try: delete_object(f.object_key)
        except Exception as exc: raise HTTPException(502,"تعذر حذف ملف المشروع من التخزين") from exc
    if settings.qdrant_url:
        try: await QdrantStore().delete_collection(f"{settings.qdrant_collection_prefix}_project_{pid}")
        except Exception as exc: raise HTTPException(502,"تعذر حذف فهرس المشروع") from exc
    db.query(VectorChunk).filter(VectorChunk.project_id==pid).delete(synchronize_session=False)
    db.query(Artifact).filter(Artifact.user_id==user.id,Artifact.project_id==pid).delete(synchronize_session=False)
    db.delete(p); db.commit(); return {"deleted":True,"files_processed":len(files),"vector_cleanup":bool(settings.qdrant_url)}

@app.post("/projects/{pid}/memory")
def add_project_memory(pid:int,data:dict,user=Depends(current_user),db:Session=Depends(get_db)):
    require_project(db,user.id,pid)
    key=str(data.get("key","")).strip()[:120]; value=str(data.get("value","")).strip()
    if not key or not value: raise HTTPException(400,"بيانات الذاكرة غير صالحة")
    row=db.scalar(select(ProjectMemory).where(ProjectMemory.project_id==pid,ProjectMemory.key==key))
    if row: row.value=value
    else: db.add(ProjectMemory(project_id=pid,key=key,value=value))
    db.commit(); row=db.scalar(select(ProjectMemory).where(ProjectMemory.project_id==pid,ProjectMemory.key==key))
    return {"id":row.id,"project_id":pid,"key":row.key,"value":row.value}

@app.delete("/projects/{pid}/memory/{mid}")
def delete_project_memory(pid:int,mid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    require_project(db,user.id,pid); row=db.scalar(select(ProjectMemory).where(ProjectMemory.id==mid,ProjectMemory.project_id==pid))
    if not row: raise HTTPException(404,"ذاكرة المشروع غير موجودة")
    db.delete(row);db.commit();return {"deleted":True}

@app.post("/projects/{pid}/conversations")
def link_project_conversation(pid:int,data:ProjectLink,user=Depends(current_user),db:Session=Depends(get_db)):
    require_project(db,user.id,pid)
    c=db.scalar(select(Conversation).where(Conversation.id==data.conversation_id,Conversation.user_id==user.id))
    if not c: raise HTTPException(404,"المحادثة غير موجودة")
    row=db.get(ProjectConversation,(pid,c.id))
    if not row: db.add(ProjectConversation(project_id=pid,conversation_id=c.id));db.commit()
    return {"linked":True}

@app.get("/projects/{pid}/context")
def project_context(pid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    p=require_project(db,user.id,pid)
    memories=db.scalars(select(ProjectMemory).where(ProjectMemory.project_id==pid)).all()
    conv_ids=[x.conversation_id for x in db.scalars(select(ProjectConversation).where(ProjectConversation.project_id==pid)).all()]
    files=db.scalars(select(FileAsset).where(FileAsset.user_id==user.id,FileAsset.id.in_(select(VectorChunk.file_id).where(VectorChunk.project_id==pid)))).all() if conv_ids or pid else []
    return {"project":project_out(p).model_dump(),"memories":[{"key":m.key,"value":m.value} for m in memories],"conversation_ids":conv_ids,"files":[{"id":f.id,"filename":f.filename} for f in files]}

@app.post("/agents/run",response_model=AgentOut)
@limiter.limit("10/minute")
async def run_agent(data:AgentRequest,request:Request,user=Depends(current_user),db:Session=Depends(get_db)):
    plan_prompt=[{"role":"user","content":f"Create a concise executable plan for this goal. Return JSON array only, each item {{name,tool,args}}. Allowed tools: {data.approved_tools}. Goal: {data.goal}"}]
    plan_profile=router.choose(active_plan(db,user.id),task="agent",preference=data.model_preference)
    try:
        plan_text,usage,model=await chat(plan_prompt,model=plan_profile.name)
        plan_json=json.loads(plan_text[plan_text.find("["):plan_text.rfind("]")+1])
    except Exception as exc:
        raise HTTPException(502,f"تعذر إنشاء خطة الوكيل: {type(exc).__name__}")
    allowed_tools=set(data.approved_tools)&{"search","fetch"}
    specs=[]
    for item in plan_json[:settings.ai_max_tool_calls]:
        tool=item.get("tool");
        if tool not in allowed_tools: continue
        specs.append(AgentStepSpec(str(item.get("name",tool)),tool,dict(item.get("args") or {})))
    idem=request.headers.get("Idempotency-Key")
    if idem:
        existing=db.scalar(select(AgentRun).where(AgentRun.user_id==user.id,AgentRun.idempotency_key==idem))
        if existing: return AgentOut(run_id=existing.id,status=existing.status,plan=json.loads(existing.plan_json or "[]"),result=json.loads(existing.result_json or "{}"))
    run_id=secrets.token_hex(16);run=AgentRun(id=run_id,user_id=user.id,goal=data.goal,status="queued",plan_json=json.dumps([s.__dict__ for s in specs],ensure_ascii=False),updated_at=now(),idempotency_key=idem,max_tokens=12000,max_tool_calls=settings.ai_max_tool_calls,max_seconds=settings.ai_max_agent_seconds);db.add(run);db.commit()
    await enqueue_worker("run_agent_job",run_id)
    return AgentOut(run_id=run_id,status="queued",plan=[s.__dict__ for s in specs],result={"queued":True})

@app.post("/agents/{run_id}/resume")
async def resume_agent(run_id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    r=db.scalar(select(AgentRun).where(AgentRun.id==run_id,AgentRun.user_id==user.id))
    if not r: raise HTTPException(404,"المهمة غير موجودة")
    if r.status not in {"paused","failed","timeout","cancelled"}: raise HTTPException(409,"المهمة ليست قابلة للاستئناف")
    r.cancel_requested=False;r.resume_requested=True;r.status="queued";r.updated_at=now();db.commit();await enqueue_worker("run_agent_job",run_id);return {"run_id":run_id,"status":"queued"}

@app.post("/research",response_model=ResearchOut)
@limiter.limit("5/minute")
async def research(data:ResearchRequest,request:Request,user=Depends(current_user),db:Session=Depends(get_db)):
    if not limits(db,user.id).web_search: raise HTTPException(402,"البحث على الويب متاح في Pro/Premium")
    run_id=secrets.token_hex(16);run=ResearchRun(id=run_id,user_id=user.id,query=data.query,status="queued",created_at=now());db.add(run);db.commit()
    await enqueue_worker("run_research_job",run_id,data.limit)
    return ResearchOut(id=run_id,query=data.query,status="queued",sources=[],result={"queued":True})
    try: result=await deep_research(data.query,data.limit)
    except Exception as exc: run.status="failed";db.commit();raise HTTPException(502,f"تعذر البحث: {type(exc).__name__}")
    sources=[]
    for item in result["sources"]:
        score=min(1.0,0.4+(0.1 if ".gov" in item["host"] or ".edu" in item["host"] else 0)+0.2*(bool(item.get("content"))))
        db.add(ResearchSource(research_id=run_id,url=item["url"],title=item.get("title",""),snippet=item.get("snippet","")[:2000],source_hash=source_id(item["url"]),quality_score=score));sources.append(item)
    run.status="completed";run.result_json=json.dumps({"source_count":len(sources)},ensure_ascii=False);db.commit()
    return ResearchOut(id=run_id,query=data.query,status=run.status,sources=sources,result={"source_count":len(sources)})

@app.get("/research/{rid}",response_model=ResearchOut)
def get_research(rid:str,user=Depends(current_user),db:Session=Depends(get_db)):
    run=db.scalar(select(ResearchRun).where(ResearchRun.id==rid,ResearchRun.user_id==user.id))
    if not run: raise HTTPException(404,"البحث غير موجود")
    sources=db.scalars(select(ResearchSource).where(ResearchSource.research_id==rid).order_by(desc(ResearchSource.quality_score))).all()
    return ResearchOut(id=rid,query=run.query,status=run.status,sources=[{"url":s.url,"title":s.title,"snippet":s.snippet,"quality_score":s.quality_score,"source_id":s.source_hash} for s in sources],result=json.loads(run.result_json or "{}"))

@app.post("/artifacts",response_model=ArtifactOut)
def create_artifact(data:ArtifactCreate,user=Depends(current_user),db:Session=Depends(get_db)):
    if data.project_id is not None: require_project(db,user.id,data.project_id)
    a=Artifact(user_id=user.id,project_id=data.project_id,name=data.name,kind=data.kind,content=data.content,updated_at=now());db.add(a);db.commit();db.refresh(a);return artifact_out(a)

@app.patch("/artifacts/{aid}",response_model=ArtifactOut)
def update_artifact(aid:int,data:ArtifactUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    a=db.scalar(select(Artifact).where(Artifact.id==aid,Artifact.user_id==user.id))
    if not a: raise HTTPException(404,"الملف غير موجود")
    a.content=data.content
    if data.name is not None:a.name=data.name
    a.version+=1;a.updated_at=now();db.commit();return artifact_out(a)

@app.get("/artifacts",response_model=list[ArtifactOut])
def list_artifacts(user=Depends(current_user),db:Session=Depends(get_db)):
    return [artifact_out(a) for a in db.scalars(select(Artifact).where(Artifact.user_id==user.id).order_by(desc(Artifact.updated_at))).all()]

@app.delete("/artifacts/{aid}")
def delete_artifact(aid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    a=db.scalar(select(Artifact).where(Artifact.id==aid,Artifact.user_id==user.id))
    if not a: raise HTTPException(404,"الملف غير موجود")
    db.delete(a);db.commit();return {"deleted":True}

@app.post("/automations",response_model=AutomationOut)
def create_automation(data:AutomationCreate,user=Depends(current_user),db:Session=Depends(get_db)):
    if data.trigger_type != "schedule": raise HTTPException(400,"نوع التشغيل غير منفذ حاليًا")
    if data.action.get("type") != "research": raise HTTPException(400,"الإجراء غير منفذ حاليًا")
    query=str(data.action.get("query") or data.name).strip()
    if not query or len(query)>1000: raise HTTPException(400,"استعلام البحث غير صالح")
    limit=int(data.action.get("limit",8));
    if limit<1 or limit>20: raise HTTPException(400,"حد النتائج غير صالح")
    a=Automation(user_id=user.id,name=data.name,trigger_type=data.trigger_type,trigger_json=json.dumps(data.trigger,ensure_ascii=False),action_json=json.dumps({"type":"research","query":query,"limit":limit},ensure_ascii=False),enabled=data.enabled);db.add(a);db.commit();db.refresh(a)
    return AutomationOut(id=a.id,name=a.name,trigger_type=a.trigger_type,trigger=json.loads(a.trigger_json),action=json.loads(a.action_json),enabled=a.enabled,last_run_at=a.last_run_at.isoformat() if a.last_run_at else None)

@app.get("/automations",response_model=list[AutomationOut])
def list_automations(user=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Automation).where(Automation.user_id==user.id).order_by(desc(Automation.created_at))).all()
    return [AutomationOut(id=a.id,name=a.name,trigger_type=a.trigger_type,trigger=json.loads(a.trigger_json),action=json.loads(a.action_json),enabled=a.enabled,last_run_at=a.last_run_at.isoformat() if a.last_run_at else None) for a in rows]

@app.delete("/automations/{aid}")
def delete_automation(aid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    a=db.scalar(select(Automation).where(Automation.id==aid,Automation.user_id==user.id))
    if not a: raise HTTPException(404,"الأتمتة غير موجودة")
    db.delete(a);db.commit();return {"deleted":True}

@app.get("/search/global",response_model=GlobalSearchOut)
def global_search(q:str,user=Depends(current_user),db:Session=Depends(get_db)):
    q=q.strip()[:200]
    if not q: return GlobalSearchOut(conversations=[],messages=[],projects=[],files=[],memories=[],tasks=[])
    like=f"%{q}%"
    conv=db.scalars(select(Conversation).where(Conversation.user_id==user.id,Conversation.title.ilike(like)).limit(20)).all()
    msgs=db.scalars(select(Message).join(Conversation).where(Conversation.user_id==user.id,Message.content.ilike(like)).order_by(desc(Message.created_at)).limit(50)).all()
    projects=db.scalars(select(Project).where(Project.user_id==user.id,Project.name.ilike(like)).limit(20)).all()
    files=db.scalars(select(FileAsset).where(FileAsset.user_id==user.id,FileAsset.filename.ilike(like)).limit(20)).all()
    mems=db.scalars(select(Memory).where(Memory.user_id==user.id,or_(Memory.key.ilike(like),Memory.value.ilike(like))).limit(20)).all()
    tasks=db.scalars(select(Task).where(Task.user_id==user.id,or_(Task.title.ilike(like),Task.description.ilike(like))).limit(20)).all()
    return GlobalSearchOut(conversations=[{"id":x.id,"title":x.title} for x in conv],messages=[{"id":x.id,"conversation_id":x.conversation_id,"role":x.role,"snippet":x.content[:500]} for x in msgs],projects=[{"id":x.id,"name":x.name} for x in projects],files=[{"id":x.id,"filename":x.filename} for x in files],memories=[{"id":x.id,"key":x.key,"value":x.value} for x in mems],tasks=[{"id":x.id,"title":x.title,"completed":x.completed} for x in tasks])

@app.get("/usage/me")
def usage_me(user=Depends(current_user),db:Session=Depends(get_db)):
    since=datetime.now(timezone.utc)-timedelta(days=30)
    rows=db.execute(select(func.sum(UsageLedger.input_tokens),func.sum(UsageLedger.output_tokens),func.sum(UsageLedger.cost_usd)).where(UsageLedger.user_id==user.id,UsageLedger.created_at>=since)).one()
    return {"days":30,"input_tokens":int(rows[0] or 0),"output_tokens":int(rows[1] or 0),"cost_usd":float(rows[2] or 0),"plan":active_plan(db,user.id)}

@app.post("/projects/{pid}/files/{fid}/index")
async def index_project_file(pid:int,fid:int,user=Depends(current_user),db:Session=Depends(get_db)):
    require_project(db,user.id,pid); asset=db.scalar(select(FileAsset).where(FileAsset.id==fid,FileAsset.user_id==user.id))
    if not asset: raise HTTPException(404,"الملف غير موجود")
    if not asset.extracted_text.strip(): raise HTTPException(400,"الملف لا يحتوي نصًا قابلًا للفهرسة")
    chunks=chunk_text(asset.extracted_text); status=semantic_status(); vectors=[]
    if status["mode"]=="hybrid":
        vectors=await embed(chunks)
        if len(vectors)!=len(chunks): raise HTTPException(502,"Embedding provider returned incomplete vectors")
    # New vectors use an isolated index version and are verified before any old vectors are removed.
    if status["mode"]=="hybrid":
        try:
            await reindex_file(QdrantStore(), f"{settings.qdrant_collection_prefix}_project_{pid}", file_id=fid, project_id=pid, filename=asset.filename, chunks=chunks, vectors=vectors, embedding_model=settings.embedding_model)
        except Exception as exc:
            db.rollback(); raise HTTPException(502,"تعذر تحديث الفهرس المتجهي") from exc
    db.query(VectorChunk).filter(VectorChunk.file_id==fid,VectorChunk.user_id==user.id).delete(synchronize_session=False)
    for i,text_chunk in enumerate(chunks):
        meta={"filename":asset.filename,"chunk":i,"file_id":fid,"project_id":pid,"section":None,"page":None,"embedding_model":settings.embedding_model if vectors else None}
        db.add(VectorChunk(user_id=user.id,project_id=pid,file_id=fid,source_text=text_chunk,embedding_json=json.dumps(vectors[i] if vectors else []),metadata_json=json.dumps(meta,ensure_ascii=False),source_page=None,source_section=None))
    db.commit(); return {"indexed":len(chunks),"mode":status["mode"],"semantic_embeddings":bool(vectors),"configuration":status,"citation_policy":"page/section only when parser provides verified metadata"}

@app.get("/projects/{pid}/rag-search")
async def rag_search(pid:int,q:str,user=Depends(current_user),db:Session=Depends(get_db)):
    require_project(db,user.id,pid); rows=db.scalars(select(VectorChunk).where(VectorChunk.user_id==user.id,VectorChunk.project_id==pid)).all()
    qv=[]; semantic_hits=[]; status=semantic_status()
    if status["mode"]=="hybrid":
        try:
            vv=await embed([q]); qv=vv[0] if vv else []
            if qv: semantic_hits=await QdrantStore().search(f"{settings.qdrant_collection_prefix}_project_{pid}",qv,limit=12,filters={"must":[{"key":"project_id","match":{"value":pid}}]})
        except Exception as exc: log.warning("qdrant_search_failed=%s",type(exc).__name__)
    chunks=[{"id":r.id,"text":r.source_text,"metadata":json.loads(r.metadata_json or '{}'),"embedding":json.loads(r.embedding_json or '[]')} for r in rows]
    ranked=rank_chunks(q,chunks,8,qv or None,semantic_hits)
    return {"query":q,"results":[{"chunk_id":x['id'],"text":x['text'],"metadata":x['metadata'],"score":round(x['score'],4),"lexical_score":round(x['lexical_score'],4),"semantic_score":round(x['semantic_score'],4),"citation":{"file_id":x['metadata'].get('file_id'),'page':x['metadata'].get('page'),'section':x['metadata'].get('section'),'source':x['metadata'].get('filename')}} for x in ranked],"mode":"hybrid" if semantic_hits else "lexical","semantic_available":bool(semantic_hits)}

@app.get("/agents/{run_id}",response_model=AgentOut)
def get_agent(run_id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    r=db.scalar(select(AgentRun).where(AgentRun.id==run_id,AgentRun.user_id==user.id))
    if not r: raise HTTPException(404,"المهمة غير موجودة")
    return AgentOut(run_id=r.id,status=r.status,plan=json.loads(r.plan_json or "[]"),result=json.loads(r.result_json or "{}"))

@app.post("/agents/{run_id}/cancel")
def cancel_agent(run_id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    r=db.scalar(select(AgentRun).where(AgentRun.id==run_id,AgentRun.user_id==user.id))
    if not r: raise HTTPException(404,"المهمة غير موجودة")
    if r.status in {"completed","failed","cancelled"}: return {"status":r.status}
    r.cancel_requested=True;r.updated_at=now();audit(db,"agent_cancel_requested",user.id,user.id,{"run_id":run_id});db.commit();return {"status":"cancellation_requested"}
