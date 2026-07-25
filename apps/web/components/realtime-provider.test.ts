import { describe, expect, it } from "vitest";

import { realtimeUrl } from "./realtime-provider";

describe("realtimeUrl", () => {
  it("connects a directly served local dashboard to the FastAPI port", () => {
    expect(
      realtimeUrl({ protocol: "http:", hostname: "127.0.0.1", port: "3000", host: "127.0.0.1:3000" }),
    ).toBe("ws://127.0.0.1:8000/api/v1/realtime");
  });

  it("uses the public origin behind the production proxy", () => {
    expect(
      realtimeUrl({ protocol: "https:", hostname: "portal.example", port: "", host: "portal.example" }),
    ).toBe("wss://portal.example/api/v1/realtime");
  });

  it("honours an explicit websocket origin", () => {
    expect(
      realtimeUrl(
        { protocol: "https:", hostname: "portal.example", port: "", host: "portal.example" },
        " wss://live.example/ws ",
      ),
    ).toBe("wss://live.example/ws");
  });
});
