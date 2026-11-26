# OpenGlaze API Reference

Current REST API for the Flask app in this repository.

**Base URL:** `http://localhost:8768/api` for Docker, `http://localhost:8767/api` for manual local runs unless `FLASK_PORT` is set.

**Authentication model:** default personal mode is single-user and mostly unauthenticated. Studio collaboration uses the lightweight simple-auth token returned by `/api/auth/simple-login`.

## Health

```http
GET /health
GET /api/health
GET /api/mode
```

`/health` returns a basic status/version payload. `/api/health` also reports mode, feature flags, and rate-limit stats. `/api/mode` returns the current run mode (`personal` or `cloud`) with its feature flags.

## Auth

### Simple login

```http
POST /api/auth/simple-login
Content-Type: application/json

{
  "display_name": "Jane Potter"
}
```

Response:

```json
{
  "user_id": "u_...",
  "display_name": "Jane Potter",
  "token": "..."
}
```

Send the token as:

```http
Authorization: Bearer <token>
```

### Current user

```http
GET /api/auth/me
Authorization: Bearer <token>
```

## Glazes

```http
GET /api/glazes
GET /api/glazes/<glaze_id>
POST /api/glazes
PUT /api/glazes/<glaze_id>
DELETE /api/glazes/<glaze_id>
GET /api/glazes/<glaze_id>/umf?cone=10
GET /api/glazes/<glaze_id>/versions
POST /api/glazes/<glaze_id>/versions
```

Create/update payloads use the glaze fields accepted by `Glaze.from_dict`, including `id`, `name`, `family`, `hex`, `chemistry`, `behavior`, `layering`, `warning`, `recipe`, `catalog_code`, `food_safe`, `notes`, and `cone`.

### Recipe versions

`POST /api/glazes/<glaze_id>/versions` saves a recipe as the glaze's newest version and current recipe:

```json
{
  "recipe": "Custer Feldspar 45, Silica 25, Whiting 18, EPK 12, +Red Iron Oxide 2",
  "note": "add iron",
  "cone": "6"
}
```

It returns `201` with the saved version (`id`, `glaze_id`, `recipe`, `note`, `cone`, `created_at`). The first save of a glaze that already had a recipe also stores that earlier recipe as a version with the note "Recipe before first edit". `GET` lists versions newest first. Both return `404` for an unknown glaze.

### Batch sheets

`POST /api/batch-sheet` scales a recipe for weighing out:

```json
{"recipe": "Custer Feldspar 45, Silica 25, Whiting 18, EPK 12, +Red Iron Oxide 2", "size": 1000, "basis": "base"}
```

`size` is in grams. With `basis` `base` (the default) the base materials weigh `size` and additions are scaled by the same factor on top; with `total` everything together weighs `size`. Materials keep their names as written, known to the library or not. The response has `rows` (`name`, `amount`, `addition`, `grams`, `running`, `known`, `lot`), base materials first, with weights rounded to 0.1 g and `running` adding the rounded weights; plus `base_grams`, `additions_grams`, `total_grams`, `base_percent` and `additions_percent`. `lot` is the studio's lot in use for that material, or null. Errors are 400 with a plain `message`.

## Combinations

```http
GET /api/combinations
GET /api/combinations?type=research-backed
GET /api/combinations?type=user-prediction
GET /api/combinations/grouped
GET /api/combinations/<combo_id>
POST /api/combinations
PUT /api/combinations/<combo_id>
POST /api/combinations/<combo_id>/promote
POST /api/combinations/<combo_id>/simulate
POST /api/combinations/simulate-all
GET /api/combinations/<combo_id>/compatibility?cone=10
```

## Chemistry

```http
POST /api/chemistry/umf
GET /api/chemistry/materials
POST /api/chemistry/batch
POST /api/chemistry/scale
POST /api/chemistry/compare
POST /api/chemistry/optimize
POST /api/chemistry/substitutions
POST /api/chemistry/defects
```

`POST /api/chemistry/umf` takes `{"recipe": "...", "cone": "6"}` and returns the UMF formula, ratios (`sio2_al2o3`, `flux_al2o3`, ...), estimated CTE (×10⁻⁶/°C), surface prediction, limit warnings and recommendations. It answers `200` for any well-formed request; `success` is `false` when the recipe cannot be fully calculated, and with unknown materials the partial UMF is still returned with `missing_materials` listing what was left out. The recipe editor calls it while you type.

`GET /api/chemistry/materials` lists the known materials (`name`, `category`, `aliases`) and the cones that have limit ranges.

Examples:

```http
POST /api/chemistry/optimize
Content-Type: application/json

{
  "recipe": "Custer Feldspar 45, Silica 25, Whiting 18, EPK 12",
  "target": "reduce_cte",
  "max_suggestions": 5
}
```

```http
POST /api/chemistry/scale
Content-Type: application/json

{
  "recipe": "Custer Feldspar 45, Silica 25, Whiting 18, EPK 12",
  "batch_size_grams": 1000,
  "unit": "grams"
}
```

```http
POST /api/chemistry/compare
Content-Type: application/json

{
  "recipe_a": "Custer Feldspar 45, Silica 25, Whiting 18, EPK 12",
  "recipe_b": "Custer Feldspar 40, Silica 30, Whiting 18, EPK 12",
  "name_a": "Original",
  "name_b": "Revision",
  "cone": 10
}
```

## Materials

```http
GET /api/materials
POST /api/materials
PUT /api/materials/<key>
DELETE /api/materials/<key>
GET /api/materials/<key>/lots
POST /api/materials/<key>/lots
PUT /api/materials/<key>/current-lot
DELETE /api/materials/<key>/lots/<lot_id>
```

`<key>` is the material's lowercase name (`custer feldspar`), URL-encoded.

`GET /api/materials` lists the published library and the studio's own materials. Each entry has `key`, `name`, `aliases`, `category`, `oxides`, `loi`, `source`, `studio` (true for the studio's own), `current_lot` (or null) and `lot_count`. `source.type` is `supplier` (with `supplier`, `document`, `url`, `date`), `theoretical` (with `formula`), `unverified`, or `custom` (with `text`).

Analyses are weight percent **as received**: the oxides plus LOI make up the raw material.

`POST /api/materials` adds a studio material:

```json
{
  "name": "Creek Clay",
  "aliases": "creek, local red",
  "category": "clay",
  "oxides": {"SiO2": 58.0, "Al2O3": 20.0, "Fe2O3": 6.0, "K2O": 2.5, "CaO": 1.0},
  "loi": 11.5,
  "source": "Lab test, 2026",
  "notes": ""
}
```

Names and aliases must not clash with existing materials. Oxides must be ones the engine knows, and oxides plus LOI must come to 80-110%; a response's `warnings` notes totals outside 98-102%. `PUT` edits a studio material (not its name); library materials are read-only.

`POST /api/materials/<key>/lots` records a lot analysis (`lot`, `oxides`, `loi`, `source`, `current`, default true). While a lot is current, every calculation uses it instead of the material's standard analysis. `PUT .../current-lot` takes `{"lot_id": <id>}` to use a lot or `{"lot_id": null}` to go back to the standard analysis.

The CLI and MCP server calculate with the published library only.

## Insight-Live import

```http
POST /api/import/insight-live/preview
POST /api/import/insight-live
```

Both take the text of a recipe CSV exported from DigitalFire Insight-Live as `csv`; the server keeps nothing between the two calls. The export has one row per recipe (`Code`, `Name`, `Description`, `Date`, `Batch`, `Location`, one column per material, `Batch total (g)`, `Comments`). Columns other than those fixed ones are read as materials when every value in them is a number, and listed in `ignored_columns` otherwise.

The preview writes nothing. It returns:

- `recipes`: each with `row` (the line it starts on, used to choose recipes), `code`, `name`, `description`, `date`, `comments`, `materials` (`name`, `amount`, `addition`), `additions` (`none`, `found`, `guessed` or `unclear`), `base_total`, `additions_total`, `warnings`, and `existing` (null, or the glaze it would duplicate, with `reason` `code` when that Insight-Live code was imported before or `name` when a glaze has the same name).
- `materials`: each export material name with the `key` and `material` name it matched (null when unmatched), `partial` (only a leading part of the name matched), `source_type`, and how many `recipes` use it.
- `unmatched`: the material names that didn't match.

The export doesn't mark additions, and its material columns follow the order materials first appear across the recipes (oldest recipe first), so only a one-recipe export keeps a recipe's own order. The base is a set of materials adding up to 100 (within 0.1); the rest are additions. When only one set adds up, or a one-recipe export's leading materials do, `additions` is `found`. When several sets add up, the one that best fits the material types wins (colorants and opacifiers as additions; silica, feldspars, frits, fluxes and clays other than bentonite in the base), and `additions` is `guessed` unless the file order agrees. When no set adds up, or two fit equally well, `additions` is `unclear` and every material is imported as base.

`POST /api/import/insight-live` creates a glaze for each chosen recipe, in one transaction:

```json
{
  "csv": "Code,Name,...",
  "rows": [2, 5],
  "mapping": {"Tile #6 Kaolin": "epk"},
  "cone": "6"
}
```

`mapping` (optional) maps export material names to our material keys; unmapped names keep the export's spelling. `cone` (optional) is stored on every imported glaze. The response (201) lists `imported` glazes with `id`, `name`, `code`, `recipe` and `missing` (material names the calculator doesn't know yet). Each glaze gets the Insight-Live code, date, description and comments in its notes, a first recipe version noted "Imported from Insight-Live (code)", and a row in `glaze_imports` keeping the recipe as the export had it.

Errors are 400 with a plain `message` alongside `error`.

## Experiments

```http
GET /api/experiments
GET /api/experiments?stage=ideation
GET /api/experiments/active
GET /api/experiments/stats
GET /api/experiments/<exp_id>
POST /api/experiments
POST /api/experiments/<exp_id>/advance
POST /api/experiments/<exp_id>/result
POST /api/experiments/<exp_id>/archive
POST /api/experiments/<exp_id>/firing-log
POST /api/experiments/<exp_id>/share
```

## Test tiles

```http
GET /api/tiles
GET /api/tiles?glaze_id=<glaze_id>
GET /api/tiles/<tile_id>
POST /api/tiles
PUT /api/tiles/<tile_id>
DELETE /api/tiles/<tile_id>
POST /api/tiles/<tile_id>/photos
DELETE /api/tiles/<tile_id>/photos/<photo_id>
GET /tile-photos/<filename>
```

A tile records one fired test of a glaze. `POST /api/tiles` takes `glaze_id` (required) and any of `label`, `fired_on` (YYYY-MM-DD), `cone`, `atmosphere` (oxidation, reduction, neutral, salt or wood), `kiln`, `clay_body`, `application`, `result` and `verdict` (keep, retest or reject). `version_id` picks the saved recipe version tested; without it the glaze's current recipe is used. The tile stores a copy of that recipe in `recipe`, and keeps it when the glaze changes. `PUT` changes only the fields sent; sending `version_id` (null for the current recipe) or a different `glaze_id` takes that recipe as the one tested.

Tiles come back with `glaze_name` and `photos` (`id`, `url`, `created_at`), most recently fired first. Photos are uploaded as multipart form-data with the image in a `photo` field: JPEG, PNG or WebP, checked by content, up to 10 MB and 20 per tile. The browser app shrinks and re-encodes photos as JPEG before upload. Photo files are served from `/tile-photos/` under random names, cacheable indefinitely. Deleting a tile, or its glaze, deletes its photo files. Errors are 400 (`invalid_tile`, `invalid_photo`), 404 or 413 with a plain `message`.

## Experiment uploads and photos

```http
POST /api/upload
GET /api/photos
```

Upload expects multipart form-data with a `photo` field. Supported extensions are JPG, JPEG, PNG, and WebP; max size is 5 MB.

## AI assistant (Kama)

```http
POST /api/ask
POST /api/ask/stream
```

Both take a JSON body with `question` (required), optional `clear` (reset conversation memory), and optional `images` (list of base64-encoded strings).

`/api/ask` returns `{"response": "..."}`. When no AI backend is reachable (Ollama, LM Studio, or a configured cloud provider), it returns HTTP `503` with `{"ai_available": false, ...}` and setup hints — not a 500.

`/api/ask/stream` returns `text/event-stream` (SSE) with `data: {"type": "content"|"error", ...}` events; when the backend is down the error event carries `"ai_available": false`.

AI backends are self-hosted by default; nothing calls out to a cloud provider unless an API key is configured.

## Inbox

```http
GET /api/inbox
POST /api/inbox
```

Idea capture for the studio. `POST` takes a JSON body with `content` (required) plus optional `base`, `top`, and `notes`. Items are attributed to the simple-auth user when a Bearer token is sent.

## Studio collaboration

Studio endpoints require a simple-auth Bearer token.

```http
POST /api/studios
GET /api/studios
POST /api/studios/join
GET /api/studios/<studio_id>
DELETE /api/studios/<studio_id>
POST /api/studios/<studio_id>/regenerate-code
GET /api/studios/<studio_id>/lab-queue
POST /api/studios/<studio_id>/lab-queue/<combo_id>/claim
POST /api/studios/<studio_id>/lab-queue/<combo_id>/release
GET /api/studios/<studio_id>/my-claims
GET /api/studios/<studio_id>/experiments
```

## Templates

```http
GET /api/templates
GET /api/templates/<template_id>
POST /api/templates/<template_id>/apply
```

Applying a template identifies the caller the same way as the stats endpoints (simple-auth Bearer token in personal mode).

## Demo endpoints

```http
GET /api/demo/glazes
POST /api/demo/compatibility
```

These are public demo/reference endpoints backed by curated demo glaze data when available.

## Error format

Errors are returned as JSON:

```json
{
  "error": "Human-readable message"
}
```

Rate limits return HTTP `429` with a `Retry-After` header. JSON-body endpoints invoked without a JSON content-type return HTTP `415` as JSON — always send `Content-Type: application/json` with JSON payloads.
