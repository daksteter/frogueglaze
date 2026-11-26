/**
 * TileView - test-tile records: a grid of tiles with their photos, and a
 * dialog to record or edit one.
 *
 * A tile tests one glaze and keeps the recipe as tested. Photos are shrunk
 * and re-encoded as JPEG in the browser before upload, which keeps them small
 * and drops the camera's location data. Uses reEl from RecipeEditor.js; text
 * reaches the page through textContent.
 */

const TV_ATMOSPHERES = ['oxidation', 'reduction', 'neutral', 'salt', 'wood'];
const TV_VERDICTS = [['keep', 'Keep'], ['retest', 'Retest'], ['reject', 'Reject']];
const TV_FIELDS = ['label', 'fired_on', 'cone', 'atmosphere', 'kiln', 'clay_body', 'application', 'result', 'verdict'];
const TV_MAX_EDGE = 2000;
const TV_MAX_PHOTOS = 20;
const TV_LAST_KEY = 'tiles.last';

function tvToday() {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 10);
}

function tvDate(iso) {
    if (!iso) return '';
    const d = new Date(`${iso.slice(0, 10)}T12:00:00`);
    return isNaN(d) ? iso : d.toLocaleDateString(undefined, { dateStyle: 'medium' });
}

function tvCap(text) {
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

function tvVerdictLabel(verdict) {
    const found = TV_VERDICTS.find(([value]) => value === verdict);
    return found ? found[1] : 'Not judged';
}

function tvError(resp, fallback) {
    return (resp.data && (resp.data.message || resp.data.error)) || fallback;
}

function tvLast() {
    try { return JSON.parse(localStorage.getItem(TV_LAST_KEY)) || {}; } catch (e) { return {}; }
}

function tvRemember(data) {
    const last = { kiln: data.kiln || '', clay_body: data.clay_body || '', schedule_id: data.schedule_id || null };
    try { localStorage.setItem(TV_LAST_KEY, JSON.stringify(last)); } catch (e) { /* private mode */ }
}

/** Shrink a photo to at most TV_MAX_EDGE pixels and re-encode it as JPEG. */
async function tvShrink(file) {
    let bitmap;
    try {
        bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
    } catch (e) {
        throw new Error(`Couldn't open ${file.name} as a photo. Try a JPEG or PNG.`);
    }
    const scale = Math.min(1, TV_MAX_EDGE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    if (bitmap.close) bitmap.close();
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85));
    if (!blob) throw new Error(`Couldn't prepare ${file.name} for upload.`);
    return blob;
}

class TileView {
    constructor({ getGlazes } = {}) {
        this.getGlazes = getGlazes || (() => []);
        this.tiles = [];
        this.glazeId = null;
        this.verdict = 'all';
        this.dialog = null;
        this.lightbox = null;
        this.queue = [];
        this.versionSeq = 0;
    }

    /** Show only this glaze's tiles (null for all) the next time the view renders. */
    showGlaze(glazeId) {
        this.glazeId = glazeId || null;
    }

    async render(container) {
        container.innerHTML = '';
        const root = reEl('div', 'tiles-view');
        this.messageEl = reEl('p', 're-alert');
        this.messageEl.hidden = true;
        this.gridEl = reEl('div', 'tv-grid');
        root.append(this._toolbar(), this.messageEl, this.gridEl);
        container.append(root);
        await this._reload();
    }

    async _reload() {
        const resp = await API.getTiles();
        this.tiles = resp.ok ? resp.data : [];
        this._message(resp.ok ? null : tvError(resp, 'Could not load the test tiles.'));
        this._renderGrid();
    }

    _glazes() {
        return [...this.getGlazes()].sort((a, b) => a.name.localeCompare(b.name));
    }

    _glaze(id) {
        return this.getGlazes().find(g => g.id === id) || null;
    }

    _message(text, el = this.messageEl) {
        if (!el) return;
        el.hidden = !text;
        el.textContent = text || '';
    }

    _toolbar() {
        const bar = reEl('div', 'tv-toolbar');
        const glazes = reEl('select', 'tv-filter');
        glazes.setAttribute('aria-label', 'Glaze');
        glazes.append(new Option('All glazes', ''), ...this._glazes().map(g => new Option(g.name, g.id)));
        glazes.value = this.glazeId || '';
        glazes.addEventListener('change', () => { this.glazeId = glazes.value || null; this._renderGrid(); });
        const verdicts = reEl('select', 'tv-filter');
        verdicts.setAttribute('aria-label', 'Verdict');
        verdicts.append(new Option('Any verdict', 'all'), ...TV_VERDICTS.map(([v, l]) => new Option(l, v)),
            new Option('Not judged', 'none'));
        verdicts.value = this.verdict;
        verdicts.addEventListener('change', () => { this.verdict = verdicts.value; this._renderGrid(); });
        const add = reEl('button', 'btn btn-primary', 'New tile');
        add.type = 'button';
        add.addEventListener('click', () => this.openTile(null));
        bar.append(reEl('h2', 're-heading', 'Test tiles'), glazes, verdicts, add);
        return bar;
    }

    _visible() {
        return this.tiles.filter(t => (!this.glazeId || t.glaze_id === this.glazeId)
            && (this.verdict === 'all' || (t.verdict || 'none') === this.verdict));
    }

    _renderGrid() {
        const tiles = this._visible();
        this.gridEl.replaceChildren(...tiles.map(tile => this._card(tile)));
        if (tiles.length) return;
        const glaze = this._glaze(this.glazeId);
        let text = 'No tiles match these filters.';
        if (!this.tiles.length) text = 'No test tiles yet. Record one with New tile.';
        else if (glaze && this.verdict === 'all') text = `No tiles for ${glaze.name} yet.`;
        this.gridEl.append(reEl('p', 'tv-empty', text));
    }

    _card(tile) {
        const card = reEl('button', 'card tv-card');
        card.type = 'button';
        card.addEventListener('click', () => this.openTile(tile));
        const thumb = reEl('div', 'tv-thumb');
        if (tile.photos.length) {
            const img = reEl('img');
            img.src = tile.photos[0].url;
            img.alt = '';
            img.loading = 'lazy';
            thumb.append(img);
            if (tile.photos.length > 1) thumb.append(reEl('span', 'tv-count', `${tile.photos.length} photos`));
        } else {
            const glaze = this._glaze(tile.glaze_id);
            if (glaze && /^#[0-9a-f]{3,8}$/i.test(glaze.hex || '')) thumb.style.backgroundColor = glaze.hex;
            thumb.append(reEl('span', 'tv-nophoto', 'No photo'));
        }
        const body = reEl('div', 'tv-card-body');
        const title = reEl('div', 'tv-card-title');
        title.append(reEl('span', 'tv-glaze', tile.glaze_name));
        if (tile.label) title.append(reEl('span', 'tv-label', tile.label));
        const facts = [tvDate(tile.fired_on), tile.cone ? `Cone ${tile.cone}` : '', tvCap(tile.atmosphere)];
        body.append(title, reEl('div', 'tv-facts', facts.filter(Boolean).join(' · ')));
        const firing = [tile.schedule_name, tile.clay_body].filter(Boolean).join(' · ');
        if (firing) body.append(reEl('div', 'tv-facts', firing));
        body.append(reEl('span', `tv-verdict tv-verdict-${tile.verdict || 'none'}`, tvVerdictLabel(tile.verdict)));
        card.append(thumb, body);
        return card;
    }

    // ---- The tile dialog ----

    async openTile(tile) {
        if (!this.dialog) this._buildDialog();
        this.editing = tile;
        this.versionTouched = false;
        this.dirty = false;
        this._fillForm(tile);
        await this._loadSchedules(tile);
        this.dialog.showModal();
        await this._loadVersions();
    }

    async _loadSchedules(tile) {
        const resp = await API.getFiringSchedules();
        this.schedules = resp.ok ? resp.data : [];
        this.f.schedule.replaceChildren(new Option('\u2014', ''), ...this.schedules.map(
            s => new Option(s.cone ? `${s.name} (cone ${s.cone})` : s.name, String(s.id))));
        const wanted = tile ? tile.schedule_id : tvLast().schedule_id;
        const known = this.schedules.find(s => s.id === wanted);
        this.f.schedule.value = known ? String(known.id) : '';
        if (!tile && known && !this.f.cone.value) this.f.cone.value = known.cone || '';
    }

    _scheduleChanged() {
        const schedule = (this.schedules || []).find(s => String(s.id) === this.f.schedule.value);
        if (schedule && schedule.cone && !this.f.cone.value) this.f.cone.value = schedule.cone;
    }

    _field(label, input, className = 'tv-field') {
        const wrap = reEl('label', className);
        wrap.append(reEl('span', 'tv-field-label', label), input);
        return wrap;
    }

    _input(name, placeholder, list) {
        const input = reEl('input');
        input.type = name === 'fired_on' ? 'date' : 'text';
        input.maxLength = 120;
        if (placeholder) input.placeholder = placeholder;
        if (list) input.setAttribute('list', list);
        return input;
    }

    _select(options) {
        const select = reEl('select');
        options.forEach(([value, label]) => select.append(new Option(label, value)));
        return select;
    }

    _buildDialog() {
        const f = {};
        f.glaze = reEl('select');
        f.version = reEl('select');
        f.recipe = reEl('p', 'tv-recipe');
        f.label = this._input('label', 'What’s written on the tile');
        f.fired_on = this._input('fired_on');
        f.cone = this._input('cone', 'e.g. 6');
        f.atmosphere = this._select([['', '—'], ...TV_ATMOSPHERES.map(a => [a, tvCap(a)])]);
        f.schedule = reEl('select');
        f.kiln = this._input('kiln', 'Which kiln, where in it', 'tv-kilns');
        f.clay_body = this._input('clay_body', 'e.g. B-Mix', 'tv-clays');
        f.application = this._input('application', 'e.g. 2 dips, 3 s; SG 1.45');
        f.result = reEl('textarea');
        f.result.rows = 4;
        f.result.maxLength = 4000;
        f.result.placeholder = 'Surface, colour, faults, how it broke over texture…';
        f.verdict = this._select([['', 'Not judged'], ...TV_VERDICTS]);
        f.photos = reEl('div', 'tv-photos');
        this.f = f;
        this.datalists = [reEl('datalist'), reEl('datalist')];
        this.datalists[0].id = 'tv-kilns';
        this.datalists[1].id = 'tv-clays';

        const dialog = reEl('dialog', 'tv-dialog');
        dialog.setAttribute('aria-label', 'Test tile');
        this.titleEl = reEl('h2', 're-heading');
        const grid = reEl('div', 'tv-form');
        grid.append(
            this._field('Glaze', f.glaze, 'tv-field tv-wide'),
            this._field('Recipe tested', f.version, 'tv-field tv-wide'), f.recipe,
            this._field('Tile label', f.label), this._field('Date fired', f.fired_on),
            this._field('Firing schedule', f.schedule), this._field('Cone', f.cone),
            this._field('Atmosphere', f.atmosphere), this._field('Kiln', f.kiln),
            this._field('Clay body', f.clay_body), this._field('Verdict', f.verdict),
            this._field('Application', f.application, 'tv-field tv-wide'),
            this._field('Result', f.result, 'tv-field tv-wide'),
        );
        this.formMessage = reEl('p', 're-alert');
        this.formMessage.hidden = true;
        dialog.append(this.titleEl, grid, this._photoSection(), this.formMessage, this._footer(), ...this.datalists);
        dialog.addEventListener('input', () => { this.dirty = true; });
        dialog.addEventListener('cancel', e => { e.preventDefault(); this._close(); });
        f.glaze.addEventListener('change', () => this._glazeChanged());
        f.schedule.addEventListener('change', () => this._scheduleChanged());
        f.version.addEventListener('change', () => { this.versionTouched = true; this._showRecipe(); });
        document.body.append(dialog);
        this.dialog = dialog;
    }

    _photoSection() {
        const section = reEl('div', 'tv-photo-section');
        const head = reEl('div', 'tv-photo-head');
        const picker = reEl('input');
        picker.type = 'file';
        picker.accept = 'image/*';
        picker.multiple = true;
        picker.hidden = true;
        picker.addEventListener('change', async () => {
            const files = [...picker.files];
            picker.value = '';
            await this._addFiles(files);
        });
        const add = reEl('button', 'btn btn-secondary', 'Add photos');
        add.type = 'button';
        add.addEventListener('click', () => picker.click());
        head.append(reEl('span', 'tv-field-label', 'Photos'), add, picker);
        section.append(head, this.f.photos);
        return section;
    }

    _footer() {
        const footer = reEl('div', 'tv-footer');
        this.deleteBtn = reEl('button', 'btn btn-secondary tv-delete', 'Delete tile');
        this.deleteBtn.type = 'button';
        this.deleteBtn.addEventListener('click', () => this._deleteTile());
        const cancel = reEl('button', 'btn btn-secondary', 'Cancel');
        cancel.type = 'button';
        cancel.addEventListener('click', () => this._close());
        this.saveBtn = reEl('button', 'btn btn-primary', 'Save');
        this.saveBtn.type = 'button';
        this.saveBtn.addEventListener('click', () => this._save());
        footer.append(this.deleteBtn, cancel, this.saveBtn);
        return footer;
    }

    _fillForm(tile) {
        const f = this.f;
        f.glaze.replaceChildren(new Option('Choose a glaze…', ''),
            ...this._glazes().map(g => new Option(g.name, g.id)));
        const glaze = this._glaze(tile ? tile.glaze_id : this.glazeId);
        const last = tvLast();
        const values = tile || {
            fired_on: tvToday(), cone: glaze && glaze.cone, atmosphere: glaze && glaze.atmosphere,
            kiln: last.kiln, clay_body: last.clay_body,
        };
        f.glaze.value = glaze ? glaze.id : '';
        TV_FIELDS.forEach(name => { f[name].value = values[name] || ''; });
        this.titleEl.textContent = tile ? 'Test tile' : 'New test tile';
        this.deleteBtn.hidden = !tile;
        this._fillSuggestions();
        this._renderPhotos();
        this._message(null, this.formMessage);
    }

    _fillSuggestions() {
        ['kiln', 'clay_body'].forEach((name, i) => {
            const values = [...new Set(this.tiles.map(t => t[name]).filter(Boolean))].sort();
            this.datalists[i].replaceChildren(...values.map(v => new Option(v)));
        });
    }

    _glazeChanged() {
        this.versionTouched = true;
        const glaze = this._glaze(this.f.glaze.value);
        if (glaze && !this.f.cone.value) this.f.cone.value = glaze.cone || '';
        if (glaze && !this.f.atmosphere.value) this.f.atmosphere.value = glaze.atmosphere || '';
        this._loadVersions();
    }

    async _loadVersions() {
        const seq = ++this.versionSeq;
        const glazeId = this.f.glaze.value;
        const resp = glazeId ? await API.getRecipeVersions(glazeId) : { ok: false };
        if (seq !== this.versionSeq) return;
        this.versions = resp.ok ? resp.data : [];
        const keep = this.editing && !this.versionTouched;
        const select = this.f.version;
        select.replaceChildren();
        if (keep && !this.editing.version_id) select.append(new Option('As recorded', 'recorded'));
        select.append(new Option('Current recipe', ''));
        this.versions.forEach((v, i) => {
            const text = [`Version ${this.versions.length - i}`, tvDate(v.created_at), v.note].filter(Boolean);
            select.append(new Option(text.join(' · '), String(v.id)));
        });
        select.value = keep ? String(this.editing.version_id || 'recorded') : '';
        this._showRecipe();
    }

    _showRecipe() {
        const value = this.f.version.value;
        let recipe = (this._glaze(this.f.glaze.value) || {}).recipe;
        if (value === 'recorded') recipe = this.editing.recipe;
        else if (value) recipe = ((this.versions || []).find(v => String(v.id) === value) || {}).recipe;
        this.f.recipe.textContent = recipe || 'No recipe recorded.';
    }

    _renderPhotos() {
        const saved = this.editing ? this.editing.photos : [];
        this.f.photos.replaceChildren(
            ...saved.map(photo => this._thumb(photo.url, () => this._deletePhoto(photo), false)),
            ...this.queue.map(item => this._thumb(item.url, () => this._unqueue(item), true)),
        );
        if (!saved.length && !this.queue.length) this.f.photos.append(reEl('p', 're-hint', 'No photos yet.'));
    }

    _thumb(url, onRemove, pending) {
        const item = reEl('div', pending ? 'tv-photo tv-pending' : 'tv-photo');
        const img = reEl('img');
        img.src = url;
        img.alt = 'Tile photo';
        img.addEventListener('click', () => this._enlarge(url));
        const remove = reEl('button', 'tv-photo-remove', '×');
        remove.type = 'button';
        remove.setAttribute('aria-label', pending ? 'Remove this photo' : 'Delete this photo');
        remove.addEventListener('click', onRemove);
        item.append(img, remove);
        if (pending) item.append(reEl('span', 'tv-photo-note', 'Not saved yet'));
        return item;
    }

    async _addFiles(files) {
        const room = TV_MAX_PHOTOS - (this.editing ? this.editing.photos.length : 0) - this.queue.length;
        if (files.length > room) {
            this._message(`A tile can have at most ${TV_MAX_PHOTOS} photos.`, this.formMessage);
            files = files.slice(0, Math.max(0, room));
        }
        for (const file of files) {
            try {
                const blob = await tvShrink(file);
                this.queue.push({ blob, url: URL.createObjectURL(blob) });
                this.dirty = true;
            } catch (e) {
                this._message(e.message, this.formMessage);
            }
        }
        this._renderPhotos();
    }

    _unqueue(item) {
        URL.revokeObjectURL(item.url);
        this.queue = this.queue.filter(other => other !== item);
        this._renderPhotos();
    }

    _clearQueue() {
        this.queue.forEach(item => URL.revokeObjectURL(item.url));
        this.queue = [];
    }

    async _deletePhoto(photo) {
        if (!confirm('Delete this photo? This can’t be undone.')) return;
        const resp = await API.deleteTilePhoto(this.editing.id, photo.id);
        if (!resp.ok) {
            this._message(tvError(resp, 'The photo could not be deleted.'), this.formMessage);
            return;
        }
        this.editing.photos = this.editing.photos.filter(p => p.id !== photo.id);
        this._renderPhotos();
        this._renderGrid();
    }

    _formData() {
        const f = this.f;
        const data = {};
        TV_FIELDS.forEach(name => { data[name] = f[name].value.trim(); });
        data.schedule_id = f.schedule.value ? Number(f.schedule.value) : null;
        const glazeChanged = !this.editing || f.glaze.value !== this.editing.glaze_id;
        if (glazeChanged) data.glaze_id = f.glaze.value;
        const version = f.version.value;
        if (version !== 'recorded' && (glazeChanged || this.versionTouched)) {
            data.version_id = version ? Number(version) : null;
        }
        return data;
    }

    async _save() {
        if (!this.f.glaze.value) {
            this._message('Choose the glaze this tile tests.', this.formMessage);
            return;
        }
        const data = this._formData();
        this.saveBtn.disabled = true;
        const resp = this.editing ? await API.updateTile(this.editing.id, data) : await API.createTile(data);
        if (!resp.ok) {
            this.saveBtn.disabled = false;
            this._message(tvError(resp, 'The tile could not be saved.'), this.formMessage);
            return;
        }
        tvRemember(data);
        this.editing = resp.data;
        const failed = await this._uploadQueue();
        this.saveBtn.disabled = false;
        await this._reload();
        if (!failed) {
            this.dirty = false;
            this.dialog.close();
            return;
        }
        // The tile is saved; keep the dialog open on it with the photos that didn't go
        this.editing = this.tiles.find(t => t.id === this.editing.id) || this.editing;
        this.versionTouched = false;
        this._fillForm(this.editing);
        this._message(failed, this.formMessage);
        await this._loadVersions();
    }

    async _uploadQueue() {
        let failed = null;
        for (const item of [...this.queue]) {
            const resp = await API.addTilePhoto(this.editing.id, item.blob);
            if (resp.ok) {
                this.editing.photos.push(resp.data);
                this._unqueue(item);
            } else {
                failed = failed || tvError(resp, 'A photo could not be uploaded.');
            }
        }
        return failed;
    }

    async _deleteTile() {
        if (!this.editing || !confirm('Delete this test tile and its photos? This can’t be undone.')) return;
        const resp = await API.deleteTile(this.editing.id);
        if (!resp.ok) {
            this._message(tvError(resp, 'The tile could not be deleted.'), this.formMessage);
            return;
        }
        this._clearQueue();
        this.dialog.close();
        await this._reload();
    }

    _close() {
        if ((this.dirty || this.queue.length) && !confirm('Discard the changes to this tile?')) return;
        this._clearQueue();
        this.dialog.close();
    }

    _enlarge(url) {
        if (!this.lightbox) {
            this.lightbox = reEl('dialog', 'tv-lightbox');
            this.lightbox.setAttribute('aria-label', 'Tile photo');
            this.lightboxImg = reEl('img');
            this.lightboxImg.alt = 'Tile photo';
            const close = reEl('button', 'tv-lightbox-close', '×');
            close.type = 'button';
            close.setAttribute('aria-label', 'Close');
            this.lightbox.append(this.lightboxImg, close);
            this.lightbox.addEventListener('click', () => this.lightbox.close());
            document.body.append(this.lightbox);
        }
        this.lightboxImg.src = url;
        this.lightbox.showModal();
    }
}

window.TileView = TileView;
