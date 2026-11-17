import test from "node:test";
import assert from "node:assert/strict";
import {performanceSnapshot,PERFORMANCE_RANGES} from "../performance.mjs";

const NOW=new Date("2026-11-17T13:00:00Z");
const dt="2026-11-15T13:00:00Z";
const model=(top,additional)=>({archivedPicks:top,allOdds:additional});
const base=(id="SP2|fixture",league="Segunda División",fecha_utc=dt)=>({
  id,liga:league,fecha_utc,local:"Tenerife",visitante:"Ceuta",
  archivado_utc:"2026-11-14T12:00:00Z"
});
const row=(n,opts={})=>({...base(),clave:"SP2|fixture|pick"+n,
  mercado:"Total goles",seleccion:"Selección "+n,estado:"PENDIENTE",resultado:"",...opts});
const odd=(opts={})=>({...base(),clave:"SP2|fixture|additional",mercado:"Total goles",
  seleccion:"Adicional",tipo_cuota:"INDICATIVA_NO_VERIFICADA",
  cuota_decimal:"1.90",estado:"PENDIENTE",resultado:"",...opts});

test("solo tres selecciones originales por encuentro, no un cuarto análisis ni un duplicado",()=>{
  const top=[row(1,{estado:"FINALIZADO",resultado:"1"}),
    row(2,{estado:"FINALIZADO",resultado:"0"}),
    row(3,{estado:"ESTADISTICA_NO_DISPONIBLE",resultado:""}),
    row(4,{estado:"FINALIZADO",resultado:"1"}),
    row(1,{estado:"FINALIZADO",resultado:"1"})];
  const perf=performanceSnapshot(model(top,[]),{},NOW);
  assert.equal(perf.top.registered,3);
  assert.equal(perf.top.settled,2);
  assert.equal(perf.top.hits,1);
  assert.equal(perf.top.misses,1);
  assert.equal(perf.top.unresolved,1);
  assert.equal(perf.top.accuracy,0.5);
  assert.equal(perf.top.profit,null);
  assert.equal(perf.top.roi,null);
  assert.equal(perf.safeguards.ignoredTopBeyondThree,1);
  assert.equal(perf.safeguards.ignoredTopDuplicates,1);
});

test("adicional solo si fue archivada antes del partido, cuota superior a 1,50 y máximo una por encuentro",()=>{
  const rows=[odd({estado:"FINALIZADO",resultado:"1"}),
    odd({clave:"SP2|fixture|other",cuota_decimal:"2.50",estado:"FINALIZADO",resultado:"1",
         archivado_utc:"2026-11-14T13:00:00Z"}),
    odd({id:"X",clave:"X|odd",cuota_decimal:"1.50"}),
    odd({id:"Y",clave:"Y|odd",cuota_decimal:"1.49"}),
    odd({id:"Z",clave:"Z|odd",archivado_utc:"2026-11-16T12:00:00Z"}),
    odd({id:"W",clave:"W|odd",tipo_cuota:"CUOTA_JUSTA_MODELO"})];
  const perf=performanceSnapshot(model([],rows),{},NOW);
  assert.equal(perf.additional.registered,1);
  assert.equal(perf.additional.settled,1);
  assert.ok(Math.abs(perf.additional.profit-0.90)<1e-12);
  assert.equal(perf.additional.roi,0.90);
  assert.equal(perf.additional.indicativeCount,1);
  assert.equal(perf.additional.observedCount,0);
  assert.equal(perf.safeguards.ignoredAdditionalDuplicates,1);
  assert.equal(perf.safeguards.ignoredAdditionalInvalid,4);
});

test("no cuenta pendientes, estadísticas ausentes ni cuota justa como pérdidas o ROI",()=>{
  const rows=[
    odd({id:"A",clave:"A|odd",estado:"PENDIENTE"}),
    odd({id:"B",clave:"B|odd",estado:"ESTADISTICA_NO_DISPONIBLE"}),
    odd({id:"C",clave:"C|odd",estado:"RESULTADO_NO_DISPONIBLE"}),
  ];
  const s=performanceSnapshot(model([row(1,{estado:"RESULTADO_NO_DISPONIBLE"})],rows),{},NOW);
  assert.equal(s.top.settled,0);
  assert.equal(s.top.accuracy,null);
  assert.equal(s.additional.settled,0);
  assert.equal(s.additional.profit,null);
  assert.equal(s.additional.roi,null);
});

test("dos cuentas independientes: acierto Top3 vs balance hipotético adicional",()=>{
  const first=row(1,{estado:"FINALIZADO",resultado:"1"});
  const second=row(2,{estado:"FINALIZADO",resultado:"0"});
  const third=row(3,{estado:"FINALIZADO",resultado:"1"});
  const s=performanceSnapshot(model([first,second,third],
    [odd({estado:"FINALIZADO",resultado:"0",cuota_decimal:"2.00",
      tipo_cuota:"OFRECIDA_API_REGISTRADA"})]),{},NOW);
  assert.equal(s.top.accuracy,2/3);
  assert.equal(s.additional.accuracy,0);
  assert.equal(s.additional.profit,-1);
  assert.equal(s.additional.observedCount,1);
  assert.equal(s.additional.observedRoi,-1);
  assert.equal(s.top.roi,null);
});

test("filtros de competición, últimas fechas, y series semanales y mensuales",()=>{
  const oldDate="2026-08-01T13:00:00Z";
  const oldTop=row(1,{id:"old",clave:"old|1",fecha_utc:oldDate,
    archivado_utc:"2026-07-31T12:00:00Z",estado:"FINALIZADO",resultado:"1"});
  const recentTop=row(2,{estado:"FINALIZADO",resultado:"0"});
  const recentOdds=odd({estado:"FINALIZADO",resultado:"1"});
  const x=model([oldTop,recentTop],[recentOdds]);
  assert.equal(performanceSnapshot(x,{},NOW).top.settled,2);
  assert.equal(performanceSnapshot(x,{range:"30"},NOW).top.settled,1);
  assert.equal(performanceSnapshot(x,{league:"Bundesliga"},NOW).top.registered,0);
  const weekly=performanceSnapshot(x,{granularity:"week"},NOW);
  const monthly=performanceSnapshot(x,{granularity:"month"},NOW);
  assert.equal(weekly.granularity,"week");
  assert.equal(monthly.granularity,"month");
  assert.equal(weekly.timeline.reduce((sum,p)=>sum+p.top,0),2);
  assert.equal(monthly.timeline.reduce((sum,p)=>sum+p.top,0),2);
  assert.ok(weekly.timeline.every(p=>p.extraProfit===null||Number.isFinite(p.extraProfit)));
  assert.equal(PERFORMANCE_RANGES.length,4);
});

test("no mezclar de exploradores ni actualizar apuestas retroactivamente",()=>{
  const x=performanceSnapshot({
    archivedPicks:[row(1,{archivado_utc:"2026-11-16T12:00:00Z"})],
    allOdds:[odd({archivado_utc:"2026-11-16T12:00:00Z"})],
    marketFutures:[{id:"fake",seleccion:"Apuesta sugerida",resultado:"1"}],
    realOddsComparison:{comparaciones:[{categoria:"result",cuota_real:8,resultado:"1"}]}
  },{},NOW);
  assert.equal(x.top.registered,0);
  assert.equal(x.additional.registered,0);
  assert.equal(x.top.profit,null);
  assert.equal(x.additional.profit,null);
  assert.equal(x.safeguards.excludesExploratory,true);
});
