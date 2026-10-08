import json
from datetime import datetime, timezone, timedelta
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select, update, and_, or_
from .config import settings
from .db import SessionLocal
from .models import Task, DeviceToken, AnalyticsEvent, RefreshToken, now

async def remind_due(ctx):
    db=SessionLocal()
    try:
        tasks=db.scalars(select(Task).where(Task.completed==False,Task.due_at.is_not(None),Task.due_at<=now(),(Task.reminded_at.is_(None)) | (Task.reminded_at < Task.due_at))).all()
        if not tasks:return
        try:
            import firebase_admin
            from firebase_admin import credentials,messaging
            if not firebase_admin._apps and settings.fcm_enabled and settings.firebase_service_account_json: firebase_admin.initialize_app(credentials.Certificate(json.loads(settings.firebase_service_account_json)))
            for task in tasks:
                tokens=db.scalars(select(DeviceToken.token).where(DeviceToken.user_id==task.user_id,DeviceToken.enabled==True)).all()
                for token in tokens:
                    try:messaging.send(messaging.Message(notification=messaging.Notification(title="Rafiq AI",body=task.title),token=token,data={"type":"task","task_id":str(task.id)}))
                    except Exception:pass
                task.reminded_at=now()
                if task.recurrence and task.due_at:
                    if task.recurrence == "daily": task.due_at=task.due_at+timedelta(days=1)
                    elif task.recurrence == "weekly": task.due_at=task.due_at+timedelta(days=7)
                    task.reminded_at=None
                task.updated_at=now()
        except Exception:pass
    finally:db.close()

async def cleanup_retention(ctx):
    db=SessionLocal()
    try:
        cutoff=now()-timedelta(days=settings.data_retention_days)
        db.query(AnalyticsEvent).filter(AnalyticsEvent.created_at<cutoff).delete()
        db.query(RefreshToken).filter(RefreshToken.expires_at<now()-timedelta(days=7)).delete()
        db.commit()
    finally: db.close()

async def recover_stale_agents(ctx):
    from .models import AgentRun
    db=SessionLocal(); now_ts=now()
    try:
        stale=db.scalars(select(AgentRun).where(AgentRun.status.in_(["running","paused"]),AgentRun.lease_until.is_not(None),AgentRun.lease_until<now_ts,AgentRun.cancel_requested==False)).all()
        for r in stale:
            r.status="queued"; r.resume_requested=True; r.worker_id=None; r.lease_until=None; r.updated_at=now_ts
            db.commit()
            await ctx["redis"].enqueue_job("run_agent_job",r.id)
    finally: db.close()

class WorkerSettings:
    functions=[remind_due,cleanup_retention,recover_stale_agents]
    cron_jobs=[cron(remind_due,minute=set(range(0,60,5))),cron(cleanup_retention,hour=3,minute=30)]
    redis_settings=RedisSettings.from_dsn(settings.rate_limit_storage_uri if settings.rate_limit_storage_uri.startswith("redis://") else "redis://redis:6379/1")

async def run_agent_job(ctx, run_id: str):
    import json, uuid
    from .models import AgentRun, AgentStep
    from .services.agents import AgentEngine, AgentStepSpec, AgentLimits
    from .services.tools import safe_tool_registry
    db=SessionLocal(); worker_id=f"arq:{uuid.uuid4().hex}"; attempt_id=uuid.uuid4().hex; lease_until=now()+timedelta(minutes=2)
    try:
        claim=db.execute(update(AgentRun).where(AgentRun.id==run_id,AgentRun.status.in_(["queued","paused"]),AgentRun.cancel_requested==False,or_(AgentRun.lease_until.is_(None),AgentRun.lease_until<now())).values(status="running",attempts=AgentRun.attempts+1,worker_id=worker_id,attempt_id=attempt_id,lease_until=lease_until,updated_at=now())).rowcount
        db.commit()
        if claim!=1: return
        run=db.get(AgentRun,run_id)
        specs=[AgentStepSpec(**x) for x in json.loads(run.plan_json or "[]")]
        checkpoint=json.loads(run.checkpoint_json or "{}")
        start=int(checkpoint.get("last_step",0)); calls=int(run.tool_calls_used or 0); tokens=int(run.total_tokens or 0)
        registry=safe_tool_registry(); tools={k:v for k,v in registry.items() if k in {"search","fetch"}}; engine=AgentEngine(tools)
        async def cancelled():
            db.expire_all(); fresh=db.get(AgentRun,run_id); return bool(not fresh or fresh.cancel_requested or fresh.worker_id!=worker_id)
        async def heartbeat():
            db.execute(update(AgentRun).where(AgentRun.id==run_id,AgentRun.worker_id==worker_id,AgentRun.attempt_id==attempt_id).values(lease_until=now()+timedelta(minutes=2),updated_at=now())); db.commit()
        async def persist(event):
            idx=int(event.get("step",0)); existing=db.scalar(select(AgentStep).where(AgentStep.run_id==run_id,AgentStep.step_index==idx))
            if not existing:
                existing=AgentStep(run_id=run_id,step_index=idx,tool=event.get("tool", ""),status="queued",input_json=json.dumps(specs[idx-1].args if idx else {},ensure_ascii=False)); db.add(existing); db.flush()
            existing.status=event.get("status",existing.status); existing.attempts=max(existing.attempts or 0,int(event.get("attempt",0))); existing.updated_at=now()
            if existing.status=="running" and existing.started_at is None: existing.started_at=now()
            if existing.status in {"completed","failed","cancelled","timeout"}: existing.finished_at=now()
            if "result" in event: existing.output_json=json.dumps(event.get("result"),ensure_ascii=False)[:20000]
            run.updated_at=now(); db.commit(); await heartbeat()
        # Renew lease between steps; the worker remains the only owner for this attempt.
        result=await engine.execute(specs,AgentLimits(max_steps=len(specs),max_tool_calls=run.max_tool_calls,max_seconds=run.max_seconds,max_tokens=run.max_tokens),start_index=start,cancel_check=cancelled,on_event=persist,initial_tool_calls=calls,initial_tokens=tokens)
        run=db.get(AgentRun,run_id)
        if run and run.worker_id==worker_id and run.attempt_id==attempt_id:
            run.tool_calls_used=int(result.get("tool_calls",calls)); run.total_tokens=int(result.get("total_tokens",tokens)); run.status="cancelled" if result.get("status")=="cancelled" else "completed"; run.result_json=json.dumps(result,ensure_ascii=False); run.lease_until=None; run.worker_id=None; run.updated_at=now(); db.commit()
    except TimeoutError as exc:
        run=db.get(AgentRun,run_id)
        if run and run.worker_id==worker_id:
            step=db.scalar(select(AgentStep).where(AgentStep.run_id==run_id,AgentStep.status=="running").order_by(AgentStep.step_index.desc()))
            if step: step.status="timeout"; step.finished_at=now(); step.updated_at=now(); step.output_json=json.dumps({"error":"timeout"})
            run.status="timeout";run.last_error=str(exc);run.lease_until=None;run.worker_id=None;run.updated_at=now();db.commit()
    except Exception as exc:
        run=db.get(AgentRun,run_id)
        if run and run.worker_id==worker_id:
            step=db.scalar(select(AgentStep).where(AgentStep.run_id==run_id,AgentStep.status=="running").order_by(AgentStep.step_index.desc()))
            if step: step.status="failed"; step.finished_at=now(); step.updated_at=now(); step.output_json=json.dumps({"error":type(exc).__name__})
            run.status="failed";run.last_error=type(exc).__name__;run.lease_until=None;run.worker_id=None;run.updated_at=now();db.commit()
    finally: db.close()

async def run_research_job(ctx, run_id: str, limit: int=8):
    import json
    from .models import ResearchRun, ResearchSource
    from .services.research import deep_research
    from .services.rag import source_id
    db=SessionLocal()
    try:
        run=db.get(ResearchRun,run_id)
        if not run or run.status=='cancelled': return
        result=await deep_research(run.query,limit)
        sources=[]
        for item in result.get('sources',[]):
            score=min(1.0,0.4+(0.1 if '.gov' in item.get('host','') or '.edu' in item.get('host','') else 0)+0.2*bool(item.get('content')))
            db.add(ResearchSource(research_id=run_id,url=item['url'],title=item.get('title',''),snippet=item.get('snippet','')[:2000],source_hash=item.get('source_id') or source_id(item['url']),quality_score=score));sources.append(item)
        pipeline=['query_planning','search','fetch','deduplicate','source_quality','claim_extraction','cross_check','synthesis','citation_validation']; run.status='completed'; run.pipeline_json=json.dumps(pipeline); run.confidence=sum(float(x.get('quality_score',0)) for x in sources)/max(1,len(sources)); run.result_json=json.dumps(result,ensure_ascii=False); db.commit()
    except Exception as exc:
        run=db.get(ResearchRun,run_id)
        if run:run.status='failed';run.result_json=json.dumps({'error':type(exc).__name__},ensure_ascii=False);db.commit()
    finally: db.close()

async def run_automation_job(ctx, execution_id:int):
    import json
    from .models import AutomationExecution, Automation
    db=SessionLocal()
    try:
        e=db.get(AutomationExecution,execution_id); a=db.get(Automation,e.automation_id) if e else None
        if not e or not a or e.status in {"completed","cancelled"}: return
        e.status="running";e.attempts+=1;e.retry_at=None;db.commit()
        action=json.loads(a.action_json or "{}")
        if action.get("type")!="research": raise ValueError("unsupported automation action")
        from .services.research import deep_research
        result=await deep_research(str(action.get("query") or a.name),int(action.get("limit",8)))
        e.status="completed";e.result_json=json.dumps(result,ensure_ascii=False);e.finished_at=now();a.last_run_at=now();db.commit()
    except Exception as exc:
        if e:
            e.failure_reason=type(exc).__name__
            if e.attempts < 3:
                delay=2 ** max(0,e.attempts-1); e.status="queued";e.retry_at=now()+timedelta(seconds=delay);db.commit()
                await ctx["redis"].enqueue_job("run_automation_job",e.id,_defer_by=delay)
            else:
                e.status="failed";e.result_json=json.dumps({"error":type(exc).__name__});e.finished_at=now();db.commit()
    finally: db.close()

async def automation_tick(ctx):
    import json
    from .models import Automation, AutomationExecution
    db=SessionLocal()
    try:
        due=db.scalars(select(Automation).where(Automation.enabled==True,Automation.trigger_type=='schedule')).all()
        for a in due:
            minute=int(json.loads(a.trigger_json or "{}").get("interval_minutes",60)); last=a.last_run_at
            if last and (now()-last).total_seconds()<minute*60: continue
            key=f"automation:{a.id}:{now().strftime('%Y%m%d%H%M')}"
            if db.scalar(select(AutomationExecution).where(AutomationExecution.idempotency_key==key)): continue
            e=AutomationExecution(automation_id=a.id,idempotency_key=key,status="queued");db.add(e);db.flush();db.commit()
            await ctx["redis"].enqueue_job("run_automation_job",e.id)
    finally: db.close()

WorkerSettings.functions += [run_agent_job, run_research_job, run_automation_job, automation_tick, recover_stale_agents]
WorkerSettings.cron_jobs += [cron(automation_tick,minute=set(range(0,60,1))),cron(recover_stale_agents,minute=set(range(0,60,5)))]
