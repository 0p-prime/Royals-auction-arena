import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.dirname(fileURLToPath(import.meta.url));
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.woff2':'font/woff2','.json':'application/json; charset=utf-8'};
export function createServer({dataPath=process.env.DATA_PATH||path.join(root,'private','dataset.json')}={}) {
 return http.createServer(async(req,res)=>{
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Cache-Control','no-store');
  res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'");
  if(req.method!=='GET'){res.writeHead(405);res.end('Method not allowed');return;}
  const pathname=new URL(req.url,'http://localhost').pathname;
  if(pathname==='/api/dataset'||pathname==='/dataset.json'){
   try {const body=await readFile(dataPath); JSON.parse(body);res.writeHead(200,{'Content-Type':'application/json'});res.end(body);}
   catch{res.writeHead(404,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'No local dataset. Run the documented import step.'}));}return;
  }
  if(pathname==='/DATA_ATTRIBUTION.txt'){res.writeHead(200,{'Content-Type':'text/plain; charset=utf-8'});res.end(await readFile(path.join(root,'DATA_ATTRIBUTION.txt')));return;}
  const files={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/core.js':'core.js','/style.css':'style.css','/assistant.js':'assistant.js','/assets/arena-logo.png':'assets/arena-logo.png','/assets/arena-icon.png':'assets/arena-icon.png','/assets/arena-crest.svg':'assets/arena-crest.svg','/assets/fonts/outfit-latin-wght-normal.woff2':'assets/fonts/outfit-latin-wght-normal.woff2','/assets/fonts/plus-jakarta-sans-latin-wght-normal.woff2':'assets/fonts/plus-jakarta-sans-latin-wght-normal.woff2'};
  if(!files[pathname]){res.writeHead(404);res.end('Not found');return;}
  try{const body=await readFile(path.join(root,'web',files[pathname]));res.writeHead(200,{'Content-Type':types[path.extname(files[pathname])]});res.end(body);}catch{res.writeHead(500);res.end('Could not load application');}
 });
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const port=Number(process.env.PORT||3000),host=process.env.HOST||'127.0.0.1';
 createServer().listen(port,host,()=>console.log(`Royals dashboard: http://${host}:${port}`));
}
