/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: ['localhost', '127.0.0.1'],
  transpilePackages: ['pdfjs-dist'],
  webpack: (config) => {
    // Resolve pdfjs-dist worker
    config.resolve.alias.canvas = false
    config.resolve.alias.jsdom = false
    return config
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
