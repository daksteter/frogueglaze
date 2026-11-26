# frogueglaze

A fork of [KyaniteLabs/openglaze](https://github.com/KyaniteLabs/openglaze), a
ceramic glaze calculator and recipe manager (Flask + SQLite, vanilla JS
frontend). The fork exists to replace DigitalFire Insight-Live for one pottery
studio, so features are judged by whether that studio needs them.

## Relationship to upstream

- This is a fork, not a contribution branch. Upstream is run largely by an
  automated bot pipeline; its org rules (issue-driven pipeline, labels,
  Blacksmith runners, KyaniteLabs branch protection) do not apply here.
- Remotes: `origin` = `daksteter/frogueglaze`, `upstream` = `KyaniteLabs/openglaze`.
  The fork was taken from upstream master at `dd56e41` (2026-11-23).
- `AGENTS.md`, `.cursorrules` and `.windsurfrules` are still upstream's
  KyaniteLabs files. Their "Agent Surfaces" notes (CLI, MCP, skill) are
  accurate; their org process rules are not. `tests/test_architecture_contract.py`
  requires `AGENTS.md` to mention `PRODUCT.md` and `ARCHITECTURE.md`.

## Fork goals

1. Fork and trim: remove features the studio won't use, tests green on Linux
   and on Windows.
2. Recipe editor with a live calculator (UMF, SiO2:Al2O3, estimated CTE, limit
   warnings), side-by-side comparison, saved versions.
3. A larger materials library from supplier data sheets, with the source of
   each analysis recorded; custom materials and lot analyses including LOI.
   DigitalFire's reference library is copyrighted: never copy from it.
4. An Insight-Live export importer that reports unmatched material names.
5. Validate UMF output against Insight-Live using real studio recipes.
6. Printable batch sheets, firing schedules, test-tile records with photos.

Likely cuts, **not yet confirmed — do not remove without asking**:
gamification (points, leaderboards), the prediction market, the SEO landing
pages, and the Ory Kratos + PostgreSQL cloud-auth stack.

## Setup and commands

Python 3.12 or newer (`requires-python` in `pyproject.toml`). On Debian the
`python3-venv` package is needed for a venv.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q          # tests (pytest.ini sets testpaths)
.venv/bin/ruff check .                 # lint, 120-char cap
.venv/bin/black --check .              # formatter is black (88), not ruff format
.venv/bin/python server.py             # app on http://localhost:8767
docker compose up -d                   # app on http://localhost:8768
```

Pin exact versions in `requirements*.txt`.

## Where things are

Read `ARCHITECTURE.md` and `PRODUCT.md` before larger changes; they separate
what is implemented from what is planned.

- Chemistry engine: `core/chemistry/` (`umf.py`, `optimizer.py`,
  `compatibility.py`, `materials.py`, `data_loader.py`). It is the solid part;
  most fork work is UI, data and parsing around it.
- Reference data: `ceramics-foundation/data/` (`materials.json` has 36 materials).
- HTTP app: `server.py` plus `webapp/routes/`; glaze CRUD is `webapp/routes/glazes.py`.
- Served frontend: `frontend/index.html` and `frontend/scripts/`. The older
  `static/dashboard.html` (with a "New Glaze" form) is not served.
- Agent interfaces: `openglaze_cli.py`, `openglaze_mcp.py`, `skills/openglaze/`.

## Cautions

- Starting the app creates and seeds its configured SQLite database. Use a
  throwaway database for experiments, never the studio's real one.
- Personal mode has no authentication; keep it bound to a private address.
- The default personal config points the AI assistant at an Ollama cloud model,
  so prompts and recipe context can leave the machine. Chemistry needs no AI.
- Chemistry results are estimates, not food-safety or kiln certification.
