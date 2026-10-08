import pytest
@pytest.mark.asyncio
async def test_ai_contract(monkeypatch):
 from app import ai
 class R:
  def raise_for_status(self): pass
  def json(self): return {'choices':[{'message':{'content':'ok'}}]}
 class C:
  async def __aenter__(self): return self
  async def __aexit__(self,*a): pass
  async def post(self,*a,**k): return R()
 monkeypatch.setattr(ai.httpx,'AsyncClient',lambda **k:C())
 assert await ai.chat([{'role':'user','content':'hello'}])=='ok'
