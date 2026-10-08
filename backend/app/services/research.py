import asyncio, hashlib, re, httpx, socket, ipaddress
from urllib.parse import urlparse
from .search import web_search
from ..ai import chat

async def _fetch(item):
    try:
        current=item['url']
        async with httpx.AsyncClient(timeout=8,follow_redirects=False,headers={'User-Agent':'RafiqAIResearch/2.0'}) as client:
            for _ in range(4):
                parsed=urlparse(current)
                if parsed.scheme not in {'http','https'}: raise ValueError('unsupported scheme')
                host=(parsed.hostname or '').lower()
                for addr in socket.getaddrinfo(host,None):
                    ip=ipaddress.ip_address(addr[4][0])
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved: raise PermissionError('private target blocked')
                r=await client.get(current)
                if r.is_redirect:
                    location=r.headers.get('location')
                    if not location: break
                    current=str(httpx.URL(current).join(location)); continue
                r.raise_for_status(); return {**item,'url':current,'content':r.text[:20000]}
        return {**item,'content':'','fetch_error':'redirect_limit'}
    except Exception as exc:return {**item,'content':'','fetch_error':type(exc).__name__}

def _queries(query):
    parts=re.split(r'\s+(?:and|or|و|أو)\s+|[؛;]',query.strip(),flags=re.I)
    return list(dict.fromkeys([query]+[p.strip() for p in parts if len(p.strip())>4]))[:4]

def _claims(content):
    return [x.strip() for x in re.split(r'(?<=[.!؟])\s+',content) if 40<=len(x.strip())<=500][:12]

def _crosscheck(sources):
    claims=[]
    for s in sources:
        for c in _claims(s.get('content','')): claims.append({'text':c,'source_id':s['source_id']})
    checked=[]
    for c in claims[:60]:
        overlap=sum(1 for x in claims if x['source_id']!=c['source_id'] and len(set(c['text'].lower().split()) & set(x['text'].lower().split()))>=4)
        checked.append({**c,'supporting_sources':overlap})
    return checked

async def deep_research(query,limit=8):
    raw=[]
    queries=_queries(query)
    sem=asyncio.Semaphore(min(4,len(queries)))
    async def search_one(q):
        async with sem:
            try: return await web_search(q,limit=max(3,limit//2))
            except Exception: return []
    batches=await asyncio.gather(*(search_one(q) for q in queries))
    for batch in batches: raw.extend(batch)
    unique={}
    for item in raw:
        url=item.get('url','');host=urlparse(url).netloc.lower()
        if url and host and url not in unique:unique[url]={**item,'source_id':'S'+hashlib.sha256(url.encode()).hexdigest()[:8],'host':host}
    sources=await asyncio.gather(*[_fetch(x) for x in list(unique.values())[:limit]])
    claims=_crosscheck(sources)
    source_context='\n\n'.join(f"[{s['source_id']}] {s.get('title','')}\n{s.get('content','')[:7000]}" for s in sources if s.get('content'))
    synthesis='';citation_valid=True
    if source_context:
        try:
            synthesis,_,_=await chat([{'role':'system','content':'You are a research synthesizer. Use ONLY supplied sources. Every factual claim must cite one or more source ids exactly as [Sxxxxxxxx]. Never invent a source or citation. Explicitly flag disagreement.'},{'role':'user','content':f'Question: {query}\nSources:\n{source_context}'}],model=None)
            allowed={s['source_id'] for s in sources}
            cited=set(re.findall(r'\[(S[A-Za-z0-9]+)\]',synthesis))
            citation_valid=cited.issubset(allowed)
            if not citation_valid:
                synthesis=re.sub(r'\[(S[A-Za-z0-9]+)\]',lambda m:m.group(0) if m.group(1) in allowed else '[UNCITED]',synthesis)
        except Exception:synthesis=''
    return {'query':query,'sources':sources,'claims':claims,'synthesis':synthesis,'citation_validation':{'valid':citation_valid,'allowed_source_ids':[s['source_id'] for s in sources]}}
