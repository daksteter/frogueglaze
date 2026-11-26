/**
 * MaterialsView - the material library with sources, the studio's own
 * materials, and lot analyses.
 *
 * Uses reEl / reFormula / reNumber from RecipeEditor.js (loaded first).
 * All user-entered text reaches the page through textContent, never HTML.
 */

const MV_OXIDES = [
    'SiO2', 'Al2O3', 'B2O3', 'Fe2O3', 'FeO', 'TiO2', 'CaO', 'MgO', 'K2O', 'Na2O', 'Li2O',
    'ZnO', 'SrO', 'BaO', 'P2O5', 'MnO', 'ZrO2', 'SnO2', 'CoO', 'CuO', 'Cr2O3', 'NiO',
];
const MV_CATEGORIES = ['feldspar', 'clay', 'silica', 'flux', 'frit', 'colorant', 'opacifier', 'other'];
const MV_FILTERS = [
    ['all', 'All materials'],
    ['studio', 'Studio materials'],
    ['lot', 'Using a lot analysis'],
    ['supplier', 'Supplier data sheet'],
    ['theoretical', 'Theoretical'],
    ['unverified', 'Unverified'],
];

function mvTotal(oxides, loi) {
    return Object.values(oxides || {}).reduce((s, v) => s + (parseFloat(v) || 0), 0) + (parseFloat(loi) || 0);
}

function mvSummary(oxides) {
    return Object.entries(oxides || {})
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([ox, v]) => `${reFormula(ox)} ${reNumber(v, 1)}`)
        .join(' · ');
}

function mvSourceText(source) {
    if (!source) return '';
    if (source.type === 'supplier') return [source.supplier, source.document, source.date].filter(Boolean).join(', ');
    if (source.type === 'theoretical') return `Theoretical: ${reFormula(source.formula || '')}`;
    if (source.type === 'unverified') return 'Unverified (inherited from upstream)';
    if (source.type === 'custom') return source.text || 'Studio material';
    return '';
}

class MaterialsView {
    constructor({ onChanged } = {}) {
        this.onChanged = onChanged;
        this.materials = [];
        this.query = '';
        this.filter = 'all';
        this.selectedKey = null;
        this.form = null; // {kind: 'material'|'lot', material?}
        this.root = null;
    }

    async render(container) {
        this.container = container;
        await this._reload();
        container.innerHTML = '';
        this.root = reEl('div', 'materials-view');
        this.root.append(this._toolbar());
        const body = reEl('div', 'mv-body');
        this.listEl = reEl('section', 'card mv-list');
        this.detailEl = reEl('section', 'card mv-detail');
        body.append(this.listEl, this.detailEl);
        this.root.append(body);
        container.append(this.root);
        this._renderList();
        this._renderDetail();
    }

    async _reload() {
        const resp = await API.getMaterialsLibrary();
        this.materials = resp.ok ? resp.data : [];
        this.loadError = resp.ok ? null : ((resp.data && resp.data.error) || 'Could not load materials.');
    }

    async _changed(selectKey) {
        if (selectKey !== undefined) this.selectedKey = selectKey;
        this.form = null;
        await this._reload();
        this._renderList();
        this._renderDetail();
        if (this.onChanged) this.onChanged();
    }

    _toolbar() {
        const bar = reEl('div', 'mv-toolbar');
        bar.append(reEl('h2', 're-heading', 'Materials'));
        const search = reEl('input', 'mv-search');
        search.type = 'search';
        search.placeholder = 'Search name, alias or oxide';
        search.value = this.query;
        search.addEventListener('input', () => { this.query = search.value; this._renderList(); });
        const filter = reEl('select', 'mv-filter');
        MV_FILTERS.forEach(([value, label]) => filter.append(new Option(label, value)));
        filter.value = this.filter;
        filter.addEventListener('change', () => { this.filter = filter.value; this._renderList(); });
        const add = reEl('button', 'btn btn-primary', 'Add studio material');
        add.type = 'button';
        add.addEventListener('click', () => { this.form = { kind: 'material' }; this.selectedKey = null; this._renderDetail(); });
        bar.append(search, filter, add);
        return bar;
    }

    _visible() {
        const q = this.query.trim().toLowerCase();
        return this.materials.filter(m => {
            if (this.filter === 'studio' && !m.studio) return false;
            if (this.filter === 'lot' && !m.current_lot) return false;
            if (['supplier', 'theoretical', 'unverified'].includes(this.filter) && m.source.type !== this.filter) return false;
            if (!q) return true;
            return m.name.toLowerCase().includes(q)
                || m.aliases.some(a => a.toLowerCase().includes(q))
                || Object.keys(m.oxides).some(ox => ox.toLowerCase() === q);
        });
    }

    _renderList() {
        this.listEl.innerHTML = '';
        if (this.loadError) {
            this.listEl.append(reEl('p', 're-alert', this.loadError));
            return;
        }
        const visible = this._visible();
        this.listEl.append(reEl('p', 're-hint', `${visible.length} of ${this.materials.length} materials`));
        const table = reEl('table', 'mv-table');
        const head = table.createTHead().insertRow();
        ['Material', 'Main oxides', 'LOI', 'Source'].forEach(h => head.append(reEl('th', null, h)));
        const body = table.createTBody();
        visible.forEach(m => {
            const row = body.insertRow();
            row.className = m.key === this.selectedKey ? 'mv-selected' : '';
            row.tabIndex = 0;
            const name = reEl('td', 'mv-name', m.name);
            if (m.studio) name.append(reEl('span', 'mv-badge', 'Studio'));
            if (m.current_lot) name.append(reEl('span', 'mv-badge mv-badge-lot', `Lot ${m.current_lot.lot}`));
            const shown = m.current_lot || m;
            row.append(name, reEl('td', 'mv-summary', mvSummary(shown.oxides)),
                reEl('td', 're-num', reNumber(shown.loi, 1)),
                reEl('td', `mv-source mv-source-${m.source.type}`, mvSourceText(m.source)));
            const open = () => { this.selectedKey = m.key; this.form = null; this._renderList(); this._renderDetail(); };
            row.addEventListener('click', open);
            row.addEventListener('keydown', e => { if (e.key === 'Enter') open(); });
        });
        this.listEl.append(table);
    }

    // ---- Detail -------------------------------------------------------

    _renderDetail() {
        const out = this.detailEl;
        out.innerHTML = '';
        const material = this.materials.find(m => m.key === this.selectedKey);
        if (this.form && this.form.kind === 'material') {
            out.append(this._analysisForm(this.form.material || null));
            return;
        }
        if (!material) {
            out.append(reEl('h3', null, 'Pick a material'),
                reEl('p', 're-hint', 'Choose a material to see its analysis and where it came from, or add one of your own.'));
            return;
        }
        const heading = reEl('h3', null, material.name);
        heading.append(reEl('span', 'mv-badge', material.studio ? 'Studio' : material.category));
        out.append(heading);
        if (material.aliases.length) out.append(reEl('p', 're-hint', `Also called: ${material.aliases.join(', ')}`));
        out.append(this._sourceBlock(material.source));
        if (material.current_lot) {
            out.append(reEl('p', 'mv-lot-note',
                `Calculations use lot ${material.current_lot.lot}, not the standard analysis below.`));
        }
        out.append(this._analysisTable(material));
        if (material.studio) out.append(this._studioActions(material));
        out.append(this._lotsSection(material));
    }

    _sourceBlock(source) {
        const block = reEl('div', `mv-sourceblock mv-source-${source.type}`);
        if (source.type === 'supplier') {
            block.append(reEl('strong', null, 'Supplier data sheet: '));
            const link = reEl('a', null, [source.supplier, source.document].filter(Boolean).join(', '));
            link.href = source.url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            block.append(link);
            if (source.date) block.append(document.createTextNode(` (${source.date})`));
        } else if (source.type === 'theoretical') {
            block.append(reEl('strong', null, 'Theoretical: '),
                document.createTextNode(`calculated from ${reFormula(source.formula || '')}.`));
        } else if (source.type === 'unverified') {
            block.append(reEl('strong', null, 'Unverified: '), document.createTextNode(source.note || ''));
        } else {
            block.append(reEl('strong', null, 'Source: '), document.createTextNode(source.text || 'not recorded'));
        }
        if (source.note && source.type !== 'unverified') block.append(reEl('p', 're-hint', source.note));
        if (source.type === 'custom' && source.notes) block.append(reEl('p', 're-hint', source.notes));
        return block;
    }

    _analysisTable(material) {
        const lot = material.current_lot;
        const table = reEl('table', 're-umf mv-analysis');
        const head = table.createTHead().insertRow();
        head.append(reEl('th', null, 'Oxide'), reEl('th', 're-num', 'Standard %'));
        if (lot) head.append(reEl('th', 're-num', `Lot ${lot.lot} %`));
        const body = table.createTBody();
        const oxides = [...new Set([...Object.keys(material.oxides), ...Object.keys(lot ? lot.oxides : {})])];
        oxides.sort((a, b) => (material.oxides[b] || 0) - (material.oxides[a] || 0));
        const addRow = (label, a, b, cls) => {
            const row = body.insertRow();
            if (cls) row.className = cls;
            row.append(reEl('td', null, label), reEl('td', 're-num', a));
            if (lot) row.append(reEl('td', 're-num', b));
        };
        oxides.forEach(ox => addRow(reFormula(ox), reNumber(material.oxides[ox], 2), lot ? reNumber(lot.oxides[ox], 2) : ''));
        addRow('LOI', reNumber(material.loi, 2), lot ? reNumber(lot.loi, 2) : '');
        addRow('Total', reNumber(mvTotal(material.oxides, material.loi), 1),
            lot ? reNumber(mvTotal(lot.oxides, lot.loi), 1) : '', 'mv-total');
        return table;
    }

    _studioActions(material) {
        const actions = reEl('div', 'mv-actions');
        const edit = reEl('button', 'btn btn-secondary', 'Edit');
        edit.type = 'button';
        edit.addEventListener('click', () => { this.form = { kind: 'material', material }; this._renderDetail(); });
        const remove = reEl('button', 'btn btn-ghost', 'Delete');
        remove.type = 'button';
        remove.addEventListener('click', async () => {
            if (!confirm(`Delete ${material.name}? Recipes that use it will show it as unknown.`)) return;
            const resp = await API.deleteStudioMaterial(material.key);
            if (resp.ok) this._changed(null);
            else alert((resp.data && resp.data.error) || 'Delete failed.');
        });
        actions.append(edit, remove);
        return actions;
    }

    // ---- Lots ---------------------------------------------------------

    _lotsSection(material) {
        const section = reEl('div', 'mv-lots');
        section.append(reEl('h4', null, 'Lot analyses'));
        const list = reEl('ul', 'mv-lot-list');
        section.append(list);
        API.getMaterialLots(material.key).then(resp => {
            const lots = resp.ok ? resp.data : [];
            if (!lots.length) list.append(reEl('li', 're-hint', 'None recorded. The standard analysis is used.'));
            lots.forEach(lot => list.append(this._lotItem(material, lot)));
        });
        if (material.current_lot) {
            const standard = reEl('button', 'btn btn-ghost', 'Use the standard analysis');
            standard.type = 'button';
            standard.addEventListener('click', async () => {
                await API.setCurrentLot(material.key, null);
                this._changed(material.key);
            });
            section.append(standard);
        }
        if (this.form && this.form.kind === 'lot') {
            section.append(this._analysisForm(material, true));
        } else {
            const add = reEl('button', 'btn btn-secondary', 'Record a lot analysis');
            add.type = 'button';
            add.addEventListener('click', () => { this.form = { kind: 'lot' }; this._renderDetail(); });
            section.append(add);
        }
        return section;
    }

    _lotItem(material, lot) {
        const item = reEl('li', lot.current ? 'mv-lot mv-lot-current' : 'mv-lot');
        const head = reEl('div', 're-version-head');
        head.append(reEl('strong', null, `Lot ${lot.lot}${lot.current ? ' (in use)' : ''}`),
            reEl('span', 're-version-date', reDate(lot.created_at)));
        item.append(head, reEl('p', 're-version-recipe', mvSummary(lot.oxides)));
        if (lot.source) item.append(reEl('p', 're-hint', lot.source));
        const actions = reEl('div', 're-version-actions');
        if (!lot.current) {
            const use = reEl('button', 'btn btn-ghost', 'Use this lot');
            use.type = 'button';
            use.addEventListener('click', async () => {
                await API.setCurrentLot(material.key, lot.id);
                this._changed(material.key);
            });
            actions.append(use);
        }
        const remove = reEl('button', 'btn btn-ghost', 'Delete');
        remove.type = 'button';
        remove.addEventListener('click', async () => {
            if (!confirm(`Delete lot ${lot.lot}?`)) return;
            await API.deleteMaterialLot(material.key, lot.id);
            this._changed(material.key);
        });
        actions.append(remove);
        item.append(actions);
        return item;
    }

    // ---- Forms --------------------------------------------------------

    /** Form for a new/edited studio material, or (isLot) a lot analysis. */
    _analysisForm(material, isLot = false) {
        const editing = !isLot && material;
        const form = reEl('form', 'mv-form');
        form.append(reEl('h4', null, isLot ? `New lot analysis for ${material.name}`
            : editing ? `Edit ${material.name}` : 'Add a studio material'));
        const field = (label, input) => {
            const wrap = reEl('label', 'mv-field', label);
            wrap.append(input);
            form.append(wrap);
            return input;
        };
        const text = (value, max) => {
            const input = reEl('input');
            input.value = value || '';
            input.maxLength = max;
            return input;
        };
        let name, aliases, category;
        const lotLabel = isLot ? field('Lot number or label', text('', 80)) : null;
        if (!isLot) {
            name = field('Name', text(editing ? material.name : '', 80));
            name.disabled = !!editing;
            aliases = field('Other names (comma separated)', text(editing ? material.aliases.join(', ') : '', 300));
            category = field('Category', reEl('select'));
            MV_CATEGORIES.forEach(c => category.append(new Option(c, c)));
            category.value = editing ? material.category : 'other';
        }
        const start = editing ? material.oxides : {};
        const grid = reEl('div', 'mv-oxide-grid');
        const inputs = {};
        MV_OXIDES.forEach(ox => {
            const cell = reEl('label', 'mv-oxide', reFormula(ox));
            const input = reEl('input');
            input.type = 'number';
            input.step = 'any';
            input.min = '0';
            input.value = start[ox] !== undefined ? start[ox] : '';
            inputs[ox] = input;
            cell.append(input);
            grid.append(cell);
        });
        form.append(reEl('p', 're-hint', 'Weight percent as received, from the data sheet. Leave blanks for oxides not listed.'), grid);
        const loi = field('LOI %', reEl('input'));
        loi.type = 'number';
        loi.step = 'any';
        loi.min = '0';
        loi.value = editing ? material.loi : '';
        const totalEl = reEl('p', 'mv-form-total');
        form.append(totalEl);
        const source = field(isLot ? 'Source (certificate, data sheet)' : 'Source (supplier, data sheet, lab test)',
            text(editing && material.source ? material.source.text : '', 500));
        const notes = !isLot ? field('Notes', text(editing && material.source ? material.source.notes : '', 500)) : null;
        let current = null;
        if (isLot) {
            current = reEl('input');
            current.type = 'checkbox';
            current.checked = true;
            const wrap = reEl('label', 'mv-check');
            wrap.append(current, document.createTextNode(' Use this lot for calculations now'));
            form.append(wrap);
        }
        const values = () => {
            const oxides = {};
            Object.entries(inputs).forEach(([ox, input]) => { if (input.value !== '') oxides[ox] = parseFloat(input.value); });
            return oxides;
        };
        const updateTotal = () => {
            const total = mvTotal(values(), loi.value);
            totalEl.textContent = `Oxides + LOI = ${total.toFixed(1)}%`;
            totalEl.classList.toggle('re-off', total > 0 && Math.abs(total - 100) > 2);
        };
        form.addEventListener('input', updateTotal);
        updateTotal();

        const msg = reEl('p', 're-save-msg');
        const save = reEl('button', 'btn btn-primary', isLot ? 'Save lot' : 'Save material');
        save.type = 'submit';
        const cancel = reEl('button', 'btn btn-ghost', 'Cancel');
        cancel.type = 'button';
        cancel.addEventListener('click', () => { this.form = null; this._renderDetail(); });
        const actions = reEl('div', 'mv-actions');
        actions.append(save, cancel);
        form.append(actions, msg);

        form.addEventListener('submit', async event => {
            event.preventDefault();
            save.disabled = true;
            const body = { oxides: values(), loi: loi.value === '' ? 0 : parseFloat(loi.value), source: source.value };
            let resp;
            if (isLot) {
                resp = await API.addMaterialLot(material.key, { ...body, lot: lotLabel.value, current: current.checked });
            } else {
                Object.assign(body, { name: name.value, aliases: aliases.value, category: category.value, notes: notes.value });
                resp = editing ? await API.updateStudioMaterial(material.key, body) : await API.createStudioMaterial(body);
            }
            save.disabled = false;
            if (!resp.ok) {
                msg.textContent = (resp.data && resp.data.error) || 'Save failed.';
                msg.classList.add('re-error');
                return;
            }
            const warnings = (resp.data && resp.data.warnings) || [];
            await this._changed(isLot ? material.key : resp.data.key);
            if (warnings.length) alert(`Saved. Note: ${warnings.join(' ')}`);
        });
        return form;
    }
}

window.MaterialsView = MaterialsView;
