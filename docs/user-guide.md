# OpenGlaze User Guide

Complete guide to using OpenGlaze for glaze management, experimentation, and studio collaboration.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Managing Glazes](#managing-glazes)
3. [The Chemistry Engine](#the-chemistry-engine)
4. [Layering and Combinations](#layering-and-combinations)
5. [The Experiment Pipeline](#the-experiment-pipeline)
6. [Working with Kama (AI)](#working-with-kama-ai)
7. [Studio Collaboration](#studio-collaboration)
8. [Firing Logs](#firing-logs)
9. [Test Tiles](#test-tiles)
10. [Firing Schedules](#firing-schedules)
11. [Tips and Best Practices](#tips-and-best-practices)

## Getting Started

### First Login

When you first access OpenGlaze:

1. Create an account or log in
2. Your studio profile is automatically created with default settings
3. The database is seeded with the community glaze collection
4. You're ready to start managing glazes!

### Navigation Overview

The interface consists of:

- **Header** — Search (⌘K), AI assistant toggle, PWA install button
- **Sidebar** — Main views: Combinations, All Glazes, Recipe editor, Materials, Import, Test tiles, Firing schedules, Studio
- **Main Content** — Context-aware based on selected view
- **Command Palette** — Press ⌘K (or Ctrl+K) for quick navigation

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `⌘K` / `Ctrl+K` | Open command palette |
| `⌘/` / `Ctrl+/` | Toggle sidebar |
| `Esc` | Close modals/panels |
| `G` then `G` | Go to Glazes |
| `G` then `C` | Go to Combinations |
| `G` then `E` | Go to Experiments |

## Managing Glazes

### Adding a Glaze

1. Navigate to **All Glazes**
2. Click **Add Glaze**
3. Fill in the required fields:
   - **Name** — e.g., "Ash Glaze #3"
   - **Recipe** — Batch percentages or gram amounts
   - **Cone** — Firing temperature (e.g., 10)
   - **Atmosphere** — Oxidation, reduction, or neutral
4. Optional fields add richness:
   - **Family** — celadon, tenmoku, shino, etc.
   - **Base Type** — porcelain, stoneware, earthenware
   - **Surface** — glossy, matte, satin, textured
   - **Food Safe** — Mark if tested food-safe
   - **Behavior** — Running, breaking, pooling notes

### Recipe Format

A recipe is a list of materials and amounts, separated by commas, semicolons or new lines:

```
Custer Feldspar 45, Silica 25, Whiting 18, EPK 12, +Red Iron Oxide 2
```

- Amounts can be percentages or batch weights; the chemistry is the same either way.
- A leading `+` marks an **addition** (a colorant or opacifier listed after the base recipe). Additions count in the chemistry like any other material.
- Material names match the materials library, including common aliases (`EPK`, `Kaolin`, `Custer`). Unknown names are reported and left out of the chemistry.

### The Recipe Editor

Open **Recipe editor** in the sidebar for a new recipe, or **Edit recipe** on any glaze card.

- **Rows:** type a material (suggestions come from the materials library) and an amount. Press Enter in the last amount to add a row. Tick **Addition** for colorants and opacifiers; the editor shows the base total and the additions separately.
- **Live chemistry:** UMF grouped into fluxes, stabilizers and glass formers, SiO₂:Al₂O₃, estimated CTE, predicted surface and limit checks for the chosen cone update as you type. Materials not in the library are highlighted and named in an "Incomplete" warning.
- **Saving:** **Save version** stores the recipe with an optional note. A new recipe needs a name and family first. The first save of an existing glaze also keeps its earlier recipe as a version, so nothing is lost.
- **Versions:** each saved version shows its date and note. **Load** puts it back in the editor (not saved until you save); **Compare** shows it side by side.
- **Compare with:** pick a saved version or another glaze to see both recipes and the chemical differences, with a plain-language note for each oxide that changed.

### Editing and Organizing

- Use the recipe editor to change recipes; each save is kept as a version
- Use families to organize collections
- Filter by family in the sidebar

### Importing Recipes

Open **Import** in the sidebar to bring recipes over from DigitalFire Insight-Live. Export your recipes from Insight-Live as CSV, then choose that file. Nothing is saved until you press **Import**.

- **Materials:** every material name in the file is listed with the library material it matched and that material's source. Matched names keep Insight-Live's spelling in the recipe, since the calculator reads them the same way. Names marked *Matched on part of the name* are worth a look. For a name that didn't match, pick one of our materials, or keep the name: the recipe then calculates once a studio material with that name (or alias) is added under **Materials**.
- **Additions:** Insight-Live's CSV doesn't mark additions, so they are worked out from the amounts: the base is the materials that add up to 100, and the rest become additions (`+`). In an export of several recipes, more than one set of materials often adds up to 100; the importer then picks by material type (colorants and opacifiers as additions) and notes beside the recipe that the additions were guessed, so check those. If nothing singles out one set, everything is imported as base and the recipe is flagged; mark the additions in the recipe editor.
- **Recipes:** tick the recipes to import. A recipe imported before (same Insight-Live code) is left unticked; importing it again adds a second copy.
- **Cone:** the export has no firing cone. The cone you choose is stored with every recipe in that import and can be changed per recipe in the recipe editor.

Each imported glaze keeps its Insight-Live code, date, description and comments in its notes, and its first saved version is the recipe as imported.

### Materials

Open **Materials** in the sidebar to see every material the calculator knows: its analysis, its LOI, and where the numbers came from.

- **Sources:** each library material is marked *Supplier data sheet* (with a link), *Theoretical* (a pure compound, calculated from its chemical formula), or *Unverified* (inherited from upstream OpenGlaze without a recorded source, to be replaced).
- **Studio materials:** **Add studio material** for anything not in the library, such as a local clay or a frit from another supplier. Enter the analysis as weight percent as received, from the data sheet, plus LOI. The form shows the running total, which should come to about 100%. Studio materials appear in the recipe editor's suggestions right away.
- **Lot analyses:** on any material, **Record a lot analysis** stores the analysis of a particular lot. While a lot is in use, every recipe that uses the material calculates with it; **Use the standard analysis** switches back. Older lots stay on record.

## The Chemistry Engine

### UMF Calculation

The Unity Molecular Formula (UMF) normalizes glaze recipes to compare them on equal footing.

**How to calculate:** open the recipe in the **Recipe editor**. The UMF, silica:alumina ratio, predicted surface and estimated thermal expansion update as you type.

Analyses are as received: a material's oxide percentages and its LOI together make up the raw material (whiting is 56% CaO and 44% LOI). The oxide percentages are used directly, so what burns off is never counted twice.

**Thermal expansion** is an estimate from the oxides (the Appen molar method with John Sankey's values), for comparing glazes within this app. It is not a measurement. It reads about 0.5–1.6 lower than Insight-Live's figures for the same recipe, most in glazes with zircon, tin or rutile, which this method treats as dissolved in the glass. Don't hold it against glaze-fit notes made with Insight-Live's numbers, and test fit on the clay body.

**Interpreting UMF:**

| SiO₂:Al₂O₃ Ratio | Typical Surface |
|-------------------|-----------------|
| < 5 | Matte to satin |
| 5–8 | Satin to glossy |
| > 8 | Very glossy, may run |

| RO Group | Typical Behavior |
|----------|-----------------|
| High CaO (0.5+) | Hard, durable, may crawl |
| High KNaO (0.3+) | Glossy, softer, more fluid |
| High MgO (0.3+) | Matte, opaque, lower expansion |
| High BaO | Toxic in raw form, unique surfaces |

### Compatibility Analysis

Before layering two glazes:

1. Go to **Combinations** view
2. Select a **Base glaze** and **Top glaze**
3. Click **Analyze Compatibility**
4. Review the report:
   - Thermal expansion match
   - Maturity overlap at target cone
   - Predicted interaction effects
   - Risk level (low/medium/high)

**Warning signs:**
- Thermal expansion difference > 1.0 → shivering or crazing risk
- Maturing temperatures differ by > 1 cone → poor fit
- Both glazes are runners → pooling/dripping risk

### Batch Sheets

Print a recipe scaled to the batch you're mixing:

1. Click **Batch sheet** on a glaze card, or in the **Recipe editor** (which uses the recipe on screen, saved or not).
2. Enter the batch size in grams and choose what it measures: **the base**, with additions weighed on top (a 1000 g batch of a recipe with 15.7 of additions weighs 1157 g), or **the whole batch**, additions included.
3. Click **Print**. Only the sheet prints.

The sheet lists every material as the recipe writes it, including ones the calculator doesn't know, such as a stain. Next to each weight is a running total, for weighing everything into one bucket without zeroing the scale, and the lot in use if one is recorded under **Materials**. It ends with blank lines for the date, who batched it, water added and specific gravity. The size and choice are remembered for next time.

### Recipe Optimizer

The optimizer computationally suggests exact material adjustments to hit target glaze properties — reducing the number of physical test firings needed.

**When to use it:**
- Your glaze crazes and you need to lower CTE to match your clay body
- You want to shift a glossy glaze toward satin or matte
- You're worried about excessive running at your firing temperature
- You need to reduce alkali content for better durability

**How to use it:**
1. Open a glaze detail view
2. Click **Optimize Recipe**
3. Select your target:
   - **Target CTE** — Enter the exact CTE of your clay body (e.g., 6.5)
   - **Reduce CTE** — Lower thermal expansion to reduce crazing risk
   - **Increase CTE** — Raise thermal expansion to reduce shivering risk
   - **More Matte** — Increase alumina relative to silica
   - **More Glossy** — Increase silica relative to alumina
   - **Reduce Alkali** — Lower KNaO for better durability
   - **Reduce Running** — Reduce fluidity to prevent pooling
4. Review ranked suggestions with predicted outcomes
5. Choose a suggestion and fire a test tile to confirm

**Understanding the results:**

| Column | Meaning |
|--------|---------|
| Recipe | The reformulated recipe with adjusted percentages |
| Change | What was modified (e.g., "Replace silica with kaolin (50% swap)") |
| Predicted CTE | Thermal expansion of the reformulated glaze |
| Predicted Surface | Expected surface finish (matte/satin/glossy) |
| Score | Higher = closer to target (threshold-crossing bonuses applied) |

**Important:** The optimizer predicts chemistry, not firing behavior. Always fire a test tile before committing to a reformulated recipe. Surface prediction depends on firing schedule, cooling rate, and application thickness.

## Layering and Combinations

### Documenting a Combination

1. In **Combinations** view, click **New Combination**
2. Select base and top glazes
3. Document your prediction:
   - What effect do you expect?
   - Risk level assessment
4. After firing, update with actual results

### Combination Types

| Type | Description |
|------|-------------|
| Research-backed | Confirmed by published sources or extensive testing |
| User-prediction | Your hypothesis before firing |
| Confirmed | You've fired it and documented results |
| Surprise | Unexpected result worth noting |

### Layering Tips

- **Thin base, thick top** — Most combinations work best with a thin base coat
- **Test tiles first** — Always test on small tiles before full pieces
- **Note application method** — Dipping, brushing, spraying affect results
- **Document everything** — Thickness, temperature, atmosphere all matter

## The Experiment Pipeline

### The 6 Stages

OpenGlaze structures glaze development into a repeatable pipeline:

```
Ideation → Prediction → Application → Firing → Analysis → Documentation
```

### Stage 1: Ideation

**What to document:**
- What are you trying to achieve?
- Reference glazes or photos
- Hypothesis about the outcome

**Example:**
> "I want to create a deep copper red by starting with a celadon base and adding 1.5% copper carbonate. Hypothesis: Reduction at cone 10 will produce a rich red with minimal pinholing."

### Stage 2: Prediction

**What to document:**
- Expected color, texture, and surface
- Potential problems
- Comparison to similar glazes in your library

**Use Kama:** Ask the AI for predictions based on your recipe.

### Stage 3: Application

**What to document:**
- Application method (dip, brush, spray)
- Number of coats
- Layer thickness
- Clay body used
- Bisque temperature

### Stage 4: Firing

**What to document:**
- Cone reached
- Atmosphere (oxidation/reduction)
- Kiln type
- Firing schedule (ramp rates, holds, cooling)
- Total firing time
- Any issues (power outages, early shutdowns)

### Stage 5: Analysis

**What to document:**
- Photos (multiple angles, close-ups)
- Color accuracy notes
- Surface quality (smooth, pinholed, crawling)
- Comparison to prediction
- Adjustments needed

### Stage 6: Documentation

**What to document:**
- Final recipe with any modifications
- Firing notes for replication
- Lessons learned
- Archive or share with studio

### Experiment Best Practices

- **One variable at a time** — Change only one thing between tests
- **Label everything** — Tiles, test pieces, photos
- **Take photos in consistent lighting** — Natural daylight, neutral background
- **Keep a physical notebook too** — Technology fails; paper doesn't

## Working with Kama (AI)

### What Kama Knows

Kama has access to:
- Your glaze library (if you provide glaze IDs)
- Ceramics Foundation reference data (materials, oxides, schedules)
- Chemistry rules and compatibility guidelines
- General ceramic glaze chemistry knowledge

### Effective Questions

**Good questions:**
- "What would 2% rutile do to this celadon?" (with glaze selected)
- "Why is my glaze crawling at cone 6?"
- "Compare the UMF of these two glazes and predict how they'd layer"
- "Suggest a substitute for gerstley borate in this recipe"

**Less effective questions:**
- "Make me a good glaze" (too vague)
- "What is clay?" (too basic, use a search engine)

### Understanding Kama's Limitations

- Kama provides guidance, not guarantees
- Always test predictions on tiles before full pieces
- Kama doesn't know your specific materials' impurities
- Local geology and water chemistry affect results

### Privacy Note

- With **local Ollama**: All queries stay on your machine
- With **cloud Claude**: Queries are sent to Anthropic's API (see their privacy policy)

## Studio Collaboration

### Creating a Studio

1. Go to **Studio** view
2. Click **Create Studio**
3. Enter studio name and description
4. Configure profile (cone, atmosphere, kiln type)

### Inviting Members

1. In Studio settings, click **Invite Member**
2. Enter their email address
3. Assign a role:
   - **Owner** — Full control, member management
   - **Admin** — Manage members, experiments, glazes
   - **Member** — Create and edit glazes and experiments
   - **Viewer** — Read-only access

### Shared Resources

Studio members share:
- Glaze library (with edit permissions based on role)
- Experiment history
- Firing logs
- Photo galleries

### Lab Assignments

Assign experiments to specific members:
1. Create an experiment
2. Click **Assign to Member**
3. Select member and set deadline
4. Member receives notification

## Firing Logs

### Creating a Firing Log

1. Go to **Firing Logs** (from Studio view)
2. Click **New Firing**
3. Enter details:
   - Date and kiln
   - Cone and atmosphere
   - Loading notes
   - Schedule (or select from presets)

### Schedules

The studio's kiln programs are kept under **Firing schedules** in the sidebar; see [Firing Schedules](#firing-schedules) below. There are no built-in presets.

### Attaching Results

Link firing logs to experiments and glazes:
- Tag which glazes were in the firing
- Attach photos of the kiln opening
- Note any kiln-related issues (hot spots, element wear)

## Test Tiles

**Test tiles** in the sidebar lists every tile, the most recently fired first. Filter by glaze or by verdict. The **Test tiles** button on a glaze card opens the list for just that glaze.

### Recording a Tile

1. Click **New tile**
2. Choose the glaze. **Recipe tested** starts at the current recipe; pick an older saved version if the tile was made from one
3. Fill in what you know: tile label (what's written on the tile), date fired, cone, atmosphere, kiln and firing, clay body, application (dips, coats, specific gravity), the result, and a verdict: keep, retest or reject. Only the glaze is required
4. **Add photos** takes pictures from the camera or files; a tile can have up to 20
5. Click **Save**

The tile keeps a copy of the recipe it tested, so editing the glaze's recipe later doesn't change the record. Changing the glaze or the recipe choice on a saved tile takes that recipe instead.

**Firing schedule** links the tile to one of the studio's [firing schedules](#firing-schedules); choosing one fills in its cone if the cone is empty. Firing schedule, kiln and clay body are filled in from the last tile you saved, and kiln and clay body suggest values used before. Click a tile to edit it, enlarge a photo, delete a photo, or delete the tile.

### Photos

Photos are shrunk to at most 2000 pixels on the long side and saved as JPEG before they're uploaded, so phone pictures stay small. This also drops the location the phone records in each picture. Photos are stored in a `tile-photos` folder beside the database, and the backup script includes them.

### Best Practices for Glaze Photos

- **Lighting**: Natural daylight or 5000K LED
- **Background**: Neutral gray or white
- **Angle**: 45° to show surface texture
- **Close-ups**: Macro for detail shots
- **Consistency**: Same setup for comparison shots

## Firing Schedules

**Firing schedules** in the sidebar holds the studio's kiln programs, each shown with its firing curve and how long it takes.

### Writing a Schedule

1. Click **New schedule**
2. Give it a name, the cone, and the unit (°F or °C)
3. Add a segment for each step of the kiln program: the rate in degrees per hour, the temperature to reach, and a hold in minutes. Leave the rate blank for full speed. A target below the previous temperature is a controlled cool. Each segment can have a short note, such as "start reduction"
4. Click **Save**

While you type, each segment's time and the time elapsed are worked out from room temperature (70 °F or 21 °C), with the peak, the total time and the firing curve below the table. Full-speed segments have no rate to time them by, so they are estimated at 500 °F/hr (278 °C/hr) and drawn dashed; the summary says when that happens. Times are estimates: a kiln that can't keep up with a rate, or a full load, takes longer.

**Print** prints the schedule on its own, with the segment table, the curve and the notes, to keep by the kiln.

Deleting a schedule doesn't delete the test tiles that used it; they lose the link and keep everything else.

## Tips and Best Practices

### For Beginners

1. **Start with known recipes** — Use community templates as baselines
2. **Document everything** — The most valuable data is the data you have
3. **Test on tiles** — Never experiment on finished work
4. **Learn UMF basics** — Understanding chemistry helps predict results
5. **Join a studio** — Collaboration accelerates learning

### For Advanced Users

1. **Build a test matrix** — Systematically vary one oxide at a time
2. **Contribute to Ceramics Foundation** — Submit verified data
3. **Automate with API** — Build tools on top of OpenGlaze
4. **Host for your community** — Set up instances for local guilds

### For Studio Managers

1. **Standardize naming** — Consistent glaze names prevent confusion
2. **Archive old recipes** — Keep history without cluttering active library
3. **Set up firing schedules** — Preset schedules ensure consistency
4. **Review analytics** — Track which glazes are used most
5. **Backup regularly** — Export data periodically

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Glaze not showing in list | Check filter settings, verify permissions |
| UMF calculation seems wrong | Verify recipe format and material names |
| Kama not responding | Check AI provider settings in config |
| Photos not uploading | Check file size (max 5MB) and format (JPG/PNG/WebP) |
| Can't invite studio member | Verify they have an OpenGlaze account |
| Database errors on startup | Delete `glaze.db` and re-run `seed_data.py` |

---

**Need more help?** Visit [GitHub Discussions](https://github.com/KyaniteLabs/openglaze/discussions) or check the [API Reference](API.md) for developers.
