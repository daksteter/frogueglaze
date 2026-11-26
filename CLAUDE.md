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

1. Fork and trim: remove features the studio won't use, tests green on
   Linux. (Done 2026-11-25. Windows test runs are not a priority.)
2. Recipe editor with a live calculator (UMF, SiO2:Al2O3, estimated CTE, limit
   warnings), side-by-side comparison, saved versions. (Built 2026-11-25.)
3. A larger materials library from supplier data sheets, with the source of
   each analysis recorded; custom materials and lot analyses including LOI.
   DigitalFire's reference library is copyrighted: never copy from it.
   (Built 2026-11-25. Still unverified, needing supplier sheets: G-200,
   F-4, generic Ball Clay, Barnard, Alkalifritte M1233, rutile. Spodumene is
   theoretical only: no supplier sheet could be sourced.)
4. An Insight-Live export importer that reports unmatched material names.
   (Built 2026-11-25; checked against one- and four-recipe exports. In a
   multi-recipe export the columns follow first appearance across recipes in
   code order, not each recipe's own order, so additions are often picked
   by material type and flagged "guessed".)
5. Validate UMF output against Insight-Live using real studio recipes.
   (Done 2026-11-25 with seven recipes: the UMF math matches Insight-Live
   to its display rounding; library differences stay under about 0.03 and
   trace to specific materials. Expansion runs 0.5-1.6 lower than
   Insight-Live's, a model difference. Still needed: supplier analyses
   for Tile #6 Kaolin and OM#4. The report and her data are in the
   git-ignored `private/` folder.)
6. Printable batch sheets, firing schedules, test-tile records with photos,
   and a deployment on an always-on studio computer (Docker, studio
   network only) with backups. (Batch sheets, test tiles and firing
   schedules built 2026-11-26.)

Removed from the fork on 2026-11-25; don't bring them back, including when
merging `upstream/master` (resolve conflicts there by keeping them deleted):

- Gamification: points, badges, streaks, the progress tracker, `/api/stats`,
  `/api/progress`.
- The prediction market: `/api/predictions*` and its tables. AI predictions
  for glaze combinations (`prediction_grade`, `simulate_combo`) stay.
- The SEO landing pages and discovery files under `docs/` (sitemap, robots,
  llms, ai.txt) and the routes that served them.
- The Ory Kratos + PostgreSQL stack and cloud mode. The app runs in personal
  mode only; `OPENGLAZE_MODE=cloud` raises `ConfigurationError`. Studio
  features identify people by simple-auth tokens (`core/auth/simple_auth.py`).

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
- Material library: `ceramics-foundation/data/materials.json`, the engine's only
  copy. Every entry records `source.type`: `supplier` (url, document, date; never
  digitalfire.com or glazy.org), `theoretical` (formula + yields, computed by
  `core/chemistry/formulas.py`), or `unverified`. `tests/test_materials_data.py`
  checks sources, formula math, totals and alias clashes. Names also match
  with spaces and punctuation ignored ("OM#4" finds "om4"), unless two
  materials share that form. Analyses are as
  received: oxide % + LOI = 100, and UMF uses the oxide % directly (never
  subtract LOI again).
- Studio materials and lot analyses: `core/studio_materials.py` (tables
  `custom_materials`, `material_lots`, `studio_state`), routes in
  `webapp/routes/materials.py`, UI in `frontend/scripts/components/MaterialsView.js`.
  `sync_engine()` runs before each request and layers them onto the library via
  `set_studio_materials()`; the CLI and MCP use the library only. Look materials
  up with `get_material()` / `resolve_material_key()`, never by holding a
  reference to the tables.
- HTTP app: `server.py` plus `webapp/routes/`; glaze CRUD is `webapp/routes/glazes.py`.
- Served frontend: `frontend/index.html` and `frontend/scripts/`. The older
  `static/dashboard.html` (with a "New Glaze" form) is not served.
- Agent interfaces: `openglaze_cli.py`, `openglaze_mcp.py`, `skills/openglaze/`.
- Recipe editor: `frontend/scripts/components/RecipeEditor.js` and
  `frontend/styles/recipe-editor.css`, backed by `POST /api/chemistry/umf`,
  `GET /api/chemistry/materials` and `/api/glazes/<id>/versions`
  (`webapp/routes/recipes.py`, `core/glazes/versions.py`, table
  `recipe_versions`). Recipes stay plain strings in `glazes.recipe`; a leading
  `+` marks an addition. New frontend files must also go in the precache list
  in `frontend/sw.js`, or its install fails.
- Batch sheets: `core/batch_sheet.py` (keeps names as written, base scaled to
  the size with additions on top, running totals, lot in use), route
  `POST /api/batch-sheet` in `webapp/routes/recipes.py`, UI
  `frontend/scripts/components/BatchSheet.js` (a dialog; printing copies the
  sheet into `#print-root` and print CSS hides everything else).
- Test tiles: `core/tiles.py` (tables `test_tiles`, `tile_photos`; a tile
  keeps a copy of the recipe it tested), routes in `webapp/routes/tiles.py`,
  UI `frontend/scripts/components/TileView.js` (the "Test tiles" view; it
  replaced upstream's experiment photo gallery). Photo files live in
  `TILE_PHOTOS_PATH`, by default `tile-photos/` beside the database
  (git-ignored: studio data), and are served from `/tile-photos/`. The
  browser re-encodes photos as JPEG before upload, dropping location data.
- Firing schedules: `core/firing.py` (table `firing_schedules`, segments as
  JSON; checks and timing from room temperature, full-speed segments
  estimated and flagged), routes in `webapp/routes/firing.py`, UI
  `frontend/scripts/components/FiringView.js`. `test_tiles.schedule_id`
  links tiles (added to older databases by `_run_migrations`). There are no
  presets: `ceramics-foundation/data/firing-schedules.json` cites
  Digitalfire, so don't seed from it.
- Insight-Live importer: `core/insight_live.py` reads the recipe CSV (one row
  per recipe, one column per material, no additions or cone marked) and
  matches names with `match_material_key()`, the calculator's own lookup.
  `core/glazes/importer.py` previews and writes glazes, a first version and a
  `glaze_imports` row (code + original amounts); routes in
  `webapp/routes/imports.py`, UI in `frontend/scripts/components/ImportView.js`.
  Tests use a made-up export; keep the studio's real recipes out of the repo.

## Cautions

- Starting the app creates and seeds its configured SQLite database. Use a
  throwaway database for experiments, never the studio's real one.
- Personal mode has no authentication; keep it bound to a private address.
- The default personal config points the AI assistant at an Ollama cloud model,
  so prompts and recipe context can leave the machine. Chemistry needs no AI.
- Chemistry results are estimates, not food-safety or kiln certification.
