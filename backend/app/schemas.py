from typing import Generic, TypeVar
from pydantic import BaseModel, EmailStr, Field, field_validator
T=TypeVar("T")
class AuthRequest(BaseModel): email: EmailStr; password: str=Field(min_length=8,max_length=128)
class RefreshBody(BaseModel): refresh_token:str=Field(min_length=32,max_length=256)
class TokenResponse(BaseModel): access_token:str; refresh_token:str; token_type:str="bearer"
class ProfileOut(BaseModel): email:EmailStr; display_name:str; locale:str; memory_enabled:bool; analytics_enabled:bool; plan:str; created_at:str
class ProfileUpdate(BaseModel):
    display_name:str|None=Field(default=None,max_length=120); locale:str=Field(default="ar",max_length=20); memory_enabled:bool|None=None; analytics_enabled:bool|None=None
    @field_validator("locale")
    @classmethod
    def valid_locale(cls,v): return v if v in {"ar","en","fr","es","tr","ur","id"} else "ar"
class ConversationCreate(BaseModel): title:str=Field(default="محادثة جديدة",min_length=1,max_length=200)
class ConversationUpdate(BaseModel): title:str=Field(min_length=1,max_length=200); pinned:bool|None=None
class ConversationOut(BaseModel): id:int; title:str; pinned:bool; updated_at:str
class MessageCreate(BaseModel): content:str=Field(min_length=1,max_length=12000); file_ids:list[int]=Field(default_factory=list,max_length=5); use_web:bool=False
class MessageOut(BaseModel): id:int; conversation_id:int; role:str; content:str; created_at:str; model:str=""; input_tokens:int=0; output_tokens:int=0
class TaskCreate(BaseModel): title:str=Field(min_length=1,max_length=300); description:str=Field(default="",max_length=5000); due_at:str|None=None; priority:str="normal"; recurrence:str|None=None
class TaskUpdate(BaseModel): title:str|None=Field(default=None,max_length=300); description:str|None=Field(default=None,max_length=5000); completed:bool|None=None; due_at:str|None=None; priority:str|None=None; recurrence:str|None=None
class TaskOut(BaseModel): id:int; title:str; description:str; completed:bool; due_at:str|None; priority:str; recurrence:str|None; updated_at:str
class SearchResult(BaseModel): conversation_id:int; conversation_title:str; message_id:int; role:str; snippet:str; created_at:str
class SyncOut(BaseModel): conversations:list[ConversationOut]; tasks:list[TaskOut]; messages:list[MessageOut]; server_time:str
class Page(BaseModel,Generic[T]): items:list[T]; next_cursor:str|None=None
class MemoryCreate(BaseModel): key:str=Field(min_length=1,max_length=120); value:str=Field(min_length=1,max_length=3000); category:str="preference"; sensitive:bool=False
class MemoryUpdate(BaseModel): value:str=Field(min_length=1,max_length=3000); category:str="preference"; sensitive:bool=False
class MemoryOut(BaseModel): id:int; key:str; value:str; category:str; sensitive:bool; created_at:str; updated_at:str
class MemorySettings(BaseModel): enabled:bool
class MemorySuggestionRequest(BaseModel): text:str=Field(min_length=1,max_length=12000)
class SessionOut(BaseModel): id:int; device_name:str; created_at:str; expires_at:str; revoked:bool
class FileOut(BaseModel): id:int; filename:str; content_type:str; size_bytes:int; status:str; created_at:str; download_url:str|None=None
class SearchWebResult(BaseModel): title:str; url:str; snippet:str
class WebSearchOut(BaseModel): query:str; results:list[SearchWebResult]
class EntitlementOut(BaseModel): plan:str; active:bool; expires_at:str|None; product_id:str|None
class PurchaseVerify(BaseModel): product_id:str; purchase_token:str
class DeviceTokenBody(BaseModel): token:str=Field(min_length=20,max_length=4096); platform:str="android"
class AnalyticsBody(BaseModel): event_name:str=Field(min_length=1,max_length=100); properties:dict[str,str|int|float|bool|None]={}
class AdminUserOut(BaseModel): id:int; email:EmailStr; display_name:str; plan:str; disabled:bool; created_at:str
class AdminStats(BaseModel): users:int; active_users:int; paid_users:int; new_users_7d:int; conversations:int; messages:int; ai_tokens:int; ai_cost:float; revenue_estimate_usd:float; errors:int; rate_limit_events:int
class ExportOut(BaseModel): user_id:int; generated_at:str; profile:dict; conversations:list; tasks:list; memories:list; projects:list=[]; artifacts:list=[]; research:list=[]; agent_runs:list=[]; automations:list=[]; files:list=[]; usage:list=[]

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    instructions: str = Field(default="",max_length=12000)
class ProjectUpdate(BaseModel):
    name: str|None = Field(default=None,max_length=160)
    instructions: str|None = Field(default=None,max_length=12000)
class ProjectOut(BaseModel):
    id:int; name:str; instructions:str; created_at:str; updated_at:str
class ProjectLink(BaseModel): conversation_id:int
class AgentRequest(BaseModel):
    goal:str=Field(min_length=3,max_length=12000)
    task_type:str="agent"
    model_preference:str="balanced"
    approved_tools:list[str]=Field(default_factory=list,max_length=12)
class AgentOut(BaseModel): run_id:str; status:str; plan:list; result:dict
class ResearchRequest(BaseModel): query:str=Field(min_length=2,max_length=1000); limit:int=Field(default=8,ge=1,le=12)
class ResearchOut(BaseModel): id:str; query:str; status:str; sources:list[dict]; result:dict
class ArtifactCreate(BaseModel): name:str=Field(min_length=1,max_length=200); kind:str=Field(min_length=1,max_length=40); content:str=Field(default="",max_length=200000); project_id:int|None=None
class ArtifactUpdate(BaseModel): content:str=Field(max_length=200000); name:str|None=None
class ArtifactOut(BaseModel): id:int; name:str; kind:str; content:str; version:int; project_id:int|None; updated_at:str
class AutomationCreate(BaseModel): name:str=Field(min_length=1,max_length=160); trigger_type:str=Field(min_length=1,max_length=40); trigger:dict={}; action:dict={}; enabled:bool=True
class AutomationOut(BaseModel): id:int; name:str; trigger_type:str; trigger:dict; action:dict; enabled:bool; last_run_at:str|None
class GlobalSearchOut(BaseModel): conversations:list[dict]; messages:list[dict]; projects:list[dict]; files:list[dict]; memories:list[dict]; tasks:list[dict]
