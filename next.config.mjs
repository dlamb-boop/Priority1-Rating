/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  serverExternalPackages: ["pdfkit", "pdfjs-dist"],
};

export default nextConfig;
