import os
os.environ.setdefault("DATABASE_URL","sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET","test-secret-test-secret-test-secret-123456")
os.environ.setdefault("AI_BASE_URL","https://example.invalid/v1")
os.environ.setdefault("AI_API_KEY","test-key")
os.environ.setdefault("RATE_LIMIT_STORAGE_URI","memory://")
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base,engine
@pytest.fixture
def client():
 Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
 with TestClient(app) as c: yield c
 Base.metadata.drop_all(engine)
