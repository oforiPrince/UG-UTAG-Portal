import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    optimizePackageImports: ["lucide-react", "recharts"],
  },
  async headers() {
    const baseHeaders = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      {
        key: "Permissions-Policy",
        value: "camera=(), microphone=(), geolocation=()",
      },
      { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    ];
    return [
      {
        // Allow same-origin iframes for public media so news/event PDFs can
        // open inline without downloading.
        source: "/api/v1/public/media/:path*",
        headers: [
          ...baseHeaders,
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
        ],
      },
      {
        // Everything except public media stays unframeable.
        source: "/:path((?!api/v1/public/media/).*)*",
        headers: [
          ...baseHeaders,
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
