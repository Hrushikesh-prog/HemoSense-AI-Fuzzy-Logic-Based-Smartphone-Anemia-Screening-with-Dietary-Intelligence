// In dev and production, /api/* is rewritten to the FastAPI server so no CORS
// setup is needed. Override the target with HEMOSENSE_API_TARGET, or skip the
// rewrite entirely by setting NEXT_PUBLIC_API_URL (see .env.example).
const API_TARGET = process.env.HEMOSENSE_API_TARGET || 'http://127.0.0.1:8000'

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${API_TARGET}/:path*`,
      },
    ]
  },
}

export default nextConfig
