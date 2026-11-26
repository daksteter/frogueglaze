-- OpenGlaze Unified Database Schema
-- SQLite schema for personal mode
-- user_id is NULLABLE: NULL for single-user data, set for simple-auth studio users

-- Glazes: All studio glazes
CREATE TABLE IF NOT EXISTS glazes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    family TEXT,
    color TEXT,
    -- Extended columns for Glaze Lab features
    hex TEXT,                    -- Color swatch hex code
    chemistry TEXT,              -- Chemical composition description
    behavior TEXT,               -- How it behaves in firing
    layering TEXT,               -- Layering recommendations
    warning TEXT,                -- Known issues (e.g., Shino crawl)
    recipe TEXT,                 -- Recipe ingredients (JSON array)
    catalog_code TEXT,           -- Commercial catalog reference
    food_safe BOOLEAN DEFAULT NULL,  -- true=known food safe, false=not food safe, null=unknown
    notes TEXT,
    -- Cone / atmosphere / display columns
    cone TEXT,
    atmosphere TEXT CHECK(atmosphere IN ('oxidation', 'reduction', 'neutral', 'salt', 'wood')),
    base_type TEXT CHECK(base_type IN ('transparent', 'opaque', 'matte', 'satin', 'gloss', 'semi-opaque')),
    surface TEXT CHECK(surface IN ('smooth', 'textured', 'crystalline', 'runny')),
    transparency TEXT CHECK(transparency IN ('transparent', 'semi-opaque', 'opaque')),
    image_url TEXT,
    user_id TEXT,                -- NULL in personal mode, tenant ID in cloud
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Combinations: Research-backed, user-predicted, confirmed, and surprise layering combos
CREATE TABLE IF NOT EXISTS combinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,                -- NULL in personal mode, tenant ID in cloud
    base TEXT NOT NULL,          -- Base glaze (applied first)
    top TEXT NOT NULL,           -- Top glaze (applied last)
    layers TEXT,                 -- JSON array, bottom to top: ["Tenmoku", "Celadon", "Chun Blue"]
    type TEXT NOT NULL CHECK(type IN ('research-backed', 'user-prediction', 'confirmed', 'surprise')),
    source TEXT,                 -- Where this combo came from: 'fired', 'community', 'manufacturer', 'chemistry_prediction'
    result TEXT,                 -- Visual result description
    chemistry TEXT,              -- Chemical explanation
    risk TEXT CHECK(risk IN ('low', 'medium', 'high')),
    effect TEXT CHECK(effect IN ('subtle', 'dramatic')),
    stage TEXT DEFAULT 'idea',   -- Pipeline stage: idea, predicting, testing, fired, documented
    prediction_grade TEXT DEFAULT 'unknown'
        CHECK(prediction_grade IN ('likely', 'possible', 'unlikely', 'unknown', 'confirmed', 'surprise')),
    notes TEXT,
    -- Firing result and discovery columns
    result_rating INTEGER CHECK(result_rating BETWEEN 1 AND 5),
    is_surprise BOOLEAN DEFAULT 0,
    surprise_rarity TEXT CHECK(surprise_rarity IN ('common', 'uncommon', 'rare', 'legendary')),
    discovered_by TEXT,
    replication_count INTEGER DEFAULT 0,
    photo_url TEXT,
    status TEXT DEFAULT 'untested' CHECK(status IN ('untested', 'predicted', 'in_kiln', 'tested', 'proven', 'failed', 'surprise')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chemistry Rules: Authoritative glaze chemistry knowledge
CREATE TABLE IF NOT EXISTS chemistry_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    conditions TEXT,
    outcomes TEXT,
    caveats TEXT,
    confidence TEXT DEFAULT 'high' CHECK(confidence IN ('high', 'medium', 'low')),
    user_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chemistry_rules_category ON chemistry_rules(category);

-- Experiments: 6-stage experiment pipeline tracking
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    combination_id INTEGER,
    base_glaze TEXT NOT NULL,
    top_glaze TEXT NOT NULL,
    stage TEXT DEFAULT 'ideation' CHECK(stage IN ('ideation', 'prediction', 'application', 'firing', 'analysis', 'documentation')),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
    prediction TEXT,
    result TEXT,
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    notes TEXT,
    photo TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Inbox: Captured glaze ideas
CREATE TABLE IF NOT EXISTS inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    base TEXT NOT NULL,
    top TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Archive: Completed experiments (successful and failed)
CREATE TABLE IF NOT EXISTS archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    name TEXT NOT NULL,
    base_glaze TEXT NOT NULL,
    top_glaze TEXT NOT NULL,
    result TEXT,
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    notes TEXT,
    photo TEXT,
    type TEXT NOT NULL CHECK(type IN ('successful', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Studios: Collaborative groups for sharing kiln testing
CREATE TABLE IF NOT EXISTS studios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    invite_code TEXT UNIQUE NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS studio_members (
    studio_id TEXT NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('admin', 'member')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (studio_id, user_id)
);

CREATE TABLE IF NOT EXISTS lab_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    studio_id TEXT NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
    combination_id INTEGER NOT NULL,
    assigned_to TEXT,
    claimed_at TIMESTAMP,
    status TEXT DEFAULT 'claimed' CHECK(status IN ('claimed', 'in_progress', 'completed', 'released')),
    claimed_by_name TEXT
);

-- Recipe versions: every save from the recipe editor, newest has the highest id
CREATE TABLE IF NOT EXISTS recipe_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    glaze_id TEXT NOT NULL REFERENCES glazes(id) ON DELETE CASCADE,
    recipe TEXT NOT NULL,
    note TEXT,
    cone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Studio materials: the studio's own materials, added to the published library
-- Where imported glazes came from (Insight-Live CSV exports). One row per
-- imported recipe; ``original`` keeps the recipe as the export had it (JSON
-- list of {name, amount, addition}) so imports can be checked later.
CREATE TABLE IF NOT EXISTS glaze_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    glaze_id TEXT NOT NULL REFERENCES glazes(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_code TEXT,
    source_name TEXT,
    source_date TEXT,
    original TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS custom_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_key TEXT NOT NULL UNIQUE,   -- lowercase name, as used in recipes
    name TEXT NOT NULL,
    aliases TEXT,                        -- JSON list of other names
    category TEXT DEFAULT 'other',
    oxides TEXT NOT NULL,                -- JSON {oxide: weight percent, as received}
    loi REAL DEFAULT 0,
    source TEXT,                         -- supplier, data sheet, or how it was measured
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Lot analyses: a dated analysis of one material; at most one is current per
-- material, and a current lot replaces the standard analysis in calculations
CREATE TABLE IF NOT EXISTS material_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_key TEXT NOT NULL,
    lot TEXT NOT NULL,
    oxides TEXT NOT NULL,
    loi REAL DEFAULT 0,
    source TEXT,
    is_current INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Small counters, e.g. materials_rev: bumped whenever studio materials or lots
-- change, so every server process knows to reload them
CREATE TABLE IF NOT EXISTS studio_state (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);

-- Firing schedules: the studio's kiln programs. ``segments`` is a JSON list of
-- {rate, target, hold, note} in ``unit`` (F or C); rate null = full speed.
-- Checked and timed in core/firing.py.
CREATE TABLE IF NOT EXISTS firing_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    cone TEXT,
    unit TEXT NOT NULL DEFAULT 'F',
    segments TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Test tiles: one fired test of a glaze. ``recipe`` is a copy of the recipe
-- as tested (and ``version_id`` the saved version it came from, if any), so
-- later edits to the glaze don't change the record. Checked in core/tiles.py.
CREATE TABLE IF NOT EXISTS test_tiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    glaze_id TEXT NOT NULL REFERENCES glazes(id) ON DELETE CASCADE,
    version_id INTEGER REFERENCES recipe_versions(id) ON DELETE SET NULL,
    recipe TEXT,
    label TEXT,                  -- what's written on the tile
    fired_on TEXT,               -- YYYY-MM-DD
    cone TEXT,
    atmosphere TEXT,
    kiln TEXT,                   -- which kiln, where in it
    schedule_id INTEGER REFERENCES firing_schedules(id) ON DELETE SET NULL,
    clay_body TEXT,
    application TEXT,            -- dips, coats, thickness, specific gravity
    result TEXT,                 -- what came out of the kiln
    verdict TEXT,                -- keep, retest, reject, or NULL (not judged)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tile photos: files in the tile-photos folder beside the database
CREATE TABLE IF NOT EXISTS tile_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tile_id INTEGER NOT NULL REFERENCES test_tiles(id) ON DELETE CASCADE,
    filename TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================================
-- INDEXES
-- ==========================================================================

CREATE INDEX IF NOT EXISTS idx_glazes_family ON glazes(family);
CREATE INDEX IF NOT EXISTS idx_glazes_user ON glazes(user_id);
CREATE INDEX IF NOT EXISTS idx_glazes_cone ON glazes(cone);
CREATE INDEX IF NOT EXISTS idx_combinations_type ON combinations(type);
CREATE INDEX IF NOT EXISTS idx_combinations_user ON combinations(user_id);
CREATE INDEX IF NOT EXISTS idx_combinations_status ON combinations(status);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiments_user ON experiments(user_id);
CREATE INDEX IF NOT EXISTS idx_archive_type ON archive(type);
CREATE INDEX IF NOT EXISTS idx_archive_user ON archive(user_id);
CREATE INDEX IF NOT EXISTS idx_studios_invite ON studios(invite_code);
CREATE INDEX IF NOT EXISTS idx_studio_members_user ON studio_members(user_id);
CREATE INDEX IF NOT EXISTS idx_lab_assignments_studio ON lab_assignments(studio_id);
CREATE INDEX IF NOT EXISTS idx_lab_assignments_combo ON lab_assignments(combination_id);
CREATE INDEX IF NOT EXISTS idx_recipe_versions_glaze ON recipe_versions(glaze_id, id);
CREATE INDEX IF NOT EXISTS idx_glaze_imports_code ON glaze_imports(source, source_code);
CREATE INDEX IF NOT EXISTS idx_glaze_imports_glaze ON glaze_imports(glaze_id);
CREATE INDEX IF NOT EXISTS idx_material_lots_key ON material_lots(material_key, id);
CREATE INDEX IF NOT EXISTS idx_test_tiles_glaze ON test_tiles(glaze_id);
CREATE INDEX IF NOT EXISTS idx_tile_photos_tile ON tile_photos(tile_id, id);
