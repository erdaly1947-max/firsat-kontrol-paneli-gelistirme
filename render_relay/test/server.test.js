import test from "node:test";
import assert from "node:assert/strict";
import {
  BINANCE_REST_ORIGINS,
  cacheTtlMs,
  createRelayServer,
  cloudinaryConfiguration,
  resolveImageUploadRoute,
  resolveReportUploadRoute,
  resolveRestRoute,
  validateRestQuery,
  validateWebSocketStreams,
} from "../server.js";



test("Cloudinary configuration trims invisible outer whitespace from copied credentials", () => {
  const names = ["CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"];
  const previous = Object.fromEntries(names.map((name) => [name, process.env[name]]));
  process.env.CLOUDINARY_CLOUD_NAME = "  CCY85JMZ  ";
  process.env.CLOUDINARY_API_KEY = "  test-api-key  ";
  process.env.CLOUDINARY_API_SECRET = "  test-api-secret  ";
  try {
    assert.deepEqual(cloudinaryConfiguration(), {
      cloudName: "CCY85JMZ",
      apiKey: "test-api-key",
      apiSecret: "test-api-secret",
    });
  } finally {
    for (const name of names) {
      if (previous[name] === undefined) delete process.env[name];
      else process.env[name] = previous[name];
    }
  }
});

test("only explicitly allowlisted public-market endpoints resolve", () => {
  assert.ok(resolveRestRoute("/binance/api/v3/exchangeInfo"));
  assert.ok(resolveRestRoute("/binance/api/v3/klines"));
  assert.ok(resolveRestRoute("/btcturk/api/v2/server/exchangeinfo"));
  assert.equal(resolveRestRoute("/binance/api/v3/account"), null);
  assert.equal(resolveRestRoute("/proxy"), null);
});

test("Binance candle route requires a safe symbol and interval", () => {
  const route = resolveRestRoute("/binance/api/v3/klines");
  assert.equal(validateRestQuery(route, new URLSearchParams("symbol=BTCUSDT&interval=1h&limit=90")), null);
  assert.notEqual(validateRestQuery(route, new URLSearchParams("symbol=BTCUSDT&interval=1h&url=https://example.com")), null);
  assert.notEqual(validateRestQuery(route, new URLSearchParams("symbol=BTCUSDT&symbol=ETHUSDT&interval=1h")), null);
  assert.notEqual(validateRestQuery(route, new URLSearchParams("symbol=BTCUSDT&interval=not-an-interval")), null);
  assert.notEqual(validateRestQuery(route, new URLSearchParams("symbol=BTCUSDT&interval=1h&limit=99999")), null);
});

test("BtcTurk ticker proxy is limited to its public USDT ticker", () => {
  const route = resolveRestRoute("/btcturk/api/v2/ticker/currency");
  assert.equal(validateRestQuery(route, new URLSearchParams("symbol=usdt")), null);
  assert.notEqual(validateRestQuery(route, new URLSearchParams("symbol=btc")), null);
  assert.notEqual(validateRestQuery(route, new URLSearchParams("symbol=usdt&url=https://example.com")), null);
});

test("only the desktop radar's public kline WebSocket streams are accepted", () => {
  assert.equal(
    validateWebSocketStreams("btcusdt@kline_5m/ethusdt@kline_1h/bnbusdt@kline_1M"),
    null,
  );
  assert.notEqual(validateWebSocketStreams(""), null);
  assert.notEqual(validateWebSocketStreams("btcusdt@trade"), null);
  assert.notEqual(validateWebSocketStreams("btcusdt@kline_1h/../account"), null);
  assert.notEqual(validateWebSocketStreams("btcusdt@kline_1h/btcusdt@kline_1h"), null);
});

test("official Binance REST fallback hosts are fixed, and cache TTLs vary by endpoint", () => {
  assert.deepEqual(BINANCE_REST_ORIGINS, [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
  ]);
  assert.equal(cacheTtlMs(resolveRestRoute("/binance/api/v3/exchangeInfo"), new URLSearchParams()), 300_000);
  assert.equal(cacheTtlMs(resolveRestRoute("/binance/api/v3/klines"), new URLSearchParams("symbol=BTCUSDT&interval=1h")), 5_000);
  assert.equal(cacheTtlMs(resolveRestRoute("/binance/api/v3/klines"), new URLSearchParams("symbol=BTCUSDT&interval=1h&startTime=1")), 30_000);
});


test("image relay routes have a separate 15 MiB limit while report uploads remain at 8 MiB", () => {
  const stage = resolveImageUploadRoute("/api/images/stage");
  const commit = resolveImageUploadRoute("/api/images/commit");
  const abort = resolveImageUploadRoute("/api/images/abort");
  const report = resolveReportUploadRoute("/api/report");
  assert.equal(stage.kind, "image_stage");
  assert.deepEqual(stage.acceptedContentTypes, ["image/png", "image/jpeg"]);
  assert.equal(stage.maxBodyBytes, 15 * 1024 * 1024);
  assert.equal(resolveReportUploadRoute("/api/images/stage"), null);
  assert.equal(commit.maxBodyBytes, 64 * 1024);
  assert.equal(abort.maxBodyBytes, 64 * 1024);
  assert.equal(report.maxBodyBytes, undefined);
});

test("image relay validates bearer auth, filename metadata and file signature", async (t) => {
  const server = createRelayServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  t.after(() => new Promise((resolve) => server.close(() => resolve())));
  const base = "http://127.0.0.1:" + server.address().port;
  const png = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1]);

  const unauthenticated = await fetch(base + "/api/images/stage", {
    method: "POST",
    headers: {
      "Content-Type": "image/png",
      "X-Image-Name-B64": Buffer.from("chart.png").toString("base64url"),
    },
    body: png,
  });
  assert.equal(unauthenticated.status, 401);

  const wrongName = await fetch(base + "/api/images/stage", {
    method: "POST",
    headers: {
      Authorization: "Bearer test-token",
      "Content-Type": "image/png",
      "X-Image-Name-B64": Buffer.from("chart.jpg").toString("base64url"),
    },
    body: png,
  });
  assert.equal(wrongName.status, 400);

  const wrongSignature = await fetch(base + "/api/images/stage", {
    method: "POST",
    headers: {
      Authorization: "Bearer test-token",
      "Content-Type": "image/png",
      "X-Image-Name-B64": Buffer.from("chart.png").toString("base64url"),
    },
    body: Buffer.from([1, 2, 3, 4]),
  });
  assert.equal(wrongSignature.status, 400);
});

test("image relay rejects more than 15 MiB while report endpoints retain 8 MiB", async (t) => {
  const server = createRelayServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  t.after(() => new Promise((resolve) => server.close(() => resolve())));
  const base = "http://127.0.0.1:" + server.address().port;
  const largeImage = Buffer.alloc(15 * 1024 * 1024 + 1);
  largeImage.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const imageResponse = await fetch(base + "/api/images/stage", {
    method: "POST",
    headers: {
      Authorization: "Bearer test-token",
      "Content-Type": "image/png",
      "X-Image-Name-B64": Buffer.from("large.png").toString("base64url"),
    },
    body: largeImage,
  });
  assert.equal(imageResponse.status, 413);

  const largeReport = Buffer.alloc(8 * 1024 * 1024 + 1);
  const reportResponse = await fetch(base + "/api/report", {
    method: "POST",
    headers: {
      Authorization: "Bearer test-token",
      "Content-Type": "application/json",
      "Content-Encoding": "gzip",
    },
    body: largeReport,
  });
  assert.equal(reportResponse.status, 413);
});
