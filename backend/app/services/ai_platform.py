from dataclasses import dataclass
from typing import Any
from ..config import settings
from .providers import OpenAICompatibleProvider, AnthropicProvider, GeminiProvider
@dataclass(frozen=True)
class ModelProfile:
    name:str; provider:str; base_url:str; api_key:str; context_tokens:int; vision:bool; audio:bool; tool_calling:bool; structured_output:bool; reasoning:int; streaming:bool; input_cost_per_1k:float; output_cost_per_1k:float; quality:int; speed:int; reliability:int; is_fallback:bool=False
    def adapter(self):
        if self.provider=='anthropic': return AnthropicProvider(self.base_url or settings.ai_anthropic_base_url,self.api_key or settings.ai_anthropic_api_key)
        if self.provider=='gemini': return GeminiProvider(self.base_url or settings.ai_gemini_base_url,self.api_key or settings.ai_gemini_api_key)
        return OpenAICompatibleProvider(self.base_url,self.api_key)
class ModelRouter:
    def __init__(self):
        self.profiles=[
          ModelProfile(settings.ai_model,settings.ai_provider_type,settings.ai_base_url,settings.ai_api_key,settings.ai_context_tokens,True,True,True,True,3,True,settings.ai_input_cost_per_1k,settings.ai_output_cost_per_1k,3,4,4),
          ModelProfile(settings.ai_pro_model,settings.ai_pro_provider_type,settings.ai_base_url,settings.ai_api_key,settings.ai_context_tokens,True,True,True,True,4,True,settings.ai_input_cost_per_1k,settings.ai_output_cost_per_1k,4,3,4),
          ModelProfile(settings.ai_premium_model,settings.ai_premium_provider_type,settings.ai_base_url,settings.ai_api_key,settings.ai_context_tokens,True,True,True,True,5,True,settings.ai_input_cost_per_1k,settings.ai_output_cost_per_1k,5,2,4)]
        if settings.ai_fallback_base_url and settings.ai_fallback_api_key:
            self.profiles.append(ModelProfile(settings.ai_fallback_model or settings.ai_model,'openai_compatible',settings.ai_fallback_base_url,settings.ai_fallback_api_key,settings.ai_context_tokens,False,False,True,False,3,True,settings.ai_input_cost_per_1k,settings.ai_output_cost_per_1k,4,3,3,True))
    def route(self,plan='free',task='chat',preference='balanced',capabilities=None,healthy_providers=None):
        capabilities=set(capabilities or [])
        allowed={'free':0,'pro':1,'premium':2}.get(plan,0)
        candidates=self.profiles[:allowed+1] or self.profiles[:1]
        if healthy_providers: candidates=[x for x in candidates if x.provider in healthy_providers] or candidates
        def compatible(p):
            return all(getattr(p,cap,False) for cap in capabilities)
        candidates=[p for p in candidates if compatible(p)] or candidates
        def score(p):
            quality=p.quality*3 if preference=='quality' else p.speed*3 if preference=='speed' else p.quality*2+p.speed
            task_bonus=p.reasoning if task in {'agent','research','coding','analysis','reasoning'} else 0
            cost_penalty=p.input_cost_per_1k+p.output_cost_per_1k
            return quality+p.reliability+task_bonus-(cost_penalty*0.01)
        chosen=max(candidates,key=score)
        return chosen,{"task":task,"plan":plan,"preference":preference,"required_capabilities":sorted(capabilities),"reason":"capability + plan + provider health + quality/speed/reliability/cost scoring"}
    def candidates(self,plan='free',task='chat',preference='balanced',capabilities=None,exclude_providers=None):
        capabilities=set(capabilities or [])
        excluded=set(exclude_providers or [])
        allowed={'free':0,'pro':1,'premium':2}.get(plan,0)
        plan_candidates=self.profiles[:allowed+1] or self.profiles[:1]
        fallback_candidates=[p for p in self.profiles if p.is_fallback]
        candidates=plan_candidates + [p for p in fallback_candidates if p not in plan_candidates]
        candidates=[p for p in candidates if p.provider not in excluded and all(getattr(p,cap,False) for cap in capabilities)]
        def score(p):
            quality=p.quality*3 if preference=='quality' else p.speed*3 if preference=='speed' else p.quality*2+p.speed
            task_bonus=p.reasoning if task in {'agent','research','coding','analysis','reasoning'} else 0
            cost_penalty=p.input_cost_per_1k+p.output_cost_per_1k
            return quality+p.reliability+task_bonus-(cost_penalty*0.01)
        return sorted(candidates,key=score,reverse=True)
    def choose(self,*args,**kwargs): return self.route(*args,**kwargs)[0]
    @staticmethod
    def estimate_cost(usage,profile): return int(usage.get('prompt_tokens',usage.get('input_tokens',0)))/1000*profile.input_cost_per_1k+int(usage.get('completion_tokens',usage.get('output_tokens',0)))/1000*profile.output_cost_per_1k
router=ModelRouter()
