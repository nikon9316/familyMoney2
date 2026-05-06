(() => {
  'use strict';

  const DB_NAME = 'family-finance-offline-v541';
  const DB_VERSION = 2;
  const QUEUE = 'queue';
  const CACHE = 'cache';

  function openDb() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(QUEUE)) {
          const store = db.createObjectStore(QUEUE, { keyPath: 'id' });
          store.createIndex('status', 'status', { unique: false });
          store.createIndex('createdAt', 'createdAt', { unique: false });
        }
        if (!db.objectStoreNames.contains(CACHE)) db.createObjectStore(CACHE, { keyPath: 'key' });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error('Не удалось открыть IndexedDB'));
    });
  }

  async function txStore(storeName, mode, fn) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, mode);
      const store = tx.objectStore(storeName);
      let result;
      Promise.resolve(fn(store)).then((r) => { result = r; }).catch(reject);
      tx.oncomplete = () => { db.close(); resolve(result); };
      tx.onerror = () => { db.close(); reject(tx.error); };
    });
  }

  function reqAsPromise(req) {
    return new Promise((resolve, reject) => {
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function enqueue(item) {
    const record = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      createdAt: new Date().toISOString(),
      status: 'pending',
      attempts: 0,
      lastError: '',
      ...item,
    };
    await txStore(QUEUE, 'readwrite', (store) => store.put(record));
    window.dispatchEvent(new CustomEvent('ff-offline-queued', { detail: record }));
    return record;
  }

  async function all() {
    return txStore(QUEUE, 'readonly', (store) => reqAsPromise(store.getAll()));
  }

  async function pending() {
    const rows = await all();
    return rows.filter((x) => x.status === 'pending').sort((a, b) => String(a.createdAt).localeCompare(String(b.createdAt)));
  }

  async function conflicts() {
    const rows = await all();
    return rows.filter((x) => x.lastError && Number(x.attempts || 0) > 0).sort((a, b) => String(a.lastAttemptAt || a.createdAt).localeCompare(String(b.lastAttemptAt || b.createdAt)));
  }

  async function remove(id) {
    return txStore(QUEUE, 'readwrite', (store) => store.delete(id));
  }

  async function update(record) {
    return txStore(QUEUE, 'readwrite', (store) => store.put(record));
  }

  async function saveInit(payload) {
    if (!payload || payload.ok === false) return;
    await txStore(CACHE, 'readwrite', (store) => store.put({ key: 'api:init:last', savedAt: new Date().toISOString(), payload }));
  }

  async function getInit() {
    const row = await txStore(CACHE, 'readonly', (store) => reqAsPromise(store.get('api:init:last')));
    return row?.payload || null;
  }

  function isQueueable(method, path) {
    return ['POST', 'PUT', 'DELETE'].includes(method) && path.startsWith('/api/') && !path.startsWith('/api/admin') && !path.includes('/export') && !path.includes('/report.pdf');
  }

  async function sync({ authHeaders, toast, onDone } = {}) {
    if (!navigator.onLine) return { ok: false, synced: 0, left: (await pending()).length, offline: true };
    const rows = await pending();
    let synced = 0;
    for (const record of rows) {
      try {
        const headers = { ...(authHeaders ? authHeaders() : {}), 'Content-Type': 'application/json', 'X-Idempotency-Key': record.id };
        const response = await fetch(record.path, { method: record.method, headers, body: record.body === null || record.body === undefined ? undefined : JSON.stringify(record.body) });
        const contentType = response.headers.get('content-type') || '';
        const payload = contentType.includes('application/json') ? await response.json() : await response.text();
        if (!response.ok || payload?.ok === false) throw new Error(payload?.error || payload || `HTTP ${response.status}`);
        await remove(record.id);
        synced += 1;
      } catch (e) {
        record.attempts = (record.attempts || 0) + 1;
        record.lastError = String(e.message || e).slice(0, 500);
        record.lastAttemptAt = new Date().toISOString();
        await update(record);
      }
    }
    const left = (await pending()).length;
    if (synced && toast) toast(`Синхронизировано offline-операций: ${synced}`, 'ok');
    if (synced && onDone) await onDone();
    window.dispatchEvent(new CustomEvent('ff-offline-sync', { detail: { synced, left } }));
    return { ok: true, synced, left };
  }

  window.FFOffline = { enqueue, all, pending, conflicts, remove, update, sync, isQueueable, saveInit, getInit };
})();
