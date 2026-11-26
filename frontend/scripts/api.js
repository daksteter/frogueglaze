/**
 * OpenGlaze API Client
 */

const API = {
    _baseUrl: '/api',
    _token: localStorage.getItem('simple_auth_token') || null,

    setToken(token) {
        this._token = token;
        localStorage.setItem('simple_auth_token', token);
    },

    _headers() {
        const h = { 'Content-Type': 'application/json' };
        if (this._token) {
            h['Authorization'] = `Bearer ${this._token}`;
        }
        return h;
    },

    async _fetch(path, options = {}) {
        try {
            const resp = await fetch(this._baseUrl + path, {
                headers: this._headers(),
                ...options,
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            return await resp.json();
        } catch (e) {
            console.warn(`API ${path} failed, using fallback:`, e.message);
            return null;
        }
    },

    // Like _fetch, but returns {ok, status, data} so callers can show the
    // server's error message instead of a silent null.
    async _send(path, method = 'GET', body) {
        try {
            const resp = await fetch(this._baseUrl + path, {
                method,
                headers: this._headers(),
                body: body === undefined ? undefined : JSON.stringify(body),
            });
            const data = await resp.json().catch(() => null);
            return { ok: resp.ok, status: resp.status, data };
        } catch (e) {
            return { ok: false, status: 0, data: { error: `Network error: ${e.message}` } };
        }
    },

    // ---- Recipe editor ----

    getMaterials() {
        return this._send('/chemistry/materials');
    },

    calculateUMF(recipe, cone) {
        return this._send('/chemistry/umf', 'POST', { recipe, cone });
    },

    compareRecipes(recipeA, recipeB, cone) {
        return this._send('/chemistry/compare', 'POST', { recipe_a: recipeA, recipe_b: recipeB, cone });
    },

    getRecipeVersions(glazeId) {
        return this._send(`/glazes/${encodeURIComponent(glazeId)}/versions`);
    },

    saveRecipeVersion(glazeId, data) {
        return this._send(`/glazes/${encodeURIComponent(glazeId)}/versions`, 'POST', data);
    },

    createGlaze(data) {
        return this._send('/glazes', 'POST', data);
    },

    // ---- Materials ----

    getMaterialsLibrary() {
        return this._send('/materials');
    },

    createStudioMaterial(data) {
        return this._send('/materials', 'POST', data);
    },

    updateStudioMaterial(key, data) {
        return this._send(`/materials/${encodeURIComponent(key)}`, 'PUT', data);
    },

    deleteStudioMaterial(key) {
        return this._send(`/materials/${encodeURIComponent(key)}`, 'DELETE');
    },

    getMaterialLots(key) {
        return this._send(`/materials/${encodeURIComponent(key)}/lots`);
    },

    addMaterialLot(key, data) {
        return this._send(`/materials/${encodeURIComponent(key)}/lots`, 'POST', data);
    },

    setCurrentLot(key, lotId) {
        return this._send(`/materials/${encodeURIComponent(key)}/current-lot`, 'PUT', { lot_id: lotId });
    },

    deleteMaterialLot(key, lotId) {
        return this._send(`/materials/${encodeURIComponent(key)}/lots/${lotId}`, 'DELETE');
    },

    makeBatchSheet(data) {
        return this._send('/batch-sheet', 'POST', data);
    },

    // ---- Test tiles ----

    getTiles() {
        return this._send('/tiles');
    },

    createTile(data) {
        return this._send('/tiles', 'POST', data);
    },

    updateTile(tileId, data) {
        return this._send(`/tiles/${encodeURIComponent(tileId)}`, 'PUT', data);
    },

    deleteTile(tileId) {
        return this._send(`/tiles/${encodeURIComponent(tileId)}`, 'DELETE');
    },

    // Multipart upload: the browser sets the Content-Type with its boundary
    async addTilePhoto(tileId, blob) {
        const form = new FormData();
        form.append('photo', blob, 'tile.jpg');
        const headers = this._token ? { Authorization: `Bearer ${this._token}` } : {};
        try {
            const resp = await fetch(`${this._baseUrl}/tiles/${encodeURIComponent(tileId)}/photos`, {
                method: 'POST', headers, body: form,
            });
            const data = await resp.json().catch(() => null);
            return { ok: resp.ok, status: resp.status, data };
        } catch (e) {
            return { ok: false, status: 0, data: { error: `Network error: ${e.message}` } };
        }
    },

    deleteTilePhoto(tileId, photoId) {
        return this._send(`/tiles/${encodeURIComponent(tileId)}/photos/${encodeURIComponent(photoId)}`, 'DELETE');
    },

    // ---- Firing schedules ----

    getFiringSchedules() {
        return this._send('/firing-schedules');
    },

    createFiringSchedule(data) {
        return this._send('/firing-schedules', 'POST', data);
    },

    updateFiringSchedule(scheduleId, data) {
        return this._send(`/firing-schedules/${encodeURIComponent(scheduleId)}`, 'PUT', data);
    },

    deleteFiringSchedule(scheduleId) {
        return this._send(`/firing-schedules/${encodeURIComponent(scheduleId)}`, 'DELETE');
    },

    timeFiringSchedule(data) {
        return this._send('/firing-schedules/timing', 'POST', data);
    },

    // ---- Insight-Live import ----

    previewInsightLiveImport(csv) {
        return this._send('/import/insight-live/preview', 'POST', { csv });
    },

    importInsightLive(data) {
        return this._send('/import/insight-live', 'POST', data);
    },

    // ---- Existing ----

    async getGlazes() {
        const result = await this._fetch('/glazes');
        return (result || []).map(g => ({
            ...g,
            // API families are singular lowercase; the UI filters and groups
            // by the plural title-case keys in FAMILY_ORDER.
            family: normalizeFamily(g.family),
        }));
    },

    async getCombinations() {
        const result = await this._fetch('/combinations');
        if (result && result.length > 0) {
            return result.map(c => ({
                ...c,
                stage: c.stage || 'idea',
                prediction_grade: c.prediction_grade || 'unknown',
            }));
        }
        return [];
    },

    async createCombination(data) {
        const result = await this._fetch('/combinations', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        return result;
    },

    async updateCombination(id, updates) {
        return await this._fetch(`/combinations/${id}`, {
            method: 'PUT',
            body: JSON.stringify(updates),
        });
    },

    async simulateCombination(id) {
        return await this._fetch(`/combinations/${id}/simulate`, {
            method: 'POST',
        });
    },

    // ---- Simple Auth ----

    async simpleLogin(displayName) {
        return await this._fetch('/auth/simple-login', {
            method: 'POST',
            body: JSON.stringify({ display_name: displayName }),
        });
    },

    async getMe() {
        return await this._fetch('/auth/me');
    },

    // ---- Studios ----

    async createStudio(name, displayName) {
        return await this._fetch('/studios', {
            method: 'POST',
            body: JSON.stringify({ name, display_name: displayName }),
        });
    },

    async joinStudio(inviteCode, displayName) {
        return await this._fetch('/studios/join', {
            method: 'POST',
            body: JSON.stringify({ invite_code: inviteCode, display_name: displayName }),
        });
    },

    async getStudios() {
        return await this._fetch('/studios');
    },

    async getStudioDetail(studioId) {
        return await this._fetch(`/studios/${studioId}`);
    },

    // ---- Lab Queue ----

    async getLabQueue(studioId) {
        return await this._fetch(`/studios/${studioId}/lab-queue`);
    },

    async claimCombo(studioId, comboId) {
        return await this._fetch(`/studios/${studioId}/lab-queue/${comboId}/claim`, {
            method: 'POST',
        });
    },

    async releaseCombo(studioId, comboId) {
        return await this._fetch(`/studios/${studioId}/lab-queue/${comboId}/release`, {
            method: 'POST',
        });
    },

    // ---- Firing Log ----

    async logFiringResult(expId, logData) {
        return await this._fetch(`/experiments/${expId}/firing-log`, {
            method: 'POST',
            body: JSON.stringify(logData),
        });
    },

    async shareExperiment(expId, studioId) {
        return await this._fetch(`/experiments/${expId}/share`, {
            method: 'POST',
            body: JSON.stringify({ studio_id: studioId }),
        });
    },

    async getStudioExperiments(studioId) {
        return await this._fetch(`/studios/${studioId}/experiments`);
    },
};

window.API = API;
