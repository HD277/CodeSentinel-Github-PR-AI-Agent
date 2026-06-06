# CodeSentinel

CodeSentinel is a self-hosted, AI-powered code review assistant. It connects to the GitHub API, parses Pull Request diffs, and runs multi-stage analysis using Gemini models to find logical bugs, security flaws, style/quality issues, and missing test cases.

It saves your review history locally in SQLite and displays reviews on a dashboard complete with an interactive 3D background animation.

## Features
- **PR Diff Parsing**: Fetches and parses GitHub Pull Request diffs, filtering out lockfiles and non-code assets automatically.
- **Multi-Stage Analysis**: Independent review pipeline steps checking for:
  - **Code Quality**: Design patterns, DRY violations, readability, complexity.
  - **Logical Bugs**: Edge cases, null references, leaks, logic errors.
  - **Security**: Hardcoded secrets, injection vulnerabilities, common exploits.
  - **Test Coverage**: Suggests unit and integration tests for newly added logic.
- **Local Database**: Stores review history and statistics locally using `aiosqlite`.
- **Modern Dashboard**: Clean frontend dashboard featuring filters, analytics, expandable cards, and a custom 3D raining symbol animation in Three.js.

---

## Getting Started

### Setup Environment Variables
1. Copy the template env file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your keys:
   - `GEMINI_API_KEY`: Required. Get one from Google AI Studio.
   - `GITHUB_TOKEN`: Optional. Set this to avoid public rate-limiting on large repositories.

---

## Installation & Running

### Method 1: Running Locally (Python)

Ensure you have Python 3.9 or higher installed.

1. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

2. **Activate the environment**:
   - **Windows (PowerShell)**:
     ```powershell
     .\venv\Scripts\Activate
     ```
   - **macOS / Linux**:
     ```bash
     source venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the server**:
   ```bash
   python main.py
   ```

5. Access the dashboard at **http://localhost:8000** in your browser.
6. To stop, use `Ctrl+C` in the terminal and type `deactivate` to exit the virtual environment.

---

### Method 2: Running with Docker

1. Build the image:
   ```bash
   docker build -t codesentinel .
   ```

2. Start the container with your `.env` variables loaded:
   ```bash
   docker run -p 8000:8000 --env-file .env codesentinel
   ```

3. Open **http://localhost:8000** in your web browser.

---

## Project Structure

```
├── backend/
│   ├── agent/            # Agent pipeline and steps (quality, bugs, security)
│   ├── api.py            # FastAPI routes and static asset serving
│   ├── config.py         # App configuration settings
│   ├── database.py       # SQLite database layer (aiosqlite)
│   ├── diff_parser.py    # Git patch parser
│   ├── github_client.py  # GitHub API client
│   └── models.py         # Pydantic data schemas
├── data/                 # Auto-created directory for sqlite database files
├── frontend/             # Dashboard single-page application (HTML/CSS/JS)
├── main.py               # Application entrypoint
└── Dockerfile            # Container definition
```
