# FastAPI web application routes

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.models import ReviewRequest, ReviewResponse, ReviewHistoryItem
from backend.github_client import parse_pr_url, fetch_pr_metadata, fetch_pr_files, get_latest_pr_commit_sha, post_pr_review
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


async def process_webhook_review(owner: str, repo: str, pr_number: int, pr_url: str):
    """Processes a PR review asynchronously and posts comments back to GitHub."""
    try:
        # Fetch PR metadata
        pr_metadata = await fetch_pr_metadata(owner, repo, pr_number)
        # Fetch PR files/diff
        files_data = await fetch_pr_files(owner, repo, pr_number)
        # Parse diff
        diff_files = parse_pr_files(files_data)
        
        if not diff_files:
            print(f"No reviewable files found for {owner}/{repo}#{pr_number}")
            return
            
        # Run review pipeline
        review = run_review(diff_files, pr_metadata)
        
        # Save to DB
        await database.save_review(review)
        
        # Post back to Github if GitHub token is configured
        if settings.GITHUB_TOKEN:
            try:
                commit_sha = await get_latest_pr_commit_sha(owner, repo, pr_number)
            except Exception as e:
                print(f"Error getting commit SHA for {owner}/{repo}#{pr_number}: {e}")
                commit_sha = ""
                
            comments = []
            global_findings = []
            
            for finding in review.findings:
                # Group findings by whether they map to a specific line
                line = finding.line_start if finding.line_start > 0 else finding.line_end
                if line > 0:
                    body_text = f"### ⚠ {finding.category.value.upper()}: {finding.title}\n\n{finding.description}"
                    if finding.suggestion:
                        body_text += f"\n\n**Proposed Fix:**\n```\n{finding.suggestion}\n```"
                    comments.append({
                        "path": finding.file,
                        "line": line,
                        "side": "RIGHT",
                        "body": body_text
                    })
                else:
                    global_findings.append(finding)
            
            # Format the summary body
            body_parts = [
                f"## 🤖 CodeSentinel Code Review Summary",
                f"{review.summary}",
                f"### 📊 Review Stats",
                f"- **Files reviewed:** {review.stats.files_reviewed}",
                f"- **Total additions:** +{review.stats.total_additions}",
                f"- **Total deletions:** -{review.stats.total_deletions}",
                f"- **Total issues found:** {len(review.findings)} total ({review.critical_count} critical, {review.warning_count} warning(s))"
            ]
            
            if hasattr(review, "changelog") and review.changelog:
                body_parts.extend([
                    "### 📝 Non-Technical Product Impact & Changelog",
                    review.changelog
                ])
            
            if global_findings:
                body_parts.append("### 🌐 Global/Repository-wide Findings")
                for gf in global_findings:
                    gf_text = f"- **[{gf.severity.value.upper()}] {gf.title}** (in `{gf.file}`)\n  {gf.description}"
                    if gf.suggestion:
                        gf_text += f"\n  *Fix:* {gf.suggestion}"
                    body_parts.append(gf_text)
                    
            summary_body = "\n\n".join(body_parts)
            
            # Determine review event type (e.g. COMMENT or REQUEST_CHANGES if there are critical bugs)
            event_type = "COMMENT"
            if review.critical_count > 0:
                event_type = "REQUEST_CHANGES"
                
            await post_pr_review(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                commit_sha=commit_sha,
                comments=comments,
                body=summary_body,
                event=event_type
            )
            print(f"Posted review and {len(comments)} inline comments on {owner}/{repo}#{pr_number}")
        else:
            print("GITHUB_TOKEN not configured; skipping comment posting to GitHub.")
            
    except Exception as e:
        print(f"Error processing webhook review for {owner}/{repo}#{pr_number}: {e}")


@app.post("/api/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Listen for GitHub webhook pull_request events."""
    event_type = request.headers.get("X-GitHub-Event")
    if not event_type:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")
        
    if event_type == "ping":
        return {"message": "pong"}
        
    if event_type != "pull_request":
        return {"message": f"Event type '{event_type}' ignored"}
        
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
    action = payload.get("action")
    if action not in ["opened", "synchronize", "reopened"]:
        return {"message": f"Action '{action}' ignored"}
        
    pr_data = payload.get("pull_request", {})
    pr_number = payload.get("number")
    repo_data = payload.get("repository", {})
    repo_name = repo_data.get("name")
    owner_data = repo_data.get("owner", {})
    owner_login = owner_data.get("login")
    pr_url = pr_data.get("html_url")
    
    if not (owner_login and repo_name and pr_number):
        raise HTTPException(status_code=400, detail="Incomplete repository or pull request information in payload")
        
    # Queue review run in background
    background_tasks.add_task(
        process_webhook_review,
        owner_login,
        repo_name,
        pr_number,
        pr_url
    )
    
    return {
        "status": "processing",
        "message": f"Review queued for {owner_login}/{repo_name}#{pr_number} in the background."
    }

