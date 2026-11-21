import test from "node:test";
import assert from "node:assert/strict";
import {confirmedOutcome,renderPerformanceView} from "../performance_view.mjs";

const original={
  id:"SP2|202611151300|tenerife|ceuta",
  clave:"SP2|202611151300|tenerife|ceuta|Total goles|Menos de 2,5",
  liga:"Segunda División",local:"Tenerife",visitante:"Ceuta",
  fecha_utc:"2026-11-15T13:00:00Z",
  archivado_utc:"2026-11-14T12:00:00Z",mercado:"Total goles",
  seleccion:"Menos de 2,5 goles",estado:"FINALIZADO",resultado:"1"
};
const indicative={...original,mercado:"Ambos marcan",seleccion:"Sí",tipo_cuota:"INDICATIVA_NO_VERIFICADA",cuota_decimal:"1.930"};
const when=new Date("2026-11-17T13:00:00Z");

test("una apuesta acertada sí figura CONFIRMADA aunque la cuota sea indicativa",()=>{
  const text=confirmedOutcome(indicative);
  assert.match(text,/ACIERTO CONFIRMADO/);
  assert.doesNotMatch(text,/NO VERIFICAD/);
});
test("un fallo deportivo sí figura CONFIRMADO y no depende de la cuota",()=>{
  const text=confirmedOutcome({...indicative,resultado:"0"});
  assert.match(text,/FALLO CONFIRMADO/);
});
test("sin resultado final la apuesta no queda etiquetada como acertada ni fallada",()=>{
  const text=confirmedOutcome({...indicative,estado:"ESTADISTICA_NO_DISPONIBLE",resultado:""});
  assert.match(text,/Estadística sin verificar/);
  assert.doesNotMatch(text,/CONFIRMADO/);
});
test("el panel distingue un acierto validado del precio no acreditado",()=>{
  const model={archivedPicks:[original],allOdds:[indicative]};
  const page=renderPerformanceView(model,{},36,when);
  assert.match(page.ledger,/ACIERTO CONFIRMADO/);
  assert.match(page.ledger,/Precio orientativo, no acreditado/);
  assert.equal(page.snapshot.top.settled,1);
  assert.equal(page.snapshot.top.profit,null);
  assert.equal(page.snapshot.additional.settled,1);
  assert.equal(page.snapshot.additional.hits,1);
  assert.ok(page.snapshot.additional.profit>0);
  assert.match(page.extraEvidence,/Resultados liquidados: 1/);
  assert.equal(page.hasMore,false);
});
test("ROI simulado Top3 y 3+1 aparece etiquetado como precio NO ofrecido",()=>{
  const a={...original,probabilidad:"0.8",resultado:"1"};
  const b={...original,clave:original.clave+"|b",probabilidad:"0.6",resultado:"0"};
  const c={...original,clave:original.clave+"|c",probabilidad:"0.7",resultado:"1"};
  const view=renderPerformanceView({archivedPicks:[a,b,c],allOdds:[
    {...indicative,cuota_decimal:"1.90",resultado:"0"}
  ]},{},36,when);
  assert.match(view.topKpis,/Balance cuota justa/);
  assert.match(view.topKpis,/ROI cuota justa/);
  assert.match(view.topFairEvidence,/rentabilidad real sería desconocida/);
  assert.match(view.combinedEvidence,/SIMULACIÓN MIXTA 3\+1/);
  assert.equal(view.snapshot.top.fairCount,3);
  assert.equal(view.snapshot.combined.financialCount,4);
  assert.match(view.ledger,/cuota justa teórica/);
  assert.match(view.ledger,/NO ofertada/);
  assert.match(view.ledger,/1,25/);
  assert.match(view.ledger,/performance-return/);
});

test("HTML de origen y nombres de mercado se escapan al mostrar las apuestas",()=>{
  const bad={...original,seleccion:'<img src=x onerror=alert(1)>'};
  const page=renderPerformanceView({archivedPicks:[bad],allOdds:[]},{},36,when);
  assert.doesNotMatch(page.ledger,/<img/);
  assert.match(page.ledger,/&lt;img/);
});


test("una adicional API muestra bookmaker, proveedor y hora de observación",()=>{
  const checked={...indicative,
    tipo_cuota:"OFRECIDA_API_REGISTRADA",
    bookmaker:"Bet 365",proveedor_cuota:"5DollarFootballAPI",
    fecha_cuota_utc:"2026-11-14T12:00:00Z",
    marca_tiempo_tipo:"CAPTURA_NO_ACTUALIZACION"
  };
  const page=renderPerformanceView({archivedPicks:[],allOdds:[checked]}, {},36,when);
  assert.match(page.ledger,/ACIERTO CONFIRMADO/);
  assert.match(page.ledger,/Bet 365/);
  assert.match(page.ledger,/5DollarFootballAPI/);
  assert.match(page.ledger,/captura/);
  assert.match(page.ledger,/sin hora de cambio del bookmaker/);
  assert.equal(page.snapshot.additional.observedCount,1);
});


test("auditoría automática muestra motivos de abstención sin inventar resultados",()=>{
  const audit={seleccion_automatica:{
    nuevas_automaticas:2,
    por_liga:{
      "Segunda División":{archivadas_automaticas:1,ya_archivadas:5,
        sin_opcion_valida:3,partidos_con_comparaciones:2},
      "Bundesliga":{archivadas_automaticas:1,ya_archivadas:0,
        sin_opcion_valida:2,partidos_con_comparaciones:3}
    }
  }};
  const model={
    archivedPicks:[original],allOdds:[indicative],
    evaluations:{odds:audit}
  };
  const rendered=renderPerformanceView(model,{},36,when);
  assert.match(rendered.autoAudit,/2<\/strong><small>nuevas adicionales/);
  assert.match(rendered.autoAudit,/5<\/strong><small>sin opción válida/);
  assert.match(rendered.autoAudit,/5<\/strong><small>ya archivados/);
  assert.match(rendered.autoAudit,/Bundesliga/);
  assert.match(rendered.autoAudit,/se abstiene/);
  assert.equal(rendered.snapshot.additional.settled,1);
  const single=renderPerformanceView(model,{league:"Segunda División"},36,when);
  assert.doesNotMatch(single.autoAudit,/Bundesliga/);
  assert.match(single.autoAudit,/Segunda División/);
});
test("antes de la primera ejecución el panel no afirma haber elegido nuevas apuestas",()=>{
  const model={archivedPicks:[],allOdds:[],evaluations:{odds:{}}};
  const rendered=renderPerformanceView(model,{},36,when);
  assert.match(rendered.autoAudit,/aparecerá cuando finalice/);
  assert.doesNotMatch(rendered.autoAudit,/nuevas adicionales/);
  assert.equal(rendered.snapshot.additional.registered,0);
});


test("cambios de código no generan falsas abstenciones cuando la API estaba desactivada",()=>{
  const page=renderPerformanceView({
    archivedPicks:[],allOdds:[],
    evaluations:{odds:{seleccion_automatica:{
      estado:"FUENTES_NO_CONSULTADAS",por_liga:{
        "Bundesliga":{no_evaluados_sin_api:4,sin_opcion_valida:0}
      }
    }}}
  },{},36,when);
  assert.match(page.autoAudit,/FUENTES NO CONSULTADAS/);
  assert.match(page.autoAudit,/no utilizó las APIs privadas/);
  assert.doesNotMatch(page.autoAudit,/sin opción válida/);
  assert.equal(page.snapshot.additional.registered,0);
});


test("el panel muestra auditoría automática por liga sin convertir ausencia de API en fallo",()=>{
  const empty={archivedPicks:[],allOdds:[],evaluations:{odds:{
    seleccion_automatica:{estado:"FUENTES_NO_CONSULTADAS",por_liga:{
      Bundesliga:{partidos_futuros:2,no_evaluados_sin_api:2}
    }}
  }}};
  const screen=renderPerformanceView(empty,{},36,when);
  assert.match(screen.autoAudit,/FUENTES NO CONSULTADAS/);
  assert.match(screen.autoAudit,/no utilizó las APIs privadas/);
  assert.equal(screen.snapshot.additional.misses,0);
  assert.equal(screen.snapshot.additional.registered,0);
});

test("las cuotas API liquidadas tienen balance independiente de las referencias indicativas",()=>{
  const another={...indicative,
    id:"D1|another",clave:"D1|another|odd",liga:"Bundesliga",
    local:"Bayern Munich",visitante:"FC Cologne",
    tipo_cuota:"OFRECIDA_API_REGISTRADA",cuota_decimal:"2.200",resultado:"0"};
  const screen=renderPerformanceView({archivedPicks:[],allOdds:[indicative,another]}, {},36,when);
  assert.equal(screen.snapshot.additional.settled,2);
  assert.equal(screen.snapshot.additional.hits,1);
  assert.equal(screen.snapshot.additional.observedSettled,1);
  assert.equal(screen.snapshot.additional.observedProfit,-1);
  assert.equal(screen.snapshot.additional.indicativeCount,1);
  assert.match(screen.extraEvidence,/ROI hipotético solo API/);
  assert.match(screen.ledger,/ACIERTO CONFIRMADO/);
  assert.match(screen.ledger,/FALLO CONFIRMADO/);
});


test("sports results use four distinct audit statuses, not the same pending color",()=>{
  const win=confirmedOutcome({...indicative,estado:"FINALIZADO",resultado:"1"});
  const loss=confirmedOutcome({...indicative,estado:"FINALIZADO",resultado:"0"});
  const pending=confirmedOutcome({...indicative,estado:"PENDIENTE",resultado:""});
  const missing=confirmedOutcome({...indicative,estado:"ESTADISTICA_NO_DISPONIBLE",resultado:""});
  assert.match(win,/status-pill final/);
  assert.match(loss,/status-pill loss/);
  assert.match(pending,/status-pill pending/);
  assert.match(missing,/status-pill missing/);
  assert.notEqual(pending,missing);
});
