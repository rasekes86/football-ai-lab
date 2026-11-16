import test from "node:test";
import assert from "node:assert/strict";
import {
 menu,reply,upcoming,hash,interpret,isFresh,showDate,madridDay
} from "../src/logic.mjs";

const NOW=new Date("2026-11-16T19:00:00Z");
const FIX=[
 {id:"SP2|later",fecha_utc:"2026-11-18T19:00:00Z",
  liga:"Segunda División",local:"Tenerife",visitante:"Ceuta",
  mercados:{corners:[{seleccion:"Más de 9,5 córners totales",probabilidad:.62,
    cuota_justa:1.613,nivel:"EXPLORATORIO_NO_VALIDADO"}]}},
 {id:"SP1|soon",fecha_utc:"2026-11-17T20:00:00Z",
  liga:"LaLiga",local:"Athletic Club",visitante:"Espanyol",
  mercados:{goals:[{seleccion:"Más de 1,5 goles",probabilidad:.76,cuota_justa:1.316,
    posicion_top3:1},{seleccion:"Más de 2,5 goles",probabilidad:.60,cuota_justa:1.667}]}},
 {id:"SP1|past",fecha_utc:"2026-11-15T19:00:00Z",
  liga:"LaLiga",local:"Osasuna",visitante:"Elche",mercados:{}}
];
const source={calculado_utc:"2026-11-16T18:30:00Z",partidos:FIX};
const feeds={forecast:source,reliability:{
  registradas:20,pendientes:20,global:{muestra:0,acierto_pct:null,brier:null}
}};
test("menu permite elegir opciones mediante botones, no solo comandos",()=>{
 const m=menu();
 assert.match(m.text,/Asistente prepartido/);
 assert.ok(m.reply_markup.inline_keyboard.flat().some(b=>b.callback_data==="markets"));
 assert.ok(m.reply_markup.inline_keyboard.flat().some(b=>b.callback_data==="q"));
});
test("próximos ordenados por hora, excluye ya comenzados",()=>{
 const arr=upcoming(source,NOW);
 assert.deepEqual(arr.map(x=>x.id),["SP1|soon","SP2|later"]);
 const m=reply("p:0",feeds,NOW);
 assert.ok(m.text.indexOf("Athletic Club")<m.text.indexOf("Tenerife"));
 assert.equal(reply("l:SP2:0",feeds,NOW).text.includes("Athletic Club"),false);
});
test("ficha abre cada mercado y conserva su Top 3",()=>{
 const m=reply("f:"+hash("SP1|soon"),feeds,NOW);
 assert.match(m.text,/Selecciones originales Top 3/);
 assert.match(m.text,/Más de 1,5 goles/);
 assert.ok(m.reply_markup.inline_keyboard.flat().some(
   b=>b.callback_data==="s:goals:"+hash("SP1|soon")));
 const sel=reply("s:goals:"+hash("SP1|soon"),feeds,NOW);
 assert.match(sel.text,/Más de 2,5 goles/);
 assert.match(sel.text,/Cuotas justas ≠ precios ofrecidos/i);
});
test("búsquedas por equipos y preguntas simples",()=>{
 assert.equal(interpret("¿Qué partidos hay mañana?"),"tomorrow");
 assert.equal(interpret("¿Cómo van los aciertos?"),"results");
 assert.equal(interpret("¿Hay cuotas de más de 1,50?"),"q");
 assert.equal(interpret("¿Y los córners?"),"k:corners:0");
 assert.match(reply(interpret("Analiza Tenerife Ceuta"),feeds,NOW).text,/Celta|Tenerife/);
});
test("no presenta precios justos como si fueran cuotas reales",()=>{
 const m=reply("q",feeds,NOW);
 assert.match(m.text,/no está activada/i);
 assert.ok(m.reply_markup.inline_keyboard.flat().some(b=>b.callback_data==="theory"));
 const t=reply("theory",feeds,NOW);
 assert.match(t.text,/NO son precios de casas/i);
 assert.match(t.text,/1,67/);
});
test("precios reales solo si se verifican proveedor, mercado, vigencia y partido",()=>{
 const odds={estado:"CON_CUOTAS",capturado_utc:"2026-11-16T18:50:00Z",
  comparaciones:[{
    fixture_id:"SP1|soon",liga:"LaLiga",local:"Athletic Club",visitante:"Espanyol",
    fecha_utc:"2026-11-17T20:00:00Z",actualizado_utc:"2026-11-16T18:30:00Z",
    etiqueta:"COMPARACION_INFORMATIVA_NO_VALIDADA",cuota_real:1.78,
    seleccion:"Más de 2,5 goles",bookmaker:"Casa demostración",
    proveedor:"5DollarFootballAPI"
   },{
    fixture_id:"SP1|soon",liga:"LaLiga",local:"Athletic Club",visitante:"Espanyol",
    fecha_utc:"2026-11-17T20:00:00Z",actualizado_utc:"2026-11-16T18:30:00Z",
    etiqueta:"COMPARACION_INFORMATIVA_NO_VALIDADA",cuota_real:3.20,
    seleccion:"Ficticia",bookmaker:"Sin validar",proveedor:"Inventado"
   }]
 };
 const ok=reply("q",{...feeds,odds},NOW);
 assert.match(ok.text,/1,78/);
 assert.doesNotMatch(ok.text,/3,20/);
 const old=reply("q",{...feeds,odds},new Date("2026-11-18T19:00:00Z"));
 assert.doesNotMatch(old.text,/1,78/);
});
test("sin muestra prospectiva no inventa porcentajes de acierto",()=>{
 const r=reply("results",feeds,NOW);
 assert.match(r.text,/Todavía no hay muestra/);
 assert.doesNotMatch(r.text,/100 %/);
});
test("fecha de Madrid y antigüedad del modelo",()=>{
 assert.equal(isFresh(source,NOW),true);
 assert.match(showDate("2026-11-18T19:00:00Z"),/20:00/);
 assert.match(madridDay(NOW),/^2026-11-16$/);
 assert.equal(isFresh(source,new Date("2026-11-21T20:00:00Z")),false);
 assert.match(reply("p:0",feeds,new Date("2026-11-21T20:00:00Z")).text,/No encuentro/);
});
