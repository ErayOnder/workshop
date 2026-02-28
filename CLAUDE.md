# Workshop — Jewelry Style Generator

AI-powered jewelry photography generator with an agentic personalization loop. Users upload a product photo, receive 3 AI-generated scene candidates per round, give feedback via dynamic chips, and iterate until satisfied. The system accumulates creative context (corrections, liked/disliked tags, scene history) to steer each new round.

## Tech Stack

- **Frontend:** Next.js 16 + React 19 + TypeScript + Tailwind CSS 4 (App Router, client components)
- **Backend:** FastAPI (async) + SQLAlchemy async + asyncpg + PostgreSQL
- **AI:** Google Gemini — `gemini-2.5-flash` (text/vision), `gemini-3.1-flash-image-preview` (image generation)
- **Image processing:** Pillow (crop/resize at finalization)
- **Icons:** lucide-react

## Running Locally

```bash
# Backend (port 8001)
cd backend && uvicorn app.main:app --reload --port 8001

# Frontend (port 3001)
cd frontend && npm run dev
```

**Required env vars** (backend `.env`):
- `GEMINI_API_KEY` — Google Gemini API key
- `DATABASE_URL` — PostgreSQL connection string (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/workshop`)

**Frontend env** (`.env.local`):
- `NEXT_PUBLIC_API_URL=http://localhost:8001`

## Project Structure

```
workshop/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, lifespan (creates tables on startup)
│   │   ├── config.py            # Pydantic settings (env vars)
│   │   ├── db/
│   │   │   ├── database.py      # SQLAlchemy engine, async session factory, init_db()
│   │   │   └── models.py        # 5 ORM models
│   │   ├── schemas/             # Pydantic request/response models
│   │   │   ├── candidates.py    # CandidateOut, DynamicChip, ImageAnalysisData
│   │   │   ├── sessions.py      # CreateSessionResponse, NextRoundRequest/Response, FinalizeRequest/Response
│   │   │   ├── feedback.py      # FeedbackRequest/Response
│   │   │   └── __init__.py      # Re-exports all schemas
│   │   ├── crud/                # Data access (one file per model)
│   │   │   ├── users.py         # ensure_user()
│   │   │   ├── products.py      # create_product(), get_product()
│   │   │   ├── sessions.py      # create/get session, creative context, increment round, finalize
│   │   │   ├── candidates.py    # create candidate, status transitions, get for round
│   │   │   └── feedback.py      # create_or_update_feedback_event, get feedback IDs
│   │   ├── services/            # Business logic orchestration
│   │   │   ├── session_service.py      # handle_create_session, handle_next_round, handle_finalize
│   │   │   ├── feedback_service.py     # handle_feedback (extracts corrections, updates context)
│   │   │   └── generation_pipeline.py  # Background: scene briefs → DB records → SSE → image gen → analysis
│   │   ├── core/                # LLM calls & pure logic
│   │   │   ├── creative_director.py    # generate_scene_briefs() — Gemini text, 8-field schema
│   │   │   ├── image_generator.py      # generate_one() — Gemini image gen with reference photo
│   │   │   ├── image_analyzer.py       # analyze_image() — Gemini vision → like/dislike chips
│   │   │   ├── feedback_processor.py   # extract_corrections_and_updates(), update_creative_context()
│   │   │   └── sse_bus.py              # In-memory pub/sub (subscribe/unsubscribe/publish per session)
│   │   └── v1/                  # Route handlers (thin, delegate to services)
│   │       ├── router.py        # Main v1 router (includes sub-routers)
│   │       ├── sessions.py      # POST /sessions, /next-round, /finalize
│   │       ├── candidates.py    # GET /candidates (poll), /events (SSE stream)
│   │       ├── feedback.py      # POST /feedback
│   │       └── images.py        # GET /images/{filename}
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx           # Root layout (Inter font, metadata)
│   │   ├── page.tsx             # Screen router: upload → review → finalization
│   │   └── globals.css          # All styles (CSS vars, animations, component classes)
│   ├── lib/
│   │   ├── api.ts               # API client (fetch wrappers + SSE via EventSource)
│   │   ├── useSession.ts        # Main hook: session lifecycle, SSE listeners, feedback, state
│   │   └── types.ts             # All TS types + static chip constants
│   ├── components/
│   │   ├── UploadZone.tsx       # Drag-drop file upload with preview
│   │   ├── CategorySelector.tsx # ring/necklace/bracelet/earrings pills
│   │   ├── GenerateButton.tsx   # Sparkles icon, spinner on loading
│   │   ├── ProgressIndicator.tsx # "Round N · Option M/3"
│   │   ├── CandidateRow.tsx     # 3-column thumbnail grid with feedback badges
│   │   ├── Podium.tsx           # Large image display (shimmer/error states)
│   │   ├── FeedbackPanel.tsx    # Like/dislike/save buttons + chip tray toggle
│   │   ├── ChipTray.tsx         # Dynamic LLM chips + static fallback + "other" text input
│   │   └── FinalizationView.tsx # Hero image + feed/story exports with download links
│   └── package.json
└── CLAUDE.md
```

## Database Models (5 tables)

| Table | Key Columns | Notes |
|-------|------------|-------|
| **users** | id (uuid PK), created_at | Anonymous, ID stored in frontend localStorage |
| **products** | id, user_id (FK), category, image_filename | Reference product photo |
| **sessions** | id, user_id (FK), product_id (FK), status, round_number, creative_context (JSON) | Status: active/finalized/abandoned |
| **candidates** | id, session_id (FK), round_number, generation_config (JSON), rendered_prompt, image_filename, generation_status, analysis_status, image_analysis (JSON), chip_dimension_map (JSON) | Index on (session_id, round_number) |
| **feedback_events** | id, session_id (FK), user_id (FK), candidate_id (FK), action, reason_tags (JSON), text_note, reward | Reward: like=1.0, dislike=-1.0, save=4.0 |

**creative_context** shape (accumulated across rounds):
```json
{
  "structural": {"model": "none|hand|partial|full", "dominance": "hero|balanced|subtle"},
  "corrections": ["PREFER: ...", "AVOID: ..."],
  "scene_history": ["Round N, slot: description"],
  "liked_tags": ["tag1"],
  "disliked_tags": ["tag2"]
}
```

## API Endpoints (v1)

| Method | Path | Status | Purpose |
|--------|------|--------|---------|
| POST | `/v1/sessions` | 202 | Create session (multipart: image + user_id + category). Returns immediately; pipeline runs in background |
| POST | `/v1/sessions/{id}/next-round` | 200 | Advance round (body: `{force: bool}`). 409 if feedback incomplete and force=false |
| POST | `/v1/sessions/{id}/feedback` | 200 | Submit feedback (body: `{candidate_id, action, reason_tags[], text_note?}`) |
| POST | `/v1/sessions/{id}/finalize` | 200 | Finalize session (body: `{selected_candidate_id}`). Returns hero + export URLs |
| GET | `/v1/sessions/{id}/candidates` | 200 | Poll candidate status (non-SSE fallback) |
| GET | `/v1/sessions/{id}/events` | SSE | Real-time stream of generation progress |
| GET | `/v1/images/{filename}` | 200 | Serve generated/uploaded images |

## SSE Events

| Event | When | Payload |
|-------|------|---------|
| `candidates_created` | DB records created, before image gen | All 3 candidates with status "pending" |
| `candidate_done` | Single image generated (or failed) | candidate_id, generation_status, image_url/error |
| `analysis_done` | Vision analysis complete for one candidate | candidate_id, analysis_status, image_analysis (chips) |
| `round_complete` | All candidates settled | session_id, round_number |
| `pipeline_error` | Unrecoverable pipeline failure | session_id, error message |

## Generation Pipeline (per round)

1. **Scene briefs** — `creative_director.generate_scene_briefs()` calls Gemini-2.5-Flash with creative context + category. Returns 3 scenes (slots: converge/explore/wildcard), each with 8-field schema (format_medium, subject, camera_framing, scene_setting, micro_details, product_action, lighting, negative_cues). A 9th field `product_fidelity` is always appended.
2. **DB insert** — 3 Candidate records created, SSE `candidates_created` published.
3. **Parallel image generation** — For each candidate: call Gemini-3.1-Flash-Image with reference product photo + compiled JSON prompt. Save PNG to `data/outputs/`.
4. **Per-image analysis** — After each image, call Gemini-2.5-Flash (vision) to generate 3-5 like chips and 3-5 dislike chips mapped to 14 preference dimensions. Analysis failure is non-fatal.
5. **Round complete** — SSE `round_complete` published when all candidates settle.

## Feedback Loop

1. User clicks like/dislike/save on a candidate.
2. `ChipTray` shows dynamic chips (from LLM analysis) or static fallback chips. User selects chips + optional text note.
3. Backend `feedback_processor.py` converts chips → natural-language corrections (`PREFER: ...` / `AVOID: ...`), updates liked/disliked aesthetic tags, detects structural preferences (e.g., `model_distracts` → `model: none`).
4. `creative_context` merges new corrections (deduplicated), migrates tags between liked/disliked, caps scene history at 15.
5. Next round's scene briefs incorporate full accumulated context.

## Frontend Architecture

- **State:** Single `useSession()` hook manages everything (no Redux/Zustand). Three phases: upload → review → finalization.
- **SSE-first:** EventSource opened immediately after session creation. Candidates appear via SSE events, not polling.
- **Optimistic updates:** Feedback stored locally before API confirms. `pendingFeedbackRequestsRef` tracks in-flight requests.
- **Auto-advance:** After submitting feedback, selection jumps to next unactioned candidate.
- **User ID:** Stored in `localStorage` as `workshop_user_id`, sent with session creation.
- **Styling:** Tailwind v4 + custom CSS classes in `globals.css`. Dark theme with purple accent (`#7b6fff`). No Tailwind utility classes in JSX — all styles via CSS classes.

## Key Design Decisions

- **SSE over polling:** Both session creation and next-round return immediately. All candidate progress delivered via SSE stream.
- **Thin routes → services → CRUD:** Route handlers are minimal; business logic in services; all DB access via CRUD functions.
- **3-candidate strategy:** Each round generates exactly 3 candidates with different creative strategies (converge on liked aesthetics, explore new direction, wildcard).
- **Dynamic chips:** Image analysis generates context-specific feedback options rather than fixed categories.
- **Non-fatal analysis:** Image analysis failure doesn't block the pipeline; candidate is usable without chips.
- **Async throughout:** FastAPI async routes, SQLAlchemy asyncio, asyncpg, async Gemini calls.
- **No auth:** Anonymous user ID in localStorage. No authentication middleware.

## Code Conventions

- Backend: Python async/await, type hints, Pydantic models for all request/response shapes
- Frontend: TypeScript strict mode, `"use client"` on all components, `@/*` path alias
- Error handling: routes catch ValueError → HTTPException; background pipeline catches all → SSE `pipeline_error`
- CORS: hardcoded to `http://localhost:3000` in backend config
- Image filenames validated with regex `^[a-zA-Z0-9_\-\.]+$`
