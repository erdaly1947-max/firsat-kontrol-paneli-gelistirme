const MAX_COMPRESSED_BYTES = 8 * 1024 * 1024;
const MAX_ZIP_BYTES = 8 * 1024 * 1024;
const MAX_IMAGE_BYTES = 15 * 1024 * 1024;
const MAX_IMAGE_CONTROL_BYTES = 64 * 1024;
const IMAGE_MANIFEST_KEY = "meta/active-images.json";
const IMAGE_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const IMAGE_TYPES = new Set(["image/png", "image/jpeg"]);
const ORPHAN_IMAGE_GRACE_MS = 10 * 60 * 1000;
const STALE_STAGE_GRACE_MS = 60 * 60 * 1000;
const REPORT_KEYS = Object.freeze({
  analysis: "latest",
  daily: "daily_latest",
  troubleshooting: "troubleshooting_latest",
  troubleshootingZip: "troubleshooting_zip_latest",
});
const JSON_REPORT_ROUTES = Object.freeze({
  "/api/report": { kind: "analysis", key: REPORT_KEYS.analysis, readPath: "/latest" },
  "/api/report/daily": { kind: "daily", key: REPORT_KEYS.daily, readPath: "/daily" },
  "/api/report/troubleshooting": { kind: "troubleshooting", key: REPORT_KEYS.troubleshooting, readPath: "/troubleshooting" },
});
const JSON_READ_ROUTES = Object.freeze({
  "/latest": { kind: "analysis", key: REPORT_KEYS.analysis },
  "/daily": { kind: "daily", key: REPORT_KEYS.daily },
  "/troubleshooting": { kind: "troubleshooting", key: REPORT_KEYS.troubleshooting },
});

function jsonResponse(payload, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store, max-age=0",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type, Content-Encoding, X-Image-Name-B64",
      "X-Content-Type-Options": "nosniff",
      ...extraHeaders,
    },
  });
}

function tokenMatches(provided, expected) {
  if (typeof provided !== "string" || typeof expected !== "string" || !expected) return false;
  let mismatch = provided.length ^ expected.length;
  const max = Math.max(provided.length, expected.length);
  for (let i = 0; i < max; i += 1) {
    mismatch |= (provided.charCodeAt(i) || 0) ^ (expected.charCodeAt(i) || 0);
  }
  return mismatch === 0;
}

async function sha256Hex(buffer) {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function readGzipJson(compressed) {
  const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream("gzip"));
  const text = await new Response(stream).text();
  return JSON.parse(text);
}

function requestTokenIsValid(request, env) {
  const authorization = request.headers.get("Authorization") || "";
  const provided = authorization.startsWith("Bearer ") ? authorization.slice(7) : "";
  return tokenMatches(provided, env.UPLOAD_TOKEN);
}

function validJsonReport(report, kind) {
  if (!report || report.report_type !== kind || report.schema_version !== 1) return false;
  if (kind === "analysis") {
    return Array.isArray(report.candidates) && report.candidate_count === report.candidates.length;
  }
  if (kind === "daily") {
    return typeof report.report_generated_at_utc === "string" &&
      report.payload && typeof report.payload === "object" &&
      report.payload.state && typeof report.payload.state === "object" &&
      report.payload.diagnostics && typeof report.payload.diagnostics === "object";
  }
  if (kind === "troubleshooting") {
    return typeof report.generated_at_utc === "string" &&
      report.daily_report && typeof report.daily_report === "object" &&
      report.diagnostics && typeof report.diagnostics === "object" &&
      Array.isArray(report.manifest?.files) && typeof report.log_tail === "string";
  }
  return false;
}

function isImageId(value) {
  return typeof value === "string" && IMAGE_ID_PATTERN.test(value);
}

function imageSignatureMatches(bytes, contentType) {
  if (!(bytes instanceof Uint8Array)) return false;
  if (contentType === "image/png") {
    const signature = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
    return bytes.length >= 8 && signature.every((value, index) => bytes[index] === value);
  }
  return contentType === "image/jpeg" && bytes.length >= 3 &&
    bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
}

function validImageFilename(filename, contentType) {
  if (typeof filename !== "string" || !filename || filename.length > 255 ||
      filename.includes("/") || filename.includes("\\") ||
      /[\u0000-\u001f\u007f]/u.test(filename) || filename === "." || filename === "..") return false;
  const name = filename.toLowerCase();
  if (contentType === "image/png") return name.endsWith(".png");
  return contentType === "image/jpeg" && (name.endsWith(".jpg") || name.endsWith(".jpeg"));
}

function decodeImageFilename(value) {
  if (typeof value !== "string" || value.length < 1 || value.length > 2048 ||
      !/^[A-Za-z0-9_-]+$/.test(value)) return null;
  try {
    const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
    const binary = atob(base64 + "=".repeat((4 - base64.length % 4) % 4));
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
}

function validManifestImage(image) {
  return Boolean(image && typeof image === "object" && isImageId(image.id) &&
    IMAGE_TYPES.has(image.content_type) && validImageFilename(image.filename, image.content_type) &&
    Number.isSafeInteger(image.size_bytes) && image.size_bytes > 0 && image.size_bytes <= MAX_IMAGE_BYTES &&
    typeof image.uploaded_at === "string" && Number.isFinite(Date.parse(image.uploaded_at)));
}

async function readActiveImageManifest(env) {
  const object = await env.IMAGES_BUCKET.get(IMAGE_MANIFEST_KEY);
  if (!object) return { exists: false, etag: null, images: [], cleanupIds: [] };
  let parsed;
  try {
    parsed = JSON.parse(await object.text());
  } catch {
    throw new Error("Etkin görüntü manifesti okunamıyor.");
  }
  const activeIds = Array.isArray(parsed?.images) ? parsed.images.map((image) => image?.id) : [];
  const cleanupIds = parsed?.cleanup_ids === undefined ? [] : parsed.cleanup_ids;
  if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.images) || parsed.images.length > 3 ||
      !parsed.images.every(validManifestImage) || new Set(activeIds).size !== activeIds.length ||
      !Array.isArray(cleanupIds) || cleanupIds.some((id) => !isImageId(id)) ||
      new Set(cleanupIds).size !== cleanupIds.length ||
      cleanupIds.some((id) => activeIds.includes(id))) {
    throw new Error("Etkin görüntü manifesti geçersiz.");
  }
  return {
    exists: true,
    etag: object.etag,
    images: [...parsed.images].sort((a, b) => Date.parse(b.uploaded_at) - Date.parse(a.uploaded_at)),
    cleanupIds,
  };
}

async function readBoundedImageBytes(request, maxBytes) {
  const declared = request.headers.get("Content-Length");
  if (declared !== null) {
    if (!/^\d+$/.test(declared)) {
      const error = new Error("Content-Length geçersiz.");
      error.status = 400;
      throw error;
    }
    if (Number(declared) > maxBytes) {
      const error = new Error("Görüntü boyut sınırını aşıyor.");
      error.status = 413;
      throw error;
    }
  }
  if (!request.body) {
    const error = new Error("İstek gövdesi boş.");
    error.status = 400;
    throw error;
  }
  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maxBytes) {
        try { await reader.cancel(); } catch { /* request is already oversized */ }
        const error = new Error("Görüntü boyut sınırını aşıyor.");
        error.status = 413;
        throw error;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  if (!total) {
    const error = new Error("İstek gövdesi boş.");
    error.status = 400;
    throw error;
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}

async function readBoundedImageJson(request) {
  const bytes = await readBoundedImageBytes(request, MAX_IMAGE_CONTROL_BYTES);
  try {
    const payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new Error("Nesne bekleniyor.");
    return payload;
  } catch {
    const error = new Error("Görüntü işlem JSON'u geçersiz.");
    error.status = 400;
    throw error;
  }
}

async function deleteKeysBestEffort(bucket, keys) {
  if (!keys.length) return;
  try {
    await bucket.delete(keys);
  } catch {
    // Inactive objects are retried by a later cleanup pass.
  }
}

async function cleanupPendingImageDeletes(env) {
  let manifest;
  try {
    manifest = await readActiveImageManifest(env);
  } catch {
    return;
  }
  if (!manifest.exists || !manifest.cleanupIds.length) return;
  const pending = [];
  for (const id of manifest.cleanupIds) {
    try {
      await env.IMAGES_BUCKET.delete("images/" + id);
    } catch {
      pending.push(id);
    }
  }
  if (pending.length === manifest.cleanupIds.length) return;
  try {
    await env.IMAGES_BUCKET.put(IMAGE_MANIFEST_KEY, JSON.stringify({
      version: 1,
      updated_at: new Date().toISOString(),
      images: manifest.images,
      cleanup_ids: pending,
    }), {
      onlyIf: { etagMatches: manifest.etag },
      httpMetadata: { contentType: "application/json; charset=utf-8", cacheControl: "no-store" },
    });
  } catch {
    // Successful deletes may remain queued; the next retry is idempotent.
  }
}

async function cleanupStaleImageObjects(env, activeImages) {
  const activeIds = new Set(activeImages.map((image) => image.id));
  const now = Date.now();
  try {
    const page = await env.IMAGES_BUCKET.list({ prefix: "images/", limit: 1000 });
    const stale = (page.objects || []).filter((object) => {
      const id = object.key.slice("images/".length);
      const uploaded = object.uploaded instanceof Date ? object.uploaded.getTime() : Date.parse(object.uploaded);
      return !activeIds.has(id) && Number.isFinite(uploaded) && now - uploaded >= ORPHAN_IMAGE_GRACE_MS;
    }).map((object) => object.key);
    await deleteKeysBestEffort(env.IMAGES_BUCKET, stale);
  } catch {
    // Cleanup failure does not affect active images and is retried later.
  }
  try {
    const page = await env.IMAGES_BUCKET.list({ prefix: "staging/", limit: 1000 });
    const stale = (page.objects || []).filter((object) => {
      const uploadedAt = object.customMetadata?.uploadedAt;
      const uploaded = uploadedAt ? Date.parse(uploadedAt) :
        (object.uploaded instanceof Date ? object.uploaded.getTime() : Date.parse(object.uploaded));
      return Number.isFinite(uploaded) && now - uploaded >= STALE_STAGE_GRACE_MS;
    }).map((object) => object.key);
    await deleteKeysBestEffort(env.IMAGES_BUCKET, stale);
  } catch {
    // Expired staging objects are retried later.
  }
}

async function deleteUncommittedImageObjects(env, ids) {
  let activeIds;
  try {
    activeIds = new Set((await readActiveImageManifest(env)).images.map((image) => image.id));
  } catch {
    // Preserve data if the active manifest cannot be read safely.
    return;
  }
  await deleteKeysBestEffort(env.IMAGES_BUCKET, ids.filter((id) => !activeIds.has(id)).map((id) => "images/" + id));
}

async function handleImageStage(request, env) {
  if (!env.IMAGES_BUCKET) return jsonResponse({ ok: false, error: "R2 görüntü deposu yapılandırılmamış." }, 503);
  if (!requestTokenIsValid(request, env)) return jsonResponse({ ok: false, error: "Yetkisiz görüntü yüklemesi." }, 401);
  await cleanupPendingImageDeletes(env);
  if ((request.headers.get("Content-Encoding") || "").trim()) {
    return jsonResponse({ ok: false, error: "Görüntüler ayrıca sıkıştırılmamalıdır." }, 415);
  }
  const contentType = (request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  if (!IMAGE_TYPES.has(contentType)) {
    return jsonResponse({ ok: false, error: "Yalnızca PNG veya JPEG görüntüleri kabul edilir." }, 415);
  }
  const filename = decodeImageFilename(request.headers.get("X-Image-Name-B64") || "");
  if (!filename || !validImageFilename(filename, contentType)) {
    return jsonResponse({ ok: false, error: "Dosya adı veya uzantısı içerik türüyle eşleşmiyor." }, 400);
  }
  let bytes;
  try {
    bytes = await readBoundedImageBytes(request, MAX_IMAGE_BYTES);
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message }, error.status || 400);
  }
  if (!imageSignatureMatches(bytes, contentType)) {
    return jsonResponse({ ok: false, error: "Dosya imzası PNG/JPEG içerik türüyle eşleşmiyor." }, 400);
  }
  const id = crypto.randomUUID().toLowerCase();
  const uploadedAt = new Date().toISOString();
  try {
    await env.IMAGES_BUCKET.put("staging/" + id, bytes, {
      httpMetadata: { contentType, cacheControl: "no-store" },
      customMetadata: { purpose: "image-stage", filename, contentType, sizeBytes: String(bytes.length), uploadedAt },
    });
  } catch {
    return jsonResponse({ ok: false, error: "Görüntü geçici olarak depolanamadı." }, 502);
  }
  return jsonResponse({ ok: true, staged_id: id, filename, content_type: contentType,
    size_bytes: bytes.length, uploaded_at: uploadedAt }, 201);
}

async function handleImageAbort(request, env) {
  if (!env.IMAGES_BUCKET) return jsonResponse({ ok: false, error: "R2 görüntü deposu yapılandırılmamış." }, 503);
  if (!requestTokenIsValid(request, env)) return jsonResponse({ ok: false, error: "Yetkisiz görüntü işlemi." }, 401);
  if ((request.headers.get("Content-Encoding") || "").trim()) return jsonResponse({ ok: false, error: "Görüntü işlem JSON'u ayrıca sıkıştırılmamalıdır." }, 415);
  if ((request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase() !== "application/json") return jsonResponse({ ok: false, error: "Görüntü işlemi application/json olmalıdır." }, 415);
  await cleanupPendingImageDeletes(env);
  let payload;
  try {
    payload = await readBoundedImageJson(request);
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message }, error.status || 400);
  }
  const ids = payload.staged_ids;
  if (!Array.isArray(ids) || ids.length > 3 || ids.some((id) => !isImageId(id)) ||
      new Set(ids).size !== ids.length) {
    return jsonResponse({ ok: false, error: "Geçici görüntü kimlikleri geçersiz." }, 400);
  }
  await deleteKeysBestEffort(env.IMAGES_BUCKET, ids.map((id) => "staging/" + id));
  return jsonResponse({ ok: true, aborted_count: ids.length });
}

async function handleImageCommit(request, env) {
  if (!env.IMAGES_BUCKET) return jsonResponse({ ok: false, error: "R2 görüntü deposu yapılandırılmamış." }, 503);
  if (!requestTokenIsValid(request, env)) return jsonResponse({ ok: false, error: "Yetkisiz görüntü işlemi." }, 401);
  await cleanupPendingImageDeletes(env);
  if ((request.headers.get("Content-Encoding") || "").trim()) {
    return jsonResponse({ ok: false, error: "Görüntü işlem JSON'u ayrıca sıkıştırılmamalıdır." }, 415);
  }
  if ((request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase() !== "application/json") {
    return jsonResponse({ ok: false, error: "Görüntü işlemi application/json olmalıdır." }, 415);
  }
  let payload;
  try {
    payload = await readBoundedImageJson(request);
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message }, error.status || 400);
  }
  const ids = payload.staged_ids;
  if (!Array.isArray(ids) || ids.length < 1 || ids.length > 3 ||
      ids.some((id) => !isImageId(id)) || new Set(ids).size !== ids.length) {
    return jsonResponse({ ok: false, error: "1–3 benzersiz geçici görüntü kimliği gereklidir." }, 400);
  }
  let active;
  try {
    active = await readActiveImageManifest(env);
  } catch {
    return jsonResponse({ ok: false, error: "Mevcut etkin görüntü listesi okunamıyor; hiçbir değişiklik yapılmadı." }, 500);
  }
  const activeIds = new Set(active.images.map((image) => image.id));
  const activeMatches = ids.filter((id) => activeIds.has(id));
  if (activeMatches.length === ids.length) {
    await deleteKeysBestEffort(env.IMAGES_BUCKET, ids.map((id) => "staging/" + id));
    await cleanupStaleImageObjects(env, active.images);
    const origin = new URL(request.url).origin;
    return jsonResponse({ ok: true, idempotent: true,
      images: active.images.map((image) => ({ ...image, url: new URL("/images/" + image.id, origin).toString() })) });
  }
  if (activeMatches.length) {
    return jsonResponse({ ok: false, error: "Bu toplu yüklemenin bir kısmı zaten etkin; yeni seçim yapıp tekrar deneyin." }, 409);
  }

  const stages = [];
  for (const id of ids) {
    let object;
    try { object = await env.IMAGES_BUCKET.get("staging/" + id); } catch { object = null; }
    if (!object) {
      await deleteKeysBestEffort(env.IMAGES_BUCKET, ids.map((item) => "staging/" + item));
      return jsonResponse({ ok: false, error: "Geçici görüntülerden biri bulunamadı; etkin liste değiştirilmedi." }, 409);
    }
    const metadata = object.customMetadata || {};
    const contentType = metadata.contentType || "";
    const sizeBytes = Number(metadata.sizeBytes);
    const uploadedAt = metadata.uploadedAt || "";
    if (metadata.purpose !== "image-stage" ||
        !validImageFilename(metadata.filename, contentType) || !IMAGE_TYPES.has(contentType) ||
        !Number.isSafeInteger(sizeBytes) || sizeBytes < 1 || sizeBytes > MAX_IMAGE_BYTES ||
        object.size !== sizeBytes || !Number.isFinite(Date.parse(uploadedAt))) {
      await deleteKeysBestEffort(env.IMAGES_BUCKET, ids.map((item) => "staging/" + item));
      return jsonResponse({ ok: false, error: "Geçici görüntü metadata'sı geçersiz; etkin liste değiştirilmedi." }, 422);
    }
    stages.push({ id, object, entry: { id, filename: metadata.filename, content_type: contentType,
      size_bytes: sizeBytes, uploaded_at: uploadedAt } });
  }

  const copiedIds = [];
  let nextImages;
  try {
    for (const item of stages) {
      const copied = await env.IMAGES_BUCKET.put("images/" + item.id, item.object.body, {
        httpMetadata: { contentType: item.entry.content_type, cacheControl: "no-store" },
        customMetadata: { purpose: "active-image", filename: item.entry.filename,
          contentType: item.entry.content_type, sizeBytes: String(item.entry.size_bytes),
          uploadedAt: item.entry.uploaded_at },
      });
      if (!copied) throw new Error("R2 image copy failed.");
      copiedIds.push(item.id);
    }
    const keep = active.images.slice(0, Math.max(0, 3 - stages.length));
    nextImages = [...stages.map((item) => item.entry), ...keep].slice(0, 3);
    const keptIds = new Set(nextImages.map((image) => image.id));
    const obsoleteIds = active.images.filter((image) => !keptIds.has(image.id)).map((image) => image.id);
    const cleanupIds = [...new Set([...active.cleanupIds, ...obsoleteIds])];
    const published = await env.IMAGES_BUCKET.put(IMAGE_MANIFEST_KEY, JSON.stringify({
      version: 1, updated_at: new Date().toISOString(), images: nextImages, cleanup_ids: cleanupIds,
    }), {
      onlyIf: active.exists ? { etagMatches: active.etag } : { etagDoesNotMatch: "*" },
      httpMetadata: { contentType: "application/json; charset=utf-8", cacheControl: "no-store" },
    });
    if (!published) {
      await deleteUncommittedImageObjects(env, copiedIds);
      await deleteKeysBestEffort(env.IMAGES_BUCKET, ids.map((id) => "staging/" + id));
      return jsonResponse({ ok: false, error: "Etkin liste eşzamanlı değişti; eski liste korundu. Yeniden deneyin." }, 409);
    }
  } catch {
    await deleteUncommittedImageObjects(env, copiedIds);
    await deleteKeysBestEffort(env.IMAGES_BUCKET, ids.map((id) => "staging/" + id));
    return jsonResponse({ ok: false, error: "Görüntü grubu etkinleştirilemedi; mevcut etkin liste korunuyor." }, 502);
  }

  await deleteKeysBestEffort(env.IMAGES_BUCKET, ids.map((id) => "staging/" + id));
  await cleanupPendingImageDeletes(env);
  await cleanupStaleImageObjects(env, nextImages);
  const origin = new URL(request.url).origin;
  return jsonResponse({ ok: true, idempotent: false,
    images: nextImages.map((image) => ({ ...image, url: new URL("/images/" + image.id, origin).toString() })) }, 201);
}

async function handleImageManifest(request, env) {
  if (!env.IMAGES_BUCKET) return jsonResponse({ ok: false, error: "R2 görüntü deposu yapılandırılmamış." }, 503);
  let active;
  try { active = await readActiveImageManifest(env); } catch {
    return jsonResponse({ ok: false, error: "Etkin görüntü listesi okunamıyor." }, 500);
  }
  await cleanupPendingImageDeletes(env);
  await cleanupStaleImageObjects(env, active.images);
  const origin = new URL(request.url).origin;
  return jsonResponse({ ok: true,
    images: active.images.map((image) => ({ ...image, url: new URL("/images/" + image.id, origin).toString() })) });
}

async function handleImageRead(request, env, imageId) {
  if (!env.IMAGES_BUCKET) return jsonResponse({ ok: false, error: "R2 görüntü deposu yapılandırılmamış." }, 503);
  let active;
  try { active = await readActiveImageManifest(env); } catch {
    return jsonResponse({ ok: false, error: "Etkin görüntü listesi okunamıyor." }, 500);
  }
  await cleanupPendingImageDeletes(env);
  const entry = active.images.find((image) => image.id === imageId);
  if (!entry) return jsonResponse({ ok: false, error: "Etkin görüntü bulunamadı." }, 404);
  let object;
  try { object = await env.IMAGES_BUCKET.get("images/" + imageId); } catch { object = null; }
  if (!object) return jsonResponse({ ok: false, error: "Görüntü içeriği bulunamadı." }, 404);
  if (object.size !== entry.size_bytes) return jsonResponse({ ok: false, error: "Görüntü boyutu etkin manifest ile eşleşmiyor." }, 500);
  const headers = new Headers({
    "Content-Type": entry.content_type,
    "Cache-Control": "no-store, max-age=0",
    "X-Content-Type-Options": "nosniff",
    "Content-Disposition": "inline; filename*=UTF-8''" + encodeURIComponent(entry.filename),
    "Access-Control-Allow-Origin": "*",
  });
  headers.set("Content-Length", String(entry.size_bytes));
  return new Response(object.body, { status: 200, headers });
}

async function getStoredJsonReport(env, route) {
  const record = await env.ANALYSIS_REPORTS.getWithMetadata(route.key, "arrayBuffer");
  if (!record || !record.value) {
    return jsonResponse({ ok: false, error: "Bu rapor türü için henüz kayıt yok." }, 404);
  }
  let report;
  try {
    report = await readGzipJson(record.value);
  } catch {
    return jsonResponse({ ok: false, error: "Saklanan rapor açılamadı." }, 500);
  }
  return jsonResponse(report, 200, {
    "X-Report-SHA256": record.metadata?.sha256 || "",
    "X-Report-Generated-At": record.metadata?.generated_at_utc || "",
    "X-Report-Type": route.kind,
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type, Content-Encoding, X-Image-Name-B64",
      "Access-Control-Max-Age": "86400",
    }});

    if (url.pathname === "/api/images/stage" && request.method === "POST") return handleImageStage(request, env);
    if (url.pathname === "/api/images/commit" && request.method === "POST") return handleImageCommit(request, env);
    if (url.pathname === "/api/images/abort" && request.method === "POST") return handleImageAbort(request, env);
    if (url.pathname === "/images/manifest" && request.method === "GET") return handleImageManifest(request, env);
    const imageMatch = /^\/images\/([0-9a-f-]{36})$/.exec(url.pathname);
    if (imageMatch && request.method === "GET" && isImageId(imageMatch[1])) {
      return handleImageRead(request, env, imageMatch[1]);
    }

    if (url.pathname === "/health" && request.method === "GET") {
      return jsonResponse({ ok: true, service: "analysis-report-store", storage: "Cloudflare KV" });
    }

    const jsonUploadRoute = JSON_REPORT_ROUTES[url.pathname];
    if (request.method === "POST" && jsonUploadRoute) {
      if (!requestTokenIsValid(request, env)) {
        return jsonResponse({ ok: false, error: "Yetkisiz yükleme." }, 401);
      }
      if ((request.headers.get("Content-Encoding") || "").toLowerCase() !== "gzip") {
        return jsonResponse({ ok: false, error: "İstek gzip sıkıştırmalı olmalıdır." }, 415);
      }
      const compressed = await request.arrayBuffer();
      if (!compressed.byteLength || compressed.byteLength > MAX_COMPRESSED_BYTES) {
        return jsonResponse({ ok: false, error: "Sıkıştırılmış rapor boyutu geçersiz." }, 413);
      }
      let report;
      try {
        report = await readGzipJson(compressed);
      } catch {
        return jsonResponse({ ok: false, error: "Gzip/JSON içeriği okunamadı." }, 400);
      }
      if (!validJsonReport(report, jsonUploadRoute.kind)) {
        return jsonResponse({ ok: false, error: "Rapor şeması geçersiz." }, 422);
      }
      const digest = await sha256Hex(compressed);
      const metadata = {
        generated_at_utc: report.generated_at_utc || report.report_generated_at_utc || new Date().toISOString(),
        report_type: jsonUploadRoute.kind,
        candidate_count: report.candidate_count ?? report.daily_report?.state?.candidates?.length ?? null,
        compressed_bytes: compressed.byteLength,
        sha256: digest,
        schema_version: report.schema_version,
      };
      await env.ANALYSIS_REPORTS.put(jsonUploadRoute.key, compressed, { metadata });
      return jsonResponse({
        ok: true,
        report_type: jsonUploadRoute.kind,
        candidate_count: metadata.candidate_count,
        compressed_bytes: compressed.byteLength,
        sha256: digest,
        read_url: new URL(jsonUploadRoute.readPath, url.origin).toString(),
      }, 201);
    }

    if (url.pathname === "/api/report/troubleshooting-zip" && request.method === "POST") {
      if (!requestTokenIsValid(request, env)) {
        return jsonResponse({ ok: false, error: "Yetkisiz yükleme." }, 401);
      }
      const contentType = (request.headers.get("Content-Type") || "").toLowerCase();
      if (!contentType.startsWith("application/zip")) {
        return jsonResponse({ ok: false, error: "ZIP dosyası application/zip olmalıdır." }, 415);
      }
      if (request.headers.has("Content-Encoding")) {
        return jsonResponse({ ok: false, error: "ZIP gövdesi ayrıca Content-Encoding içermemelidir." }, 415);
      }
      const archive = await request.arrayBuffer();
      if (!archive.byteLength || archive.byteLength > MAX_ZIP_BYTES) {
        return jsonResponse({ ok: false, error: "ZIP boyutu geçersiz veya 8 MiB sınırını aşıyor." }, 413);
      }
      const signature = new Uint8Array(archive, 0, Math.min(4, archive.byteLength));
      const isZip = signature.length >= 4 && signature[0] === 0x50 && signature[1] === 0x4b &&
        ((signature[2] === 0x03 && signature[3] === 0x04) ||
         (signature[2] === 0x05 && signature[3] === 0x06) ||
         (signature[2] === 0x07 && signature[3] === 0x08));
      if (!isZip) return jsonResponse({ ok: false, error: "Geçerli ZIP başlığı bulunamadı." }, 400);
      const digest = await sha256Hex(archive);
      await env.ANALYSIS_REPORTS.put(REPORT_KEYS.troubleshootingZip, archive, {
        metadata: {
          generated_at_utc: new Date().toISOString(),
          report_type: "troubleshooting_zip",
          compressed_bytes: archive.byteLength,
          sha256: digest,
        },
      });
      return jsonResponse({
        ok: true,
        report_type: "troubleshooting_zip",
        compressed_bytes: archive.byteLength,
        sha256: digest,
        read_url: new URL("/troubleshooting.zip", url.origin).toString(),
      }, 201);
    }

    if (request.method === "GET" && (url.pathname === "/chatgpt/daily" || url.pathname === "/chatgpt/troubleshooting")) {
      const isDaily = url.pathname === "/chatgpt/daily";
      const key = isDaily ? REPORT_KEYS.daily : REPORT_KEYS.troubleshooting;
      const kind = isDaily ? "daily" : "troubleshooting";
      const record = await env.ANALYSIS_REPORTS.getWithMetadata(key, "arrayBuffer");
      if (!record || !record.value) {
        return jsonResponse({ ok: false, error: "İstenen rapor bulunamadı." }, 404);
      }
      try {
        const report = await readGzipJson(record.value);
        const select = (value, keys) => {
          if (!value || typeof value !== "object" || Array.isArray(value)) return {};
          const result = {};
          for (const field of keys) if (Object.prototype.hasOwnProperty.call(value, field)) result[field] = value[field];
          return result;
        };
        const stateKeys = [
          "application_version", "radar", "source", "generated_at_utc", "generated_at_local",
          "live_stream_status", "history_status", "live_stream_healthy", "status",
          "bootstrap_completed", "bootstrap_total", "bootstrap_progress_pct", "bootstrap_errors",
          "bootstrap_successful", "bootstrap_skipped", "bootstrap_ready", "bootstrap_retry_seconds",
          "common_pair_count", "scan_symbol_count", "universe_generated_at_utc",
          "btcturk_universe_generated_at_utc", "fan_token_count", "stablecoin_count"
        ];
        let payload;
        if (isDaily) {
          const body = report.payload || {};
          payload = {
            report_type: report.report_type,
            schema_version: report.schema_version,
            report_generated_at_utc: report.report_generated_at_utc,
            generated_at_local: body.state?.generated_at_local,
            state: select(body.state, stateKeys),
            diagnostics: body.diagnostics && typeof body.diagnostics === "object" ? body.diagnostics : {}
          };
        } else {
          const dailyState = report.daily_report?.state || {};
          payload = {
            report_type: report.report_type,
            schema_version: report.schema_version,
            generated_at_utc: report.generated_at_utc,
            application: report.application,
            summary: report.summary || {},
            state: select(dailyState, stateKeys),
            diagnostics: report.diagnostics && typeof report.diagnostics === "object" ? report.diagnostics : {},
            manifest: Array.isArray(report.manifest?.files) ? report.manifest.files : [],
            log_tail: typeof report.log_tail === "string" ? report.log_tail.slice(-12000) : ""
          };
        }
        return jsonResponse(payload, 200, {
          "X-Report-SHA256": record.metadata?.sha256 || "",
          "X-Report-Generated-At": record.metadata?.generated_at_utc || "",
          "X-Report-Type": kind + "-summary"
        });
      } catch {
        return jsonResponse({ ok: false, error: "Rapor özeti oluşturulamadı." }, 500);
      }
    }

    if (request.method === "GET" && url.pathname === "/chatgpt/analysis") {
      const record = await env.ANALYSIS_REPORTS.getWithMetadata(REPORT_KEYS.analysis, "arrayBuffer");
      if (!record || !record.value) {
        return jsonResponse({ ok: false, error: "Analiz raporu bulunamadı." }, 404);
      }
      try {
        const report = await readGzipJson(record.value);
        const fields = [
          "symbol", "base_asset", "quote_asset", "phase", "state", "phase_timeframe",
          "latest_price", "findings", "evidence_groups", "relative_strength_vs_btc_pct_points",
          "btc_return_correlation", "missing_checks", "source_market_pair", "btcturk_market_pair",
          "category_status", "data_note", "risk_plan", "data_freshness", "opportunity_score",
          "score_0_100", "final_decision", "decision_class", "decision_reason",
          "strong_opportunity_qualified", "strong_opportunity_gate_reasons", "liquidity_assessment"
        ];
        const candidates = (Array.isArray(report.candidates) ? report.candidates : []).map((candidate) => {
          const compact = {};
          for (const field of fields) {
            if (candidate && Object.prototype.hasOwnProperty.call(candidate, field)) compact[field] = candidate[field];
          }
          return compact;
        });
        return jsonResponse({
          report_type: report.report_type,
          schema_version: report.schema_version,
          generated_at_utc: report.generated_at_utc,
          source_state_generated_at_utc: report.source_state_generated_at_utc,
          application_version: report.application_version,
          radar: report.radar,
          universe: report.universe,
          market_context: report.market_context,
          market_context_freshness: report.market_context_freshness,
          market_context_warning: report.market_context_warning,
          candidate_count: report.candidate_count,
          candidates,
          interpretation_limits: report.interpretation_limits
        }, 200, {
          "X-Report-SHA256": record.metadata?.sha256 || "",
          "X-Report-Generated-At": record.metadata?.generated_at_utc || "",
          "X-Report-Type": "analysis-summary"
        });
      } catch {
        return jsonResponse({ ok: false, error: "Analiz özeti oluşturulamadı." }, 500);
      }
    }

    const readPath = url.pathname.startsWith("/read/") ? `/${url.pathname.slice(6)}` : url.pathname;
    const jsonReadRoute = JSON_READ_ROUTES[readPath];
    if (request.method === "GET" && jsonReadRoute) {
      return getStoredJsonReport(env, jsonReadRoute);
    }

    if (url.pathname === "/troubleshooting.zip" && request.method === "GET") {
      const record = await env.ANALYSIS_REPORTS.getWithMetadata(REPORT_KEYS.troubleshootingZip, "arrayBuffer");
      if (!record || !record.value) {
        return jsonResponse({ ok: false, error: "Henüz sorun giderme ZIP paketi yüklenmedi." }, 404);
      }
      return new Response(record.value, {
        status: 200,
        headers: {
          "Content-Type": "application/zip",
          "Content-Disposition": 'attachment; filename="firsat_kontrol_devir_latest.zip"',
          "Cache-Control": "no-store, max-age=0",
          "X-Report-SHA256": record.metadata?.sha256 || "",
          "X-Report-Generated-At": record.metadata?.generated_at_utc || "",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }

    return jsonResponse({ ok: false, error: "Uç nokta bulunamadı." }, 404);
  },
};
