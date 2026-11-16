import test from "node:test";
import assert from "node:assert/strict";
import { MARKET_OPTIONS, optionByKey, marketSnapshot, isHit } from "../markets.mjs";

const clock=new Date("2026-11-16T12:00:00Z");
const provenance=["football-data.co.uk · histórico CSV"];
function game(date, league, home, away, hg, ag, totals={}) {
  const stats={};
  for(const key of ["corners","shots","on_target","yellow","red","fouls"]){
    const value=totals[key]||null;
    stats[key]={
      local:value?.[0]??null,visitante:value?.[1]??null,
      total:value?(value[0]===null||value[1]===null?null:value[0]+value[1]):null,
      fuentes:value?provenance:[]
    };
  }
  return {id:league+"|"+date+"|"+home+"|"+away,
    liga:league,fecha:date,local:home,visitante:away,goles_local:hg,goles_visitante:ag,
    fuente_marcador:provenance[0],estadisticas:stats};
}
const rows=[
  game("2026-11-15","Segunda División","Tenerife","Ceuta",2,0,
       {corners:[5,7],shots:[11,15],yellow:[2,2]}),
  game("2026-11-15","LaLiga","Real Madrid","Getafe",1,1,
       {corners:[2,5],shots:[15,10],fouls:[13,14],red:[0,0]}),
  game("2026-11-16","Premier League","Arsenal","Chelsea",2,1,
       {corners:[5,4],shots:[12,8]}),
  game("2026-04-02","LaLiga","Valencia","Girona",1,2,
       {corners:[4,8],shots:[8,14]}),
];
const pick=(market,result,state="FINALIZADO")=>({
  id:"some-id",liga:"Segunda División",local:"Tenerife",visitante:"Ceuta",
  mercado:market,resultado:result,estado:state,fecha_utc:"2026-11-15T13:00:00Z"
});
const model={marketHistory:rows,archivedPicks:[
  pick("Córners totales","1"),pick("Córners totales","", "PENDIENTE"),
  pick("Doble oportunidad","0")
]};

test("catálogo visible incluye las estadísticas solicitadas",()=>{
  assert.equal(MARKET_OPTIONS.length>=9,true);
  for(const name of ["corners","fouls","shots","on_target","double","result","btts"]){
    assert.equal(optionByKey(name).key,name);
  }
  assert.deepEqual(optionByKey("double").lines,["1X","X2","12"]);
});

test("córners: promedio, línea, muestra, filtros y prospectivos separados",()=>{
  const v=marketSnapshot(model,{market:"corners",days:"90",line:"9.5"},clock);
  assert.equal(v.verified,3);
  assert.equal(v.missing,0);
  assert.equal(v.average,(12+7+9)/3);
  assert.equal(v.median,9);
  assert.equal(v.above,1);
  assert.equal(v.picks.registered,2);
  assert.equal(v.picks.evaluated,1);
  assert.equal(v.picks.hits,1);
  assert.equal(v.picks.accuracy,1);
  assert.equal(v.distribution.reduce((a,b)=>a+b.count,0),3);
  const filtered=marketSnapshot(model,{
    market:"corners",league:"Segunda División",days:"30",line:"9.5"
  },clock);
  assert.equal(filtered.verified,1);
  assert.equal(filtered.average,12);
  assert.equal(filtered.picks.evaluated,1);
});

test("faltas: disponibles si hay fuente y nunca convertir ausencias en ceros",()=>{
  const s=marketSnapshot(model,{market:"fouls",days:"90",line:"21.5"},clock);
  assert.equal(s.verified,1);
  assert.equal(s.missing,2);
  assert.equal(s.average,27);
  assert.equal(s.aboveRate,1);
  const none=marketSnapshot(model,{market:"fouls",league:"Segunda División",
      days:"90",line:"21.5"},clock);
  assert.equal(none.verified,0);
  assert.equal(none.average,null);
  assert.equal(none.aboveRate,null);
  assert.equal(none.missing,1);
});

test("doble oportunidad: frecuencia observada no altera el acierto del Top 3",()=>{
  const s=marketSnapshot(model,{market:"double",days:"90",line:"1X"},clock);
  assert.equal(s.verified,3);
  assert.equal(s.above,3);
  assert.equal(s.picks.registered,1);
  assert.equal(s.picks.hits,0);
  assert.equal(s.picks.accuracy,0);
  const x2=marketSnapshot(model,{market:"double",days:"90",line:"X2"},clock);
  assert.equal(x2.above,1);
  assert.deepEqual(x2.distribution.map(x=>x.count),[2,1,0]);
});

test("filtros: periodos y búsqueda acentuada del equipo",()=>{
  const old=marketSnapshot(model,{market:"corners",days:"365"},clock);
  assert.equal(old.verified,4);
  const recent=marketSnapshot(model,{market:"corners",days:"30",
      team:"Ténerífe"},clock);
  assert.equal(recent.verified,1);
  const empty=marketSnapshot(model,{market:"corners",days:"30",team:"Málaga"},clock);
  assert.equal(empty.verified,0);
});

test("tiros y tarjetas: 0 observado es un dato válido",()=>{
  const shots=marketSnapshot(model,{market:"shots",days:"30",line:"19.5"},clock);
  assert.equal(shots.verified,3);
  assert.equal(shots.above,3);
  const red=marketSnapshot(model,{market:"red",days:"30",line:"0.5"},clock);
  assert.equal(red.verified,1);
  assert.equal(red.average,0);
  assert.equal(red.aboveRate,0);
});

test("evaluación estricta de resultados históricos",()=>{
  const obs={verified:true,outcome:"X",btts:"Sí",total:3};
  assert.equal(isHit(obs,optionByKey("double"),"1X"),true);
  assert.equal(isHit(obs,optionByKey("double"),"X2"),true);
  assert.equal(isHit(obs,optionByKey("double"),"12"),false);
  assert.equal(isHit(obs,optionByKey("btts"),"Sí"),true);
  assert.equal(isHit({...obs,verified:false},optionByKey("btts"),"Sí"),null);
});
