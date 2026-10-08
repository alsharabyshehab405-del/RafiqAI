import hashlib, logging, math, uuid, httpx
from ..config import settings
log=logging.getLogger("rafiq.rag")

def chunk_text(text,size=1200,overlap=150):
    text=text.strip(); out=[]; i=0
    while text and i<len(text):
        out.append(text[i:i+size])
        if i+size>=len(text): break
        i += max(1,size-overlap)
    return out

def lexical_score(query,text):
    q=set(query.lower().split()); t=set(text.lower().split()); return len(q&t)/max(1,len(q))

def cosine(a,b):
    if not a or not b: return 0.0
    if len(a)!=len(b): return 0.0
    dot=sum(x*y for x,y in zip(a,b)); na=math.sqrt(sum(x*x for x in a)); nb=math.sqrt(sum(x*x for x in b))
    return dot/(na*nb) if na and nb else 0.0

async def embed(texts:list[str])->list[list[float]]:
    if not settings.embedding_base_url or not settings.embedding_api_key or not settings.embedding_model: return []
    async with httpx.AsyncClient(timeout=30) as c:
        r=await c.post(settings.embedding_base_url.rstrip('/')+'/embeddings',json={'model':settings.embedding_model,'input':texts},headers={'Authorization':f'Bearer {settings.embedding_api_key}'})
        r.raise_for_status()
        data=r.json().get('data',[])
        vectors=[x.get('embedding',[]) for x in data]
        if len(vectors)!=len(texts) or any(not v for v in vectors): raise RuntimeError('embedding provider returned incomplete vectors')
        return vectors

class QdrantStore:
    def _headers(self): return {'api-key':settings.qdrant_api_key} if settings.qdrant_api_key else {}
    def _url(self,path): return f"{settings.qdrant_url.rstrip('/')}{path}"

    async def ensure_collection(self,collection,dimension):
        if not settings.qdrant_url: raise RuntimeError('qdrant not configured')
        async with httpx.AsyncClient(timeout=settings.qdrant_timeout_seconds) as c:
            r=await c.get(self._url(f'/collections/{collection}'),headers=self._headers())
            if r.status_code==200:
                info=r.json().get('result',{}).get('config',{}).get('params',{}).get('vectors',{})
                existing_dim=info.get('size') if isinstance(info,dict) else None
                if existing_dim is not None and int(existing_dim)!=int(dimension): raise ValueError('qdrant collection embedding dimension mismatch')
                return
            if r.status_code!=404: r.raise_for_status()
            create=await c.put(self._url(f'/collections/{collection}'),json={'vectors':{'size':dimension,'distance':'Cosine'}},headers=self._headers())
            if create.status_code not in (200,201,409): create.raise_for_status()

    async def upsert(self,collection,items):
        if not items: return
        await self.ensure_collection(collection,len(items[0]['vector']))
        dim=len(items[0]['vector'])
        if any(len(x.get('vector',[]))!=dim for x in items): raise ValueError('inconsistent embedding dimensions')
        async with httpx.AsyncClient(timeout=settings.qdrant_timeout_seconds) as c:
            r=await c.put(self._url(f'/collections/{collection}/points'),json={'points':items},headers=self._headers()); r.raise_for_status()

    async def delete_points(self,collection,*,file_id=None,project_id=None,index_version=None,exclude_index_version=None):
        if not settings.qdrant_url: return
        must=[]
        if file_id is not None: must.append({'key':'file_id','match':{'value':file_id}})
        if project_id is not None: must.append({'key':'project_id','match':{'value':project_id}})
        if index_version is not None: must.append({'key':'index_version','match':{'value':index_version}})
        if not must: raise ValueError('delete_points requires file_id or project_id')
        filt={'must':must}
        if exclude_index_version is not None: filt['must_not']=[{'key':'index_version','match':{'value':exclude_index_version}}]
        async with httpx.AsyncClient(timeout=settings.qdrant_timeout_seconds) as c:
            r=await c.post(self._url(f'/collections/{collection}/points/delete'),json={'filter':filt},headers=self._headers())
            if r.status_code==404: return
            r.raise_for_status()

    async def verify_points(self,collection,*,file_id,project_id,index_version,expected_count):
        if not settings.qdrant_url: raise RuntimeError('qdrant not configured')
        async with httpx.AsyncClient(timeout=settings.qdrant_timeout_seconds) as c:
            r=await c.post(self._url(f'/collections/{collection}/points/scroll'),json={'filter':{'must':[{'key':'file_id','match':{'value':file_id}},{'key':'project_id','match':{'value':project_id}},{'key':'index_version','match':{'value':index_version}}]},'limit':expected_count+1,'with_payload':True,'with_vector':False},headers=self._headers())
            if r.status_code==404: raise RuntimeError('qdrant collection missing during verification')
            r.raise_for_status()
            points=r.json().get('result',{}).get('points',[])
            if len(points)!=expected_count:
                raise RuntimeError(f'qdrant re-index verification failed: expected {expected_count}, got {len(points)}')
            for point in points:
                payload=point.get('payload') or {}
                if payload.get('file_id')!=file_id or payload.get('project_id')!=project_id or payload.get('index_version')!=index_version:
                    raise RuntimeError('qdrant re-index verification metadata mismatch')
            return True

    async def delete_collection(self,collection):
        if not settings.qdrant_url:return
        async with httpx.AsyncClient(timeout=settings.qdrant_timeout_seconds) as c:
            r=await c.delete(self._url(f'/collections/{collection}'),headers=self._headers())
            if r.status_code not in (200,404): r.raise_for_status()

    async def search(self,collection,vector,limit=8,filters=None):
        if not settings.qdrant_url:return []
        async with httpx.AsyncClient(timeout=settings.qdrant_timeout_seconds) as c:
            r=await c.post(self._url(f'/collections/{collection}/points/search'),json={'vector':vector,'limit':limit,'with_payload':True,**({'filter':filters} if filters else {})},headers=self._headers());
            if r.status_code==404:return []
            r.raise_for_status(); return r.json().get('result',[])

async def reindex_file(store: QdrantStore, collection: str, *, file_id: int, project_id: int, filename: str, chunks: list[str], vectors: list[list[float]], embedding_model: str | None = None):
    if not chunks:
        raise ValueError('cannot index empty chunk set')
    if len(vectors) != len(chunks) or any(not vector for vector in vectors):
        raise ValueError('embedding provider returned incomplete vectors')
    dimension=len(vectors[0])
    if dimension <= 0 or any(len(vector) != dimension for vector in vectors):
        raise ValueError('inconsistent embedding dimensions')
    await store.ensure_collection(collection,dimension)
    index_version=uuid.uuid4().hex
    points=[{'id':f'{file_id}:{index_version}:{i}','vector':vector,'payload':{'filename':filename,'chunk':i,'file_id':file_id,'project_id':project_id,'section':None,'page':None,'text':chunks[i],'embedding_model':embedding_model,'index_version':index_version}} for i,vector in enumerate(vectors)]
    try:
        await store.upsert(collection,points)
        await store.verify_points(collection,file_id=file_id,project_id=project_id,index_version=index_version,expected_count=len(points))
        await store.delete_points(collection,file_id=file_id,project_id=project_id,exclude_index_version=index_version)
    except Exception:
        try:
            await store.delete_points(collection,file_id=file_id,project_id=project_id,index_version=index_version)
        except Exception as cleanup_exc:
            log.warning("qdrant_failed_index_cleanup file=%s project=%s version=%s error=%s",file_id,project_id,index_version,type(cleanup_exc).__name__)
        raise
    return index_version

def rank_chunks(query,chunks,limit=8,semantic_query=None,semantic_hits=None):
    # Hybrid retrieval is a union of lexical candidates and independent semantic hits.
    byid={str(x.get('id')):x for x in chunks}
    candidates=list(chunks)
    for hit in semantic_hits or []:
        hid=str(hit.get('id'))
        if hid in byid:
            byid[hid]['semantic_score']=float(hit.get('score',0.0))
        elif hit.get('payload'):
            payload=hit['payload']; candidates.append({'id':hit.get('id'),'text':payload.get('text',''),'metadata':payload,'embedding':[],'semantic_score':float(hit.get('score',0.0))})
    ranked=[]
    for x in candidates:
        lex=lexical_score(query,x.get('text','')); sem=float(x.get('semantic_score',cosine(semantic_query,x.get('embedding',[])) if semantic_query else 0.0))
        score=0.45*lex+0.55*sem if semantic_query or sem else lex
        ranked.append({**x,'lexical_score':lex,'semantic_score':sem,'score':score})
    unique={str(x.get('id')):x for x in ranked}
    return sorted(unique.values(),key=lambda x:x['score'],reverse=True)[:limit]

def source_id(text): return hashlib.sha256(text.encode()).hexdigest()[:16]

def semantic_status():
    configured=bool(settings.embedding_base_url and settings.embedding_api_key and settings.embedding_model and settings.qdrant_url)
    return {'embedding_provider_configured':bool(settings.embedding_base_url and settings.embedding_api_key and settings.embedding_model),'vector_db_configured':bool(settings.qdrant_url),'mode':'hybrid' if configured else 'lexical'}
