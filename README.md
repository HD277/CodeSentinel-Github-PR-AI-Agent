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
│   ├── agent/            # Agent pipeline and steps (quality, bugs, security, critic, changelog)
│   ├── eval/             # Golden evaluation dataset and regression runner
│   ├── api.py            # FastAPI routes, webhook receiver, and static asset serving
│   ├── config.py         # App configuration settings
│   ├── database.py       # SQLite database layer (aiosqlite)
│   ├── diff_parser.py    # Git patch parser
│   ├── github_client.py  # GitHub API client and review posting helper
│   └── models.py         # Pydantic data schemas
├── data/                 # Auto-created directory for sqlite database files
├── frontend/             # Dashboard single-page application (HTML/CSS/JS)
├── main.py               # Application entrypoint
├── render.yaml           # Deployment blueprint configuration file
└── Dockerfile            # Container definition
```

---

## GitHub Webhook Integration (Active Code Review)

CodeSentinel can run as an active CI/CD agent, listening to GitHub Pull Request webhook events. When a PR is created or updated, CodeSentinel processes the changes in the background and posts the inline review comments directly back to the GitHub PR.

### Setup Instructions

1. **Enable GitHub Token**:
   Make sure you have a GitHub Personal Access Token (PAT) configured in your `.env` as `GITHUB_TOKEN`. The token needs `write` permission on the `pull requests` scope of the repository.

2. **Add Webhook to GitHub Repository**:
   - Go to your GitHub repository -> **Settings** -> **Webhooks** -> **Add webhook**.
   - **Payload URL**: `https://your-domain.com/api/webhook/github` (or your local ngrok URL for testing).
   - **Content type**: `application/json`.
   - **Which events**: Select **Let me select individual events** and check **Pull requests**. Uncheck everything else.
   - Click **Add webhook**.

---

## Automated Evaluation Suite & Regression Testing

To verify the quality and precision of CodeSentinel's analysis and detect regressions before deployment, you can run the automated evaluation harness.

The harness runs the review pipeline against a "golden dataset" of code changes containing known vulnerabilities, bugs, and quality concerns. It evaluates findings using LLM-as-a-judge for Precision and maps them to expectations for Recall.

### Running Evaluations

Ensure your environment variables are configured, then run:

```bash
python -m backend.eval.run_eval
```

On execution, the script:
1. Reviews all test cases in `backend/eval/dataset.py`.
2. Computes **Precision, Recall, JSON Success Rate, and Token/Latency metrics**.
3. Compares metrics against `backend/eval/baseline.json`. If performance degrades (e.g. recall drops or JSON parsing errors occur), it exits with a non-zero code.
4. Generates a Markdown report and saves a JSON trace of the run in `backend/eval/reports/`.

---

## Deployment to Production (Self-Hosting)

CodeSentinel is fully dockerized and ready for single-click deployment to popular hosting platforms.

### Deploying to Render
1. Create an account on [Render](https://render.com).
2. Click **New** -> **Blueprint**.
3. Connect your fork/repository.
4. Render will read `render.yaml` automatically. Define the `GEMINI_API_KEY` and `GITHUB_TOKEN` values in the environment variables screen.
5. Deploy. The blueprint sets up a persistent SQLite volume mounted at `/app/data` to preserve your dashboard history between restarts.
