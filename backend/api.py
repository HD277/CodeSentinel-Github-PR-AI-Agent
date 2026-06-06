# FastAPI web application routes

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.models import ReviewRequest, ReviewResponse, ReviewHistoryItem
from backend.github_client import parse_pr_url, fetch_pr_metadata, fetch_pr_files
from backend.diff_parser import parse_pr_files
from backend.agent.pipeline import run_review
from backend import database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await database.init_db()
    print("  Database initialized.")
    yield


app = FastAPI(
    title="CodeSentinel API",
    version="1.0.0",
    description="AI-powered GitHub PR code review agent",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


# API routes


@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard page."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(str(index_path))


@app.get("/styles.css")
async def serve_css():
    """Serve the CSS file."""
    css_path = FRONTEND_DIR / "styles.css"
    return FileResponse(str(css_path), media_type="text/css")


@app.get("/app.js")
async def serve_js():
    """Serve the JavaScript file."""
    js_path = FRONTEND_DIR / "app.js"
    return FileResponse(str(js_path), media_type="application/javascript")


@app.post("/api/review", response_model=ReviewResponse)
async def create_review(request: ReviewRequest):
    """Submit a GitHub PR URL for AI-powered code review."""
    # Parse the PR URL
    try:
        owner, repo, pr_number = parse_pr_url(request.pr_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    print(f"Reviewing PR: {owner}/{repo}#{pr_number}")

    try:
        pr_metadata = await fetch_pr_metadata(owner, repo, pr_number)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch PR metadata from GitHub: {e}"
        )

    print(f"  PR Title: {pr_metadata.title}")
    print(f"  Author: {pr_metadata.author}")
    print(f"  Files Changed: {pr_metadata.files_changed}")

    # Fetch PR files/diff
    try:
        files_data = await fetch_pr_files(owner, repo, pr_number)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch PR diff from GitHub: {e}"
        )

    # Parse diff into structured format
    diff_files = parse_pr_files(files_data)

    if not diff_files:
        # No reviewable code files
        review = ReviewResponse(
            pr=pr_metadata,
            findings=[],
            summary="No reviewable code files found in this PR. The changes may only contain binary files, lock files, or other non-code assets.",
        )
        await database.save_review(review)
        return review

    print(f"  Reviewable files: {len(diff_files)}")
    print()

    # Run the AI review pipeline
    try:
        review = run_review(diff_files, pr_metadata)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Review pipeline failed: {e}"
        )

    # Save to database
    try:
        await database.save_review(review)
    except Exception as e:
        print(f"  Warning: Could not save review to database: {e}")

    return review


@app.get("/api/reviews", response_model=list[ReviewHistoryItem])
async def list_reviews():
    """List recent reviews."""
    return await database.get_reviews(limit=50)


@app.get("/api/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: str):
    """Get a specific review by ID."""
    review = await database.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.get("/api/stats")
async def get_stats():
    """Get aggregate review statistics."""
    return await database.get_stats()


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "CodeSentinel",
        "version": "1.0.0",
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "github_token_configured": bool(settings.GITHUB_TOKEN),
    }
