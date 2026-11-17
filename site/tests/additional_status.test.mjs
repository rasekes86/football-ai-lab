import test from "node:test";
import assert from "node:assert/strict";
import {additionalStatus} from "../additional_status.mjs";

const now=new Date("2026-11-18T00:10:00Z");
const kick="2026-11-21T18:00:00Z";
const match=(code=null)=>({
  id:"SP1|test",fecha_utc:kick,odds:[],additionalAudit:code
});

test("never queried stays pending, not an apparent failure",()=>{
  const status=additionalStatus(match(),now);
  assert.equal(status.code,"NOT_QUERIED");
  assert.equal(status.style,"pending");
  assert.match(status.label,/Pendiente de consulta/);
});
test("consulted and rejected is explicitly not viable",()=>{
  const status=additionalStatus(match("NO_SUPERA_FILTROS"),now);
  assert.equal(status.code,"NO_VIABLE");
  assert.match(status.label,/Sin adicional viable/);
  assert.match(status.explanation,/filtros/);
});
test("consulted but no comparable quote distinguishes the reason",()=>{
  const status=additionalStatus(match("SIN_CUOTAS_COMPATIBLES"),now);
  assert.equal(status.code,"NO_COMPATIBLE");
  assert.match(status.label,/Sin adicional viable/);
  assert.match(status.explanation,/no se obtuvo una cuota compatible/);
});
test("archived additional wins even if stale reason suggests rejected",()=>{
  const m=match("NO_SUPERA_FILTROS");
  m.odds=[{
    id:m.id,cuota_decimal:"1.62",tipo_cuota:"OFRECIDA_API_REGISTRADA",
    archivado_utc:"2026-11-17T18:00:00Z"
  }];
  assert.equal(additionalStatus(m,now).code,"ASSIGNED");
});
test("historic match without additional does not claim pending consultation",()=>{
  const m=match("SIN_CONSULTAR");
  m.fecha_utc="2026-11-16T12:00:00Z";
  assert.equal(additionalStatus(m,now),null);
});
