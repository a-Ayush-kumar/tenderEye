import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
