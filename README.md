# frogueglaze

> **A custom fork of [OpenGlaze](https://github.com/KyaniteLabs/openglaze)**, the free, open-source, self-hosted ceramic glaze calculator, trimmed and extended for one pottery studio moving off DigitalFire Insight-Live. The app still calls itself OpenGlaze. See [About this fork](#about-this-fork) for what's different from upstream.

**TL;DR:** OpenGlaze — open-source ceramic glaze calculator (UMF, CTE, recipe optimizer) you can self-host. Best for potters, ceramic artists, studios, and educators.

<p align="center">
  <img src="branding/openglaze-512.png" alt="OpenGlaze icon: a split-dipped shino and tenmoku test tile" width="160">
</p>

<p align="center">
  <strong>Free ceramic glaze calculator, recipe manager, and UMF analyzer.<br>100% open source. Self-hosted. No paywalls.</strong>
</p>

<p align="center">
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT">
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python 3.12+">
  </a>
  <a href="https://www.docker.com/">
    <img src="https://img.shields.io/badge/Docker-Ready-blue" alt="Docker Ready">
  </a>
</p>

<p align="center">
  <a href="#about-this-fork">About this fork</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#documentation">Docs</a> •
  <a href="#self-hosting">Self-Host</a>
</p>

---

## About this fork

frogueglaze is a fork of [KyaniteLabs/openglaze](https://github.com/KyaniteLabs/openglaze), taken from upstream `master` at commit `dd56e41` (2026-11-23). It exists to help one pottery studio replace DigitalFire Insight-Live, and features are kept, cut or added by whether that studio needs them.

It is not a contribution branch: changes here are not sent upstream, though self-contained pieces such as the Insight-Live importer may be offered back later. If you want the full OpenGlaze product, use [upstream](https://github.com/KyaniteLabs/openglaze).

### What's different from upstream

**Added**

- A **recipe editor** with live chemistry: UMF, SiO₂:Al₂O₃, estimated CTE, surface prediction and cone limit checks update as you type. Every save is kept as a version with a note, and any version or other glaze can be compared side by side. See the [user guide](docs/user-guide.md#the-recipe-editor).
- **Additions** in recipes: a leading `+` marks a colorant or opacifier listed after the base, for example `Custer Feldspar 45, Silica 25, Whiting 18, EPK 12, +Red Iron Oxide 2`.
- API endpoints for the editor: `POST /api/chemistry/umf`, `GET /api/chemistry/materials`, and `GET`/`POST /api/glazes/<id>/versions` ([API reference](docs/API.md)).
- A **Materials** view: every material's analysis, LOI and source. Each library analysis is marked as a supplier data sheet (linked), theoretical (calculated from the chemical formula), or unverified. The studio can add its own materials and record lot analyses; a lot in use replaces the standard analysis in every calculation. See the [user guide](docs/user-guide.md#materials).
- **Batch sheets**: print any recipe scaled to a batch size, with a running total for weighing into one bucket, additions on top of the base, and the lot in use. See the [user guide](docs/user-guide.md#batch-sheets).
- **Test tiles**: record each fired tile with the recipe it tested, firing, clay body, application, result, verdict and photos. Photos are shrunk in the browser, which also drops their location data. See the [user guide](docs/user-guide.md#test-tiles).
- **Firing schedules**: the studio's kiln programs, segment by segment, with each segment's time, the total, the firing curve and a printable card for the kiln. Test tiles link to the schedule they were fired with. See the [user guide](docs/user-guide.md#firing-schedules).
- An **Insight-Live importer**: choose a recipe CSV exported from Insight-Live, check how each material name matched the library (and pick a material for any that didn't), then import the recipes as glazes. Additions are worked out from the amounts, and each glaze keeps its Insight-Live code and comments. See the [user guide](docs/user-guide.md#importing-recipes).
- A larger library: 55 materials, 20 of them from supplier data sheets (Custer feldspar, nepheline syenite, EPK, Redart, bentonite, Hawthorn Bond, Old Hickory M-23, Alberta Slip, Ferro frits 3110/3124/3134/3195, Fusion frits F-2/F-12/F-19/F-69, Gerstley Borate, talc, wollastonite, ilmenite) and 29 calculated from chemical formulas. Six inherited entries are still marked unverified.

**Removed**

- Gamification: points, badges, streaks, leaderboards and the progress tracker.
- The prediction market (`/api/predictions*`). AI predictions for glaze combinations stay.
- The SEO landing pages and discovery files (sitemap, robots.txt, llms.txt), and the routes that served them.
- Cloud mode, with its Ory Kratos auth and PostgreSQL. The app runs in personal mode on SQLite; studio features use the simple display-name sign-in.

**Changed and fixed**

- **UMF calculation:** upstream subtracted LOI twice: from the batch amount and again through the oxide percentages, which already exclude it. Whiting, clays and carbonates were undercounted. For Custer 45, Silica 25, Whiting 18, EPK 12, upstream reports Al₂O₃ 0.63 and SiO₂ 5.60; the correct values are 0.46 and 3.94.
- The material library is one file, `ceramics-foundation/data/materials.json`, with a recorded source for every analysis. Upstream kept a separate hard-coded copy in the engine.
- Docker Compose runs one app container, with the database and test-tile photos on the `openglaze_data` volume and other uploads on `openglaze_uploads`.
- Windows: data files are read as UTF-8, and each request's database connection is closed, so the app and its tests no longer trip over cp1252 decoding or locked files.

### Plans

1. **Materials:** replace the remaining unverified analyses with supplier data sheets. DigitalFire's reference library is copyrighted and is not used.
2. **Validation:** run real studio recipes through both tools and compare the UMF numbers.
3. **Studio extras:** a deployment on a studio computer with backups. (Batch sheets, test tiles and firing schedules are done.)

### Staying in sync with upstream

```bash
git remote add upstream https://github.com/KyaniteLabs/openglaze.git
git fetch upstream
git merge upstream/master
```

When a merge touches the removed features, keep them deleted.

---

## Screenshots

Screenshots of the current app are pending — see [docs/screenshots/README.md](docs/screenshots/README.md) for the capture list and instructions.

---


## Overview

OpenGlaze is a **free, open-source ceramic glaze management system** for potters, ceramic artists, and studios. It combines a **UMF calculator**, **CTE analysis engine**, **computational recipe optimizer**, and **AI-powered glaze consulting** — all in one self-hosted application.

### 30-second example: diagnose a crazing glaze

1. Enter a glaze recipe such as feldspar/silica/whiting/kaolin.
2. OpenGlaze calculates UMF, oxide roles, SiO₂:Al₂O₃ ratio, and estimated CTE.
3. If the glaze fit looks risky, the optimizer suggests material adjustments for the next test tile.
4. You still fire a real test tile — but you waste less clay, material, and kiln space getting there.

Built by potters, for potters. Your glaze recipes stay on your infrastructure. No subscriptions. No feature gates. MIT licensed.

**Why OpenGlaze?**

- 🏠 **Own your data** — Self-host on your own server. Recipes never leave your studio.
- 🔓 **Truly open** — MIT licensed, no proprietary lock-in, full source code available
- 🧮 **Computational chemistry** — UMF calculator, CTE prediction, and recipe optimizer using stoichiometric analysis — not guesswork
- 🧠 **AI-powered** — Kama assistant understands glaze chemistry and answers technical questions
- 🎨 **Studio-ready** — Studio groups, invite codes, lab assignments and shared glaze libraries
- ☕ **Free forever** — No paywalls, no subscriptions, no feature gates. Voluntary support only.

## What is OpenGlaze?

OpenGlaze is a **ceramic glaze calculator and recipe management tool** designed for anyone working with glazes:

- **Hobby potters** who want to understand their glazes at the molecular level
- **Studio ceramicists** managing dozens of recipes and test firings
- **Educators** teaching glaze chemistry with transparent, reproducible tools
- **Production potters** optimizing recipes for consistency and cost

At its core, OpenGlaze automates the chemistry that ceramicists have historically done by hand or with spreadsheets: calculating Unity Molecular Formula (UMF), estimating thermal expansion coefficient (CTE), and suggesting material adjustments to achieve target properties.

### How It Compares

| Tool | What It Does | How OpenGlaze Fits |
|------|-------------|-------------------|
| **Glazy** | Recipe database & community | Export from Glazy → analyze & optimize in OpenGlaze |
| **DigitalFire** | Ceramic chemistry education & reference | Deep educational content; OpenGlaze is the practical calculator |
| **INSIGHT** | Desktop glaze calculation software | Similar chemistry engine; OpenGlaze is web-based, open-source, and self-hosted |
| **HyperGlaze** | Recipe database | Import recipes into OpenGlaze for UMF analysis |

OpenGlaze is not a replacement for these tools — it complements them. Many users maintain their recipe libraries in Glazy and use OpenGlaze for computational analysis and optimization.

## Quick Start

### Docker (Recommended, 2 minutes)

The Docker path is a single-user, self-hosted install: the app keeps its SQLite database and uploaded photos on the named volumes `openglaze_data` and `openglaze_uploads`. The defaults in `.env.example` work out of the box on a fresh clone; set a real `SECRET_KEY` before exposing the app publicly.

```bash
# Clone this fork
git clone https://github.com/daksteter/frogueglaze.git
cd frogueglaze

# Copy environment file and set a real SECRET_KEY before public use
cp .env.example .env

# Start OpenGlaze
docker compose up -d

# Access at http://localhost:8768
curl http://localhost:8768/health
```

### Manual Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run (the SQLite database is created and seeded with the community glazes on first start)
python server.py
```

Open http://localhost:8768 in your browser. (Docker default; manual install defaults to 8767.)

### CLI, MCP, and Agent Skill

OpenGlaze also ships agent-friendly local surfaces:

```bash
python -m openglaze_cli brief
python -m openglaze_cli umf --recipe "Custer Feldspar 45, Silica 25, Whiting 18, EPK 12" --cone 10
python -m openglaze_cli batch --recipe "Custer Feldspar 45, Silica 25, Whiting 18, EPK 12" --size 500
python -m openglaze_mcp
```

- CLI: `python -m openglaze_cli` exposes project brief, UMF, batch scaling, and substitutions.
- MCP: `python -m openglaze_mcp` starts a stdio MCP server with glaze recipe tools for agent hosts.
- Skill: [`skills/openglaze/SKILL.md`](skills/openglaze/SKILL.md) guides compatible agents on when to use the CLI or MCP server and how to keep glaze-safety claims bounded.

Example MCP config:

```json
{
  "mcpServers": {
    "openglaze": {
      "command": "python",
      "args": ["-m", "openglaze_mcp"]
    }
  }
}
```

## Features

<table>
<tr>
<td width="50%">

### 🎨 Glaze Management
- Store unlimited glazes with chemistry, recipes, and visual references
- Track family relationships and base types
- **UMF calculator** with automatic oxide analysis and SiO₂:Al₂O₃ ratio
- **Recipe editor** with live UMF, CTE and limit checks as you type, saved versions, and side-by-side comparison
- Recipe scaling and batch calculator with cost estimation
- Food safety and cone range annotations (cone 06 through 10)

</td>
<td width="50%">

### 🔬 Chemistry Engine
- **UMF calculator** — Unity Molecular Formula from any batch recipe
- **CTE analysis** — Thermal expansion coefficient prediction for crazing/shivering risk
- Glaze compatibility analysis and material substitution suggestions
- **Recipe optimizer** — Computational suggestions to hit target CTE, surface (matte/glossy), or durability
- Batch reporting with cost estimation
- Oxide analysis with automatic role classification (flux, stabilizer, glass former)

</td>
</tr>
<tr>
<td width="50%">

### 🧠 AI Assistant (Kama)
- Context-aware glaze consulting
- Streaming responses for real-time help
- Local LLM support (Ollama) or cloud (Claude)
- Chemistry-aware prompt injection
- Experiment suggestion engine

</td>
<td width="50%">

### 🧪 Experiment Pipeline
- 6-stage workflow: Ideation → Prediction → Application → Firing → Analysis → Documentation
- Photo documentation at each stage
- Structured firing log integration
- Result comparison and archiving
- Reproducibility tracking

</td>
</tr>
<tr>
<td width="50%">

### 👥 Studio Collaboration
- Studio groups and invite-code joining
- Lab assignment tracking
- Shared experiment views
- Simple local-token identity for lightweight collaboration
- Role-based authorization and comment threads are roadmap items

</td>
<td width="50%">
</td>
</tr>
</table>

### More Features

- 🧮 **Recipe Optimizer** — Computational glaze recipe optimizer suggesting exact material adjustments to hit target CTE, surface, or durability without physical testing
- 📸 **Photo Documentation** — Gallery view across multiple firings
- 🔥 **Firing Logs** — Atmosphere, cone, and schedule tracking
- 🧮 **Layering Tracker** — Document and predict base/top combinations
- 💾 **Import/Export** — JSON/CSV export in the legacy dashboard; Glazy/INSIGHT import is a roadmap integration
- 📱 **PWA** — Install as an app on mobile/desktop
- ⌨️ **Command Palette** — Quick navigation with ⌘K
- 🔐 **Auth** — simple local auth for studio features


## Tech Stack

| Component | Technology | License |
|-----------|------------|---------|
| Backend | Flask 3.x (Python) | MIT |
| Frontend | Vanilla JS SPA | MIT |
| Database | SQLite | Public Domain |
| Auth | Simple local tokens | — |
| AI | Ollama (local) / Anthropic Claude (cloud) | — |
| Import/Export | JSON/CSV export in legacy dashboard; broader Glazy/INSIGHT import is roadmap | MIT |
| Chemistry | Custom UMF Engine | MIT |
| Container | Docker + Compose | — |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Browser    │  │   PWA App    │  │   API Clients│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                     Flask Application                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  Glazes  │ │Chemistry │ │    AI    │ │ Templates│       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Studios  │ │   Auth   │ │Analytics │ │  Uploads │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                      Data Layer                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐  │
│  │SQLite    │  │Uploads   │  │Ceramics Foundation Data  │  │
│  │          │  │(photos)  │  │(Materials, Recipes, etc.)│  │
│  └──────────┘  └──────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Documentation

| Document | Description |
|----------|-------------|
| [Installation](docs/installation.md) | Docker and manual setup guides |
| [Configuration](docs/configuration.md) | Environment variables and settings |
| [API Reference](docs/API.md) | REST API endpoints and examples |
| [Architecture](docs/architecture.md) | System design and data flow |
| [User Guide](docs/user-guide.md) | End-user feature walkthrough |
| [Development](docs/development.md) | Contributing and local dev setup |
| [Self-Hosting](docs/self-hosting.md) | Production deployment guide |
| [Support](docs/support.md) | Voluntary support for the project |
| [Changelog](CHANGELOG.md) | Version history and release notes |

## Self-Hosting

OpenGlaze is designed for self-hosting. All components are open source.

### Minimum Requirements

- 1 CPU core
- 1 GB RAM
- 10 GB storage
- Docker & Docker Compose

### Deployment Options

| Platform | Cost | Difficulty | Best For |
|----------|------|------------|----------|
| VPS (Hetzner, DO, Linode) | $5-20/mo | Medium | Full control |
| Render / Railway / Fly.io | $7-25/mo | Easy | Managed platforms |
| Raspberry Pi / Bare Metal | $0 | Hard | Offline/local use |

See [docs/self-hosting.md](docs/self-hosting.md) for detailed deployment instructions for each platform.

## Customizing Glaze Collections

Glaze templates live in `core/templates/` and `templates/`. To add your own:

1. Create a YAML file following the `community-glazes.yaml` format
2. Add glaze entries with `name`, `cone`, `atmosphere`, `base_type`, `recipe`, etc.
3. Import it via the API, or add it to the first-start seeding logic in `server.py` (`seed_database`, which currently loads `core/templates/community-glazes.yaml`)

Importing via the API needs no code changes.

## Data

The `ceramics-foundation/` directory contains canonical ceramic reference data:

- **30+ materials** with oxide analyses and aliases
- **19 oxides** with molecular weights, roles, and safety ratings
- **Firing schedules** for cone 06 through 10
- **UMF target ranges** and surface prediction thresholds
- **Layering rules** and material substitutions
- **Studio recipes** in YAML format

All data is versioned, sourced, and cited. See [ceramics-foundation/](ceramics-foundation/) for the full dataset.

## Templates

Pre-built glaze collections:

- **Cone 10 Reduction (Community)** — 28 traditional reduction glazes
- **Cone 6 Oxidation (Community)** — 12 electric kiln glazes
- **Cone 6 Reduction (Community)** — 4 gas kiln reduction glazes

See [templates/](templates/) and [ceramics-foundation/recipes/](ceramics-foundation/recipes/).

## Testing

```bash
# Run the full test suite
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

The test suite covers:
- Kama AI context injection and streaming
- Chemistry context retrieval and UMF calculation
- Recipe optimizer (target CTE, surface, alkali, running risk)
- Flask route imports and response formats
- System prompt generation and database schema

## Contributing

This fork is maintained for one studio and isn't looking for contributions. To contribute to OpenGlaze itself, see [upstream](https://github.com/KyaniteLabs/openglaze) and its contributing guide.

## Security

See [SECURITY.md](SECURITY.md) for our security policy and vulnerability reporting process.

## Support

This fork has no public issue tracker. For OpenGlaze in general:

- [Upstream discussions](https://github.com/KyaniteLabs/openglaze/discussions) — community help
- [Upstream issues](https://github.com/KyaniteLabs/openglaze/issues) — bugs in OpenGlaze itself (check that they also happen upstream before reporting)

## License

- **Code, documentation and templates**: [MIT License](LICENSE) — free to use,
  modify and distribute, including commercially.
- **Third-party components**: keep their own licenses; the components table
  near the top of this file lists them.

The glaze templates under `templates/` follow the same MIT terms as the rest of
the repository — see [templates/README.md](templates/README.md#licensing).

## Acknowledgments

- [OpenGlaze](https://github.com/KyaniteLabs/openglaze) by KyaniteLabs, which this fork is built on
- The ceramics community for sharing knowledge and recipes
- Contributors who have helped build OpenGlaze
- [Ceramic Arts Network](https://ceramicartsnetwork.org/) for glaze chemistry references
- [Digitalfire](https://digitalfire.com/) for oxide data and UMF methodology

---

<p align="center">
  <strong>Built with ❤️ for the ceramics community</strong>
</p>

<p align="center">
  <a href="https://github.com/daksteter/frogueglaze">This fork</a> •
  <a href="https://github.com/KyaniteLabs/openglaze">Upstream OpenGlaze</a>
</p>
