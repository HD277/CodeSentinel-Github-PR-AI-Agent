# sqlite database helper functions

import json
import uuid
from pathlib import Path

import aiosqlite

from backend.config import settings
from backend.models import (
    ReviewResponse,
    ReviewHistoryItem,
    Finding,
    PRMetadata,
    ReviewStats,
)

# Ensure the data directory exists
Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)


async def init_db():
    # create tables
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                pr_url TEXT NOT NULL,
                pr_title TEXT DEFAULT '',
                repo TEXT DEFAULT '',
                pr_number INTEGER DEFAULT 0,
                author TEXT DEFAULT '',
                total_findings INTEGER DEFAULT 0,
                critical_count INTEGER DEFAULT 0,
                warning_count INTEGER DEFAULT 0,
                info_count INTEGER DEFAULT 0,
                suggestion_count INTEGER DEFAULT 0,
                files_reviewed INTEGER DEFAULT 0,
                review_time_seconds REAL DEFAULT 0.0,
                tokens_used INTEGER DEFAULT 0,
                summary TEXT DEFAULT '',
                changelog TEXT DEFAULT '',
                findings_json TEXT DEFAULT '[]',
                pr_metadata_json TEXT DEFAULT '{}',
                stats_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()

        # Try to alter table to add changelog column in case db already existed
        try:
            await db.execute("ALTER TABLE reviews ADD COLUMN changelog TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass


async def save_review(review: ReviewResponse) -> str:
    # save review response
    review_id = review.id or str(uuid.uuid4())

    critical = sum(1 for f in review.findings if f.severity.value == "critical")
    warning = sum(1 for f in review.findings if f.severity.value == "warning")
    info = sum(1 for f in review.findings if f.severity.value == "info")
    suggestion = sum(1 for f in review.findings if f.severity.value == "suggestion")

    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("""
            INSERT INTO reviews (
                id, pr_url, pr_title, repo, pr_number, author,
                total_findings, critical_count, warning_count, info_count, suggestion_count,
                files_reviewed, review_time_seconds, tokens_used,
                summary, changelog, findings_json, pr_metadata_json, stats_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review_id,
            review.pr.url,
            review.pr.title,
            review.pr.repo_full_name,
            review.pr.pr_number,
            review.pr.author,
            len(review.findings),
            critical, warning, info, suggestion,
            review.stats.files_reviewed,
            review.stats.review_time_seconds,
            review.stats.tokens_used,
            review.summary,
            review.changelog,
            json.dumps([f.model_dump() for f in review.findings]),
            review.pr.model_dump_json(),
            review.stats.model_dump_json(),
            review.created_at,
        ))
        await db.commit()

    return review_id


async def get_review(review_id: str) -> ReviewResponse | None:
    # fetch by id
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
        row = await cursor.fetchone()

    if not row:
        return None

    findings = [Finding(**f) for f in json.loads(row["findings_json"])]
    pr = PRMetadata(**json.loads(row["pr_metadata_json"]))
    stats = ReviewStats(**json.loads(row["stats_json"]))

    # Handle older records where changelog is missing
    changelog_val = row["changelog"] if "changelog" in row.keys() else ""

    return ReviewResponse(
        id=row["id"],
        pr=pr,
        findings=findings,
        stats=stats,
        summary=row["summary"],
        changelog=changelog_val,
        created_at=row["created_at"],
    )


async def get_reviews(limit: int = 50) -> list[ReviewHistoryItem]:
    # fetch recent history list
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()

    return [
        ReviewHistoryItem(
            id=row["id"],
            pr_url=row["pr_url"],
            pr_title=row["pr_title"],
            repo=row["repo"],
            total_findings=row["total_findings"],
            critical_count=row["critical_count"],
            warning_count=row["warning_count"],
            review_time_seconds=row["review_time_seconds"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


async def get_stats() -> dict:
    # get aggregate stats
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cursor = await db.execute("""
            SELECT
                COUNT(*) as total_reviews,
                COALESCE(SUM(total_findings), 0) as total_findings,
                COALESCE(SUM(critical_count), 0) as total_critical,
                COALESCE(SUM(warning_count), 0) as total_warnings,
                COALESCE(AVG(review_time_seconds), 0) as avg_review_time,
                COALESCE(AVG(total_findings), 0) as avg_findings_per_review
            FROM reviews
        """)
        row = await cursor.fetchone()

    return {
        "total_reviews": row[0],
        "total_findings": row[1],
        "total_critical": row[2],
        "total_warnings": row[3],
        "avg_review_time": round(row[4], 2),
        "avg_findings_per_review": round(row[5], 1),
    }
