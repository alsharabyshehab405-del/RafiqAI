import time
from ..config import settings

_failures={}
_open_until={}

def allowed(provider:str):
    until=_open_until.get(provider,0)
    return time.monotonic() >= until

def success(provider:str):
    _failures[provider]=0
    _open_until.pop(provider,None)

def failure(provider:str):
    n=_failures.get(provider,0)+1
    _failures[provider]=n
    if n>=3:_open_until[provider]=time.monotonic()+30
