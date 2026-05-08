import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow accessing the dev server via 127.0.0.1 (in addition to localhost)
  // so HMR / dev resources are not blocked by the cross-origin guard.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: "/api/v1/:path*",
          destination: "http://localhost:8000/api/v1/:path*",
        },
      ],
    };
  },
};

export default nextConfig;
