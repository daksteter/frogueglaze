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
