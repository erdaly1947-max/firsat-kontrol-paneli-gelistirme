import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/index.js", import.meta.url), "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source, "utf8").toString("base64")}`;
const { default: worker } = await import(moduleUrl);

function makeR2Bucket() {
  const store = new Map();
  let nextEtag = 1;
  return {
    failImageCopies: false,
    failManifestWrites: false,
    failDeleteKeys: new Set(),
    _store: store,
    async put(key, value, options = {}) {
      if (this.failImageCopies && key.startsWith("images/")) throw new Error("injected image-copy failure");
      if (this.failManifestWrites && key === "meta/active-images.json") throw new Error("injected manifest failure");
      const current = store.get(key);
      const conditions = options.onlyIf || {};
      if (conditions.etagMatches && current?.etag !== conditions.etagMatches) return null;
      if (conditions.etagDoesNotMatch === "*" && current) return null;
      let bytes;
      if (value instanceof ReadableStream) {
        bytes = new Uint8Array(await new Response(value).arrayBuffer());
      } else if (value instanceof ArrayBuffer) {
        bytes = new Uint8Array(value.slice(0));
      } else if (ArrayBuffer.isView(value)) {
        bytes = new Uint8Array(value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength));
      } else if (typeof value === "string") {
        bytes = new TextEncoder().encode(value);
      } else {
        throw new TypeError("unsupported mock R2 body");
      }
      const stored = {
        key, bytes, size: bytes.byteLength, etag: "mock-etag-" + nextEtag++,
        uploaded: new Date(),
        customMetadata: { ...(options.customMetadata || {}) },
        httpMetadata: { ...(options.httpMetadata || {}) },
      };
      store.set(key, stored);
      return { key, size: stored.size, etag: stored.etag, uploaded: stored.uploaded,
        customMetadata: stored.customMetadata, httpMetadata: stored.httpMetadata };
    },
    async get(key) {
      const stored = store.get(key);
      if (!stored) return null;
      const bytes = stored.bytes;
      return {
        key, size: stored.size, etag: stored.etag, uploaded: stored.uploaded,
        customMetadata: stored.customMetadata, httpMetadata: stored.httpMetadata,
        body: new Blob([bytes]).stream(),
        async text() { return new TextDecoder().decode(bytes); },
        async arrayBuffer() { return bytes.slice().buffer; },
      };
    },
    async head(key) {
      const stored = store.get(key);
      return stored ? { key, size: stored.size, etag: stored.etag, uploaded: stored.uploaded,
        customMetadata: stored.customMetadata, httpMetadata: stored.httpMetadata } : null;
    },
    async delete(keys) {
      for (const key of Array.isArray(keys) ? keys : [keys]) {
        if (this.failDeleteKeys.has(key)) throw new Error("injected delete failure");
        store.delete(key);
      }
    },
    async list({ prefix = "", limit = 1000 } = {}) {
      const objects = [...store.values()].filter((item) => item.key.startsWith(prefix)).slice(0, limit)
        .map((item) => ({ key: item.key, size: item.size, etag: item.etag, uploaded: item.uploaded,
          customMetadata: item.customMetadata, httpMetadata: item.httpMetadata }));
      return { objects, truncated: false, cursor: "" };
    },
  };
}

function makeEnv() {
  const store = new Map();
  return {
    UPLOAD_TOKEN: "test-upload-token",
    IMAGES_BUCKET: makeR2Bucket(),
    ANALYSIS_REPORTS: {
      async put(key, value, options = {}) {
        const bytes = new Uint8Array(value);
        const copy = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        store.set(key, { value: copy, metadata: options.metadata || {} });
      },
      async getWithMetadata(key) {
        return store.get(key) || { value: null, metadata: null };
      },
    },
  };
}

function makeReport(overrides = {}) {
  const candidates = [{ symbol: "ABCUSDT", final_decision: "İZLE" }];
  return {
    report_type: "analysis",
    schema_version: 1,
    generated_at_utc: "2026-10-26T12:00:00Z",
    candidate_count: candidates.length,
    candidates,
    ...overrides,
  };
}

function gzipJson(value) {
  const stream = new Blob([JSON.stringify(value)]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Response(stream).arrayBuffer();
}

function uploadRequest(body, { token = "test-upload-token", encoding = "gzip" } = {}) {
  const headers = { "Content-Type": "application/json", "Content-Encoding": encoding };
  if (token !== null) headers.Authorization = `Bearer ${token}`;
  return new Request("https://reports.test/api/report", {
    method: "POST",
    headers,
    body,
  });
}

test("health and preflight endpoints respond", async () => {
  const env = makeEnv();
  const health = await worker.fetch(new Request("https://reports.test/health"), env);
  assert.equal(health.status, 200);
  assert.equal((await health.json()).service, "analysis-report-store");

  const preflight = await worker.fetch(new Request("https://reports.test/api/report", { method: "OPTIONS" }), env);
  assert.equal(preflight.status, 204);
  assert.equal(preflight.headers.get("Access-Control-Allow-Origin"), "*");
});

test("upload requires the correct bearer token and gzip content encoding", async () => {
  const env = makeEnv();
  const body = await gzipJson(makeReport());
  const unauthorized = await worker.fetch(uploadRequest(body, { token: "wrong" }), env);
  assert.equal(unauthorized.status, 401);

  const unsupported = await worker.fetch(uploadRequest(body, { encoding: "identity" }), env);
  assert.equal(unsupported.status, 415);
});

test("invalid gzip/JSON and invalid report schema are rejected", async () => {
  const env = makeEnv();
  const badGzip = await worker.fetch(uploadRequest(new TextEncoder().encode("not gzip")), env);
  assert.equal(badGzip.status, 400);

  const invalidSchema = makeReport({ schema_version: 2 });
  const response = await worker.fetch(uploadRequest(await gzipJson(invalidSchema)), env);
  assert.equal(response.status, 422);
});

test("valid report is stored compressed and /latest returns readable JSON", async () => {
  const env = makeEnv();
  const report = makeReport({
    candidates: [
      { symbol: "ABCUSDT", final_decision: "İZLE" },
      { symbol: "XYZUSDT", final_decision: "GİRİŞ KOŞULU BEKLE" },
    ],
    candidate_count: 2,
  });
  const response = await worker.fetch(uploadRequest(await gzipJson(report)), env);
  assert.equal(response.status, 201);
  const upload = await response.json();
  assert.equal(upload.ok, true);
  assert.equal(upload.candidate_count, 2);
  assert.match(upload.sha256, /^[0-9a-f]{64}$/);
  assert.equal(upload.read_url, "https://reports.test/latest");

  const latest = await worker.fetch(new Request("https://reports.test/latest"), env);
  assert.equal(latest.status, 200);
  assert.deepEqual(await latest.json(), report);
  assert.equal(latest.headers.get("X-Report-SHA256"), upload.sha256);
  assert.equal(latest.headers.get("Cache-Control"), "no-store, max-age=0");
});

test("latest is 404 before first upload and unknown routes are 404", async () => {
  const env = makeEnv();
  const latest = await worker.fetch(new Request("https://reports.test/latest"), env);
  assert.equal(latest.status, 404);
  const missing = await worker.fetch(new Request("https://reports.test/not-found"), env);
  assert.equal(missing.status, 404);
});

test("compressed upload size is bounded", async () => {
  const env = makeEnv();
  const oversized = new Uint8Array(8 * 1024 * 1024 + 1);
  const response = await worker.fetch(uploadRequest(oversized), env);
  assert.equal(response.status, 413);
});

test("daily and troubleshooting JSON reports have separate upload and read routes", async () => {
  const env = makeEnv();
  const daily = {
    report_type: "daily",
    schema_version: 1,
    report_generated_at_utc: "2026-10-26T12:10:00Z",
    payload: {
      report_generated_at_utc: "2026-10-26T12:10:00Z",
      state: { status: "RUNNING", candidates: [] },
      diagnostics: { application: "FIRSAT-KONTROL PANELİ" },
    },
    markdown: "# Daily report",
  };
  const dailyUpload = await worker.fetch(
    new Request("https://reports.test/api/report/daily", {
      method: "POST",
      headers: { Authorization: "Bearer test-upload-token", "Content-Type": "application/json", "Content-Encoding": "gzip" },
      body: await gzipJson(daily),
    }),
    env,
  );
  assert.equal(dailyUpload.status, 201);
  assert.equal((await dailyUpload.json()).read_url, "https://reports.test/daily");
  const dailyRead = await worker.fetch(new Request("https://reports.test/daily"), env);
  assert.equal(dailyRead.status, 200);
  assert.deepEqual(await dailyRead.json(), daily);

  const troubleshooting = {
    report_type: "troubleshooting",
    schema_version: 1,
    generated_at_utc: "2026-10-26T12:11:00Z",
    daily_report: daily,
    diagnostics: { status: "RUNNING" },
    manifest: { files: [{ name: "manifest.json", size_bytes: 12, sha256: "abc" }] },
    log_tail: "test log line",
  };
  const upload = await worker.fetch(
    new Request("https://reports.test/api/report/troubleshooting", {
      method: "POST",
      headers: { Authorization: "Bearer test-upload-token", "Content-Type": "application/json", "Content-Encoding": "gzip" },
      body: await gzipJson(troubleshooting),
    }),
    env,
  );
  assert.equal(upload.status, 201);
  assert.equal((await upload.json()).read_url, "https://reports.test/troubleshooting");
  const read = await worker.fetch(new Request("https://reports.test/troubleshooting"), env);
  assert.equal(read.status, 200);
  assert.deepEqual(await read.json(), troubleshooting);
});

test("troubleshooting ZIP can be uploaded and downloaded without replacing JSON reports", async () => {
  const env = makeEnv();
  const archive = new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0x01, 0x02, 0x03]);
  const upload = await worker.fetch(
    new Request("https://reports.test/api/report/troubleshooting-zip", {
      method: "POST",
      headers: { Authorization: "Bearer test-upload-token", "Content-Type": "application/zip" },
      body: archive,
    }),
    env,
  );
  assert.equal(upload.status, 201);
  assert.equal((await upload.json()).read_url, "https://reports.test/troubleshooting.zip");
  const download = await worker.fetch(new Request("https://reports.test/troubleshooting.zip"), env);
  assert.equal(download.status, 200);
  assert.equal(download.headers.get("Content-Type"), "application/zip");
  assert.deepEqual(new Uint8Array(await download.arrayBuffer()), archive);
  const missingDailyBeforeUpload = await worker.fetch(new Request("https://reports.test/daily"), makeEnv());
  assert.equal(missingDailyBeforeUpload.status, 404);
});

test("new report routes require bearer auth and ZIP content type", async () => {
  const env = makeEnv();
  const unauthorized = await worker.fetch(
    new Request("https://reports.test/api/report/daily", {
      method: "POST",
      headers: { Authorization: "Bearer wrong", "Content-Type": "application/json", "Content-Encoding": "gzip" },
      body: await gzipJson({
        report_type: "daily", schema_version: 1, report_generated_at_utc: "2026-10-26T12:00:00Z",
        payload: { state: {}, diagnostics: {} },
      }),
    }),
    env,
  );
  assert.equal(unauthorized.status, 401);
  const wrongContentType = await worker.fetch(
    new Request("https://reports.test/api/report/troubleshooting-zip", {
      method: "POST",
      headers: { Authorization: "Bearer test-upload-token", "Content-Type": "application/octet-stream" },
      body: new Uint8Array([0x50, 0x4b, 0x03, 0x04]),
    }),
    env,
  );
  assert.equal(wrongContentType.status, 415);
});


function imageStageRequest(filename, bytes, contentType = "image/png", token = "test-upload-token") {
  const headers = {
    "Content-Type": contentType,
    "X-Image-Name-B64": Buffer.from(filename, "utf8").toString("base64url"),
  };
  if (token !== null) headers.Authorization = "Bearer " + token;
  return new Request("https://reports.test/api/images/stage", {
    method: "POST", headers, body: bytes,
  });
}

function pngHeader(extra = []) {
  return new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, ...extra]);
}

async function stagePng(env, filename = "chart.png") {
  const response = await worker.fetch(imageStageRequest(filename, pngHeader([1, 2, 3])), env);
  assert.equal(response.status, 201);
  return (await response.json()).staged_id;
}

async function commitImages(env, ids) {
  return worker.fetch(new Request("https://reports.test/api/images/commit", {
    method: "POST",
    headers: { Authorization: "Bearer test-upload-token", "Content-Type": "application/json" },
    body: JSON.stringify({ staged_ids: ids }),
  }), env);
}

test("image stage requires auth, a safe filename, matching MIME/signature, and a 15 MiB per-image limit", async () => {
  const env = makeEnv();
  const unauthenticated = await worker.fetch(
    imageStageRequest("chart.png", pngHeader(), "image/png", null), env,
  );
  assert.equal(unauthenticated.status, 401);

  const mismatchName = await worker.fetch(
    imageStageRequest("chart.jpg", pngHeader()), env,
  );
  assert.equal(mismatchName.status, 400);

  const mismatchSignature = await worker.fetch(
    imageStageRequest("chart.png", new Uint8Array([1, 2, 3])), env,
  );
  assert.equal(mismatchSignature.status, 400);

  const wrongMime = await worker.fetch(
    imageStageRequest("chart.gif", pngHeader(), "image/gif"), env,
  );
  assert.equal(wrongMime.status, 415);

  const oversized = new Uint8Array(15 * 1024 * 1024 + 1);
  oversized.set(pngHeader());
  const tooLarge = await worker.fetch(
    imageStageRequest("chart.png", oversized), env,
  );
  assert.equal(tooLarge.status, 413);

  const compressed = await worker.fetch(new Request("https://reports.test/api/images/stage", {
    method: "POST",
    headers: {
      Authorization: "Bearer test-upload-token", "Content-Type": "image/png",
      "Content-Encoding": "gzip", "X-Image-Name-B64": Buffer.from("chart.png").toString("base64url"),
    },
    body: pngHeader(),
  }), env);
  assert.equal(compressed.status, 415);
});

test("image commit caps the active manifest at three and replaces the oldest server-uploaded image", async () => {
  const env = makeEnv();
  const ids = [];
  for (const name of ["one.png", "two.png", "three.png"]) ids.push(await stagePng(env, name));
  const firstCommit = await commitImages(env, ids);
  assert.equal(firstCommit.status, 201);
  const before = await (await worker.fetch(new Request("https://reports.test/images/manifest"), env)).json();
  assert.equal(before.images.length, 3);
  assert.deepEqual(new Set(before.images.map((item) => item.id)), new Set(ids));
  const oldestId = [...before.images].sort((a, b) => Date.parse(a.uploaded_at) - Date.parse(b.uploaded_at))[0].id;
  const newestId = [...before.images].sort((a, b) => Date.parse(b.uploaded_at) - Date.parse(a.uploaded_at))[0].id;

  const replacementId = await stagePng(env, "four.png");
  const replacement = await commitImages(env, [replacementId]);
  assert.equal(replacement.status, 201);
  const after = await (await worker.fetch(new Request("https://reports.test/images/manifest"), env)).json();
  assert.equal(after.images.length, 3);
  assert.ok(after.images.some((item) => item.id === newestId));
  assert.ok(after.images.some((item) => item.id === replacementId));
  assert.ok(!after.images.some((item) => item.id === oldestId));
});

test("only manifest-listed images are publicly readable, and abort deletes staging only", async () => {
  const env = makeEnv();
  const stagedId = await stagePng(env, "visible.png");
  const inactive = await worker.fetch(new Request("https://reports.test/images/" + stagedId), env);
  assert.equal(inactive.status, 404);

  const abort = await worker.fetch(new Request("https://reports.test/api/images/abort", {
    method: "POST",
    headers: { Authorization: "Bearer test-upload-token", "Content-Type": "application/json" },
    body: JSON.stringify({ staged_ids: [stagedId] }),
  }), env);
  assert.equal(abort.status, 200);
  assert.equal(await env.IMAGES_BUCKET.get("staging/" + stagedId), null);
  const manifest = await (await worker.fetch(new Request("https://reports.test/images/manifest"), env)).json();
  assert.deepEqual(manifest.images, []);
});

test("failed staging-group activation preserves the previous manifest and active bytes", async () => {
  const env = makeEnv();
  const firstId = await stagePng(env, "first.png");
  assert.equal((await commitImages(env, [firstId])).status, 201);
  const before = await (await worker.fetch(new Request("https://reports.test/images/manifest"), env)).json();
  const originalBytes = new Uint8Array(await (await worker.fetch(new Request(before.images[0].url), env)).arrayBuffer());

  const secondId = await stagePng(env, "second.png");
  env.IMAGES_BUCKET.failImageCopies = true;
  const failed = await commitImages(env, [secondId]);
  assert.equal(failed.status, 502);
  env.IMAGES_BUCKET.failImageCopies = false;
  const after = await (await worker.fetch(new Request("https://reports.test/images/manifest"), env)).json();
  assert.deepEqual(after.images.map((item) => item.id), before.images.map((item) => item.id));
  const afterBytes = new Uint8Array(await (await worker.fetch(new Request(after.images[0].url), env)).arrayBuffer());
  assert.deepEqual(afterBytes, originalBytes);
});

test("image write routes require auth and existing report uploads still use ANALYSIS_REPORTS KV", async () => {
  const env = makeEnv();
  const unauthenticated = await worker.fetch(new Request("https://reports.test/api/images/commit", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ staged_ids: ["00000000-0000-0000-0000-000000000000"] }),
  }), env);
  assert.equal(unauthenticated.status, 401);

  const report = makeReport();
  const upload = await worker.fetch(uploadRequest(await gzipJson(report)), env);
  assert.equal(upload.status, 201);
  const latest = await worker.fetch(new Request("https://reports.test/latest"), env);
  assert.equal(latest.status, 200);
  assert.deepEqual(await latest.json(), report);
  assert.equal(env.IMAGES_BUCKET._store.has("latest"), false);
});


test("manifest-write failure preserves the previous active image set and removes new copies", async () => {
  const env = makeEnv();
  const firstId = await stagePng(env, "first.png");
  assert.equal((await commitImages(env, [firstId])).status, 201);
  const before = await (await worker.fetch(new Request("https://reports.test/images/manifest"), env)).json();

  const secondId = await stagePng(env, "second.png");
  env.IMAGES_BUCKET.failManifestWrites = true;
  const failed = await commitImages(env, [secondId]);
  assert.equal(failed.status, 502);
  env.IMAGES_BUCKET.failManifestWrites = false;

  const after = await (await worker.fetch(new Request("https://reports.test/images/manifest"), env)).json();
  assert.deepEqual(after.images.map((item) => item.id), before.images.map((item) => item.id));
  assert.equal(await env.IMAGES_BUCKET.get("images/" + secondId), null);
  assert.equal(await env.IMAGES_BUCKET.get("staging/" + secondId), null);
});

test("failed deletion of a replaced image is queued privately and retried on a later request", async () => {
  const env = makeEnv();
  const firstIds = [];
  for (const name of ["one.png", "two.png", "three.png"]) firstIds.push(await stagePng(env, name));
  assert.equal((await commitImages(env, firstIds)).status, 201);
  const before = await (await worker.fetch(new Request("https://reports.test/images/manifest"), env)).json();
  const oldestId = [...before.images].sort((a, b) => Date.parse(a.uploaded_at) - Date.parse(b.uploaded_at))[0].id;
  env.IMAGES_BUCKET.failDeleteKeys.add("images/" + oldestId);

  const replacementId = await stagePng(env, "replacement.png");
  assert.equal((await commitImages(env, [replacementId])).status, 201);
  const replacementManifest = await env.IMAGES_BUCKET.get("meta/active-images.json");
  const queued = JSON.parse(await replacementManifest.text());
  assert.ok(queued.cleanup_ids.includes(oldestId));
  assert.equal(queued.images.length, 3);
  assert.ok(!queued.images.some((item) => item.id === oldestId));
  assert.ok(await env.IMAGES_BUCKET.get("images/" + oldestId));

  const publicResponse = await worker.fetch(new Request("https://reports.test/images/manifest"), env);
  const publicBody = await publicResponse.json();
  assert.equal(publicBody.images.length, 3);
  assert.equal(Object.hasOwn(publicBody, "cleanup_ids"), false);

  env.IMAGES_BUCKET.failDeleteKeys.delete("images/" + oldestId);
  const retryResponse = await worker.fetch(new Request("https://reports.test/images/manifest"), env);
  const retriedBody = await retryResponse.json();
  assert.equal(retriedBody.images.length, 3);
  assert.ok(!retriedBody.images.some((item) => item.id === oldestId));
  assert.equal(await env.IMAGES_BUCKET.get("images/" + oldestId), null);
  const cleanedManifest = JSON.parse(await (await env.IMAGES_BUCKET.get("meta/active-images.json")).text());
  assert.ok(!cleanedManifest.cleanup_ids.includes(oldestId));
});
