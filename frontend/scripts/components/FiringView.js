/**
 * FiringView - the studio's firing schedules: cards with each firing curve,
 * and a dialog to write, check and print one.
 *
 * Timing comes from the server (POST /api/firing-schedules/timing while
 * editing), so the numbers shown are the ones that get saved. Uses reEl from
 * RecipeEditor.js and printOnly from BatchSheet.js; text reaches the page
 * through textContent.
 */

const FV_SVG = 'http://www.w3.org/2000/svg';
const FV_UNIT_KEY = 'firing.unit';

function fvDuration(minutes) {
    const total = Math.round(minutes || 0);
    const h = Math.floor(total / 60);
    const m = total % 60;
    if (!h) return `${m} min`;
    return m ? `${h} h ${m} min` : `${h} h`;
}

function fvText(value) {
    return value === null || value === undefined ? '' : String(value);
}

function fvSummary(timing, unit) {
    let text = `Peak ${timing.peak} °${unit} · about ${fvDuration(timing.total_minutes)}`;
    const full = timing.full_speed_segments;
    if (full) {
        text += ` (${full} full-speed segment${full > 1 ? 's' : ''} estimated at ${timing.full_speed_rate} °${unit}/hr)`;
    }
    return text;
}

function fvSvg(tag, attrs, text) {
    const el = document.createElementNS(FV_SVG, tag);
    Object.entries(attrs || {}).forEach(([key, value]) => el.setAttribute(key, value));
    if (text !== undefined) el.textContent = text;
    return el;
}

/** The firing curve: temperature against hours; full-speed ramps are dashed. */
function fvChart(timing, unit, { axes = true } = {}) {
    const W = 600;
    const H = axes ? 260 : 110;
    const pad = axes ? { l: 52, r: 14, t: 12, b: 30 } : { l: 4, r: 4, t: 6, b: 4 };
    const step = unit === 'C' ? 200 : 500;
    const top = Math.max(step, Math.ceil(timing.peak / step) * step);
    const hours = Math.max(1, Math.ceil(timing.total_minutes / 60));
    const x = minutes => pad.l + (minutes / 60 / hours) * (W - pad.l - pad.r);
    const y = temp => H - pad.b - (temp / top) * (H - pad.t - pad.b);
    const svg = fvSvg('svg', { viewBox: `0 0 ${W} ${H}`, class: axes ? 'fv-chart' : 'fv-chart fv-mini', role: 'img' });
    svg.setAttribute('aria-label', `Firing curve: ${fvSummary(timing, unit)}`);
    if (axes) {
        for (let t = 0; t <= top; t += step) {
            svg.append(fvSvg('line', { x1: pad.l, x2: W - pad.r, y1: y(t), y2: y(t), class: 'fv-grid' }),
                fvSvg('text', { x: pad.l - 6, y: y(t) + 4, class: 'fv-axis', 'text-anchor': 'end' }, `${t}°`));
        }
        const every = hours <= 12 ? 1 : hours <= 24 ? 2 : 4;
        for (let h = 0; h <= hours; h += every) {
            svg.append(fvSvg('text', { x: x(h * 60), y: H - 10, class: 'fv-axis', 'text-anchor': 'middle' }, `${h} h`));
        }
    }
    const pts = timing.points;
    for (let i = 1; i < pts.length; i++) {
        svg.append(fvSvg('line', {
            x1: x(pts[i - 1].minutes), y1: y(pts[i - 1].temp), x2: x(pts[i].minutes), y2: y(pts[i].temp),
            class: pts[i].full ? 'fv-curve fv-full' : 'fv-curve',
        }));
    }
    return svg;
}

class FiringView {
    constructor() {
        this.schedules = [];
        this.dialog = null;
        this.timing = null;
        this.timingSeq = 0;
        this.timer = null;
    }

    async render(container) {
        container.innerHTML = '';
        const root = reEl('div', 'firing-view');
        this.messageEl = reEl('p', 're-alert');
        this.messageEl.hidden = true;
        this.gridEl = reEl('div', 'fv-cards');
        const add = reEl('button', 'btn btn-primary', 'New schedule');
        add.type = 'button';
        add.addEventListener('click', () => this.open(null));
        const bar = reEl('div', 'fv-toolbar');
        bar.append(reEl('h2', 're-heading', 'Firing schedules'), add);
        root.append(bar, this.messageEl, this.gridEl);
        container.append(root);
        await this._reload();
    }

    async _reload() {
        const resp = await API.getFiringSchedules();
        this.schedules = resp.ok ? resp.data : [];
        this._message(resp.ok ? null : this._error(resp, 'Could not load the firing schedules.'));
        if (!this.gridEl) return;
        this.gridEl.replaceChildren(...this.schedules.map(s => this._card(s)));
        if (!this.schedules.length) {
            this.gridEl.append(reEl('p', 'fv-empty', 'No firing schedules yet. Add the studio’s kiln programs with New schedule.'));
        }
    }

    _error(resp, fallback) {
        return (resp.data && (resp.data.message || resp.data.error)) || fallback;
    }

    _message(text, el = this.messageEl) {
        if (!el) return;
        el.hidden = !text;
        el.textContent = text || '';
    }

    _card(schedule) {
        const card = reEl('button', 'card fv-card');
        card.type = 'button';
        card.addEventListener('click', () => this.open(schedule));
        const facts = [schedule.cone ? `Cone ${schedule.cone}` : '', `${schedule.segments.length} segments`,
            `about ${fvDuration(schedule.timing.total_minutes)}`].filter(Boolean).join(' · ');
        card.append(reEl('span', 'fv-card-title', schedule.name), reEl('span', 'fv-facts', facts),
            fvChart(schedule.timing, schedule.unit, { axes: false }));
        if (schedule.tile_count) {
            const n = schedule.tile_count;
            card.append(reEl('span', 'fv-facts', `Used by ${n} test tile${n > 1 ? 's' : ''}`));
        }
        return card;
    }

    // ---- The schedule dialog ----

    open(schedule) {
        if (!this.dialog) this._buildDialog();
        this.editing = schedule;
        const f = this.f;
        f.name.value = schedule ? schedule.name : '';
        f.cone.value = schedule ? fvText(schedule.cone) : '';
        f.unit.value = schedule ? schedule.unit : (localStorage.getItem(FV_UNIT_KEY) || 'F');
        f.notes.value = schedule ? fvText(schedule.notes) : '';
        this.rowsEl.replaceChildren();
        (schedule ? schedule.segments : [{}]).forEach(seg => this._addRow(seg));
        this.titleEl.textContent = schedule ? 'Firing schedule' : 'New firing schedule';
        this.deleteBtn.hidden = !schedule;
        this._message(null, this.formMessage);
        this.dirty = false;
        this.dialog.showModal();
        this._retime(0);
    }

    _input(className, placeholder, mode = 'decimal') {
        const input = reEl('input', className);
        input.type = 'text';
        input.inputMode = mode;
        if (placeholder) input.placeholder = placeholder;
        return input;
    }

    _field(label, input, className = 'fv-field') {
        const wrap = reEl('label', className);
        wrap.append(reEl('span', 'tv-field-label', label), input);
        return wrap;
    }

    _buildDialog() {
        const f = {};
        f.name = this._input(null, 'e.g. Cone 6 glaze, slow cool', 'text');
        f.name.maxLength = 80;
        f.cone = this._input(null, 'e.g. 6', 'text');
        f.cone.maxLength = 20;
        f.unit = reEl('select');
        f.unit.append(new Option('°F', 'F'), new Option('°C', 'C'));
        f.notes = reEl('textarea');
        f.notes.rows = 2;
        f.notes.maxLength = 2000;
        f.notes.placeholder = 'Kiln, loading, when to use it…';
        this.f = f;

        const dialog = reEl('dialog', 'tv-dialog fv-dialog');
        dialog.setAttribute('aria-label', 'Firing schedule');
        this.titleEl = reEl('h2', 're-heading');
        const head = reEl('div', 'fv-form');
        head.append(this._field('Name', f.name, 'fv-field fv-name'), this._field('Cone', f.cone),
            this._field('Unit', f.unit), this._field('Notes', f.notes, 'fv-field fv-wide'));
        this.summaryEl = reEl('p', 'fv-summary');
        this.chartEl = reEl('div', 'fv-chart-box');
        this.formMessage = reEl('p', 're-alert');
        this.formMessage.hidden = true;
        dialog.append(this.titleEl, head, this._segmentTable(), this.summaryEl, this.chartEl,
            this.formMessage, this._footer());
        dialog.addEventListener('input', () => { this.dirty = true; });
        dialog.addEventListener('cancel', e => { e.preventDefault(); this._close(); });
        f.unit.addEventListener('change', () => { this._unitLabels(); this._retime(); });
        document.body.append(dialog);
        this.dialog = dialog;
    }

    _segmentTable() {
        const wrap = reEl('div', 'fv-segments');
        const table = reEl('table', 'fv-table');
        const head = table.createTHead().insertRow();
        this.headCells = ['#', 'Rate', 'To', 'Hold (min)', 'Note', 'Time', 'Elapsed', ''].map(label => {
            const th = reEl('th', null, label);
            head.append(th);
            return th;
        });
        this.rowsEl = table.createTBody();
        const add = reEl('button', 'btn btn-secondary fv-add', 'Add segment');
        add.type = 'button';
        add.addEventListener('click', () => {
            this._addRow({}).querySelector('input').focus();
            this.dirty = true;
        });
        const hint = reEl('p', 're-hint', 'Leave the rate blank for full speed. A target below the previous temperature is a controlled cool.');
        wrap.append(table, add, hint);
        return wrap;
    }

    _unitLabels() {
        const unit = this.f.unit.value;
        this.headCells[1].textContent = `Rate (°${unit}/hr)`;
        this.headCells[2].textContent = `To (°${unit})`;
    }

    _addRow(seg) {
        const tr = this.rowsEl.insertRow();
        const rate = this._input('fv-num', 'Full');
        rate.value = fvText(seg.rate);
        const target = this._input('fv-num');
        target.value = fvText(seg.target);
        const hold = this._input('fv-num', '0');
        hold.value = seg.hold ? String(seg.hold) : '';
        const note = this._input('fv-note', null, 'text');
        note.maxLength = 80;
        note.value = fvText(seg.note);
        const remove = reEl('button', 'tv-photo-remove fv-remove', '×');
        remove.type = 'button';
        remove.setAttribute('aria-label', 'Remove this segment');
        remove.addEventListener('click', () => {
            tr.remove();
            this.dirty = true;
            this._renumber();
            this._retime();
        });
        const cells = [reEl('span', 'fv-n'), rate, target, hold, note, reEl('span', 'fv-time'),
            reEl('span', 'fv-time'), remove];
        cells.forEach(cell => tr.insertCell().append(cell));
        [rate, target, hold].forEach(input => input.addEventListener('input', () => this._retime()));
        this._renumber();
        this._unitLabels();
        return tr;
    }

    _renumber() {
        [...this.rowsEl.rows].forEach((tr, i) => { tr.querySelector('.fv-n').textContent = String(i + 1); });
    }

    _segments() {
        return [...this.rowsEl.rows].map(tr => {
            const [rate, target, hold, note] = tr.querySelectorAll('input');
            return { rate: rate.value.trim() || null, target: target.value.trim(), hold: hold.value.trim() || 0, note: note.value.trim() };
        });
    }

    /** Time the segments after a pause in typing. */
    _retime(delay = 250) {
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this._timeNow(), delay);
    }

    /** Ask the server to time the segments now; true when they're valid. */
    async _timeNow() {
        clearTimeout(this.timer);
        const seq = ++this.timingSeq;
        const resp = await API.timeFiringSchedule({ unit: this.f.unit.value, segments: this._segments() });
        if (seq !== this.timingSeq) return false;
        this.timing = resp.ok ? resp.data : null;
        this._showTiming(resp.ok ? null : this._error(resp, 'The schedule could not be timed.'));
        return resp.ok;
    }

    _showTiming(problem) {
        const rows = [...this.rowsEl.rows];
        rows.forEach((tr, i) => {
            const seg = this.timing && this.timing.segments[i];
            const [time, elapsed] = tr.querySelectorAll('.fv-time');
            time.textContent = seg ? fvDuration(seg.ramp_minutes) : '';
            elapsed.textContent = seg ? fvDuration(seg.elapsed_minutes) : '';
            tr.classList.toggle('fv-cooling', !!seg && seg.direction === 'cool');
        });
        this.summaryEl.textContent = problem || fvSummary(this.timing, this.f.unit.value);
        this.summaryEl.classList.toggle('fv-problem', !!problem);
        this.chartEl.replaceChildren();
        if (this.timing) this.chartEl.append(fvChart(this.timing, this.f.unit.value));
    }

    _footer() {
        const footer = reEl('div', 'tv-footer');
        const button = (label, className, action) => {
            const b = reEl('button', `btn ${className}`, label);
            b.type = 'button';
            b.addEventListener('click', action);
            return b;
        };
        this.deleteBtn = button('Delete schedule', 'btn-secondary tv-delete', () => this._delete());
        this.saveBtn = button('Save', 'btn-primary', () => this._save());
        footer.append(this.deleteBtn, button('Print', 'btn-secondary', () => this._print()),
            button('Cancel', 'btn-secondary', () => this._close()), this.saveBtn);
        return footer;
    }

    async _save() {
        const data = {
            name: this.f.name.value.trim(), cone: this.f.cone.value.trim(), unit: this.f.unit.value,
            notes: this.f.notes.value.trim(), segments: this._segments(),
        };
        this.saveBtn.disabled = true;
        const resp = this.editing
            ? await API.updateFiringSchedule(this.editing.id, data)
            : await API.createFiringSchedule(data);
        this.saveBtn.disabled = false;
        if (!resp.ok) {
            this._message(this._error(resp, 'The schedule could not be saved.'), this.formMessage);
            return;
        }
        try { localStorage.setItem(FV_UNIT_KEY, data.unit); } catch (e) { /* private mode */ }
        this.dirty = false;
        this.dialog.close();
        await this._reload();
    }

    async _delete() {
        const n = this.editing.tile_count;
        let tiles = '';
        if (n === 1) tiles = ' 1 test tile uses it; it keeps its record but loses the link.';
        if (n > 1) tiles = ` ${n} test tiles use it; they keep their records but lose the link.`;
        if (!confirm(`Delete ${this.editing.name}?${tiles} This can’t be undone.`)) return;
        const resp = await API.deleteFiringSchedule(this.editing.id);
        if (!resp.ok) {
            this._message(this._error(resp, 'The schedule could not be deleted.'), this.formMessage);
            return;
        }
        this.dirty = false;
        this.dialog.close();
        await this._reload();
    }

    _close() {
        if (this.dirty && !confirm('Discard the changes to this schedule?')) return;
        clearTimeout(this.timer);
        this.dialog.close();
    }

    async _print() {
        if (!(await this._timeNow())) {
            this._message('Fix the segments before printing.', this.formMessage);
            return;
        }
        this._message(null, this.formMessage);
        printOnly(this._sheet());
    }

    /** The printable card for the kiln room. */
    _sheet() {
        const unit = this.f.unit.value;
        const sheet = reEl('article', 'bs-sheet fv-sheet');
        const facts = [this.f.cone.value.trim() ? `Cone ${this.f.cone.value.trim()}` : '', `°${unit}`,
            this.dirty ? 'Unsaved changes' : '',
            `Printed ${new Date().toLocaleDateString(undefined, { dateStyle: 'medium' })}`];
        sheet.append(reEl('h1', null, this.f.name.value.trim() || 'Untitled schedule'),
            reEl('p', 'bs-facts', facts.filter(Boolean).join(' · ')));
        const table = reEl('table', 'bs-table');
        const head = table.createTHead().insertRow();
        ['Seg', `Rate (°${unit}/hr)`, `To (°${unit})`, 'Hold (min)', 'Note', 'Elapsed'].forEach((label, i) => {
            head.append(reEl('th', i && i < 4 ? 'bs-num' : null, label));
        });
        const body = table.createTBody();
        this._segments().forEach((seg, i) => {
            const tr = body.insertRow();
            const timed = this.timing.segments[i];
            [String(i + 1), seg.rate || 'Full', seg.target, seg.hold || '—', seg.note,
                timed ? fvDuration(timed.elapsed_minutes) : ''].forEach((value, j) => {
                tr.append(reEl('td', j && j < 4 ? 'bs-num' : null, String(value)));
            });
        });
        sheet.append(table, reEl('p', 'bs-size fv-print-summary', fvSummary(this.timing, unit)),
            fvChart(this.timing, unit));
        if (this.f.notes.value.trim()) sheet.append(reEl('p', 'fv-print-notes', this.f.notes.value.trim()));
        return sheet;
    }
}

window.FiringView = FiringView;
