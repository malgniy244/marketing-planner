# Marketing Auction Planner

**Stack's Bowers & Ponterio · HK Office**

A planning tool for managing marketing tasks across auction cycles (Apr, Jun, Oct, Dec). Allows the team to pick ideas from the ideas bank, assign tasks to Ceci, track decisions, and annotate tasks for future cycles.

## Features

- **Auction Cycle Selector** — Switch between cycles (APR HK26, JUN, OCT, DEC)
- **Ideas Bank** — 80+ pre-loaded marketing ideas derived from historical task data, filterable by category
- **One-click Add** — Add any idea to the current cycle with a single click
- **Decision Tracking** — Mark each task as Do / Skip / Defer
- **Task Detail** — Set due dates, assignee, status, notes per task
- **Repeat Flag** — Mark tasks as "Always Do", "Never Again", or "Case by Case" for future cycle planning
- **Comments** — Team can comment on any task for context and discussion
- **Custom Tasks** — Add one-off tasks not in the ideas bank

## Deployment (Railway)

1. Create a new Railway project
2. Add a **PostgreSQL** database service
3. Deploy this repo as a new service
4. Set environment variables:
   - `APP_PASSWORD` — access password (default: `crystal2026`)
   - `SECRET_KEY` — any random string
   - `DATABASE_URL` — auto-set by Railway when you link the PostgreSQL service
5. The database schema and seed data are created automatically on first run

## Tech Stack

- **Backend**: Flask + psycopg3
- **Database**: PostgreSQL
- **Frontend**: Vanilla HTML/CSS/JS (no framework)
- **Deployment**: Railway
