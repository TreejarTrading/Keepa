/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Lint is run separately; don't block production builds on it.
  eslint: { ignoreDuringBuilds: true },
  images: { unoptimized: true },
};

export default nextConfig;
