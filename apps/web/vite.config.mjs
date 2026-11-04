import {defineConfig} from 'vite';
// Development only. No arbitrary remote proxy, target from request or cookie auth.
const target=new URL(process.env.OI_WEB_API_TARGET || 'http://127.0.0.1:8000');
if(target.protocol!=='http:' || !['127.0.0.1','localhost','[::1]'].includes(target.hostname) ||
   target.username || target.password || target.pathname!=='/' || target.search || target.hash) {
  throw Error('The H1 development API target must be an explicit loopback HTTP origin.');
}
const proxy=Object.fromEntries(['/v1','/health'].map(path=>[path,{target:target.origin,changeOrigin:true,followRedirects:false}]));
const headers={
 'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
 'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
 'Permissions-Policy':'camera=(), microphone=(), geolocation=()'
};
export default defineConfig({
 server:{host:'127.0.0.1',port:5173,strictPort:true,cors:false,hmr:false,proxy,headers},
 preview:{host:'127.0.0.1',port:4173,strictPort:true,cors:false,proxy,headers},
 build:{target:'es2022',sourcemap:false},
});
