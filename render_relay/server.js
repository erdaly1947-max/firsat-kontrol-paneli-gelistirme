import http from "node:http";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { pathToFileURL } from "node:url";
import { WebSocket, WebSocketServer } from "ws";
import { BoundedRestCache } from "./rest_cache.js";

const PORT = Number.parseInt(process.env.PORT || "10000", 10);
const REST_WINDOW_MS = 60_000;
const REST_LIMIT_PER_IP = 1_200;
const MAX_WS_PER_IP = 128;
const MAX_WS_GLOBAL = 200;
const REPORT_WORKER_BASE_URL = "https://firsat-kontrol-analysis-report.erdaly1947.workers.dev";
const REPORT_MAX_BODY_BYTES = 8 * 1024 * 1024;
const IMAGE_MAX_BODY_BYTES = 15 * 1024 * 1024;
const IMAGE_CONTROL_BODY_BYTES = 64 * 1024;
const REPORT_RATE_WINDOW_MS = 60_000;
const REPORT_RATE_LIMIT_PER_IP = 20;
const REPORT_RATE_BUCKETS = new Map();
const REPORT_UPLOAD_ROUTES = new Map([
  ["/api/report", { kind: "analysis", contentType: "application/json", workerPath: "/api/report", encoding: "gzip" }],
  ["/api/report/daily", { kind: "daily", contentType: "application/json", workerPath: "/api/report/daily", encoding: "gzip" }],
  ["/api/report/troubleshooting", { kind: "troubleshooting", contentType: "application/json", workerPath: "/api/report/troubleshooting", encoding: "gzip" }],
  ["/api/report/troubleshooting-zip", { kind: "troubleshooting_zip", contentType: "application/zip", workerPath: "/api/report/troubleshooting-zip", encoding: null }],
]);
const IMAGE_UPLOAD_ROUTES = new Map([
  ["/api/images/stage", { kind: "image_stage", acceptedContentTypes: ["image/png", "image/jpeg"], maxBodyBytes: IMAGE_MAX_BODY_BYTES }],
  ["/api/images/commit", { kind: "image_commit", acceptedContentTypes: ["application/json"], maxBodyBytes: IMAGE_CONTROL_BODY_BYTES }],
  ["/api/images/abort", { kind: "image_abort", acceptedContentTypes: ["application/json"], maxBodyBytes: IMAGE_CONTROL_BODY_BYTES }],
]);
const CLOUDINARY_IMAGE_PREFIX = "fkp_screenshot_";
const CLOUDINARY_STAGE_TAG = "fkp-staged";
const CLOUDINARY_ACTIVE_TAG = "fkp-active";
const CLOUDINARY_IMAGE_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const REST_BUCKETS = new Map();
const REST_CACHE = new BoundedRestCache();
const ACTIVE_WS_BY_IP = new Map();
let activeWebSocketCount = 0;

export const BINANCE_REST_ORIGINS = [
  "https://data-api.binance.vision",
  "https://api.binance.com",
  "https://api-gcp.binance.com",
  "https://api1.binance.com",
  "https://api2.binance.com",
  "https://api3.binance.com",
  "https://api4.binance.com",
];

const BINANCE_WS_ORIGINS = [
  "wss://data-stream.binance.vision:443",
  "wss://stream.binance.com:443",
  "wss://stream.binance.com:9443",
];

const ROUTES = [
  { prefix: "/binance", path: "/api/v3/exchangeInfo", exchange: "binance", allowedParams: [] },
  { prefix: "/binance", path: "/api/v3/klines", exchange: "binance", allowedParams: ["symbol", "interval", "limit", "startTime", "endTime", "timeZone"] },
  { prefix: "/binance", path: "/api/v3/ticker/24hr", exchange: "binance", allowedParams: ["symbol", "symbols", "type", "windowSize"] },
  { prefix: "/binance", path: "/api/v3/depth", exchange: "binance", allowedParams: ["symbol", "limit"] },
  { prefix: "/btcturk", path: "/api/v2/server/exchangeinfo", exchange: "btcturk", allowedParams: [] },
  { prefix: "/btcturk", path: "/api/v2/ticker/currency", exchange: "btcturk", allowedParams: ["symbol"] },
  { prefix: "/btcturk", path: "/api/v2/ticker", exchange: "btcturk", allowedParams: [] },
];

const ROUTE_BY_PATH = new Map(ROUTES.map((route) => [route.prefix + route.path, route]));
const UPSTREAMS = {
  binance: BINANCE_REST_ORIGINS,
  btcturk: ["https://api.btcturk.com"],
};

const CACHE_TTL_MS = {
  "/api/v3/exchangeInfo": 300_000,
  "/api/v2/server/exchangeinfo": 60_000,
  "/api/v2/ticker/currency": 3_000,
  "/api/v2/ticker": 2_000,
  "/api/v3/ticker/24hr": 2_000,
  "/api/v3/depth": 1_000,
  "/api/v3/klines": 5_000,
};

function jsonResponse(res, status, value, headers = {}) {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Access-Control-Allow-Origin": "*",
    ...headers,
  });
  res.end(JSON.stringify(value));
}

function clientIp(request) {
  const forwarded = request.headers["x-forwarded-for"];
  if (typeof forwarded === "string" && forwarded.trim()) {
    return forwarded.split(",")[0].trim().slice(0, 80) || "unknown";
  }
  return request.socket.remoteAddress || "unknown";
}

function checkRestRateLimit(ip, now = Date.now()) {
  let bucket = REST_BUCKETS.get(ip);
  if (!bucket || now - bucket.startedAt >= REST_WINDOW_MS) {
    bucket = { startedAt: now, count: 0 };
    REST_BUCKETS.set(ip, bucket);
  }
  bucket.count += 1;
  if (bucket.count > REST_LIMIT_PER_IP) {
    return Math.max(1, Math.ceil((REST_WINDOW_MS - (now - bucket.startedAt)) / 1_000));
  }
  if (REST_BUCKETS.size > 5_000) {
    for (const [key, value] of REST_BUCKETS.entries()) {
      if (now - value.startedAt >= REST_WINDOW_MS) REST_BUCKETS.delete(key);
    }
  }
  return 0;
}

export function resolveRestRoute(pathname) {
  return ROUTE_BY_PATH.get(pathname) || null;
}

export function resolveReportUploadRoute(pathname) {
  return REPORT_UPLOAD_ROUTES.get(pathname) || null;
}

export function resolveImageUploadRoute(pathname) {
  return IMAGE_UPLOAD_ROUTES.get(pathname) || null;
}

function isSafeSymbol(value) {
  return typeof value === "string" && /^[A-Z0-9]{3,30}$/.test(value);
}

export function validateRestQuery(route, params) {
  if (!route) return "Endpoint izin listesinde değil.";
  const allowed = new Set(route.allowedParams);
  for (const key of params.keys()) {
    if (!allowed.has(key)) return "İzin verilmeyen sorgu parametresi.";
    if (params.getAll(key).length !== 1) return "Tekrarlanan sorgu parametresi kabul edilmiyor.";
  }

  if (route.exchange === "binance") {
    const symbol = params.get("symbol");
    if (symbol !== null && !isSafeSymbol(symbol)) return "Geçersiz parite kodu.";

    const symbols = params.get("symbols");
    if (symbols !== null) {
      if (symbol !== null) return "symbol ve symbols birlikte kullanılamaz.";
      let list;
      try {
        list = JSON.parse(symbols);
      } catch {
        return "symbols JSON dizisi olmalı.";
      }
      if (!Array.isArray(list) || list.length < 1 || list.length > 100 || !list.every(isSafeSymbol)) {
        return "symbols listesi geçersiz veya çok büyük.";
      }
    }

    if (route.path === "/api/v3/klines") {
      const interval = params.get("interval");
      const intervals = new Set([
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M",
      ]);
      if (symbol === null || interval === null) return "Kline için symbol ve interval zorunludur.";
      if (!intervals.has(interval)) return "İzin verilmeyen mum aralığı.";
    }

    const limit = params.get("limit");
    if (limit !== null && (!/^\d+$/.test(limit) || Number(limit) < 1 || Number(limit) > 1_000)) {
      return "limit değeri izin verilen aralıkta değil.";
    }

    for (const key of ["startTime", "endTime"]) {
      const value = params.get(key);
      if (value !== null && (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)))) {
        return "Zaman parametresi geçersiz.";
      }
    }

    const timeZone = params.get("timeZone");
    if (timeZone !== null && !/^(?:-?\d{1,2}(?::[0-5]\d)?|[+-]\d{1,2}:[0-5]\d)$/.test(timeZone)) {
      return "timeZone parametresi geçersiz.";
    }
  } else if (
    route.path === "/api/v2/ticker/currency"
    && (params.get("symbol") || "").toLowerCase() !== "usdt"
  ) {
    return "Yalnızca USDT ticker sorgusu kabul edilir.";
  }

  return null;
}

export function validateWebSocketStreams(streams) {
  if (typeof streams !== "string" || streams.length === 0 || streams.length > 40_000) {
    return "streams parametresi eksik veya çok uzun.";
  }
  const names = streams.split("/");
  if (names.length < 1 || names.length > 200) return "Akış sayısı izin verilen aralıkta değil.";
  const valid = /^[a-z0-9]{3,30}@kline_(?:5m|15m|30m|1h|4h|1d|1w|1M)$/;
  if (!names.every((name) => valid.test(name))) {
    return "Yalnızca izin verilen genel Binance mum akışları kabul edilir.";
  }
  if (new Set(names).size !== names.length) return "Tekrarlanan akış adı kabul edilmiyor.";
  return null;
}

export function cacheTtlMs(route, params) {
  if (route.path === "/api/v3/klines" && (params.has("startTime") || params.has("endTime"))) {
    return 30_000;
  }
  return CACHE_TTL_MS[route.path] || 0;
}

function readCache(key, now = Date.now()) {
  return REST_CACHE.get(key, now);
}

function writeCache(key, entry) {
  REST_CACHE.set(key, entry);
}

async function fetchPublicMarketData(route, url) {
  let lastFailure = { status: 502, message: "Piyasa veri kaynağına bağlanılamadı." };

  for (const origin of UPSTREAMS[route.exchange]) {
    const target = new URL(route.path, origin);
    target.search = url.search;
    try {
      const upstream = await fetch(target, {
        method: "GET",
        redirect: "manual",
        headers: {
          "Accept": "application/json",
          "User-Agent": "FirsatKontrolMarketRelay/1.0",
        },
        signal: AbortSignal.timeout(12_000),
      });
      const body = await upstream.text();
      const contentType = upstream.headers.get("content-type") || "application/json";

      if (upstream.ok) {
        if (!contentType.toLowerCase().includes("json")) {
          lastFailure = { status: 502, message: "Üst kaynak JSON olmayan yanıt verdi." };
          continue;
        }
        return {
          status: upstream.status,
          body,
          contentType,
          cacheControl: "public, max-age=0, must-revalidate",
          upstreamHost: new URL(origin).hostname,
        };
      }

      lastFailure = {
        status: upstream.status,
        message: "Üst kaynak HTTP " + upstream.status + " yanıtı verdi.",
      };
      if (![403, 451, 500, 502, 503, 504].includes(upstream.status)) break;
    } catch (error) {
      lastFailure = {
        status: 502,
        message: error?.name === "TimeoutError"
          ? "Üst kaynağın bağlantı zaman aşımı."
          : "Üst kaynağa HTTPS bağlantısı kurulamadı.",
      };
    }
  }

  return {
    status: lastFailure.status,
    body: JSON.stringify({ error: lastFailure.message, source: route.exchange }),
    contentType: "application/json; charset=utf-8",
    cacheControl: "no-store",
    upstreamHost: "unavailable",
  };
}


function checkReportRateLimit(ip, now = Date.now()) {
  let bucket = REPORT_RATE_BUCKETS.get(ip);
  if (!bucket || now - bucket.startedAt >= REPORT_RATE_WINDOW_MS) {
    bucket = { startedAt: now, count: 0 };
    REPORT_RATE_BUCKETS.set(ip, bucket);
  }
  bucket.count += 1;
  if (bucket.count > REPORT_RATE_LIMIT_PER_IP) {
    return Math.max(1, Math.ceil((REPORT_RATE_WINDOW_MS - (now - bucket.startedAt)) / 1_000));
  }
  if (REPORT_RATE_BUCKETS.size > 5_000) {
    for (const [key, value] of REPORT_RATE_BUCKETS.entries()) {
      if (now - value.startedAt >= REPORT_RATE_WINDOW_MS) REPORT_RATE_BUCKETS.delete(key);
    }
  }
  return 0;
}

async function readLimitedBody(request, maxBytes) {
  const chunks = [];
  let total = 0;
  for await (const chunk of request) {
    total += chunk.length;
    if (total > maxBytes) {
      const error = new Error("Rapor boyut sınırını aşıyor.");
      error.status = 413;
      throw error;
    }
    chunks.push(chunk);
  }
  if (total === 0) {
    const error = new Error("Rapor gövdesi boş.");
    error.status = 400;
    throw error;
  }
  return Buffer.concat(chunks, total);
}

function decodeImageFilename(value) {
  if (typeof value !== "string" || value.length < 1 || value.length > 2048 || !/^[A-Za-z0-9_-]+$/.test(value)) return null;
  try {
    const bytes = Buffer.from(value, "base64url");
    if (!bytes.length || bytes.toString("base64url") !== value) return null;
    const filename = bytes.toString("utf8");
    if (!Buffer.from(filename, "utf8").equals(bytes)) return null;
    if (!filename || filename.length > 255 || filename.includes("/") || filename.includes("\\") ||
        /[\u0000-\u001f\u007f]/u.test(filename)) return null;
    if (!/\.(?:png|jpe?g)$/i.test(filename)) return null;
    return filename;
  } catch {
    return null;
  }
}

function imageBodyMatchesType(body, contentType) {
  if (contentType === "image/png") {
    return body.length >= 8 && body.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
  }
  return contentType === "image/jpeg" && body.length >= 3 &&
    body[0] === 0xff && body[1] === 0xd8 && body[2] === 0xff;
}

function imageFilenameMatchesType(filename, contentType) {
  const lower = filename.toLowerCase();
  if (contentType === "image/png") return lower.endsWith(".png");
  return contentType === "image/jpeg" && (lower.endsWith(".jpg") || lower.endsWith(".jpeg"));
}


export function cloudinaryConfiguration() {
  const cloudName = String(process.env.CLOUDINARY_CLOUD_NAME || "").trim();
  const apiKey = String(process.env.CLOUDINARY_API_KEY || "").trim();
  // Copy/paste in dashboard fields can preserve invisible outer whitespace;
  // Cloudinary secrets do not require leading or trailing whitespace.
  const apiSecret = String(process.env.CLOUDINARY_API_SECRET || "").trim();
  if (!cloudName || !apiKey || !apiSecret.trim()) {
    const error = new Error("Cloudinary bağlantısı ayarlanmadı. Render ortamına CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY ve CLOUDINARY_API_SECRET ekleyin.");
    error.status = 503;
    throw error;
  }
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(cloudName) || !/^[A-Za-z0-9_-]{1,128}$/.test(apiKey)) {
    const error = new Error("Cloudinary bağlantı ayarları geçersiz görünüyor.");
    error.status = 503;
    throw error;
  }
  return { cloudName, apiKey, apiSecret };
}
function cloudinaryApiBase(config) {
  return "https://api.cloudinary.com/v1_1/" + encodeURIComponent(config.cloudName);
}
function cloudinaryHeaders(config, extra = {}) {
  return {
    Authorization: "Basic " + Buffer.from(config.apiKey + ":" + config.apiSecret, "utf8").toString("base64"),
    Accept: "application/json",
    "User-Agent": "FirsatKontrolCloudinaryRelay/1.0",
    ...extra,
  };
}
export async function cloudinaryRequest(config, path, options = {}) {
  const init = {
    method: options.method || "GET",
    headers: cloudinaryHeaders(config, options.headers || {}),
    signal: AbortSignal.timeout(options.timeoutMs || 30_000),
  };
  if (options.body !== undefined) init.body = options.body;
  let response;
  try { response = await fetch(cloudinaryApiBase(config) + path, init); }
  catch {
    const error = new Error("Cloudinary bağlantısı başarısız oldu.");
    error.status = 502;
    throw error;
  }
  let raw = "";
  try { raw = await response.text(); }
  catch {
    const error = new Error("Cloudinary yanıtı okunamadı.");
    error.status = 502;
    throw error;
  }
  let payload = {};
  try { payload = raw ? JSON.parse(raw) : {}; }
  catch {
    const error = new Error("Cloudinary geçerli bir JSON yanıtı vermedi.");
    error.status = 502;
    throw error;
  }
  if (!response.ok || payload.error) {
    let detail = "";
    if (typeof payload.error === "string") detail = payload.error;
    else if (payload.error && typeof payload.error.message === "string") detail = payload.error.message;
    // Surface Cloudinary's useful diagnosis while never echoing credentials.
    for (const secret of [config.apiKey, config.apiSecret]) {
      if (secret) detail = detail.split(secret).join("[gizli değer gizlendi]");
    }
    detail = detail.replace(/[\r\n\t]+/g, " ").trim().slice(0, 240);
    const suffix = detail ? ": " + detail : ".";
    const error = new Error("Cloudinary isteği başarısız oldu (HTTP " + response.status + ")" + suffix);
    error.status = response.status === 429 || response.status === 420 ? 503 : 502;
    throw error;
  }
  return payload;
}
function cloudinaryImageId(publicId) {
  if (typeof publicId !== "string" || !publicId.startsWith(CLOUDINARY_IMAGE_PREFIX)) return null;
  const id = publicId.slice(CLOUDINARY_IMAGE_PREFIX.length);
  return CLOUDINARY_IMAGE_ID_RE.test(id) ? id.toLowerCase() : null;
}
function cloudinaryImageMime(resource) {
  const format = String(resource?.format || "").toLowerCase();
  if (format === "png") return "image/png";
  if (format === "jpg" || format === "jpeg") return "image/jpeg";
  return null;
}
function cloudinaryResourceFilename(resource, id, contentType) {
  const encoded = resource?.context?.custom?.filename_b64;
  if (typeof encoded === "string" && encoded.length > 0 && encoded.length <= 1024 && /^[A-Za-z0-9_-]+$/.test(encoded)) {
    try {
      const bytes = Buffer.from(encoded, "base64url");
      const filename = bytes.toString("utf8");
      if (bytes.length && bytes.toString("base64url") === encoded &&
          Buffer.from(filename, "utf8").equals(bytes) && imageFilenameMatchesType(filename, contentType)) return filename;
    } catch {
      // Optional filename metadata is ignored if malformed.
    }
  }
  return id + (contentType === "image/png" ? ".png" : ".jpg");
}
function cloudinaryImageRecord(resource) {
  const id = cloudinaryImageId(resource?.public_id);
  const contentType = cloudinaryImageMime(resource);
  const sizeBytes = resource?.bytes;
  const uploadedAt = resource?.created_at;
  if (!id || !contentType || !Number.isSafeInteger(sizeBytes) || sizeBytes < 1 || sizeBytes > IMAGE_MAX_BODY_BYTES ||
      typeof uploadedAt !== "string" || !uploadedAt) throw new Error("Cloudinary görüntü kaydı geçersiz.");
  return { id, filename: cloudinaryResourceFilename(resource, id, contentType), content_type: contentType, size_bytes: sizeBytes, uploaded_at: uploadedAt };
}
function cloudinaryTime(resource) {
  const value = Date.parse(resource?.created_at || "");
  return Number.isFinite(value) ? value : 0;
}
async function cloudinaryListScreenshots(config) {
  const found = [];
  let nextCursor = null;
  let pages = 0;
  do {
    const params = new URLSearchParams({
      prefix: CLOUDINARY_IMAGE_PREFIX,
      max_results: "500",
      tags: "true",
      context: "true",
      fields: "public_id,asset_id,created_at,bytes,format,secure_url,tags,context",
    });
    if (nextCursor) params.set("next_cursor", nextCursor);
    const payload = await cloudinaryRequest(config, "/resources/image/upload?" + params.toString());
    if (!Array.isArray(payload.resources)) throw new Error("Cloudinary görüntü listesi geçersiz.");
    for (const resource of payload.resources) if (cloudinaryImageId(resource?.public_id)) found.push(resource);
    nextCursor = typeof payload.next_cursor === "string" && payload.next_cursor ? payload.next_cursor : null;
    pages += 1;
  } while (nextCursor && pages < 5);
  if (nextCursor) throw new Error("Cloudinary görüntü listesi beklenenden büyük.");
  return found;
}
function cloudinarySortedActive(resources) {
  return resources.filter((resource) =>
    Array.isArray(resource.tags) && resource.tags.includes(CLOUDINARY_ACTIVE_TAG) && cloudinaryImageId(resource.public_id))
    .sort((a,b) => cloudinaryTime(b) - cloudinaryTime(a));
}
async function cloudinaryChangeTag(config, tag, command, publicIds) {
  if (!publicIds.length) return;
  const form = new URLSearchParams();
  form.set("tag", tag);
  form.set("command", command);
  for (const publicId of publicIds) form.append("public_ids[]", publicId);
  await cloudinaryRequest(config, "/image/tags", { method:"POST", headers:{"Content-Type":"application/x-www-form-urlencoded"}, body:form.toString() });
}
async function cloudinaryDeleteResources(config, publicIds) {
  if (!publicIds.length) return;
  const form = new URLSearchParams();
  for (const publicId of publicIds) form.append("public_ids[]", publicId);
  const payload = await cloudinaryRequest(config, "/resources/image/upload", {
    method:"DELETE", headers:{"Content-Type":"application/x-www-form-urlencoded"}, body:form.toString(),
  });
  if (payload.partial === true ||
      (payload.deleted && Object.values(payload.deleted).some((status) => status !== "deleted" && status !== "not_found"))) {
    throw new Error("Cloudinary bazı eski görüntüleri silemedi.");
  }
}
async function cloudinaryStageImage(config, body, filename, contentType) {
  const id = randomUUID().toLowerCase();
  const publicId = CLOUDINARY_IMAGE_PREFIX + id;
  const form = new FormData();
  form.append("file", new Blob([body], {type:contentType}), filename);
  form.set("public_id", publicId);
  form.set("overwrite", "false");
  form.set("tags", CLOUDINARY_STAGE_TAG);
  form.set("context", "filename_b64=" + Buffer.from(filename, "utf8").toString("base64url"));
  const payload = await cloudinaryRequest(config, "/image/upload", {method:"POST",body:form,timeoutMs:90_000});
  if (payload.public_id !== publicId || typeof payload.secure_url !== "string") throw new Error("Cloudinary görüntüyü beklenen kimlikle kaydetmedi.");
  return {ok:true,staged_id:id};
}
async function cloudinaryCommitImages(config, stagedIds) {
  if (!Array.isArray(stagedIds) || stagedIds.length < 1 || stagedIds.length > 3 ||
      !stagedIds.every((id) => typeof id === "string" && CLOUDINARY_IMAGE_ID_RE.test(id)) ||
      new Set(stagedIds.map((id)=>id.toLowerCase())).size !== stagedIds.length) {
    const error = new Error("1–3 geçerli görüntü kimliği gereklidir."); error.status = 400; throw error;
  }
  const resources = await cloudinaryListScreenshots(config);
  const byPublicId = new Map(resources.map((item)=>[item.public_id,item]));
  const staged = stagedIds.map((id)=>byPublicId.get(CLOUDINARY_IMAGE_PREFIX+id.toLowerCase()));
  if (staged.some((item)=>!item || !Array.isArray(item.tags) || !item.tags.includes(CLOUDINARY_STAGE_TAG))) {
    const error = new Error("Geçici görüntüler Cloudinary'de bulunamadı; mevcut görüntüler korunuyor."); error.status = 409; throw error;
  }
  if (staged.some((item)=>item.tags.includes(CLOUDINARY_ACTIVE_TAG))) {
    const error = new Error("Görüntü grubu daha önce etkinleştirilmiş."); error.status = 409; throw error;
  }
  const active = cloudinarySortedActive(resources);
  const keepCount = Math.min(active.length, Math.max(0, 3-staged.length));
  const replace = active.slice(keepCount);
  const stagedPublicIds = staged.map((item)=>item.public_id);
  await cloudinaryChangeTag(config,CLOUDINARY_ACTIVE_TAG,"add",stagedPublicIds);
  if (replace.length) {
    try { await cloudinaryDeleteResources(config,replace.map((item)=>item.public_id)); }
    catch {
      try { await cloudinaryChangeTag(config,CLOUDINARY_ACTIVE_TAG,"remove",replace.map((item)=>item.public_id)); }
      catch { /* Manifest stays capped at three; later requests retry cleanup. */ }
    }
  }
  try { await cloudinaryChangeTag(config,CLOUDINARY_STAGE_TAG,"remove",stagedPublicIds); }
  catch { /* Active tag protects committed images from abort cleanup. */ }
  const finalRecords = [...active.slice(0,keepCount),...staged]
    .sort((a,b)=>cloudinaryTime(b)-cloudinaryTime(a)).slice(0,3).map(cloudinaryImageRecord);
  return {ok:true,images:finalRecords};
}
async function cloudinaryAbortImages(config, stagedIds) {
  if (!Array.isArray(stagedIds) || stagedIds.length > 3 ||
      !stagedIds.every((id)=>typeof id==="string" && CLOUDINARY_IMAGE_ID_RE.test(id))) {
    const error=new Error("Geçici görüntü kimlikleri geçersiz."); error.status=400; throw error;
  }
  if (!stagedIds.length) return {ok:true,aborted_count:0};
  const resources = await cloudinaryListScreenshots(config);
  const byPublicId = new Map(resources.map((item)=>[item.public_id,item]));
  const disposable = stagedIds.map((id)=>byPublicId.get(CLOUDINARY_IMAGE_PREFIX+id.toLowerCase()))
    .filter((item)=>item && Array.isArray(item.tags) && item.tags.includes(CLOUDINARY_STAGE_TAG) && !item.tags.includes(CLOUDINARY_ACTIVE_TAG));
  await cloudinaryDeleteResources(config,disposable.map((item)=>item.public_id));
  return {ok:true,aborted_count:disposable.length};
}
async function cloudinaryActiveResources(config) {
  const resources = await cloudinaryListScreenshots(config);
  let active = cloudinarySortedActive(resources);
  const cutoff = Date.now()-24*60*60*1000;
  const staleStage = resources.filter((item)=>Array.isArray(item.tags) && item.tags.includes(CLOUDINARY_STAGE_TAG) &&
    !item.tags.includes(CLOUDINARY_ACTIVE_TAG) && cloudinaryTime(item)>0 && cloudinaryTime(item)<cutoff);
  const staleOrphans = resources.filter((item)=>Array.isArray(item.tags) && !item.tags.includes(CLOUDINARY_ACTIVE_TAG) &&
    !item.tags.includes(CLOUDINARY_STAGE_TAG) && cloudinaryTime(item)>0 && cloudinaryTime(item)<cutoff);
  for (const batch of [staleStage,staleOrphans]) if (batch.length) {
    try { await cloudinaryDeleteResources(config,batch.map((item)=>item.public_id)); }
    catch { /* Inactive leftovers remain hidden; later reads retry cleanup. */ }
  }
  if (active.length>3) {
    const extra=active.slice(3);
    try { await cloudinaryDeleteResources(config,extra.map((item)=>item.public_id)); }
    catch {
      try { await cloudinaryChangeTag(config,CLOUDINARY_ACTIVE_TAG,"remove",extra.map((item)=>item.public_id)); }
      catch { /* Response still remains limited to three images. */ }
    }
    active=active.slice(0,3);
  }
  return active;
}
async function handleCloudinaryImageUpload(request,response,route) {
  if (request.method!=="POST") { jsonResponse(response,405,{ok:false,error:"Yalnızca POST kabul edilir."},{Allow:"POST"}); request.resume(); return; }
  const token=bearerToken(request);
  if (!token) { jsonResponse(response,401,{ok:false,error:"Görüntü aktarım kimliği doğrulanamadı."}); request.resume(); return; }
  const expectedToken=process.env.REPORT_RELAY_TOKEN;
  if (expectedToken && (expectedToken.length>8192 || Buffer.byteLength(token)!==Buffer.byteLength(expectedToken) ||
      !timingSafeEqual(Buffer.from(token),Buffer.from(expectedToken)))) {
    jsonResponse(response,401,{ok:false,error:"Görüntü aktarım kimliği doğrulanamadı."}); request.resume(); return;
  }
  const contentType=String(request.headers["content-type"]||"").split(";")[0].trim().toLowerCase();
  const contentEncoding=String(request.headers["content-encoding"]||"").trim().toLowerCase();
  if (!route.acceptedContentTypes.includes(contentType)) {
    jsonResponse(response,415,{ok:false,error:route.kind==="image_stage"?"Görüntü içerik türü PNG/JPEG olmalıdır.":"Görüntü kontrol isteği JSON olmalıdır."});
    request.resume(); return;
  }
  if (contentEncoding!=="") { jsonResponse(response,415,{ok:false,error:"Görüntü aktarımında Content-Encoding kullanılmamalıdır."}); request.resume(); return; }
  let filename=null;
  if (route.kind==="image_stage") {
    filename=decodeImageFilename(request.headers["x-image-name-b64"]);
    if (!filename || !imageFilenameMatchesType(filename,contentType)) {
      jsonResponse(response,400,{ok:false,error:"Dosya adı metadata'sı veya uzantısı içerik türüyle eşleşmiyor."}); request.resume(); return;
    }
  }
  const declaredLength=request.headers["content-length"];
  if (declaredLength!==undefined && (!/^\d+$/.test(String(declaredLength)) || Number(declaredLength)>route.maxBodyBytes)) {
    jsonResponse(response,413,{ok:false,error:route.kind==="image_stage"?"Görüntü boyut sınırını aşıyor.":"Görüntü kontrol isteği çok büyük."});
    request.resume(); return;
  }
  const retryAfter=checkReportRateLimit(clientIp(request));
  if (retryAfter>0) { jsonResponse(response,429,{ok:false,error:"Görüntü aktarım istek sınırına ulaşıldı."},{"Retry-After":String(retryAfter)}); request.resume(); return; }
  let body;
  try { body=await readLimitedBody(request,route.maxBodyBytes); }
  catch(error) {
    request.resume();
    jsonResponse(response,error.status||400,{ok:false,error:error.status===413
      ?(route.kind==="image_stage"?"Görüntü boyut sınırını aşıyor.":"Görüntü kontrol isteği çok büyük.")
      :"Görüntü aktarım gövdesi okunamadı."}); return;
  }
  if (route.kind==="image_stage" && !imageBodyMatchesType(body,contentType)) {
    jsonResponse(response,400,{ok:false,error:"Dosya imzası PNG/JPEG içerik türüyle eşleşmiyor."}); return;
  }
  try {
    const config=cloudinaryConfiguration();
    let result;
    if (route.kind==="image_stage") result=await cloudinaryStageImage(config,body,filename,contentType);
    else {
      let payload;
      try { payload=JSON.parse(body.toString("utf8")); }
      catch { jsonResponse(response,400,{ok:false,error:"Görüntü kontrol isteği geçerli JSON değil."}); return; }
      if (!payload || typeof payload!=="object" || Array.isArray(payload)) {
        jsonResponse(response,400,{ok:false,error:"Görüntü kontrol isteği geçersiz."}); return;
      }
      result=route.kind==="image_commit" ? await cloudinaryCommitImages(config,payload.staged_ids) : await cloudinaryAbortImages(config,payload.staged_ids);
    }
    jsonResponse(response,200,{...result,ok:true,relay:"render"});
  } catch(error) {
    jsonResponse(response,Number.isInteger(error?.status)?error.status:502,{ok:false,error:String(error?.message||"Cloudinary aktarımı başarısız.").slice(0,400)});
  }
}
async function handleCloudinaryImageManifest(request,response) {
  if (request.method!=="GET") { jsonResponse(response,405,{ok:false,error:"Yalnızca GET kabul edilir."},{Allow:"GET"}); return; }
  const retryAfter=checkRestRateLimit(clientIp(request));
  if (retryAfter>0) { jsonResponse(response,429,{ok:false,error:"Görüntü listesi için istek sınırına ulaşıldı."},{"Retry-After":String(retryAfter)}); return; }
  try {
    const config=cloudinaryConfiguration();
    const resources=await cloudinaryActiveResources(config);
    jsonResponse(response,200,{ok:true,images:resources.map(cloudinaryImageRecord)});
  } catch(error) {
    jsonResponse(response,Number.isInteger(error?.status)?error.status:502,{ok:false,error:String(error?.message||"Cloudinary görüntü listesi alınamadı.").slice(0,400)});
  }
}
async function handleCloudinaryImageDownload(request,response,imageId) {
  if (request.method!=="GET") { jsonResponse(response,405,{ok:false,error:"Yalnızca GET kabul edilir."},{Allow:"GET"}); return; }
  if (!CLOUDINARY_IMAGE_ID_RE.test(imageId)) { jsonResponse(response,400,{ok:false,error:"Görüntü kimliği geçersiz."}); return; }
  const retryAfter=checkRestRateLimit(clientIp(request));
  if (retryAfter>0) { jsonResponse(response,429,{ok:false,error:"Görüntü indirme istek sınırına ulaşıldı."},{"Retry-After":String(retryAfter)}); return; }
  try {
    const config=cloudinaryConfiguration();
    const resources=await cloudinaryActiveResources(config);
    const resource=resources.find((item)=>cloudinaryImageId(item.public_id)===imageId.toLowerCase());
    if (!resource) { jsonResponse(response,404,{ok:false,error:"Etkin görüntü bulunamadı."}); return; }
    const contentType=cloudinaryImageMime(resource);
    let assetUrl;
    try { assetUrl=new URL(resource.secure_url||""); }
    catch { jsonResponse(response,502,{ok:false,error:"Cloudinary görüntü adresi doğrulanamadı."}); return; }
    const expectedPath="/"+config.cloudName+"/image/upload/";
    if (!contentType || assetUrl.protocol!=="https:" || assetUrl.hostname!=="res.cloudinary.com" || !assetUrl.pathname.includes(expectedPath)) {
      jsonResponse(response,502,{ok:false,error:"Cloudinary görüntü adresi doğrulanamadı."}); return;
    }
    let upstream;
    try { upstream=await fetch(assetUrl,{headers:{Accept:contentType},signal:AbortSignal.timeout(30_000)}); }
    catch { jsonResponse(response,502,{ok:false,error:"Cloudinary görüntüsü indirilemedi."}); return; }
    if (!upstream.ok) { jsonResponse(response,502,{ok:false,error:"Cloudinary görüntüsüne erişilemedi."}); return; }
    const upstreamType=String(upstream.headers.get("content-type")||"").split(";")[0].trim().toLowerCase();
    const bytes=Buffer.from(await upstream.arrayBuffer());
    if (upstreamType!==contentType || bytes.length<1 || bytes.length>IMAGE_MAX_BODY_BYTES || !imageBodyMatchesType(bytes,contentType)) {
      jsonResponse(response,502,{ok:false,error:"Cloudinary görüntü içeriği doğrulanamadı."}); return;
    }
    const requestUrl = new URL(request.url || "/", "https://relay.invalid");
    if (requestUrl.searchParams.get("format") === "base64") {
      // Text-only inspection path for clients that cannot consume image/png or image/jpeg responses.
      // Keep this convenience path small; normal image downloads remain binary and unchanged.
      if (bytes.length > 512 * 1024) {
        jsonResponse(response, 413, { ok:false, error:"Görüntü inceleme çıktısı 512 KiB sınırını aşıyor." });
        return;
      }
      jsonResponse(response, 200, {
        ok:true,
        id:imageId.toLowerCase(),
        content_type:contentType,
        size_bytes:bytes.length,
        encoding:"base64",
        data:bytes.toString("base64"),
      });
      return;
    }
    response.writeHead(200,{"Content-Type":contentType,"Content-Length":String(bytes.length),"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Access-Control-Allow-Origin":"*"});
    response.end(bytes);
  } catch(error) {
    jsonResponse(response,Number.isInteger(error?.status)?error.status:502,{ok:false,error:String(error?.message||"Cloudinary görüntüsü alınamadı.").slice(0,400)});
  }
}


function bearerToken(request) {
  const value = request.headers.authorization;
  if (typeof value !== "string" || value.length > 8_192) return "";
  const match = /^Bearer ([^\s]+)$/.exec(value);
  return match?.[1] || "";
}

async function handleReportUpload(request, response, route) {
  if (request.method !== "POST") {
    jsonResponse(response, 405, { ok: false, error: "Yalnızca POST kabul edilir." }, { Allow: "POST" });
    request.resume();
    return;
  }

  const token = bearerToken(request);
  if (!token) {
    jsonResponse(response, 401, { ok: false, error: "Rapor aktarım kimliği doğrulanamadı." });
    request.resume();
    return;
  }

  const configuredRelayToken = process.env.REPORT_RELAY_TOKEN;
  if (
    configuredRelayToken
    && (
      configuredRelayToken.length > 8_192
      || Buffer.byteLength(token) !== Buffer.byteLength(configuredRelayToken)
      || !timingSafeEqual(Buffer.from(token), Buffer.from(configuredRelayToken))
    )
  ) {
    jsonResponse(response, 401, { ok: false, error: "Rapor aktarım kimliği doğrulanamadı." });
    request.resume();
    return;
  }

  const contentType = String(request.headers["content-type"] || "").split(";")[0].trim().toLowerCase();
  const contentEncoding = String(request.headers["content-encoding"] || "").trim().toLowerCase();
  const acceptedTypes = route.acceptedContentTypes || [route.contentType];
  if (!acceptedTypes.includes(contentType)) {
    jsonResponse(response, 415, { ok: false, error: route.kind.startsWith("image_")
      ? "Görüntü içerik türü PNG/JPEG olmalıdır."
      : "Rapor içerik türü beklenen biçimde değil." });
    request.resume();
    return;
  }
  if (contentEncoding !== (route.encoding || "")) {
    jsonResponse(response, 415, { ok: false, error: route.kind.startsWith("image_")
      ? "Görüntü aktarımında Content-Encoding kullanılmamalıdır."
      : "Rapor sıkıştırma biçimi beklenen biçimde değil." });
    request.resume();
    return;
  }

  let imageFilename = null;
  if (route.kind === "image_stage") {
    imageFilename = decodeImageFilename(request.headers["x-image-name-b64"]);
    if (!imageFilename || !imageFilenameMatchesType(imageFilename, contentType)) {
      jsonResponse(response, 400, { ok: false, error: "Dosya adı metadata'sı veya uzantısı içerik türüyle eşleşmiyor." });
      request.resume();
      return;
    }
  }

  const maxBodyBytes = Number.isSafeInteger(route.maxBodyBytes) ? route.maxBodyBytes : REPORT_MAX_BODY_BYTES;
  const declaredLength = request.headers["content-length"];
  if (declaredLength !== undefined && (!/^\d+$/.test(String(declaredLength)) || Number(declaredLength) > maxBodyBytes)) {
    jsonResponse(response, 413, { ok: false, error: route.kind.startsWith("image_")
      ? "Görüntü boyut sınırını aşıyor."
      : "Rapor boyut sınırını aşıyor." });
    request.resume();
    return;
  }

  const retryAfter = checkReportRateLimit(clientIp(request));
  if (retryAfter > 0) {
    jsonResponse(response, 429, { ok: false, error: "Rapor aktarım istek sınırına ulaşıldı." }, {
      "Retry-After": String(retryAfter),
    });
    request.resume();
    return;
  }

  let body;
  try {
    body = await readLimitedBody(request, maxBodyBytes);
  } catch (error) {
    request.resume();
    jsonResponse(response, error.status || 400, { ok: false, error: error.status === 413 ? (route.kind.startsWith("image_") ? "Görüntü boyut sınırını aşıyor." : error.message) : "Aktarım gövdesi okunamadı." });
    return;
  }

  if (route.kind === "image_stage" && !imageBodyMatchesType(body, contentType)) {
    jsonResponse(response, 400, { ok: false, error: "Dosya imzası PNG/JPEG içerik türüyle eşleşmiyor." });
    return;
  }

  const requestId = randomUUID();
  const upstreamToken = process.env.CLOUDFLARE_REPORT_TOKEN || token;
  const headers = {
    "Authorization": "Bearer " + upstreamToken,
    "Accept": "application/json",
    "Content-Type": (route.contentType || contentType) + ((route.contentType || contentType) === "application/json" ? "; charset=utf-8" : ""),
    "User-Agent": "FirsatKontrolReportRelay/1.0",
    "X-Request-ID": requestId,
  };
  if (route.encoding) headers["Content-Encoding"] = route.encoding;
  if (route.kind === "image_stage") headers["X-Image-Name-B64"] = String(request.headers["x-image-name-b64"]);

  let upstream;
  let responseText;
  try {
    upstream = await fetch(REPORT_WORKER_BASE_URL + route.workerPath, {
      method: "POST",
      headers,
      body,
      redirect: "manual",
      signal: AbortSignal.timeout(25_000),
    });
    responseText = await upstream.text();
  } catch (error) {
    jsonResponse(response, 502, {
      ok: false,
      error: error?.name === "TimeoutError"
        ? "Cloudflare rapor deposuna iletim zaman aşımına uğradı."
        : "Cloudflare rapor deposuna iletim başarısız.",
      report_kind: route.kind,
      request_id: requestId,
    });
    return;
  }

  let result = {};
  try {
    result = responseText ? JSON.parse(responseText) : {};
  } catch {
    jsonResponse(response, 502, {
      ok: false,
      error: "Cloudflare rapor deposu beklenen JSON yanıtını vermedi.",
      report_kind: route.kind,
      request_id: requestId,
    });
    return;
  }

  if (!upstream.ok || result?.ok !== true) {
    const status = upstream.status >= 400 && upstream.status < 500 ? upstream.status : 502;
    jsonResponse(response, status, {
      ok: false,
      error: typeof result?.error === "string" ? result.error.slice(0, 400) : "Cloudflare rapor deposu yüklemeyi onaylamadı.",
      report_kind: route.kind,
      request_id: requestId,
    });
    return;
  }

  jsonResponse(response, 200, {
    ...result,
    ok: true,
    report_kind: route.kind,
    request_id: requestId,
    relay: "render",
    forwarded_at_utc: new Date().toISOString(),
  });
}

async function handleHttp(request, response) {
  let url;
  try {
    url = new URL(request.url || "/", "https://relay.invalid");
  } catch {
    jsonResponse(response, 400, { error: "Geçersiz URL." });
    return;
  }

  if (url.pathname === "/healthz") {
    if (request.method !== "GET") {
      jsonResponse(response, 405, { error: "Yalnızca GET kabul edilir." }, { Allow: "GET" });
      return;
    }
    jsonResponse(response, 200, {
      ok: true,
      service: "firsat-kontrol-market-relay",
      version: 2,
    });
    return;
  }

  if (url.pathname === "/ws/binance/stream") {
    jsonResponse(response, 426, { error: "Bu yol yalnızca WebSocket bağlantısı içindir." }, {
      Upgrade: "websocket",
    });
    return;
  }

  const imageUploadRoute = resolveImageUploadRoute(url.pathname);
  if (imageUploadRoute) {
    await handleCloudinaryImageUpload(request, response, imageUploadRoute);
    return;
  }
  if (url.pathname === "/images/manifest") {
    await handleCloudinaryImageManifest(request, response);
    return;
  }
  const imageMatch = /^\/images\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.exec(url.pathname);
  if (imageMatch) {
    await handleCloudinaryImageDownload(request, response, imageMatch[1]);
    return;
  }

  const reportRoute = REPORT_UPLOAD_ROUTES.get(url.pathname);
  if (reportRoute) {
    await handleReportUpload(request, response, reportRoute);
    return;
  }

  if (request.method !== "GET") {
    jsonResponse(response, 405, { error: "Yalnızca GET kabul edilir." }, { Allow: "GET" });
    return;
  }

  const route = resolveRestRoute(url.pathname);
  if (!route) {
    jsonResponse(response, 404, { error: "Endpoint izin listesinde değil." });
    return;
  }

  const retryAfter = checkRestRateLimit(clientIp(request));
  if (retryAfter > 0) {
    jsonResponse(response, 429, { error: "İstek sınırına ulaşıldı; sonra tekrar deneyin." }, {
      "Retry-After": String(retryAfter),
    });
    return;
  }

  const invalidQuery = validateRestQuery(route, url.searchParams);
  if (invalidQuery) {
    jsonResponse(response, 400, { error: invalidQuery });
    return;
  }

  const ttl = cacheTtlMs(route, url.searchParams);
  const cacheKey = route.exchange + ":" + route.path + "?" + url.searchParams.toString();
  if (ttl > 0) {
    const cached = readCache(cacheKey);
    if (cached) {
      response.writeHead(cached.status, {
        "Content-Type": cached.contentType,
        "Cache-Control": cached.cacheControl,
        "X-Content-Type-Options": "nosniff",
        "Access-Control-Allow-Origin": "*",
        "X-Firsat-Relay-Cache": "HIT",
        "X-Firsat-Relay-Upstream": cached.upstreamHost,
      });
      response.end(cached.body);
      return;
    }
  }

  const result = await fetchPublicMarketData(route, url);
  const headers = {
    "Content-Type": result.contentType,
    "Cache-Control": result.cacheControl,
    "X-Content-Type-Options": "nosniff",
    "Access-Control-Allow-Origin": "*",
    "X-Firsat-Relay-Cache": "MISS",
    "X-Firsat-Relay-Upstream": result.upstreamHost,
  };
  response.writeHead(result.status, headers);
  response.end(result.body);

  if (result.status >= 200 && result.status < 300 && ttl > 0) {
    writeCache(cacheKey, { ...result, expiresAt: Date.now() + ttl });
  }
}

function writeUpgradeError(socket, status, message) {
  const phrase = status === 429 ? "Too Many Requests" : "Bad Request";
  const body = JSON.stringify({ error: message });
  socket.write(
    "HTTP/1.1 " + status + " " + phrase + "\r\n"
    + "Content-Type: application/json\r\n"
    + "Content-Length: " + Buffer.byteLength(body) + "\r\n"
    + "Connection: close\r\n\r\n" + body,
  );
  socket.destroy();
}

function acquireWebSocketSlot(ip) {
  const current = ACTIVE_WS_BY_IP.get(ip) || 0;
  if (current >= MAX_WS_PER_IP || activeWebSocketCount >= MAX_WS_GLOBAL) return false;
  ACTIVE_WS_BY_IP.set(ip, current + 1);
  activeWebSocketCount += 1;
  return true;
}

function releaseWebSocketSlot(ip) {
  const current = ACTIVE_WS_BY_IP.get(ip) || 0;
  if (current <= 1) ACTIVE_WS_BY_IP.delete(ip);
  else ACTIVE_WS_BY_IP.set(ip, current - 1);
  activeWebSocketCount = Math.max(0, activeWebSocketCount - 1);
}

function bridgeBinanceStream(client, streams) {
  let closed = false;
  let upstream = null;
  let endpointIndex = 0;

  const cleanup = () => {
    if (closed) return;
    closed = true;
    if (upstream && upstream.readyState !== WebSocket.CLOSED) {
      try {
        upstream.close();
      } catch {
        upstream.terminate();
      }
    }
  };

  client.on("close", cleanup);
  client.on("error", cleanup);

  const tryNextEndpoint = () => {
    if (closed || client.readyState !== WebSocket.OPEN) return;
    if (endpointIndex >= BINANCE_WS_ORIGINS.length) {
      client.close(1013, "Binance public stream is unavailable");
      return;
    }

    const origin = BINANCE_WS_ORIGINS[endpointIndex++];
    const target = origin + "/stream?streams=" + streams;
    let opened = false;
    let fallbackStarted = false;
    let connectTimer;

    const next = () => {
      if (opened || fallbackStarted || closed) return;
      fallbackStarted = true;
      clearTimeout(connectTimer);
      try {
        upstream?.terminate();
      } catch {
        // Retry only against the next allowlisted official public stream host.
      }
      setTimeout(tryNextEndpoint, 100);
    };

    upstream = new WebSocket(target, {
      handshakeTimeout: 7_000,
      maxPayload: 2 * 1024 * 1024,
      perMessageDeflate: false,
      headers: { "User-Agent": "FirsatKontrolMarketRelay/1.0" },
    });

    connectTimer = setTimeout(() => {
      if (!opened) next();
    }, 7_500);

    upstream.on("open", () => {
      if (fallbackStarted || closed) {
        upstream.close();
        return;
      }
      opened = true;
      clearTimeout(connectTimer);
      upstream.on("message", (data, isBinary) => {
        if (client.readyState === WebSocket.OPEN) client.send(data, { binary: isBinary });
      });
      upstream.on("error", () => {
        if (client.readyState === WebSocket.OPEN) client.close(1011, "Upstream stream error");
      });
    });

    upstream.on("error", () => {
      if (!opened) next();
    });

    upstream.on("close", () => {
      clearTimeout(connectTimer);
      if (!opened) next();
      else if (!closed && client.readyState === WebSocket.OPEN) {
        client.close(1011, "Upstream stream closed");
      }
    });
  };

  tryNextEndpoint();
}

export function createRelayServer() {
  const server = http.createServer((request, response) => {
    handleHttp(request, response).catch(() => {
      if (!response.headersSent) {
        jsonResponse(response, 502, { error: "Piyasa verisi isteği tamamlanamadı." });
      } else {
        response.destroy();
      }
    });
  });

  const webSocketServer = new WebSocketServer({
    noServer: true,
    maxPayload: 64 * 1024,
    perMessageDeflate: false,
  });

  server.on("upgrade", (request, socket, head) => {
    let url;
    try {
      url = new URL(request.url || "/", "https://relay.invalid");
    } catch {
      writeUpgradeError(socket, 400, "Geçersiz WebSocket URL.");
      return;
    }

    if (request.method !== "GET" || url.pathname !== "/ws/binance/stream") {
      writeUpgradeError(socket, 400, "WebSocket endpoint izin listesinde değil.");
      return;
    }
    if (
      url.searchParams.getAll("streams").length !== 1
      || [...url.searchParams.keys()].some((key) => key !== "streams")
    ) {
      writeUpgradeError(socket, 400, "Yalnızca tek streams parametresi kabul edilir.");
      return;
    }

    const streams = url.searchParams.get("streams");
    const streamError = validateWebSocketStreams(streams);
    if (streamError) {
      writeUpgradeError(socket, 400, streamError);
      return;
    }

    const ip = clientIp(request);
    if (!acquireWebSocketSlot(ip)) {
      writeUpgradeError(socket, 429, "WebSocket bağlantı sınırına ulaşıldı.");
      return;
    }

    webSocketServer.handleUpgrade(request, socket, head, (client) => {
      let released = false;
      const release = () => {
        if (released) return;
        released = true;
        releaseWebSocketSlot(ip);
      };
      client.once("close", release);
      client.once("error", release);
      webSocketServer.emit("connection", client, request);
      bridgeBinanceStream(client, streams);
    });
  });

  return server;
}

const invokedAsMain = process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href;

if (invokedAsMain) {
  const server = createRelayServer();
  server.listen(PORT, "0.0.0.0", () => {
    console.log("Fırsat Kontrol piyasa geçidi " + PORT + " portunda hazır.");
  });
}
