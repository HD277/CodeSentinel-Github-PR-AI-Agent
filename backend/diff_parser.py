# Parse diff patches from github api

from pathlib import Path

from backend.config import settings
from backend.models import DiffFile


# Allowed code files
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".vue", ".svelte", ".html", ".css", ".scss",
    ".sql", ".sh", ".bash", ".yaml", ".yml", ".toml", ".json",
}

# Ignore lockfiles and assets
SKIP_PATTERNS = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.lock", "poetry.lock", "Gemfile.lock",
    ".min.js", ".min.css", ".map",
}


def _detect_language(filename: str) -> str:
    # get lang name from extension
    ext_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".jsx": "React JSX", ".tsx": "React TSX", ".java": "Java",
        ".go": "Go", ".rs": "Rust", ".cpp": "C++", ".c": "C",
        ".h": "C/C++ Header", ".hpp": "C++ Header", ".cs": "C#",
        ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
        ".kt": "Kotlin", ".scala": "Scala", ".vue": "Vue",
        ".svelte": "Svelte", ".html": "HTML", ".css": "CSS",
        ".scss": "SCSS", ".sql": "SQL", ".sh": "Shell",
        ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
        ".json": "JSON",
    }
    ext = Path(filename).suffix.lower()
    return ext_map.get(ext, "Unknown")


def _should_skip_file(filename: str) -> bool:
    # check if file matches skip patterns
    # Skip binary/lock files
    for pattern in SKIP_PATTERNS:
        if filename.endswith(pattern):
            return True

    # Only review known code extensions
    ext = Path(filename).suffix.lower()
    if ext and ext not in CODE_EXTENSIONS:
        return True

    return False


def _extract_added_lines(patch: str) -> list[str]:
    # pull lines that start with +
    added = []
    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])  # Remove the leading +
    return added


def parse_pr_files(files_data: list[dict]) -> list[DiffFile]:
    # parse github payload into list of diffs
    diff_files = []

    for file_data in files_data:
        filename = file_data.get("filename", "")

        # Skip non-code files
        if _should_skip_file(filename):
            continue

        patch = file_data.get("patch", "")

        # Skip files with no patch (binary files, etc.)
        if not patch:
            continue

        # Skip files that are too large
        if len(patch) > settings.MAX_DIFF_SIZE:
            patch = patch[:settings.MAX_DIFF_SIZE] + "\n... [truncated — diff too large]"

        diff_file = DiffFile(
            filename=filename,
            language=_detect_language(filename),
            additions=file_data.get("additions", 0),
            deletions=file_data.get("deletions", 0),
            patch=patch,
            added_lines=_extract_added_lines(patch),
            status=file_data.get("status", "modified"),
        )
        diff_files.append(diff_file)

    # Limit number of files
    if len(diff_files) > settings.MAX_FILES_PER_REVIEW:
        diff_files = diff_files[:settings.MAX_FILES_PER_REVIEW]

    return diff_files
