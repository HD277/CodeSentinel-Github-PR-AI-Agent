"""Golden dataset for CodeSentinel evaluation and benchmarking.

Each case represents a pull request file containing a specific category of issue
along with annotated ground-truth issues for calculating precision and recall.
"""

from backend.models import DiffFile

GOLDEN_DATASET = [
    {
        "id": "case_1_sql_injection",
        "description": "Critical SQL Injection vulnerability via string formatting",
        "files": [
            DiffFile(
                filename="auth.py",
                language="python",
                additions=15,
                deletions=2,
                status="modified",
                patch=(
                    "@@ -3,6 +3,15 @@\n"
                    " def login_user(db_connection, username, password):\n"
                    "-    # TODO: implement authentication safely\n"
                    "-    pass\n"
                    "+    # Retrieve user record based on credentials\n"
                    "+    cursor = db_connection.cursor()\n"
                    "+    # Concatenating raw inputs directly into sql\n"
                    "+    query = f\"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'\"\n"
                    "+    cursor.execute(query)\n"
                    "+    user = cursor.fetchone()\n"
                    "+    if user:\n"
                    "+        return {\"id\": user[0], \"username\": user[1], \"authenticated\": True}\n"
                    "+    return {\"authenticated\": False}\n"
                ),
                added_lines=[
                    "    # Retrieve user record based on credentials",
                    "    cursor = db_connection.cursor()",
                    "    # Concatenating raw inputs directly into sql",
                    "    query = f\"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'\"",
                    "    cursor.execute(query)",
                    "    user = cursor.fetchone()",
                    "    if user:",
                    "        return {\"id\": user[0], \"username\": user[1], \"authenticated\": True}",
                    "    return {\"authenticated\": False}",
                ]
            )
        ],
        "pr_title": "Implement login database lookup",
        "expected_issues": [
            {
                "category": "security",
                "severity": "critical",
                "file": "auth.py",
                "line_start": 6,
                "line_end": 7,
                "keywords": ["sql injection", "execute", "concatenate", "query"],
            }
        ]
    },
    {
        "id": "case_2_resource_leak",
        "description": "Resource leak due to unclosed file descriptor",
        "files": [
            DiffFile(
                filename="file_helper.py",
                language="python",
                additions=10,
                deletions=1,
                status="modified",
                patch=(
                    "@@ -1,5 +1,10 @@\n"
                    " def read_config_values(path):\n"
                    "-    return {}\n"
                    "+    # Load config file manually\n"
                    "+    f = open(path, 'r')\n"
                    "+    data = f.read()\n"
                    "+    # Split lines and extract config key-value pairs\n"
                    "+    config = {}\n"
                    "+    for line in data.splitlines():\n"
                    "+        if '=' in line:\n"
                    "+            k, v = line.split('=', 1)\n"
                    "+            config[k.strip()] = v.strip()\n"
                    "+    return config\n"
                ),
                added_lines=[
                    "    # Load config file manually",
                    "    f = open(path, 'r')",
                    "    data = f.read()",
                    "    # Split lines and extract config key-value pairs",
                    "    config = {}",
                    "    for line in data.splitlines():",
                    "        if '=' in line:",
                    "            k, v = line.split('=', 1)",
                    "            config[k.strip()] = v.strip()",
                    "    return config",
                ]
            )
        ],
        "pr_title": "Add helper to read custom config file format",
        "expected_issues": [
            {
                "category": "bug",
                "severity": "warning",
                "file": "file_helper.py",
                "line_start": 2,
                "line_end": 4,
                "keywords": ["leak", "close", "with open", "resource"],
            }
        ]
    },
    {
        "id": "case_3_logic_off_by_one",
        "description": "Off-by-one logic bug in range calculation or slice",
        "files": [
            DiffFile(
                filename="array_utils.py",
                language="python",
                additions=8,
                deletions=1,
                status="modified",
                patch=(
                    "@@ -2,6 +2,13 @@\n"
                    " def get_sliding_windows(items, size):\n"
                    "-    return []\n"
                    "+    windows = []\n"
                    "+    # Off-by-one: should iterate up to len(items) - size + 1\n"
                    "+    # If range is len(items) - size, the last slice is missed\n"
                    "+    limit = len(items) - size\n"
                    "+    for i in range(limit):\n"
                    "+        windows.append(items[i:i + size])\n"
                    "+    return windows\n"
                ),
                added_lines=[
                    "    windows = []",
                    "    # Off-by-one: should iterate up to len(items) - size + 1",
                    "    # If range is len(items) - size, the last slice is missed",
                    "    limit = len(items) - size",
                    "    for i in range(limit):",
                    "        windows.append(items[i:i + size])",
                    "    return windows",
                ]
            )
        ],
        "pr_title": "Implement sliding window generator helper",
        "expected_issues": [
            {
                "category": "bug",
                "severity": "warning",
                "file": "array_utils.py",
                "line_start": 4,
                "line_end": 6,
                "keywords": ["off-by-one", "limit", "range", "miss", "index"],
            }
        ]
    }
]
