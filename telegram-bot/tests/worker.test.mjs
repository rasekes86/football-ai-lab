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
