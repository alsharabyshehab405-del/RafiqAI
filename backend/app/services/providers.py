from dataclasses import dataclass
from typing import Protocol, AsyncIterator
import json, httpx

class AIProvider(Protocol):
    async def complete(self,messages:list[dict],model:str,**kwargs)->dict: ...
    async def stream(self,messages:list[dict],model:str,**kwargs)->AsyncIterator[str]: ...

def _openai_tools_to_anthropic(tools):
    out=[]
    for t in tools or []:
        fn=t.get('function',t)
        out.append({'name':fn.get('name',''),'description':fn.get('description',''),'input_schema':fn.get('parameters',{'type':'object','properties':{}})})
    return out

def _openai_tools_to_gemini(tools):
    declarations=[]
    for t in tools or []:
        fn=t.get('function',t)
        declarations.append({'name':fn.get('name',''),'description':fn.get('description',''),'parameters':fn.get('parameters',{'type':'object','properties':{}})})
    return [{'function_declarations':declarations}] if declarations else []

@dataclass
class OpenAICompatibleProvider:
    base_url:str; api_key:str; timeout:float=90
    async def complete(self,messages,model,**kwargs):
        body={'model':model,'messages':messages,**{k:v for k,v in kwargs.items() if v is not None}}
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout,connect=15)) as c:
            r=await c.post(self.base_url.rstrip('/')+'/chat/completions',json=body,headers={'Authorization':f'Bearer {self.api_key}'});r.raise_for_status();return r.json()
    async def stream(self,messages,model,**kwargs):
        body={'model':model,'messages':messages,'stream':True,**{k:v for k,v in kwargs.items() if v is not None}}
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout,connect=15)) as c:
            async with c.stream('POST',self.base_url.rstrip('/')+'/chat/completions',json=body,headers={'Authorization':f'Bearer {self.api_key}'}) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith('data:'): continue
                    payload=line[5:].strip()
                    if payload=='[DONE]': break
                    try:
                        d=json.loads(payload); piece=d.get('choices',[{}])[0].get('delta',{}).get('content')
                        if piece: yield piece
                    except json.JSONDecodeError: continue

@dataclass
class AnthropicProvider:
    base_url:str='https://api.anthropic.com'; api_key:str=''; timeout:float=90
    def _body(self,messages,model,kwargs):
        system='\n'.join(str(m.get('content','')) for m in messages if m.get('role')=='system'); msgs=[m for m in messages if m.get('role')!='system']
        body={'model':model,'messages':msgs,'max_tokens':kwargs.get('max_tokens',2048)}
        if system: body['system']=system
        for k in ('temperature','top_p','top_k'):
            if kwargs.get(k) is not None: body[k]=kwargs[k]
        if kwargs.get('tools') is not None: body['tools']=_openai_tools_to_anthropic(kwargs['tools'])
        if kwargs.get('tool_choice') is not None:
            tc=kwargs['tool_choice']; body['tool_choice']={'type':'auto'} if tc=='auto' else tc
        if kwargs.get('response_format') is not None: raise NotImplementedError('Anthropic structured response format is not normalized by this adapter')
        return body
    async def complete(self,messages,model,**kwargs):
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r=await c.post(self.base_url.rstrip('/')+'/v1/messages',json=self._body(messages,model,kwargs),headers={'x-api-key':self.api_key,'anthropic-version':'2023-06-01'});r.raise_for_status();d=r.json();
            content=[x for x in d.get('content',[]) if x.get('type')=='text']; calls=[{'id':x.get('id'),'type':'function','function':{'name':x.get('name'),'arguments':json.dumps(x.get('input',{}),ensure_ascii=False)}} for x in d.get('content',[]) if x.get('type')=='tool_use']
            return {'choices':[{'message':{'content':''.join(x.get('text','') for x in content),'tool_calls':calls}}],'usage':d.get('usage',{})}
    async def stream(self,messages,model,**kwargs):
        body=self._body(messages,model,kwargs);body['stream']=True
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            async with c.stream('POST',self.base_url.rstrip('/')+'/v1/messages',json=body,headers={'x-api-key':self.api_key,'anthropic-version':'2023-06-01'}) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith('data:'): continue
                    try:
                        d=json.loads(line[5:].strip())
                        if d.get('type')=='content_block_delta':
                            piece=d.get('delta',{}).get('text')
                            if piece: yield piece
                    except json.JSONDecodeError: continue

@dataclass
class GeminiProvider:
    base_url:str='https://generativelanguage.googleapis.com'; api_key:str=''; timeout:float=90
    def _body(self,messages,kwargs):
        contents=[];system=[]
        for m in messages:
            if m.get('role')=='system': system.append(str(m.get('content','')));continue
            role='model' if m.get('role')=='assistant' else 'user';contents.append({'role':role,'parts':[{'text':str(m.get('content',''))}]})
        body={'contents':contents}
        if system: body['systemInstruction']={'parts':[{'text':'\n'.join(system)}]}
        config={}
        for src,dst in [('temperature','temperature'),('max_tokens','maxOutputTokens'),('top_p','topP'),('top_k','topK')]:
            if kwargs.get(src) is not None: config[dst]=kwargs[src]
        if config: body['generationConfig']=config
        if kwargs.get('tools') is not None: body['tools']=_openai_tools_to_gemini(kwargs['tools'])
        if kwargs.get('response_format') is not None: raise NotImplementedError('Gemini structured response format is not normalized by this adapter')
        return body
    async def complete(self,messages,model,**kwargs):
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r=await c.post(f'{self.base_url.rstrip("/")}/v1beta/models/{model}:generateContent?key={self.api_key}',json=self._body(messages,kwargs));r.raise_for_status();d=r.json();parts=d.get('candidates',[{}])[0].get('content',{}).get('parts',[]);text=''.join(p.get('text','') for p in parts);calls=[]
            for p in parts:
                fc=p.get('functionCall')
                if fc: calls.append({'id':fc.get('name'),'type':'function','function':{'name':fc.get('name'),'arguments':json.dumps(fc.get('args',{}),ensure_ascii=False)}})
            return {'choices':[{'message':{'content':text,'tool_calls':calls}}],'usage':d.get('usageMetadata',{})}
    async def stream(self,messages,model,**kwargs):
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            async with c.stream('POST',f'{self.base_url.rstrip("/")}/v1beta/models/{model}:streamGenerateContent?alt=sse&key={self.api_key}',json=self._body(messages,kwargs)) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith('data:'): continue
                    try:
                        d=json.loads(line[5:].strip());parts=d.get('candidates',[{}])[0].get('content',{}).get('parts',[]);piece=''.join(p.get('text','') for p in parts)
                        if piece: yield piece
                    except json.JSONDecodeError: continue
