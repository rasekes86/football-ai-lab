import test from "node:test";
import assert from "node:assert/strict";
import {
  LEAGUES, FEEDS, parseCsv, numberOrNull, settled,
  calculateMetrics, calculateOdds, buildModel, matchStatus
} from "../data.mjs";

test("seis ligas disponibles y rutas oficiales de los CSV", () => {
  assert.equal(LEAGUES.length, 6);
  assert.equal(FEEDS.seguimiento_selecciones, "seguimiento_selecciones.csv");
  assert.equal(FEEDS.cuotas, "seguimiento_oportunidades_150.csv");
});

test("CSV: comillas, separadores, CRLF y nuevas líneas dentro de celdas", () => {
  const text = '\uFEFFid,seleccion,fuente\r\nA,"Más de 2,5 goles","Casa, ""online"""\r\nB,"línea uno\nlínea dos",otro\r\n';
  assert.deepEqual(parseCsv(text), [
    { id: "A", seleccion: "Más de 2,5 goles", fuente: 'Casa, "online"' },
    { id: "B", seleccion: "línea uno\nlínea dos", fuente: "otro" }
  ]);
  assert.throws(() => parseCsv('a,b\n"sin cerrar,b'), /comillas sin cerrar/);
});

test("decimales de los CSV originales sin conversión destructiva española", () => {
  assert.equal(numberOrNull("1.650"), 1.65);
  assert.equal(numberOrNull("0.866907"), .866907);
  assert.equal(numberOrNull(""), null);
  assert.equal(numberOrNull("no-disponible"), null);
});

test("solo FINALIZADO 1 o 0 puede contar como evaluado", () => {
  const rows = [
    { estado: "FINALIZADO", resultado: "1" },
    { estado: "FINALIZADO", resultado: "0" },
    { estado: "RESULTADO_NO_DISPONIBLE", resultado: "" },
    { estado: "ESTADISTICA_NO_DISPONIBLE", resultado: "" },
    { estado: "PENDIENTE", resultado: "" }
  ];
  assert.equal(settled(rows[0]), true);
  assert.equal(settled(rows[1]), true);
  assert.equal(settled(rows[2]), false);
  assert.deepEqual(calculateMetrics(rows), {
    registered: 5, evaluated: 2, hits: 1, losses: 1, pending: 1, missing: 2, accuracy: .5
  });
});

test("balance y ROI hipotéticos: solo cuotas FINALIZADO, sin doble cómputo", () => {
  const rows = [
    { estado: "FINALIZADO", resultado: "1", retorno_simulado_unidad: "0.650" },
    { estado: "FINALIZADO", resultado: "1", retorno_simulado_unidad: "0.930" },
    { estado: "FINALIZADO", resultado: "0", retorno_simulado_unidad: "-1.000" },
    { estado: "FINALIZADO", resultado: "1", retorno_simulado_unidad: "1.170" },
    { estado: "PENDIENTE", resultado: "", retorno_simulado_unidad: "" }
  ];
  const result=calculateOdds(rows);
  assert.equal(result.evaluated,4);
  assert.equal(result.hits,3);
  assert.equal(result.priced,4);
  assert.ok(Math.abs(result.profit-1.75)<1e-10);
  assert.ok(Math.abs(result.roi-.4375)<1e-10);
  assert.equal(calculateOdds([rows[4]]).profit,null);
});

test("el Top 3 archivado manda sobre recálculos posteriores", () => {
  const start = "2026-11-20T20:00:00+00:00";
  const id="SP1|202611202000|ath bilbao|espanyol";
  const base={id,liga:"LaLiga",local:"Athletic Club",visitante:"Espanyol",fecha_utc:start};
  const prev={...base,fecha_analisis_utc:"2026-11-14T10:00:00+00:00",prob_local:".5"};
  const pick=(sel,state="PENDIENTE",result="")=>({...base,clave:id+"|"+sel,mercado:"Total goles",seleccion:sel,probabilidad:"0.8",cuota_justa:"1.25",estado:state,resultado:result});
  const model=buildModel({
    predicciones:[{...base,prob_local:".8"}],
    historico_predicciones:[prev],
    selecciones:[{...base,mercado:"Córners",seleccion:"PRONÓSTICO RECALCULADO",probabilidad:".99"}],
    historico_selecciones:[pick("Original A"),pick("Original B"),pick("Original C")],
    seguimiento_selecciones:[pick("Original A","FINALIZADO","1"),pick("Original B"),pick("Original C")],
    seguimiento:[{...base,estado:"FINALIZADO",resultado_local:"2",resultado_visitante:"0"}],
    cuotas:[]
  },new Date("2026-11-16T12:00:00Z"));
  assert.equal(model.matches.length,1);
  assert.equal(model.matches[0].picks.length,3);
  assert.equal(model.matches[0].picks[0].seleccion,"Original A");
  assert.equal(model.matches[0].historicalForecast.prob_local,".5");
  assert.equal(model.matches[0].forecast.prob_local,".8");
  assert.equal(model.matches[0].status,"PARCIAL");
  assert.equal(model.top.evaluated,1);
  assert.equal(model.countForecasts,1);
});

test("sin estadística no es fallo ni partido finalizado", () => {
  assert.equal(matchStatus({picks:[
    {estado:"ESTADISTICA_NO_DISPONIBLE",resultado:""},
    {estado:"RESULTADO_NO_DISPONIBLE",resultado:""},
    {estado:"PENDIENTE",resultado:""}
  ]}),"SIN_DATOS");
});

test("desglose postpartido enlazado sin modificar las selecciones originales", () => {
  assert.equal(FEEDS.desglose_postpartido, "desglose_postpartido.json");
  const base = {id:"SP2|test",liga:"Segunda División",local:"Tenerife",
    visitante:"Ceuta",fecha_utc:"2026-11-15T13:00:00+00:00"};
  const original = {...base,clave:"SP2|test|corner",mercado:"Córners totales",
    seleccion:"Más de 9,5 córners totales",estado:"PENDIENTE",resultado:""};
  const reviewed = {...original,estado:"FINALIZADO",resultado:"1",valor_real:"10"};
  const details = {id:base.id,marcador:"2-0",estadisticas:{
    corners:{local:6,visitante:4,total:10,nombre:"Córners",fuentes:["https://site.api.espn.com/summary"]}
  },selecciones:[{clave:original.clave,estado:"FINALIZADO",resultado:"1",
    explicacion:"ACIERTO: 6 local + 4 visitante = 10"}]};
  const model=buildModel({historico_selecciones:[original],
    seguimiento_selecciones:[reviewed],
    desglose_postpartido:{partidos:[details],auditoria_estadisticas:{completos:1}}});
  assert.equal(model.matches[0].picks[0].resultado,"1");
  assert.equal(model.matches[0].breakdown.estadisticas.corners.total,10);
  assert.equal(model.top.evaluated,1);
});
