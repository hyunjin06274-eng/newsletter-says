# Newsletter SaaS - Self-Correcting Pipeline with Modern UI

## Role
Full-Stack AI Agent Architect building a cloud-ready Newsletter SaaS.

## Context
Transform the existing local Python newsletter pipeline (6-country lubricant MI newsletter for SK Enmove) into a cloud-based SaaS with self-correcting quality loops.

### Existing Pipeline (Reference)
Source code at: `../뉴스레터 작성_24개 병렬ver/`
- Phase 0.5: LLM keyword generation (Gemini)
- Phase 1: 4-domain parallel news crawling (macro/industry/competitor/lubricant) x 6 countries
- Phase 1.5: Merge + dedupe
- Phase 2: Article scoring with LLM (Anthropic Claude)
- Phase 2.5: LLM snippet enrichment
- Phase 2.7: Similar article grouping
- Phase 3: HTML newsletter generation
- Phase 3.5: Quality validation
- Phase 4: Gmail API sending

### API Keys Available
- `ANTHROPIC_API_KEY` - Claude API (scoring, enrichment, newsletter generation)
- `GOOGLE_API_KEY` - Gemini (keyword generation) + Gmail OAuth2
- `TAVILY_API_KEY` - SNS content collection

## Task: Build These 4 Components

### 1. LangGraph Self-Correcting Workflow (`backend/agent/`)

Map existing phases to LangGraph nodes:
```
KeywordGenerator -> Collector -> Merger -> Scorer -> Enricher -> Grouper -> Writer -> Auditor
                                                                              ^          |
                                                                              |  (fail)  |
                                                                              +----------+
                                                                              (pass) -> Sender
```

- **Auditor Node**: LLM-based quality check (accuracy, tone, completeness)
  - Score < threshold: return feedback to Writer with specific issues
  - Max 3 iterations, then force-send with warning
- **State**: Use TypedDict with MemorySaver for checkpoint/resume
- Each node wraps the logic from existing scripts (import and adapt)

### 2. FastAPI Service Layer (`backend/main.py`, `backend/api/`)

Endpoints:
- `POST /api/runs` - Start a newsletter run (country, date, options)
- `GET /api/runs/{id}` - Get run status + progress
- `GET /api/runs/{id}/events` - SSE stream for real-time updates
- `GET /api/runs` - List all runs with pagination
- `GET /api/newsletters/{id}` - Get generated newsletter HTML
- `PUT /api/settings` - Update schedule, countries, recipients
- `GET /api/settings` - Get current settings

Use BackgroundTasks for async agent execution. SQLite for run history.

### 3. Next.js + Tailwind CSS Dashboard (`frontend/`)

Pages:
- `/` - Dashboard: active run status, recent newsletters, quick actions
- `/runs` - Run history with filters
- `/runs/[id]` - Single run detail with real-time progress
- `/settings` - Schedule, countries, recipients config
- `/newsletters/[id]` - Newsletter preview

Design:
- Dark/light mode toggle
- Status badges: Collecting, Scoring, Writing, Auditing, Sending, Complete, Failed
- Real-time progress via SSE
- Mobile responsive

### 4. Serverless Automation (`.github/workflows/`, `vercel.json`)

- GitHub Actions: cron schedule to trigger runs
- Vercel: Deploy frontend + serverless API functions
- Environment variables managed via Vercel/GitHub secrets

## Project Structure
```
newsletter-saas/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── requirements.txt
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py            # LangGraph workflow definition
│   │   ├── state.py            # State TypedDict
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── keyword_generator.py
│   │       ├── collector.py
│   │       ├── merger.py
│   │       ├── scorer.py
│   │       ├── enricher.py
│   │       ├── grouper.py
│   │       ├── writer.py
│   │       ├── auditor.py
│   │       └── sender.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── database.py
│   └── tests/
│       └── test_graph.py
├── frontend/
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── runs/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   ├── settings/page.tsx
│   │   └── newsletters/[id]/page.tsx
│   └── components/
│       ├── Dashboard.tsx
│       ├── RunCard.tsx
│       ├── StatusBadge.tsx
│       ├── ProgressTimeline.tsx
│       └── NewsletterPreview.tsx
├── .github/workflows/
│   └── schedule.yml
├── vercel.json
├── .env.example
├── .gitignore
└── README.md
```

## Completion Criteria

The project is DONE when:
1. `backend/agent/graph.py` has a working LangGraph workflow with all nodes and auditor loop
2. `backend/main.py` serves FastAPI with all endpoints listed above
3. `frontend/` has a working Next.js app with dashboard, run detail, and settings pages
4. `.github/workflows/schedule.yml` has a valid cron workflow
5. `vercel.json` has proper deployment config
6. All files are syntactically valid (Python passes `python -m py_compile`, TypeScript passes `npx tsc --noEmit`)

When all criteria are met, output:
<promise>NEWSLETTER SAAS COMPLETE</promise>

## Iteration Strategy

On each iteration:
1. Check what files exist and their completeness
2. Identify the most critical missing piece
3. Implement or fix it
4. Run syntax checks on changed files
5. If all criteria met, output the promise tag
