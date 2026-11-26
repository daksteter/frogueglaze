/**
 * RecipeEditor - edit a glaze recipe with a live UMF calculator,
 * saved versions, and side-by-side comparison.
 *
 * Recipes are stored as plain strings ("Custer Feldspar 45, Silica 25,
 * +Red Iron Oxide 2"); a leading "+" marks an addition after the base.
 * All user-entered text reaches the page through textContent, never HTML.
 */

const RE_OXIDE_GROUPS = [
    ['Fluxes', ['Li2O', 'Na2O', 'K2O', 'MgO', 'CaO', 'SrO', 'BaO', 'ZnO', 'PbO']],
    ['Stabilizers', ['Al2O3', 'B2O3']],
    ['Glass formers', ['SiO2']],
];
const RE_SUBSCRIPTS = '₀₁₂₃₄₅₆₇₈₉';
const RE_DEBOUNCE_MS = 300;

/** Subscript atom counts (digits after an element or ")"), not coefficients like ·10H2O. */
function reFormula(formula) {
    return String(formula).replace(/([A-Za-z)])(\d+)/g, (_, before, digits) =>
        before + digits.replace(/\d/g, d => RE_SUBSCRIPTS[d]));
}

function reNumber(value, digits = 2) {
    return typeof value === 'number' && isFinite(value) ? value.toFixed(digits) : '—';
}

function reEl(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined && text !== null) el.textContent = text;
    return el;
}

/** Split a recipe string into editor rows. */
function reParseRecipe(recipe) {
    const rows = [];
    String(recipe || '').split(/[,\n;]/).forEach(raw => {
        let part = raw.trim();
        if (!part || !/\d/.test(part)) return;
        const addition = part.startsWith('+');
        if (addition) part = part.slice(1).trim();
        const match = part.match(/^(.+?)\s+([\d.]+)\s*%?\s*$/);
        rows.push(match
            ? { material: match[1].trim(), amount: match[2], addition }
            : { material: part, amount: '', addition });
    });
    return rows;
}

/** Join editor rows into a recipe string: base first, then "+" additions. */
function reRecipeString(rows) {
    const valid = rows.filter(r => r.material.trim() && parseFloat(r.amount) > 0);
    const entry = r => `${r.addition ? '+' : ''}${r.material.trim()} ${parseFloat(r.amount)}`;
    return [...valid.filter(r => !r.addition), ...valid.filter(r => r.addition)].map(entry).join(', ');
}

/** SQLite CURRENT_TIMESTAMP is UTC "YYYY-MM-DD HH:MM:SS"; show local time. */
function reDate(timestamp) {
    if (!timestamp) return '';
    const date = new Date(String(timestamp).replace(' ', 'T') + 'Z');
    return isNaN(date) ? String(timestamp) : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function reRecipeColumn(label, recipe) {
    const column = reEl('div', 're-compare-col');
    column.append(reEl('h4', null, label));
    const list = reEl('ul', 're-compare-recipe');
    reParseRecipe(recipe).forEach(row => {
        list.append(reEl('li', row.addition ? 're-addition' : null,
            `${row.addition ? '+ ' : ''}${row.material} ${row.amount}`));
    });
    if (!list.children.length) list.append(reEl('li', 're-hint', 'Empty'));
    column.append(list);
    return column;
}

const RE_METRIC_LABELS = {
    sio2_al2o3: 'SiO₂ : Al₂O₃',
    flux_al2o3: 'Flux : Al₂O₃',
    knao_cao: 'KNaO : CaO',
    flux_diversity: 'Flux count',
};

/**
 * Comparison table: rows that differ, then one line naming the unchanged
 * ones, so the real differences are not buried.
 */
function reDifferenceTable(allDifferences, targetLabel) {
    const wrap = reEl('div');
    const table = reEl('table', 're-diff');
    const metric = d => d.category === 'oxide' ? reFormula(d.metric)
        : RE_METRIC_LABELS[d.metric] || d.metric.replace(/_/g, ' ');
    const rounded = d => typeof d.delta === 'number' ? Math.round(d.delta * 1000) / 1000 : null;
    const listed = allDifferences.filter(d => d.metric !== 'al2o3_sio2'); // inverse of SiO2:Al2O3
    const unchanged = listed.filter(d => rounded(d) === 0);
    const differences = listed.filter(d => rounded(d) !== 0);
    const explained = differences.some(d => d.interpretation);
    const head = table.createTHead().insertRow();
    head.append(reEl('th'), reEl('th', 're-num', 'This recipe'), reEl('th', 're-num', targetLabel),
        reEl('th', 're-num', 'Change'));
    if (explained) head.append(reEl('th', null, 'What it means'));
    const body = table.createTBody();
    const change = d => {
        const value = rounded(d);
        return value === null ? '' : `${value > 0 ? '+' : ''}${value.toFixed(3)}`;
    };
    differences.forEach(d => {
        const row = body.insertRow();
        row.append(
            reEl('td', null, metric(d)),
            reEl('td', 're-num', reNumber(d.base_value, 3)),
            reEl('td', 're-num', reNumber(d.top_value, 3)),
            reEl('td', 're-num', change(d)),
        );
        if (explained) row.append(reEl('td', 're-interp', d.interpretation || ''));
    });
    if (differences.length) wrap.append(table);
    else wrap.append(reEl('p', 're-hint', 'No chemical differences.'));
    if (unchanged.length) {
        wrap.append(reEl('p', 're-hint', `Unchanged: ${unchanged.map(metric).join(', ')}.`));
    }
    return wrap;
}

/** Oxide-by-oxide table for two UMF formulas (no interpretations). */
function reUmfDiffTable(umfA, umfB, targetLabel) {
    const oxides = [...new Set([...Object.keys(umfA), ...Object.keys(umfB)])];
    const order = RE_OXIDE_GROUPS.flatMap(([, list]) => list);
    const rank = ox => (order.indexOf(ox) + 1) || order.length + 1;
    oxides.sort((x, y) => rank(x) - rank(y) || x.localeCompare(y));
    const differences = oxides.map(ox => {
        const a = umfA[ox] || 0;
        const b = umfB[ox] || 0;
        return { category: 'oxide', metric: ox, base_value: a, top_value: b, delta: b - a };
    });
    return reDifferenceTable(differences, targetLabel);
}

class RecipeEditor {
    constructor({ onSaved } = {}) {
        this.onSaved = onSaved;
        this.materials = null;
        this.cones = ['6', '10'];
        this.glaze = null;
        this.rows = [];
        this.cone = '6';
        this.newName = '';
        this.newFamily = '';
        this.versions = [];
        this.result = null;
        this.compareKey = '';
        this.dirty = false;
        this._calcTimer = null;
        this._calcSeq = 0;
        this.root = null;
        this.loaded = false;
    }

    /** Load a glaze (or null for a new recipe) into the editor. */
    async load(glaze) {
        this.loaded = true;
        this.glaze = glaze || null;
        this.rows = reParseRecipe(glaze && glaze.recipe);
        if (this.rows.length === 0) this.rows = [{ material: '', amount: '', addition: false }];
        this.cone = (glaze && glaze.cone) ? String(glaze.cone).replace(/^cone[_ ]?/i, '') : '6';
        this.newName = '';
        this.newFamily = '';
        this.compareKey = '';
        this.dirty = false;
        this.result = null;
        this.versions = glaze ? (await API.getRecipeVersions(glaze.id)).data || [] : [];
    }

    /** Render into a container (the main canvas). Keeps unsaved edits. */
    async render(container) {
        if (!this.materials) {
            const resp = await API.getMaterials();
            this.materials = (resp.data && resp.data.materials) || [];
            if (resp.data && resp.data.cones && resp.data.cones.length) this.cones = resp.data.cones;
        }
        container.innerHTML = '';
        this.root = reEl('div', 'recipe-editor');
        this.root.append(this._toolbar(), this._body(), reEl('section', 'card re-compare'));
        container.appendChild(this.root);
        this._renderRows();
        this._renderVersions();
        this._calculate(true);
    }

    // ---- Layout -------------------------------------------------------

    _toolbar() {
        const bar = reEl('div', 're-toolbar');
        const title = reEl('div', 're-title');
        if (this.glaze) {
            title.append(reEl('h2', 're-heading', this.glaze.name));
        } else {
            title.append(reEl('h2', 're-heading', 'New recipe'));
            const name = reEl('input', 're-name');
            name.placeholder = 'Recipe name';
            name.maxLength = 100;
            name.value = this.newName;
            name.addEventListener('input', () => { this.newName = name.value; });
            const family = reEl('select', 're-family');
            family.append(new Option('Family…', ''));
            Object.entries(window.FAMILY_KEY_ALIASES || {}).forEach(([key, label]) => {
                family.append(new Option(label, key));
            });
            family.value = this.newFamily;
            family.addEventListener('change', () => { this.newFamily = family.value; });
            title.append(name, family);
        }
        this.statusEl = reEl('span', 're-status');
        title.append(this.statusEl);

        const coneLabel = reEl('label', 're-cone-label', 'Cone ');
        const cone = reEl('select', 're-cone');
        if (!this.cones.includes(this.cone)) this.cones = [...this.cones, this.cone];
        this.cones.forEach(c => cone.append(new Option(c, c)));
        cone.value = this.cone;
        cone.addEventListener('change', () => {
            this.cone = cone.value;
            this._markDirty();
            this._calculate(true);
        });
        coneLabel.append(cone);

        const newBtn = reEl('button', 'btn btn-secondary', 'New recipe');
        newBtn.type = 'button';
        newBtn.addEventListener('click', async () => {
            if (this.dirty && !confirm('Discard unsaved changes?')) return;
            await this.load(null);
            this.render(this.root.parentElement);
        });
        bar.append(title, coneLabel, newBtn);
        this._updateStatus();
        return bar;
    }

    _body() {
        const body = reEl('div', 're-body');

        const recipe = reEl('section', 'card re-recipe');
        recipe.append(reEl('h3', null, 'Recipe'));
        const table = reEl('table', 're-table');
        const head = table.createTHead().insertRow();
        ['Material', 'Amount', 'Addition', '% of total', ''].forEach(h => head.append(reEl('th', null, h)));
        this.tbody = table.createTBody();
        const datalist = reEl('datalist');
        datalist.id = 're-materials';
        (this.materials || []).forEach(m => datalist.append(new Option(m.name)));
        const add = reEl('button', 'btn btn-ghost re-add', '+ Add material');
        add.type = 'button';
        add.addEventListener('click', () => {
            this.rows.push({ material: '', amount: '', addition: false });
            this._renderRows();
            const inputs = this.tbody.querySelectorAll('.re-material');
            inputs[inputs.length - 1].focus();
        });
        this.totalsEl = reEl('p', 're-totals');
        recipe.append(table, datalist, add, this.totalsEl, this._saveForm());

        const results = reEl('section', 'card re-results');
        const heading = reEl('h3', null, 'Chemistry ');
        this.calcStateEl = reEl('span', 're-calc-state');
        heading.append(this.calcStateEl);
        this.resultsEl = reEl('div', 're-results-body');
        results.append(heading, this.resultsEl);

        const history = reEl('section', 'card re-history');
        this.versionsEl = reEl('ul', 're-versions');
        this.compareSelect = reEl('select', 're-compare-select');
        this.compareSelect.addEventListener('change', () => {
            this.compareKey = this.compareSelect.value;
            this._renderCompare();
        });
        history.append(reEl('h3', null, 'Versions'), this.versionsEl,
            reEl('h3', null, 'Compare with'), this.compareSelect);

        body.append(recipe, results, history);
        return body;
    }

    _saveForm() {
        const form = reEl('div', 're-save');
        const note = reEl('input', 're-note');
        note.placeholder = 'Note for this version (optional)';
        note.maxLength = 200;
        const save = reEl('button', 'btn btn-primary', 'Save version');
        save.type = 'button';
        save.addEventListener('click', () => this._save(note, save));
        this.saveMsgEl = reEl('p', 're-save-msg');
        form.append(note, save);
        const wrap = reEl('div');
        wrap.append(form, this.saveMsgEl);
        return wrap;
    }

    // ---- Recipe rows --------------------------------------------------

    _renderRows() {
        this.tbody.innerHTML = '';
        this.rows.forEach((row, index) => {
            const tr = this.tbody.insertRow();
            const material = reEl('input', 're-material');
            material.setAttribute('list', 're-materials');
            material.placeholder = 'Start typing a material';
            material.value = row.material;
            material.addEventListener('input', () => { row.material = material.value; this._changed(); });
            const amount = reEl('input', 're-amount');
            amount.type = 'number';
            amount.min = '0';
            amount.step = 'any';
            amount.value = row.amount;
            amount.addEventListener('input', () => { row.amount = amount.value; this._changed(); });
            amount.addEventListener('keydown', event => {
                if (event.key !== 'Enter' || index !== this.rows.length - 1) return;
                event.preventDefault();
                this.root.querySelector('.re-add').click();
            });
            const addition = reEl('input');
            addition.type = 'checkbox';
            addition.checked = row.addition;
            addition.title = 'Addition: listed after the base recipe (colorants, opacifiers)';
            addition.addEventListener('change', () => { row.addition = addition.checked; this._changed(); });
            const remove = reEl('button', 'btn btn-ghost re-remove', '×');
            remove.type = 'button';
            remove.title = 'Remove material';
            remove.addEventListener('click', () => {
                this.rows.splice(index, 1);
                if (this.rows.length === 0) this.rows.push({ material: '', amount: '', addition: false });
                this._renderRows();
                this._changed();
            });
            [material, amount, addition, reEl('span', 're-percent'), remove].forEach(el => {
                tr.insertCell().append(el);
            });
        });
        this._updateTotals();
        this._markUnknown();
    }

    _changed() {
        this._markDirty();
        this._updateTotals();
        this._calculate();
    }

    _updateTotals() {
        const amount = r => parseFloat(r.amount) > 0 ? parseFloat(r.amount) : 0;
        const base = this.rows.filter(r => !r.addition).reduce((s, r) => s + amount(r), 0);
        const additions = this.rows.filter(r => r.addition).reduce((s, r) => s + amount(r), 0);
        const total = base + additions;
        this.tbody.querySelectorAll('.re-percent').forEach((el, i) => {
            el.textContent = total > 0 && amount(this.rows[i]) > 0 ? `${(amount(this.rows[i]) / total * 100).toFixed(1)}%` : '';
        });
        const parts = [`Base ${reNumber(base, 2)}`];
        if (additions > 0) parts.push(`additions ${reNumber(additions, 2)}`, `total ${reNumber(total, 2)}`);
        this.totalsEl.textContent = parts.join(' · ');
        this.totalsEl.classList.toggle('re-off', base > 0 && Math.abs(base - 100) > 0.05);
        this.totalsEl.title = 'The chemistry is the same whatever the total; the base is usually written to 100.';
    }

    _markUnknown() {
        const missing = new Set(((this.result && this.result.missing_materials) || []).map(m => m.toLowerCase()));
        this.tbody.querySelectorAll('.re-material').forEach((input, i) => {
            const unknown = missing.has(this.rows[i].material.trim().toLowerCase());
            input.classList.toggle('re-unknown', unknown);
            input.title = unknown ? 'Not in the materials library: left out of the chemistry' : '';
        });
    }

    // ---- Live chemistry -----------------------------------------------

    _calculate(immediate = false) {
        clearTimeout(this._calcTimer);
        const run = async () => {
            const recipe = reRecipeString(this.rows);
            const seq = ++this._calcSeq;
            if (!recipe) {
                this.result = null;
                this.calcStateEl.textContent = '';
                this._renderResults();
                this._renderCompare();
                return;
            }
            this.calcStateEl.textContent = 'calculating…';
            const resp = await API.calculateUMF(recipe, this.cone);
            if (seq !== this._calcSeq) return; // a newer edit superseded this one
            this.result = resp.ok
                ? resp.data
                : { success: false, error: (resp.data && resp.data.error) || 'The calculation failed.' };
            this.calcStateEl.textContent = '';
            this._renderResults();
            this._markUnknown();
            this._renderCompare();
        };
        if (immediate) run();
        else this._calcTimer = setTimeout(run, RE_DEBOUNCE_MS);
    }

    _renderResults() {
        const out = this.resultsEl;
        out.innerHTML = '';
        const r = this.result;
        if (!r) {
            out.append(reEl('p', 're-hint', 'Add materials and amounts to see the chemistry.'));
            return;
        }
        const missing = r.missing_materials || [];
        if (missing.length) {
            const verb = missing.length === 1 ? 'is' : 'are';
            out.append(reEl('p', 're-alert',
                `Incomplete: ${missing.join(', ')} ${verb} not in the materials library, so ${missing.length === 1 ? 'it is' : 'they are'} left out of these numbers.`));
        } else if (!r.success) {
            out.append(reEl('p', 're-alert', r.error || 'This recipe could not be calculated.'));
        }
        if (!r.umf_formula) return;

        const ratios = r.ratios || {};
        const keys = reEl('dl', 're-keys');
        [
            ['SiO₂ : Al₂O₃', reNumber(ratios.sio2_al2o3, 1)],
            ['Est. CTE (×10⁻⁶/°C)', reNumber(r.thermal_expansion, 2)],
            ['Surface', r.surface_prediction || '—'],
            ['Flux : Al₂O₃', reNumber(ratios.flux_al2o3, 2)],
        ].forEach(([term, value]) => keys.append(reEl('dt', null, term), reEl('dd', null, value)));
        out.append(keys, reEl('p', 're-hint re-cte-note',
            'Expansion is an estimate (Appen method, Sankey\'s values) for comparing glazes in this app. ' +
            'It reads 0.5–1.6 lower than Insight-Live\'s figures, most with zircon, tin or rutile.'),
        this._umfTable(r.umf_formula));

        const limits = r.limit_warnings || [];
        if (limits.length) {
            const list = reEl('ul', 're-limits');
            limits.forEach(w => list.append(reEl('li', null, w)));
            out.append(reEl('h4', null, `Limit checks at cone ${r.cone}`), list);
        } else {
            out.append(reEl('p', 're-ok', `Within the typical cone ${r.cone} limits.`));
        }
    }

    _umfTable(umf) {
        const table = reEl('table', 're-umf');
        const oxides = Object.keys(umf);
        const grouped = new Set(RE_OXIDE_GROUPS.flatMap(([, list]) => list));
        const groups = RE_OXIDE_GROUPS.map(([label, list]) => [label, list.filter(ox => oxides.includes(ox))]);
        groups.push(['Other', oxides.filter(ox => !grouped.has(ox)).sort()]);
        groups.filter(([, list]) => list.length).forEach(([label, list]) => {
            const head = table.insertRow();
            head.className = 're-group';
            const th = reEl('th', null, label);
            th.colSpan = 2;
            head.append(th);
            list.forEach(ox => {
                const row = table.insertRow();
                row.append(reEl('td', null, reFormula(ox)), reEl('td', 're-num', reNumber(umf[ox], 3)));
            });
        });
        return table;
    }

    // ---- Saving and versions ------------------------------------------

    async _save(noteInput, button) {
        const msg = this.saveMsgEl;
        const fail = text => { msg.textContent = text; msg.classList.add('re-error'); };
        msg.className = 're-save-msg';
        const recipe = reRecipeString(this.rows);
        if (!recipe) return fail('Add at least one material with an amount first.');
        if (!this.glaze && (!this.newName.trim() || !this.newFamily)) {
            return fail('Give the new recipe a name and a family first.');
        }
        button.disabled = true;
        try {
            if (!this.glaze) {
                const name = this.newName.trim();
                const created = await API.createGlaze({ name, family: this.newFamily, cone: this.cone });
                if (!created.ok) return fail((created.data && created.data.error) || 'Could not create the recipe.');
                this.glaze = { id: created.data.id, name, family: this.newFamily, recipe: '', cone: this.cone };
                this.root.replaceChild(this._toolbar(), this.root.firstChild);
            }
            const saved = await API.saveRecipeVersion(this.glaze.id, {
                recipe, note: noteInput.value.trim(), cone: this.cone,
            });
            if (!saved.ok) return fail((saved.data && saved.data.error) || 'Save failed.');
            this.glaze.recipe = recipe;
            this.glaze.cone = this.cone;
            noteInput.value = '';
            this.dirty = false;
            this._updateStatus();
            this.versions = (await API.getRecipeVersions(this.glaze.id)).data || [];
            msg.textContent = `Saved as v${this.versions.length}.`;
            this._renderVersions();
            if (this.onSaved) await this.onSaved(this.glaze);
        } finally {
            button.disabled = false;
        }
    }

    _renderVersions() {
        this.versionsEl.innerHTML = '';
        if (this.versions.length === 0) {
            this.versionsEl.append(reEl('li', 're-hint', this.glaze
                ? 'No saved versions yet. The first save also keeps the current recipe.'
                : 'Save the recipe to start its version history.'));
        }
        this.versions.forEach((version, index) => {
            const number = this.versions.length - index;
            const item = reEl('li', 're-version');
            const head = reEl('div', 're-version-head');
            head.append(reEl('strong', null, `v${number}`), reEl('span', 're-version-date', reDate(version.created_at)));
            const actions = reEl('div', 're-version-actions');
            const load = reEl('button', 'btn btn-ghost', 'Load');
            load.type = 'button';
            load.title = 'Put this version in the editor (not saved until you save)';
            load.addEventListener('click', () => {
                if (this.dirty && !confirm('Replace your unsaved changes with this version?')) return;
                this.rows = reParseRecipe(version.recipe);
                if (version.cone) this.cone = String(version.cone);
                this.root.replaceChild(this._toolbar(), this.root.firstChild);
                this._renderRows();
                this._markDirty();
                this._calculate(true);
            });
            const compare = reEl('button', 'btn btn-ghost', 'Compare');
            compare.type = 'button';
            compare.addEventListener('click', () => {
                this.compareKey = `v:${version.id}`;
                this.compareSelect.value = this.compareKey;
                this._renderCompare();
            });
            actions.append(load, compare);
            item.append(head, reEl('p', 're-version-note', version.note || 'No note'),
                reEl('p', 're-version-recipe', version.recipe), actions);
            this.versionsEl.append(item);
        });
        this._renderCompareOptions();
    }

    // ---- Comparison ---------------------------------------------------

    _renderCompareOptions() {
        const select = this.compareSelect;
        select.innerHTML = '';
        select.append(new Option('Nothing (no comparison)', ''));
        if (this.versions.length) {
            const group = document.createElement('optgroup');
            group.label = 'Saved versions';
            this.versions.forEach((v, i) => {
                const label = `v${this.versions.length - i}${v.note ? ` – ${v.note}` : ''}`;
                group.append(new Option(label, `v:${v.id}`));
            });
            select.append(group);
        }
        const others = (window._glazesCache || [])
            .filter(gz => gz.recipe && (!this.glaze || gz.id !== this.glaze.id))
            .sort((a, b) => a.name.localeCompare(b.name));
        if (others.length) {
            const group = document.createElement('optgroup');
            group.label = 'Other glazes';
            others.forEach(gz => group.append(new Option(gz.name, `g:${gz.id}`)));
            select.append(group);
        }
        select.value = this.compareKey;
        if (select.value !== this.compareKey) this.compareKey = '';
    }

    _compareTarget() {
        const [kind, id] = [this.compareKey.slice(0, 1), this.compareKey.slice(2)];
        if (kind === 'v') {
            const index = this.versions.findIndex(v => String(v.id) === id);
            if (index < 0) return null;
            return { label: `v${this.versions.length - index}`, recipe: this.versions[index].recipe };
        }
        if (kind === 'g') {
            const glaze = (window._glazesCache || []).find(gz => gz.id === id);
            return glaze ? { label: glaze.name, recipe: glaze.recipe } : null;
        }
        return null;
    }

    async _renderCompare() {
        const panel = this.root && this.root.querySelector('.re-compare');
        if (!panel) return;
        const target = this._compareTarget();
        const recipe = reRecipeString(this.rows);
        panel.innerHTML = '';
        panel.classList.toggle('re-hidden', !target);
        if (!target) return;
        panel.append(reEl('h3', null, `Side by side: this recipe and ${target.label}`));
        const grid = reEl('div', 're-compare-grid');
        grid.append(reRecipeColumn('This recipe', recipe), reRecipeColumn(target.label, target.recipe));
        panel.append(grid);
        if (!recipe) return;

        const seq = this._cmpSeq = (this._cmpSeq || 0) + 1;
        const resp = await API.compareRecipes(recipe, target.recipe, this.cone);
        if (seq !== this._cmpSeq) return;
        if (!resp.ok || !resp.data || !resp.data.success) {
            // Usually unknown materials: compare the partial UMFs instead.
            const [mine, theirs] = await Promise.all([
                API.calculateUMF(recipe, this.cone), API.calculateUMF(target.recipe, this.cone),
            ]);
            if (seq !== this._cmpSeq) return;
            const a = mine.data || {};
            const b = theirs.data || {};
            if (!a.umf_formula || !b.umf_formula) {
                panel.append(reEl('p', 're-alert', (resp.data && resp.data.error) || 'These recipes could not be compared.'));
                return;
            }
            const missing = [...new Set([...(a.missing_materials || []), ...(b.missing_materials || [])])];
            if (missing.length) {
                panel.append(reEl('p', 're-alert', `Incomplete: ${missing.join(', ')} left out of both sides of this comparison.`));
            }
            panel.append(reUmfDiffTable(a.umf_formula, b.umf_formula, target.label),
                reEl('p', 're-hint', `Change = ${target.label} minus this recipe, in UMF moles.`));
            return;
        }
        panel.append(reDifferenceTable(resp.data.differences || [], target.label),
            reEl('p', 're-hint', `Change = ${target.label} minus this recipe, in UMF moles.`));
    }

    _markDirty() {
        this.dirty = true;
        this._updateStatus();
    }

    _updateStatus() {
        if (!this.statusEl) return;
        this.statusEl.textContent = this.dirty ? 'Unsaved changes' : (this.glaze ? 'Saved' : '');
        this.statusEl.classList.toggle('re-dirty', this.dirty);
    }
}

window.RecipeEditor = RecipeEditor;
window.reParseRecipe = reParseRecipe;
window.reRecipeString = reRecipeString;
