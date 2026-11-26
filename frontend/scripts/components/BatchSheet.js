/**
 * BatchSheet - a recipe scaled to a batch size, previewed in a dialog and
 * printed on its own.
 *
 * openBatchSheet({ name, recipe, cone, detail }) opens it for any recipe,
 * saved or not. The scaling comes from POST /api/batch-sheet; printing copies
 * the sheet into #print-root so the rest of the app stays off the page.
 * Uses reEl from RecipeEditor.js. Text reaches the page through textContent.
 */

const BS_SIZE_KEY = 'batchSheet.size';
const BS_BASIS_KEY = 'batchSheet.basis';

function bsGrams(value) {
    return typeof value === 'number' ? value.toFixed(1) : '—';
}

function bsStored(key, fallback) {
    try { return localStorage.getItem(key) || fallback; } catch (e) { return fallback; }
}

function bsStore(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* private mode */ }
}

class BatchSheet {
    constructor() {
        this.dialog = null;
        this.sheet = null;
        this.seq = 0;
    }

    open({ name, recipe, cone, detail } = {}) {
        this.source = { name: name || 'Untitled recipe', recipe: recipe || '', cone, detail };
        this.size = parseFloat(bsStored(BS_SIZE_KEY, '1000')) || 1000;
        this.basis = bsStored(BS_BASIS_KEY, 'base') === 'total' ? 'total' : 'base';
        if (!this.dialog) this._build();
        this.dialog.showModal();
        this._refresh();
    }

    _build() {
        const dialog = reEl('dialog', 'bs-dialog');
        dialog.setAttribute('aria-label', 'Batch sheet');
        const controls = reEl('div', 'bs-controls');
        const sizeLabel = reEl('label', 'bs-field', 'Batch size (g) ');
        this.sizeInput = reEl('input');
        this.sizeInput.type = 'number';
        this.sizeInput.min = '1';
        this.sizeInput.step = 'any';
        this.sizeInput.addEventListener('input', () => {
            const value = parseFloat(this.sizeInput.value);
            if (value > 0) { this.size = value; bsStore(BS_SIZE_KEY, String(value)); this._refresh(); }
        });
        sizeLabel.append(this.sizeInput);
        this.basisSelect = reEl('select');
        this.basisSelect.append(new Option('for the base; additions on top', 'base'),
            new Option('for the whole batch', 'total'));
        this.basisSelect.addEventListener('change', () => {
            this.basis = this.basisSelect.value;
            bsStore(BS_BASIS_KEY, this.basis);
            this._refresh();
        });
        const print = reEl('button', 'btn btn-primary', 'Print');
        print.type = 'button';
        print.addEventListener('click', () => this._print());
        const close = reEl('button', 'btn btn-secondary', 'Close');
        close.type = 'button';
        close.addEventListener('click', () => dialog.close());
        controls.append(sizeLabel, this.basisSelect, print, close);
        this.messageEl = reEl('p', 're-alert');
        this.messageEl.hidden = true;
        this.previewEl = reEl('div', 'bs-preview');
        dialog.append(controls, this.messageEl, this.previewEl);
        document.body.append(dialog);
        this.dialog = dialog;
    }

    async _refresh() {
        this.sizeInput.value = String(this.size);
        this.basisSelect.value = this.basis;
        const seq = ++this.seq;
        const resp = await API.makeBatchSheet({ recipe: this.source.recipe, size: this.size, basis: this.basis });
        if (seq !== this.seq) return;
        this.messageEl.hidden = resp.ok;
        if (!resp.ok) {
            this.messageEl.textContent = (resp.data && (resp.data.message || resp.data.error)) || 'The batch sheet could not be made.';
            this.previewEl.replaceChildren();
            this.sheet = null;
            return;
        }
        this.sheet = resp.data;
        this.previewEl.replaceChildren(this._sheet(resp.data));
    }

    _sheet(data) {
        const page = reEl('article', 'bs-sheet');
        const head = reEl('header', 'bs-head');
        head.append(reEl('h1', null, this.source.name));
        const facts = [
            this.source.cone ? `Cone ${this.source.cone}` : null,
            this.source.detail || null,
            `Printed ${new Date().toLocaleDateString(undefined, { dateStyle: 'medium' })}`,
        ].filter(Boolean);
        head.append(reEl('p', 'bs-facts', facts.join(' · ')));
        let size = `${bsGrams(data.total_grams)} g to weigh`;
        if (data.additions_grams && data.basis === 'base') {
            size = `Base ${bsGrams(data.base_grams)} g + additions ${bsGrams(data.additions_grams)} g = ${size}`;
        } else if (data.additions_grams) {
            size = `Whole batch ${size}, additions included`;
        }
        head.append(reEl('p', 'bs-size', `${size}.`));
        page.append(head, this._table(data), this._blanks());
        return page;
    }

    _table(data) {
        const table = reEl('table', 'bs-table');
        const head = table.createTHead().insertRow();
        ['', 'Material', 'Recipe', 'Weigh (g)', 'Running total (g)', 'Lot'].forEach((label, i) => {
            head.append(reEl('th', i >= 2 && i <= 4 ? 'bs-num' : null, label));
        });
        const body = table.createTBody();
        let inAdditions = false;
        data.rows.forEach(row => {
            if (row.addition && !inAdditions) {
                inAdditions = true;
                const divider = body.insertRow();
                divider.className = 'bs-divider';
                const cell = reEl('td', null, 'Additions');
                cell.colSpan = 6;
                divider.append(cell);
            }
            const tr = body.insertRow();
            tr.append(reEl('td', 'bs-tick', '☐'),
                reEl('td', 'bs-material', row.name),
                reEl('td', 'bs-num', String(row.amount)),
                reEl('td', 'bs-num bs-weigh', bsGrams(row.grams)),
                reEl('td', 'bs-num', bsGrams(row.running)),
                reEl('td', 'bs-lot', row.lot || ''));
        });
        const total = table.createTFoot().insertRow();
        const percent = Math.round((data.base_percent + data.additions_percent) * 100) / 100;
        total.append(reEl('td'), reEl('td', 'bs-material', 'Total'), reEl('td', 'bs-num', String(percent)),
            reEl('td', 'bs-num bs-weigh', bsGrams(data.total_grams)), reEl('td'), reEl('td'));
        return table;
    }

    _blanks() {
        const blanks = reEl('dl', 'bs-blanks');
        ['Date batched', 'Batched by', 'Water added', 'Specific gravity', 'Notes'].forEach(term => {
            blanks.append(reEl('dt', null, term), reEl('dd'));
        });
        return blanks;
    }

    _print() {
        if (!this.sheet) return;
        let root = document.getElementById('print-root');
        if (!root) {
            root = reEl('div');
            root.id = 'print-root';
            document.body.append(root);
        }
        root.replaceChildren(this.previewEl.firstElementChild.cloneNode(true));
        document.body.classList.add('printing');
        const done = () => {
            document.body.classList.remove('printing');
            root.replaceChildren();
            window.removeEventListener('afterprint', done);
        };
        window.addEventListener('afterprint', done);
        window.print();
    }
}

const batchSheet = new BatchSheet();

function openBatchSheet(options) {
    batchSheet.open(options);
}

window.openBatchSheet = openBatchSheet;
