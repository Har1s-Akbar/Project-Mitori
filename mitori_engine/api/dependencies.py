import os
from core_python.interfaces import EngineProtocol
from fastapi import Request, HTTPException
import redis.asyncio as redis
from managers.manager_cpp import engine_registry as cpp_registry
from managers.manager_python import engine_registry as python_registry

from dotenv import load_dotenv

load_dotenv()

ENGINE_MODE = os.getenv("ENGINE_MODE", "CPP").upper()

async def get_redis(requests:Request) ->redis.Redis:
    return requests.app.state.redis

def get_matching_engine(ticker: str) -> EngineProtocol:
    """
    Dynamically swaps the engine backend without changing route logic.
    """
    if ENGINE_MODE == "CPP":
        engine = cpp_registry.get_engine(ticker)
    elif ENGINE_MODE == "PYTHON":
        engine = python_registry.get_engine(ticker)
    else:
        raise HTTPException(status_code=500, detail="Invalid ENGINE_MODE")

    if not engine:
        raise HTTPException(status_code=400, detail=f"Market {ticker} not initialized.")
    
    return engine