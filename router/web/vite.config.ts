import { defineConfig } from 'vite';
const apiOrigin = process.env.ROUTER_API_ORIGIN ?? 'http://127.0.0.1:8000';
const proxy = { '/api': apiOrigin, '/v1': apiOrigin };
export default defineConfig({ server: { port: Number(process.env.ROUTER_WEB_PORT ?? 5173), strictPort: true, proxy }, preview: { host:'127.0.0.1',port:Number(process.env.ROUTER_WEB_PORT??4173),strictPort:true,proxy } });
