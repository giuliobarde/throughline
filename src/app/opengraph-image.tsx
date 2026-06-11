import { ImageResponse } from "next/og";

export const alt = "Throughline — the tech wire, ranked daily";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#0a0a0a",
        }}
      >
        <div style={{ display: "flex", fontSize: 96, fontWeight: 700 }}>
          <span style={{ color: "#fafafa" }}>through</span>
          <span style={{ color: "#f59e0b" }}>line</span>
        </div>
        <div
          style={{
            marginTop: 24,
            fontSize: 30,
            color: "#f59e0b",
            textTransform: "uppercase",
            letterSpacing: 10,
          }}
        >
          the tech wire, ranked daily
        </div>
      </div>
    ),
    size,
  );
}
