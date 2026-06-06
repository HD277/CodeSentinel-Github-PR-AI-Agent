import pytest
from backend.diff_parser import _detect_language, _should_skip_file, parse_pr_files


def test_detect_language():
    assert _detect_language("script.py") == "Python"
    assert _detect_language("app.js") == "JavaScript"
    assert _detect_language("main.cpp") == "C++"
    assert _detect_language("unknown.xyz") == "Unknown"


def test_should_skip_file():
    # Should skip lock files and minified files
    assert _should_skip_file("package-lock.json") is True
    assert _should_skip_file("vendor/jquery.min.js") is True
    assert _should_skip_file("app.css.map") is True

    # Should not skip code files
    assert _should_skip_file("src/main.py") is False
    assert _should_skip_file("components/App.tsx") is False


def test_parse_pr_files():
    mock_files = [
        {
            "filename": "src/main.py",
            "additions": 10,
            "deletions": 2,
            "status": "modified",
            "patch": "@@ -1,2 +1,10 @@\n+def new_func():\n+    pass"
        },
        {
            "filename": "package-lock.json",
            "additions": 1000,
            "deletions": 0,
            "status": "added",
            "patch": "@@ -0,0 +1,1000 @@\n+big json data"
        }
    ]

    diff_files = parse_pr_files(mock_files)

    # Should only parse main.py and skip package-lock.json
    assert len(diff_files) == 1
    
    f = diff_files[0]
    assert f.filename == "src/main.py"
    assert f.language == "Python"
    assert f.additions == 10
    assert f.deletions == 2
    assert f.status == "modified"
    assert len(f.added_lines) == 2
    assert "def new_func():" in f.added_lines
