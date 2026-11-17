import test from "node:test";
import assert from "node:assert/strict";
import {realOddsSnapshot,oddsCoverageSnapshot,ODDS_LEAGUES,REAL_ODDS_CATEGORIES} from "../real_odds.mjs";
import {buildModel} from "../data.mjs";

const NOW=new Date("2026-11-16T12:00:00Z");
const FIXTURE="SP1|202611202000|ath bilbao|espanyol";
function row(provider,category,price,market,book="Bet365",more={}){
  const p=category==="corners"?.62:category==="yellow"?.60:.58;
  return {
    fixture_id:FIXTURE,liga:"LaLiga",local:"Athletic Club",visitante:"Espanyol",
    fecha_utc:"2026-11-20T20:00:00Z",categoria:category,
    seleccion:category==="corners"?"Más de 9,5 córners totales":
      category==="yellow"?"Más de 4,5 tarjetas amarillas totales":"Sí",
    probabilidad_modelo:p,nivel:"EXPLORATORIO_NO_VALIDADO",posicion_top3:null,
    cuota_real:price,bookmaker:book,bookmaker_id:book,
    mercado_proveedor:market,resultado_proveedor:"over",linea:9.5,
    p_implicita:1/price,p_mercado_sin_margen:.5,
    margen_casa:.04,diferencia_puntos_pct:(p-.5)*100,
    ev_teorico_unidad:Math.round((p*price-1)*10000)/10000,
    actualizado_utc:"2026-11-16T12:00:00Z",
    capturado_utc:"2026-11-16T12:00:00Z",
    marca_tiempo_tipo:"CAPTURA_NO_ACTUALIZACION",proveedor:provider,
    etiqueta:"COMPARACION_INFORMATIVA_NO_VALIDADA",
    ...more
  };
}
const data={
  realOddsRaw:{estado:"CON_CUOTAS",capturado_utc:NOW.toISOString()},
  realOddsComparison:{comparaciones:[
    row("5DollarFootballAPI","corners",1.85,"corners"),
    row("API-Football","yellow",1.92,"yellow","Validado ES"),
    row("The Odds API V4","btts",1.87,"btts","Otra casa",
      {resultado_proveedor:"yes",linea:null}),
    row("API-Football","corners",2.04,"corners","Bet365")
  ]}
};
test("fuentes gratuitas respetadas sin inventar cuotas para tarjetas genéricas",()=>{
  const snap=realOddsSnapshot(data,{},NOW);
  assert.equal(snap.cards.length,3);
  assert.equal(snap.quotes,4);
  assert.deepEqual(new Set(snap.cards.map(x=>x.categoria)),
    new Set(["corners","yellow","btts"]));
  assert.equal(REAL_ODDS_CATEGORIES.length,6);
});
test("mismo bookmaker en proveedores distintos no mezcla cotizaciones",()=>{
  const snap=realOddsSnapshot(data,{market:"corners"},NOW);
  assert.equal(snap.cards.length,1);
  assert.equal(snap.cards[0].opciones.length,2);
  assert.equal(snap.cards[0].mejor.proveedor,"API-Football");
  assert.equal(snap.cards[0].mejor.cuota_real,2.04);
});
test("amarillas quedan separadas de córners y no se admite fuente desconocida",()=>{
  assert.equal(realOddsSnapshot(data,{market:"yellow"},NOW).cards.length,1);
  const fake={...data,realOddsComparison:{comparaciones:[
    row("Fuente sin contrastar","yellow",3.5,"yellow"),
    row("5DollarFootballAPI","yellow",1.9,"yellow",
      "Bet365",{etiqueta:"TARJETAS_GENERICAS_NO_EQUIVALENTES"})
  ]}};
  assert.equal(realOddsSnapshot(fake,{},NOW).cards.length,0);
});
test("cotización gratuita caducada o partido pasado no figura como actual",()=>{
  const old=new Date("2026-11-17T13:00:00Z");
  assert.equal(realOddsSnapshot(data,{},old).cards.length,0);
  const post=new Date("2026-11-21T20:00:00Z");
  assert.equal(realOddsSnapshot(data,{},post).cards.length,0);
});
test("modelo de datos preserva Top3 con las nuevas fuentes",()=>{
  const model=buildModel({
    cuotas_reales_verificadas:data.realOddsRaw,
    comparacion_cuotas_reales:data.realOddsComparison
  },NOW);
  assert.equal(realOddsSnapshot(model,{},NOW).cards.length,3);
  assert.equal(model.archivedPicks.length,0);
});

test("la auditoría de seis ligas informa ausencias sin inventar cuotas",()=>{
  const raw={
    estado:"CON_CUOTAS",capturado_utc:NOW.toISOString(),
    cuotas:[{fixture_id:FIXTURE,liga:"LaLiga",proveedor:"5DollarFootballAPI",
      fecha_utc:"2026-11-20T20:00:00Z"}],
    auditoria:{fuentes_gratuitas:[
      {proveedor:"5DollarFootballAPI",estado:"CON_CUOTAS",community_segunda_activada:false,
       cobertura_ligas:{
         "LaLiga":{estado:"CON_CUOTAS",partidos_modelo:4,eventos_proveedor:4,
                    partidos_emparejados:4,partidos_consultados:4,
                    motivos_descartados:{}},
         "Premier League":{estado:"SIN_COINCIDENCIA_VERIFICADA",partidos_modelo:7,
                    eventos_proveedor:7,partidos_emparejados:0,
                    partidos_consultados:0,motivos_descartados:{equipos:7}},
         "Segunda División":{estado:"NO_INCLUIDA_EN_FREE",partidos_modelo:5,
                    eventos_proveedor:0,partidos_emparejados:0,
                    partidos_consultados:0,motivos_descartados:{}}
       }},
      {proveedor:"API-Football",estado:"DESACTIVADO"}
    ]}
  };
  const snap=oddsCoverageSnapshot({realOddsRaw:raw},NOW);
  assert.equal(snap.rows.length,6);
  assert.deepEqual(snap.rows.map(x=>x.name),ODDS_LEAGUES);
  assert.equal(snap.rows.find(x=>x.name==="LaLiga").games,1);
  assert.equal(snap.rows.find(x=>x.name==="Premier League").games,0);
  assert.equal(snap.rows.find(x=>x.name==="Premier League").reasons.equipos,7);
  assert.equal(snap.rows.find(x=>x.name==="Segunda División").state,"NO_INCLUIDA_EN_FREE");
  assert.equal(snap.backupStatus,"DESACTIVADO");
  assert.equal(oddsCoverageSnapshot({realOddsRaw:raw},
    new Date("2026-11-18T13:00:00Z")).stale,true);
});
