/**
 * ImportView - import recipes from an Insight-Live CSV export.
 *
 * The file is read in the browser and sent to the server for a preview: each
 * recipe with its additions, and how each material name matched. The user
 * maps unmatched names, picks recipes and a cone, then imports. Nothing is
 * saved before Import is pressed.
 *
 * Uses reEl from RecipeEditor.js (loaded first). Text from the file reaches
 * the page through textContent, never HTML.
 */

const IV_SOURCE_LABELS = {
    supplier: 'Supplier data sheet',
    theoretical: 'Theoretical',
    unverified: 'Unverified',
    custom: 'Studio material',
};

function ivMessage(resp, fallback) {
    const data = resp && resp.data;
    return (data && (data.message || data.error)) || fallback;
}

/** Decode as UTF-8, falling back to Windows-1252 for older exports. */
async function ivReadFile(file) {
    const bytes = await file.arrayBuffer();
    try {
        return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    } catch (e) {
        return new TextDecoder('windows-1252').decode(bytes);
    }
}

function ivPlural(count, word) {
    return `${count} ${word}${count === 1 ? '' : 's'}`;
}

class ImportView {
    constructor({ onImported, openGlaze } = {}) {
        this.onImported = onImported;
        this.openGlaze = openGlaze;
        this.cones = null;
        this.library = [];
        this._reset();
    }

    _reset() {
        this.fileName = null;
        this.csv = null;
        this.preview = null;
        this.mapping = {}; // export name -> material key chosen by the user ('' keeps the name)
        this.selected = new Set(); // rows to import
        this.cone = '';
        this.result = null;
        this.error = null;
        this.busy = false;
    }

    async render(container) {
        this.container = container;
        const [library, chemistry] = await Promise.all([
            API.getMaterialsLibrary(),
            this.cones ? null : API.getMaterials(),
        ]);
        this.library = library.ok ? library.data : [];
        if (chemistry) this.cones = (chemistry.ok && chemistry.data.cones) || ['6', '10'];
        this._draw();
    }

    _draw() {
        this.container.innerHTML = '';
        this.root = reEl('div', 'import-view');
        this.root.append(this._intro());
        if (this.result) {
            this.root.append(this._resultCard());
        } else if (this.preview) {
            this.recipesEl = this._recipesCard();
            this.root.append(this._materialsCard(), this.recipesEl, this._actions());
        }
        this.container.append(this.root);
    }

    _intro() {
        const card = reEl('section', 'card iv-intro');
        card.append(reEl('h2', 're-heading', 'Import from Insight-Live'));
        card.append(reEl('p', 're-hint',
            'Choose a recipe CSV exported from Insight-Live. You can check how every recipe and ' +
            'material name reads before anything is saved.'));
        const row = reEl('div', 'iv-file');
        const input = reEl('input');
        input.type = 'file';
        input.accept = '.csv,text/csv';
        input.addEventListener('change', () => {
            if (input.files && input.files[0]) this._load(input.files[0]);
        });
        row.append(input);
        if (this.busy && !this.preview) row.append(reEl('span', 're-hint', 'Reading…'));
        card.append(row);
        if (this.error) card.append(reEl('p', 're-alert', this.error));
        if (this.preview && !this.result) card.append(this._summary());
        return card;
    }

    async _load(file) {
        this._reset();
        this.fileName = file.name;
        this.busy = true;
        this._draw();
        const text = await ivReadFile(file);
        const resp = await API.previewInsightLiveImport(text);
        this.busy = false;
        if (resp.ok) {
            this.csv = text;
            this.preview = resp.data;
            resp.data.recipes.forEach(r => {
                if (r.materials.length && !(r.existing && r.existing.reason === 'code')) this.selected.add(r.row);
            });
        } else {
            this.error = ivMessage(resp, 'The file could not be read.');
        }
        this._draw();
    }

    _summary() {
        const p = this.preview;
        const unmatched = p.unmatched.length;
        let text = `${this.fileName}: ${ivPlural(p.recipes.length, 'recipe')} using ` +
            `${ivPlural(p.materials.length, 'material')}. `;
        text += unmatched ? `${ivPlural(unmatched, 'material name')} didn't match the library.`
            : 'Every material name matched the library.';
        const box = reEl('div', 'iv-summary');
        box.append(reEl('p', null, text));
        if (p.ignored_columns.length) {
            box.append(reEl('p', 're-hint', `Columns not read as materials: ${p.ignored_columns.join(', ')}.`));
        }
        return box;
    }

    /** The material key a name will use: the user's choice, else the match. */
    _keyFor(material) {
        return material.name in this.mapping ? this.mapping[material.name] : (material.key || '');
    }

    _isUnmatched(name) {
        const material = this.preview.materials.find(m => m.name === name);
        return !material || !this._keyFor(material);
    }

    _materialsCard() {
        const card = reEl('section', 'card');
        card.append(reEl('h3', null, 'Materials'));
        card.append(reEl('p', 're-hint',
            'Matched names stay as Insight-Live spells them. For a name that didn\'t match, pick one ' +
            'of our materials, or keep the name and add it later under Materials as a studio material ' +
            'with the same name.'));
        const table = reEl('table', 'mv-table iv-materials');
        const head = table.createTHead().insertRow();
        head.append(reEl('th', null, 'In Insight-Live'), reEl('th', null, 'Our material'),
            reEl('th', null, 'Source'), reEl('th', 're-num', 'Recipes'));
        const body = table.createTBody();
        this.preview.materials.forEach(material => body.append(this._materialRow(material)));
        card.append(table);
        return card;
    }

    _materialRow(material) {
        const row = reEl('tr');
        const pick = reEl('select');
        if (!material.key) pick.append(new Option('Not matched: keep the name', ''));
        this.library.forEach(m => pick.append(new Option(m.studio ? `${m.name} (studio)` : m.name, m.key)));
        pick.value = this._keyFor(material);
        const pickCell = reEl('td');
        pickCell.append(pick);
        if (material.partial && pick.value === material.key) {
            pickCell.append(reEl('div', 'iv-note', 'Matched on part of the name; check it.'));
        }
        const source = reEl('td', 'mv-source');
        const update = () => {
            const entry = this.library.find(m => m.key === pick.value);
            const type = entry && entry.source ? entry.source.type : null;
            source.textContent = type ? (IV_SOURCE_LABELS[type] || type) : '—';
            source.classList.toggle('mv-source-unverified', type === 'unverified');
            row.classList.toggle('iv-unmatched', !pick.value);
        };
        pick.addEventListener('change', () => {
            this.mapping[material.name] = pick.value;
            update();
            const fresh = this._recipesCard();
            this.recipesEl.replaceWith(fresh);
            this.recipesEl = fresh;
        });
        update();
        row.append(reEl('td', 'mv-name', material.name), pickCell, source,
            reEl('td', 're-num', String(material.recipes)));
        return row;
    }

    _recipesCard() {
        const card = reEl('section', 'card');
        card.append(reEl('h3', null, 'Recipes'));
        const table = reEl('table', 'mv-table iv-recipes');
        const head = table.createTHead().insertRow();
        const all = reEl('input');
        all.type = 'checkbox';
        all.title = 'Select all';
        const importable = this.preview.recipes.filter(r => r.materials.length);
        all.checked = importable.length > 0 && importable.every(r => this.selected.has(r.row));
        all.addEventListener('change', () => {
            importable.forEach(r => (all.checked ? this.selected.add(r.row) : this.selected.delete(r.row)));
            const fresh = this._recipesCard();
            this.recipesEl.replaceWith(fresh);
            this.recipesEl = fresh;
            this._updateImportButton();
        });
        const allCell = reEl('th');
        allCell.append(all);
        head.append(allCell, reEl('th', null, 'Recipe'), reEl('th', null, 'Materials'), reEl('th', null, 'Notes'));
        const body = table.createTBody();
        this.preview.recipes.forEach(recipe => body.append(this._recipeRow(recipe)));
        card.append(table);
        return card;
    }

    _recipeRow(recipe) {
        const row = reEl('tr');
        const check = reEl('input');
        check.type = 'checkbox';
        check.checked = this.selected.has(recipe.row);
        check.disabled = !recipe.materials.length;
        check.addEventListener('change', () => {
            if (check.checked) this.selected.add(recipe.row);
            else this.selected.delete(recipe.row);
            this._updateImportButton();
        });
        const checkCell = reEl('td');
        checkCell.append(check);

        const nameCell = reEl('td');
        nameCell.append(reEl('div', 'mv-name', recipe.name));
        const meta = [recipe.code, recipe.date].filter(Boolean).join(' · ');
        if (meta) nameCell.append(reEl('div', 'mv-summary', meta));
        if (recipe.description) nameCell.append(reEl('div', 'mv-summary', recipe.description));

        const list = reEl('ul', 'iv-recipe');
        recipe.materials.forEach(m => {
            const item = reEl('li', m.addition ? 're-addition' : null, `${m.addition ? '+ ' : ''}${m.name} ${m.amount}`);
            if (this._isUnmatched(m.name)) item.classList.add('iv-missing');
            list.append(item);
        });
        const materialsCell = reEl('td');
        materialsCell.append(list);

        row.append(checkCell, nameCell, materialsCell, this._notesCell(recipe));
        return row;
    }

    _notesCell(recipe) {
        const cell = reEl('td', 'iv-notes');
        if (recipe.existing) {
            cell.append(reEl('div', 'iv-note', recipe.existing.reason === 'code'
                ? `Imported before as "${recipe.existing.name}". Importing again adds a second copy.`
                : `A glaze named "${recipe.existing.name}" already exists. Importing adds another.`));
        }
        if (recipe.additions === 'found') {
            cell.append(reEl('div', 're-hint',
                `Base ${recipe.base_total}, additions ${recipe.additions_total}.`));
        }
        recipe.warnings.forEach(w => cell.append(reEl('div', 'iv-note', w)));
        return cell;
    }

    _actions() {
        const card = reEl('section', 'card iv-actions');
        const coneLabel = reEl('label', 'iv-cone', 'Cone ');
        const cone = reEl('select');
        cone.append(new Option('Not set', ''));
        (this.cones || []).forEach(c => cone.append(new Option(c, c)));
        cone.value = this.cone;
        cone.addEventListener('change', () => { this.cone = cone.value; });
        coneLabel.append(cone);
        this.importBtn = reEl('button', 'btn btn-primary');
        this.importBtn.type = 'button';
        this.importBtn.addEventListener('click', () => this._import());
        const row = reEl('div', 'iv-action-row');
        row.append(coneLabel, this.importBtn);
        card.append(row);
        card.append(reEl('p', 're-hint',
            'Insight-Live\'s export doesn\'t include a firing cone. The cone chosen here is stored with ' +
            'every imported recipe and can be changed per recipe in the recipe editor.'));
        this.importMsg = reEl('p', 're-alert');
        this.importMsg.hidden = true;
        card.append(this.importMsg);
        this._updateImportButton();
        return card;
    }

    _updateImportButton() {
        if (!this.importBtn) return;
        const count = this.selected.size;
        this.importBtn.textContent = this.busy ? 'Importing…' : `Import ${ivPlural(count, 'recipe')}`;
        this.importBtn.disabled = this.busy || count === 0;
    }

    async _import() {
        this.busy = true;
        this._updateImportButton();
        const mapping = {};
        Object.entries(this.mapping).forEach(([name, key]) => { if (key) mapping[name] = key; });
        const resp = await API.importInsightLive({
            csv: this.csv, rows: [...this.selected], mapping, cone: this.cone,
        });
        this.busy = false;
        if (!resp.ok) {
            this.importMsg.textContent = ivMessage(resp, 'The import failed.');
            this.importMsg.hidden = false;
            this._updateImportButton();
            return;
        }
        this.result = resp.data.imported;
        if (this.onImported) await this.onImported();
        this._draw();
    }

    _resultCard() {
        const card = reEl('section', 'card');
        card.append(reEl('h3', null, `Imported ${ivPlural(this.result.length, 'recipe')}`));
        const list = reEl('ul', 'iv-result');
        this.result.forEach(item => {
            const li = reEl('li');
            const open = reEl('button', 'btn btn-ghost', 'Open in recipe editor');
            open.type = 'button';
            open.addEventListener('click', () => this.openGlaze && this.openGlaze(item.id));
            li.append(reEl('span', 'mv-name', item.name));
            if (item.code) li.append(reEl('span', 'mv-summary', ` ${item.code}`));
            li.append(open);
            if (item.missing.length) {
                li.append(reEl('div', 'iv-note', `Not in the library yet: ${item.missing.join(', ')}`));
            }
            list.append(li);
        });
        card.append(list);
        if (this.result.some(item => item.missing.length)) {
            card.append(reEl('p', 're-hint',
                'A recipe with a missing material calculates once that material is added under Materials ' +
                'as a studio material with the same name, or once the recipe editor swaps it for another.'));
        }
        const again = reEl('button', 'btn btn-secondary', 'Import another file');
        again.type = 'button';
        again.addEventListener('click', () => { this._reset(); this._draw(); });
        card.append(again);
        return card;
    }
}

window.ImportView = ImportView;
