import httpx
from ..config import settings
async def web_search(query:str,limit:int=5):
    if not settings.web_search_base_url or not settings.web_search_api_key: return []
    headers={"Authorization":f"Bearer {settings.web_search_api_key}","Accept":"application/json"}
    params={"q":query,"count":limit}
    async with httpx.AsyncClient(timeout=settings.web_search_timeout_seconds) as c:
        r=await c.get(settings.web_search_base_url,headers=headers,params=params);r.raise_for_status();data=r.json()
    results=[]
    for x in data.get("web",{}).get("results",[])[:limit]:
        if x.get("url") and x.get("title"): results.append({"title":x["title"],"url":x["url"],"snippet":x.get("description","")[:500]})
    return results
