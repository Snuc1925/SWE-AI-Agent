# SWE AI Agent - Skill Library and Evaluation Platform

A full-stack web application for managing an AI agent skill library and evaluating new `SKILL.md` files by format and content quality. The system is designed around a configurable rule-based evaluation profile: the LLM extracts structured features, while scoring is performed deterministically by user-defined rules.

---

## Features

### Skill library management
- Browse a curated Software Engineering skill library grouped by category
- View skill metadata, instructions, raw markdown, and extracted feature data
- Import new `.md` skill files and export existing skills
- Search skills by name, description, category, level, and tags
- Persist skill records in JSON files under `database/`

### Configurable skill evaluation
- Evaluate pasted or uploaded `SKILL.md` content
- Extract content features with an LLM using a configurable feature definition list
- Compute deterministic scores from boolean and integer features
- Configure feature definitions, percentile scoring, criteria, conditions, and score actions from the UI
- Cache feature extraction by profile hash and source hash to reduce repeated LLM calls
- Export evaluation results as an HTML report

### Feature synchronization and visualization
- Sync extracted features for all skills in the library
- Reuse cached feature values when the profile and skill content are unchanged
- Show sync logs for cache hits, LLM calls, successes, and failures
- Visualize feature distribution across the skill library

### Frontend application
- Single-page React application with Skill Browser, Skill Detail, and Evaluation screens
- Profile editor for LLM model configuration, feature definitions, bucket scoring, and criteria rules
- Feature correction flow before deterministic scoring
- Developer-friendly Vite dev server with Docker volume mounts for live code reload

---

## Project Structure

```text
source_code/
|-- backend/                         # Python backend shared by all services
|   |-- requirements.txt
|   |-- Dockerfile
|   |-- shared/                      # Shared config, schemas, DB helpers, markdown parser
|   `-- services/
|       |-- skill_management/        # Skill CRUD, import/export, registry search
|       |-- skill_evaluation/        # Feature extraction, rule engine, calibration, HTML export
|       `-- skill_testing/           # Experimental runtime testing code, not started by compose
|
|-- frontend/                        # React + TypeScript + Vite UI
|   `-- src/
|       |-- api/client.ts            # API client and shared frontend types
|       |-- pages/SkillBrowser.tsx   # Library browser, sync, visualization
|       |-- pages/SkillDetail.tsx    # Skill detail and extracted features
|       `-- pages/EvaluationPage.tsx # Evaluation profile editor and scoring UI
|
|-- skill-library/                   # 100 curated Software Engineering skills
|   |-- api-backend/
|   |-- frontend/
|   |-- testing/
|   |-- devops-platform/
|   |-- security/
|   `-- ...
|
|-- database/                        # JSON persistence
|   |-- skills.json
|   |-- evaluation_feature_cache.json
|   `-- evaluation_profiles/
|       `-- default_distribution.json
|
|-- docker-compose.yml               # Development/runtime composition
|-- .env.example                     # LLM configuration example
|-- README.md
`-- API.md
```

---

## Prerequisites

| Tool | Minimum version | Notes |
|------|-----------------|-------|
| Docker | 24+ | Recommended way to run the project |
| Docker Compose | v2+ | Used by `docker compose` |
| Node.js | 18+ | Only needed for local frontend development outside Docker |
| Python | 3.10+ | Only needed for local backend development outside Docker |
| DeepSeek API key | optional but recommended | Required for live LLM feature extraction |

---

## Getting Started

### 1. Configure environment variables

```bash
cd source_code
cp .env.example .env
```

Edit `.env` if you want live LLM extraction:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

If no API key is provided, endpoints that require live LLM extraction return a clear error. Cached feature data can still be displayed when available.

### 2. Start the application

```bash
docker compose up
```

Services:

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3002 | Main web UI |
| Skill Management API | http://localhost:8001/docs | Skill library API |
| Skill Evaluation API | http://localhost:8002/docs | Evaluation and feature extraction API |

The compose file mounts:

```text
./skill-library -> /data/skills
./database      -> /database
./backend       -> /app
./frontend      -> /app
```

Backend and frontend code changes are picked up without rebuilding the Docker images.

---

## Usage

### Browse the skill library

1. Open http://localhost:3002.
2. Go to **Skill Browser**.
3. Filter skills by level or category, search by text, and open a skill detail page.
4. Use **Sync Features** to extract or refresh feature values for the library.
5. Open the visualization tab to inspect how feature values are distributed across skills.

### Evaluate a new skill

1. Go to **Evaluation**.
2. Paste markdown content or upload a `SKILL.md` file.
3. Edit the evaluation profile if needed:
   - LLM model and API key
   - feature definitions
   - percentile scoring scheme
   - criteria and deterministic rule steps
4. Click **Extract Features** to inspect and correct feature values.
5. Click **Score Reviewed Features** or **Evaluate Directly**.
6. Export the result as an HTML report when needed.

### Configure the evaluation profile

The default profile is stored at:

```text
database/evaluation_profiles/default_distribution.json
```

The profile defines:

- `llm`: provider, base URL, model, and API key
- `features`: boolean/integer feature definitions and extraction guidance
- `bucket_scheme`: score mapping for percentile-based integer scoring
- `criteria`: deterministic rule steps such as `force_score`, `set_score_from_bucket`, `add`, `subtract`, `cap_max`, and `set_baseline`
- `format_features` and `format_criteria`: deterministic format checks built from markdown/frontmatter parsing

---

## API Reference

Detailed API documentation is available in [API.md](./API.md).

Interactive docs:

| Service | Swagger UI |
|---------|------------|
| Skill Management | http://localhost:8001/docs |
| Skill Evaluation | http://localhost:8002/docs |

Important endpoints:

| Method | Path | Service | Description |
|--------|------|---------|-------------|
| `GET` | `/skills` | Management | List skills |
| `POST` | `/skills/import` | Management | Import a `SKILL.md` file |
| `GET` | `/skills/{skill_id}` | Management | Get full skill detail |
| `GET` | `/skills/{skill_id}/export` | Management | Export markdown |
| `POST` | `/evaluate/markdown` | Evaluation | Extract features and score markdown |
| `POST` | `/evaluate/features` | Evaluation | Extract features only |
| `POST` | `/evaluate/score-features` | Evaluation | Score reviewed feature values |
| `POST` | `/evaluate/export-html` | Evaluation | Export evaluation result as HTML |
| `GET` | `/evaluation/profiles/default` | Evaluation | Load the default profile |
| `PUT` | `/evaluation/profiles/default` | Evaluation | Save the default profile |

---

## Development

### Frontend only

```bash
cd source_code/frontend
npm install
npm run dev
```

The Vite dev server proxies API calls:

```text
/api/management -> http://skill-management:8001
/api/evaluation -> http://skill-evaluation:8002
```

When running outside Docker, update proxy targets if needed.

### Backend only

```bash
cd source_code/backend
pip install -r requirements.txt
PYTHONPATH=. SKILLS_DIR=../skill-library JSON_DATABASE_DIR=../database \
uvicorn services.skill_management.main:app --reload --host 0.0.0.0 --port 8001
```

In another terminal:

```bash
cd source_code/backend
PYTHONPATH=. SKILLS_DIR=../skill-library JSON_DATABASE_DIR=../database \
EVALUATION_PROFILE_DIR=../database/evaluation_profiles \
uvicorn services.skill_evaluation.main:app --reload --host 0.0.0.0 --port 8002
```

### Useful checks

```bash
docker compose config --quiet
find skill-library -name SKILL.md | wc -l
```

The expected skill count is `100`.
