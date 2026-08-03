/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      {
        source: "/dashboard/connected-tools",
        destination: "/dashboard/vault",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
