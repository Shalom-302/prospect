import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  output: process.env.NEXT_STANDALONE ? "standalone" : undefined, // build Docker (Linux)
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
