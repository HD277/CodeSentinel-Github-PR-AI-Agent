import pytest
from httpx import AsyncClient, ASGITransport

from backend.api import app


@pytest.mark.asyncio
async def test_health_check():
    """Verify the health check endpoint returns 200 and expected format."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "CodeSentinel"
    assert "version" in data
    assert "gemini_configured" in data


@pytest.mark.asyncio
async def test_invalid_pr_url():
    """Verify that an invalid PR URL is rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/review", json={"pr_url": "https://github.com/invalid/url"})
    
    assert response.status_code == 400
    assert "Invalid GitHub PR URL" in response.json()["detail"]
