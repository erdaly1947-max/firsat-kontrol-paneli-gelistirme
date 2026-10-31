import WebSocket from "ws";

const stream = "btcusdt@kline_1m";
const endpoints = [
  "wss://data-stream.binance.vision:443/stream?streams=" + stream,
  "wss://stream.binance.com:443/stream?streams=" + stream,
  "wss://stream.binance.com:9443/stream?streams=" + stream,
];
const HANDSHAKE_TIMEOUT_MS = 8_000;
const LIVE_MESSAGE_TIMEOUT_MS = 12_000;

function verifyEndpoint(endpoint) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(endpoint, {
      handshakeTimeout: HANDSHAKE_TIMEOUT_MS,
      perMessageDeflate: false,
      maxPayload: 1024 * 1024,
    });
    let opened = false;
    let completed = false;
    const timer = setTimeout(() => {
      finish(new Error(
        opened
          ? "WebSocket açıldı ancak canlı kline mesajı gelmedi."
          : "WebSocket el sıkışması zaman aşımına uğradı."
      ));
    }, HANDSHAKE_TIMEOUT_MS + LIVE_MESSAGE_TIMEOUT_MS);

    function finish(error) {
      if (completed) return;
      completed = true;
      clearTimeout(timer);
      try { ws.terminate(); } catch {}
      if (error) reject(error);
      else resolve();
    }

    ws.on("open", () => {
      opened = true;
      console.log("BINANCE_DIRECT_WEBSOCKET_HANDSHAKE_OK endpoint=" + new URL(endpoint).host);
    });

    ws.on("message", (raw) => {
      let envelope;
      try {
        envelope = JSON.parse(raw.toString());
      } catch (error) {
        finish(new Error("Binance WebSocket geçerli JSON göndermedi: " + error.message));
        return;
      }

      const payload = envelope?.data ?? envelope;
      if (payload?.e !== "kline" || !payload?.k) return;

      const candle = payload.k;
      if (
        candle.s !== "BTCUSDT"
        || candle.i !== "1m"
        || !Number.isSafeInteger(Number(candle.t))
      ) {
        finish(new Error("Binance canlı mum mesajı beklenen BTCUSDT/1m verisi değil."));
        return;
      }

      console.log(
        "BINANCE_DIRECT_WEBSOCKET_KLINE_OK symbol=" + candle.s
        + " interval=" + candle.i
        + " eventTime=" + String(payload.E ?? "unknown")
      );
      finish();
    });

    ws.on("error", (error) => {
      finish(new Error("Binance doğrudan WebSocket bağlantısı başarısız: " + error.message));
    });

    ws.on("close", (code, reason) => {
      if (!completed) {
        finish(new Error(
          "Canlı mum alınmadan WebSocket kapandı: "
          + code + " " + reason.toString()
        ));
      }
    });
  });
}

const failures = [];
for (const endpoint of endpoints) {
  try {
    await verifyEndpoint(endpoint);
    console.log("BINANCE_DIRECT_WEBSOCKET_LIVE_OK");
    process.exit(0);
  } catch (error) {
    const detail = error?.message || String(error);
    failures.push(new URL(endpoint).host + ": " + detail);
    console.warn("BINANCE_DIRECT_WEBSOCKET_ENDPOINT_FAILED " + failures.at(-1));
  }
}

throw new Error(
  "Binance'in hiçbir doğrudan WebSocket adresinden canlı mum alınamadı. "
  + failures.join(" | ")
);
