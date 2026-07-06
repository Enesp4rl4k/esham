import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: {
    // Static export has no image optimization server; unoptimized passes
    // src through as-is while still giving us layout-shift prevention and
    // the correct loading="lazy" / sizes attributes from next/image.
    unoptimized: true,
  },
};

export default nextConfig;
