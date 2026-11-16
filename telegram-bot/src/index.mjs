/** Worker público sólo para el webhook: procesa mensajes del chat privado autorizado.
 * Las credenciales son secretos Cloudflare, nunca valores del código.
 */
import {interpret,reply} from "./logic.mjs";

const RAW="https://raw.githubusercontent.com/rasekes86/football-ai-lab/main/output/";
const SOURCES={
 forecast:"pronosticos_mercados_futuros.json",
 dossier:"informes_partidos.json",
 reliability:"fiabilidad_mercados_futuros.json",
 odds:"comparacion_cuotas_reales.json",
};
function hex(buffer){
 return Array.from(new Uint8Array(buffer),b=>b.toString(16).padStart(2,"0")).join("");
}
export async function hookSecret(token){
 return hex(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(token)));
}
function same(a,b){
 if(!a||!b||a.length!==b.length)return false;
 let d=0;for(let i=0;i<a.length;i++)d|=a.charCodeAt(i)^b.charCodeAt(i);
 return d===0;
}
async function dataFor(action,fetcher){
 const requireForecast=!(["menu","help","leagues","markets","results"].includes(action));
 const keys=["results"].includes(action)?["reliability"]:
  requireForecast?["forecast",...(
   action.startsWith("c:")?["dossier"]:
   action==="q"||action.startsWith("q:")?["odds"]:[]
  )]:[];
 const results=await Promise.all(keys.map(async k=>{
  const res=await fetcher(RAW+SOURCES[k],{
   cf:{cacheTtl:90,cacheEverything:true},
   headers:{"Accept":"application/json"}
  });
  if(!res.ok)throw new Error("Fuente no disponible");
  const txt=await res.text();
  if(txt.length>2300000)throw new Error("Respuesta demasiado grande");
  return [k,JSON.parse(txt)];
 }));
 return Object.fromEntries(results);
}
async function telegram(method,body,env,fetcher){
 const res=await fetcher("https://api.telegram.org/bot"+env.TELEGRAM_BOT_TOKEN+"/"+method,{
  method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify(body)
 });
 if(!res.ok)throw new Error("Telegram rechazó la operación");
 const obj=await res.json();
 if(obj.ok!==true)throw new Error("Telegram no confirmó la operación");
 return obj;
}
export async function handle(request,env,fetcher=fetch){
 const url=new URL(request.url);
 if(request.method==="GET"&&url.pathname==="/health")
  return new Response("Football AI Lab Telegram: preparado",{
   headers:{"Content-Type":"text/plain; charset=utf-8","Cache-Control":"no-store"}
  });
 if(url.pathname!=="/telegram")return new Response("Not found",{status:404});
 if(request.method!=="POST")return new Response("Method not allowed",{status:405});
 const token=String(env?.TELEGRAM_BOT_TOKEN||"");
 const chatId=String(env?.TELEGRAM_CHAT_ID||"");
 if(!token||!chatId)return new Response("Not configured",{status:503});
 const expected=await hookSecret(token);
 const supplied=request.headers.get("X-Telegram-Bot-Api-Secret-Token")||"";
 if(!same(supplied,expected))return new Response("Forbidden",{status:403});
 const length=Number(request.headers.get("content-length")||0);
 if(length>50000)return new Response("Payload too large",{status:413});
 let update;
 try{update=await request.json();}catch{return new Response("Invalid JSON",{status:400});}
 const callback=update?.callback_query||null;
 const message=callback?.message||update?.message;
 // Bot personal: solo acepta una conversación privada y un remitente.
 const from=callback?.from||update?.message?.from;
 if(!message||message.chat?.type!=="private"||
    String(message.chat?.id)!==chatId||
    String(from?.id)!==chatId)return new Response("ok");
 const action=callback?String(callback.data||"").slice(0,64):
  interpret(String(update.message?.text||"").slice(0,250));
 if(callback?.id){
  try{await telegram("answerCallbackQuery",{callback_query_id:callback.id},env,fetcher);}
  catch{ /* La navegación es válida aunque Telegram no confirme el spinner. */ }
 }
 let card;
 try{card=reply(action,await dataFor(action,fetcher),new Date());}
 catch{
  card=reply("help",{},new Date());
  card.text="⚠️ No puedo leer los datos actualizados de GitHub ahora. "+
    "No mostraré cifras inventadas.\n\n"+card.text;
 }
 const fields={
  chat_id:chatId,text:card.text,reply_markup:card.reply_markup,
  disable_web_page_preview:true
 };
 try{
  if(callback?.message?.message_id){
   try{
    await telegram("editMessageText",{
     ...fields,message_id:callback.message.message_id
    },env,fetcher);
    return new Response("ok");
   }catch{ /* Si el mensaje no es editable, enviamos uno nuevo. */ }
  }
  await telegram("sendMessage",fields,env,fetcher);
  return new Response("ok");
 }catch{
  // Se devuelve error para que Telegram reintente la entrega del update.
  return new Response("Temporary delivery failure",{status:502});
 }
}
export default {fetch(request,env){return handle(request,env);}};
