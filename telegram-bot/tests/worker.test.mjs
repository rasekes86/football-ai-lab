import test from "node:test";
import assert from "node:assert/strict";
import {handle,hookSecret} from "../src/index.mjs";

const token="123456:AAabcdefghijklmnopqrstuvwxyz";
const env={TELEGRAM_BOT_TOKEN:token,TELEGRAM_CHAT_ID:"234567890"};
const url="https://fictional.workers.dev/telegram";
const msg={message:{message_id:21,
  chat:{id:234567890,type:"private"},from:{id:234567890},text:"/start"}};
function message(data=msg,secret=""){
 return new Request(url,{method:"POST",
  headers:{"Content-Type":"application/json",
   "X-Telegram-Bot-Api-Secret-Token":secret},
  body:JSON.stringify(data)});
}
test("sin firma correcta el webhook ni procesa ni consulta las fuentes",async()=>{
 const forbidden=()=>{throw Error("Should not call network");};
 assert.equal((await handle(message(),env,forbidden)).status,403);
 assert.equal((await handle(message(msg,"x"),env,forbidden)).status,403);
});
test("chat distinto no obtiene respuestas aunque conozca la firma",async()=>{
 const wrong={message:{message_id:1,chat:{type:"private",id:9999999},
  from:{id:9999999},text:"/start"}};
 const blocked=await handle(message(wrong,await hookSecret(token)),env,
  ()=>{throw Error("Forbidden network");});
 assert.equal(blocked.status,200);
});
test("solo el chat privado obtiene botones y comandos",async()=>{
 const calls=[];
 const transport=async (endpoint,options)=>{
  calls.push([endpoint,options]);
  return new Response(JSON.stringify({ok:true,result:{}}),{
    headers:{"Content-Type":"application/json"}
  });
 };
 const accepted=await handle(message(msg,await hookSecret(token)),env,transport);
 assert.equal(accepted.status,200);
 assert.equal(calls.length,1);
 const body=JSON.parse(calls[0][1].body);
 assert.equal(body.chat_id,"234567890");
 assert.ok(body.reply_markup.inline_keyboard.flat().some(b=>b.callback_data==="markets"));
 assert.equal(calls[0][0].includes("/sendMessage"),true);
 assert.equal(JSON.stringify(body).includes(token),false);
});
test("webhook callbacks usan edición y contestan la pulsación",async()=>{
 const calls=[];
 const cb={callback_query:{id:"q123",data:"markets",from:{id:234567890},
  message:{message_id:1,chat:{type:"private",id:234567890}}}};
 const transport=async (endpoint,options)=>{
   calls.push([endpoint,JSON.parse(options.body)]);
   return new Response(JSON.stringify({ok:true,result:{}}),{
     headers:{"Content-Type":"application/json"}
   });
 };
 const out=await handle(message(cb,await hookSecret(token)),env,transport);
 assert.equal(out.status,200);
 assert.equal(calls.length,2);
 assert.match(calls[0][0],/answerCallbackQuery/);
 assert.match(calls[1][0],/editMessageText/);
 assert.match(calls[1][1].text,/Selecciona|mercado/);
});


test("sin secreto GitHub el botón informa y nunca lanza acciones",async()=>{
 const calls=[];
 const req={message:{message_id:22,chat:{id:234567890,type:"private"},
             from:{id:234567890},text:"/comprobar"}};
 const transport=async (url,options)=>{
  calls.push([url,options]);
  return new Response(JSON.stringify({ok:true,result:{}}),
   {headers:{"Content-Type":"application/json"}});
 };
 const res=await handle(message(req,await hookSecret(token)),env,transport);
 assert.equal(res.status,200);
 assert.equal(calls.length,1);
 assert.doesNotMatch(calls[0][0],/github/);
 assert.match(JSON.parse(calls[0][1].body).text,/necesita configurar/);
});
test("despacho aceptado y protección contra repetición en 15 minutos",async()=>{
 const {requestVerification}=await import("../src/index.mjs");
 const runs={workflow_runs:[]};
 let sent=0;
 const transport=async (url,options)=>{
  if(url.includes("/runs?"))return new Response(JSON.stringify(runs),{status:200});
  if(url.includes("/dispatches")){sent++;return new Response(null,{status:204});}
  throw Error("URL inesperada");
 };
 const arg={FOOTBALL_ACTIONS_TOKEN:"test-not-secret"};
 const now=new Date("2026-11-22T20:01:00Z");
 assert.match(await requestVerification(arg,transport,now),/recibido/);
 assert.equal(sent,1);
 runs.workflow_runs=[{head_branch:"main",created_at:"2026-11-22T20:00:00Z",status:"completed"}];
 assert.match(await requestVerification(arg,transport,now),/15 minutos/);
 assert.equal(sent,1);
 runs.workflow_runs[0].status="in_progress";
 assert.match(await requestVerification(arg,transport,now),/en marcha/);
 assert.equal(sent,1);
});
test("chat ajeno no puede activar verificación aunque mande el comando",async()=>{
 const request={message:{message_id:23,chat:{id:99,type:"private"},
                from:{id:99},text:"/comprobar"}};
 let network=false;
 const res=await handle(message(request,await hookSecret(token)),
  {...env,FOOTBALL_ACTIONS_TOKEN:"test"},()=>{network=true;throw Error("no");});
 assert.equal(res.status,200);
 assert.equal(network,false);
});


test("GitHub informa el código seguro de rechazo sin revelar secretos ni mensajes externos",async()=>{
 const {requestVerification}=await import("../src/index.mjs");
 const token="fake-sensitive-token-for-tests";
 const cases=[
  [401,"token inválido"],
  [403,"Actions"],
  [404,"no encuentra el workflow"],
  [422,"workflow_dispatch"],
  [429,"límite temporal"],
  [500,"HTTP 500"]
 ];
 for(const [status,phrase] of cases){
  const mock=async url=>url.includes("/runs?")?
   new Response(JSON.stringify({workflow_runs:[]}),{status:200}):
   new Response(JSON.stringify({message:"Secret from external source "+token}),{status});
  const text=await requestVerification({FOOTBALL_ACTIONS_TOKEN:token},mock,new Date());
  assert.match(text,new RegExp(phrase,"i"),"Caso HTTP "+status);
  assert.doesNotMatch(text,new RegExp(token));
  assert.doesNotMatch(text,/Secret from external source/);
 }
});
test("error de lectura de Actions se distingue del permiso de ejecución",async()=>{
 const {requestVerification}=await import("../src/index.mjs");
 const mock=async()=>new Response(null,{status:403});
 const text=await requestVerification({FOOTBALL_ACTIONS_TOKEN:"test"},mock,new Date());
 assert.match(text,/lectura a Actions/);
});
