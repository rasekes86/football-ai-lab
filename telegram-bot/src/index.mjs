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

const GH_WORKFLOW="https://api.github.com/repos/rasekes86/football-ai-lab/actions/workflows/verify-results.yml";
const ghHeaders=token=>({
 "Accept":"application/vnd.github+json",
 "Authorization":"Bearer "+token,
 "X-GitHub-Api-Version":"2022-11-28",
 "User-Agent":"football-ai-lab-telegram"
});
/** Solo invocado tras validar firma de Telegram, chat privado e identidad. */
export async function requestVerification(env,fetcher=fetch,now=new Date()){
 const token=String(env?.FOOTBALL_ACTIONS_TOKEN||"").trim();
 if(!token)return "⚠️ La verificación necesita configurar FOOTBALL_ACTIONS_TOKEN en el Worker. No he iniciado una revisión.";
 try{
  const runs=await fetcher(GH_WORKFLOW+"/runs?per_page=5",{
   headers:ghHeaders(token)});
  if(!runs.ok)return "⚠️ No puedo consultar el estado en GitHub. Comprueba permisos Actions del token.";
  const payload=await runs.json();
  if(!Array.isArray(payload.workflow_runs))
   return "⚠️ GitHub no devolvió un estado válido; no se ha iniciado nada.";
  for(const run of payload.workflow_runs){
   const at=Date.parse(run.created_at||"");
   if(run.head_branch!=="main"||!Number.isFinite(at))continue;
   if(["queued","in_progress","waiting","pending","requested"].includes(run.status))
    return "⏳ Ya hay una verificación en marcha. Te avisaré con el resultado.";
   if(at<=now.getTime()+60000&&now.getTime()-at<15*60000)
    return "⏳ Ya solicitaste una verificación en los últimos 15 minutos. No se duplicarán consultas.";
  }
  const result=await fetcher(GH_WORKFLOW+"/dispatches",{
   method:"POST",headers:{...ghHeaders(token),"Content-Type":"application/json"},
   body:JSON.stringify({ref:"main"})
  });
  if(result.status!==204)
   return "⚠️ GitHub no aceptó iniciar la verificación. Revisa la autorización del token.";
  return "🔄 GitHub ha recibido la solicitud. Se comprobarán los partidos finalizados sin rehacer pronósticos ni cuotas. El resumen 3+1 llegará a este chat.";
 }catch{
  return "⚠️ Fallo de conexión con GitHub. No se ha confirmado ninguna ejecución.";
 }
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
 try{card=action==="verify"?{
  text:await requestVerification(env,fetcher,new Date()),
  reply_markup:reply("results",{},new Date()).reply_markup
 }:reply(action,await dataFor(action,fetcher),new Date());}
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
