import {
  LEAGUES, FEEDS, parseCsv, numberOrNull, settled,
  calculateMetrics, calculateOdds, buildModel
} from "./data.mjs";
import { MARKET_OPTIONS, optionByKey, marketSnapshot, isHit } from "./markets.mjs";
import { futureMarketSnapshot } from "./future_markets.mjs";
import { reliabilitySnapshot } from "./reliability.mjs";
import { radarSnapshot } from "./radar.mjs";
import { realOddsSnapshot } from "./real_odds.mjs";

const REPO_BASE = "https://raw.githubusercontent.com/rasekes86/football-ai-lab/main/output/";
const GITHUB_URL = "https://github.com/rasekes86/football-ai-lab";
const SHEET_URL = "https://docs.google.com/spreadsheets/d/1XSDuxhggZ3UCNkJDmakYG8WQdWPcqQtykj49DuIqJsU/edit";
const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
})[ch]);
const strip = value => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const countFmt = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 });
const percentFmt = new Intl.NumberFormat("es-ES", { style: "percent", maximumFractionDigits: 1 });
const numberFmt = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const momentFmt = new Intl.DateTimeFormat("es-ES", {
  timeZone: "Europe/Madrid", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
});
const dateFmt = new Intl.DateTimeFormat("es-ES", {
  timeZone: "Europe/Madrid", day: "2-digit", month: "short", year: "numeric"
});
const timeFmt = new Intl.DateTimeFormat("es-ES", {
  timeZone: "Europe/Madrid", hour: "2-digit", minute: "2-digit"
});
const percent = value => value === null || value === undefined || !Number.isFinite(Number(value))
  ? "—" : percentFmt.format(Number(value));
const decimal = value => numberOrNull(value) === null ? "—" : numberFmt.format(numberOrNull(value));
const integer = value => countFmt.format(value || 0);
const displayDate = value => {
  const d = new Date(value);
  return Number.isFinite(d.getTime()) ? momentFmt.format(d) : "Fecha no disponible";
};
const displayDay = value => {
  const d = new Date(value);
  return Number.isFinite(d.getTime()) ? dateFmt.format(d) : "—";
};
const money = value => value === null ? "SIN MUESTRA" :
  (value > 0 ? "+" : value < 0 ? "−" : "") + numberFmt.format(Math.abs(value)) + " u.";
const textOrDash = input => input === null || input === undefined || input === "" ? "—" : String(input);

const state = {
  data: null,
  view: "overview",
  matchLimit: 24,
  historyLimit: 40,
  marketLimit: 35,
  futureMarketLimit: 18,
  radarLimit: 20,
  realOddsLimit: 24,
  errors: [],
  lastFocus: null,
  crests: {}
};

function leagueShort(name) {
  return ({
    "LaLiga": "L1", "Segunda División": "L2",
    "Premier League": "PL", "Bundesliga": "BL",
    "Serie A": "SA", "Ligue 1": "L1"
  })[name] || "FT";
}
function leagueClass(name) {
  return ({
    "Segunda División": "sp2", "Premier League": "e0",
    "Bundesliga": "d1", "Serie A": "i1", "Ligue 1": "f1"
  })[name] || "";
}
function leagueLogo(name) {
  return `<span class="league-symbol ${leagueClass(name)}" aria-hidden="true">${escapeHtml(leagueShort(name))}</span>`;
}
function outcome(row) {
  if (!settled(row)) return "none";
  return String(row.resultado) === "1" ? "win" : "loss";
}
function resultText(row) {
  if (settled(row)) return String(row.resultado) === "1" ? "ACIERTO" : "FALLO";
  const status = row?.estado || "PENDIENTE";
  if (status === "ESTADISTICA_NO_DISPONIBLE") return "SIN ESTADÍSTICA";
  if (status === "RESULTADO_NO_DISPONIBLE") return "SIN MARCADOR";
  if (status.startsWith("EXCLUIDO")) return "EXCLUIDO";
  return "PENDIENTE";
}
function resultPill(row) {
  const result = outcome(row);
  return `<span class="status-pill ${result === "win" ? "final" : result === "loss" ? "loss" : row?.estado?.includes("NO_DISPONIBLE") ? "missing" : ""}">${resultText(row)}</span>`;
}
function matchPill(match) {
  const status = match.status;
  const label = ({
    FINALIZADO: "TOP 3 LIQUIDADO", PARCIAL: "REVISIÓN PARCIAL",
    SIN_DATOS: "FALTAN DATOS", PENDIENTE: "PENDIENTE"
  })[status] || "PENDIENTE";
  const css = ({
    FINALIZADO: "final", PARCIAL: "partial", SIN_DATOS: "missing", PENDIENTE: ""
  })[status] || "";
  return `<span class="status-pill ${css}">${label}</span>`;
}
function abbreviateTeam(name) {
  return String(name || "").split(/\s+/).filter(Boolean).slice(0,2).map(x => x[0].toUpperCase()).join("");
}
function crestUrl(league, team) {
  const url = state.crests[league + "|" + team];
  return typeof url === "string" && url.startsWith("https://a.espncdn.com/") ? url : "";
}
function teamCrest(league, team, small = false) {
  const url = crestUrl(league, team);
  const classes = "team-monogram crest-shell" + (small ? " small-crest" : "") +
    (url ? " has-crest" : "");
  return `<span class="${classes}" aria-hidden="true">
    <span class="crest-initials">${escapeHtml(abbreviateTeam(team))}</span>
    ${url ? `<img class="team-crest" src="${escapeHtml(url)}" alt="" loading="lazy" decoding="async">` : ""}
  </span>`;
}
function teamPair(row) {
  return `<span class="team-pair-with-crests">
    ${teamCrest(row.liga, row.local, true)}
    <span>${escapeHtml(row.local)} – ${escapeHtml(row.visitante)}</span>
    ${teamCrest(row.liga, row.visitante, true)}
  </span>`;
}
function empty(message) {
  return `<div class="empty">${escapeHtml(message)}</div>`;
}
function kpi(label, value, foot, highlight = false) {
  return `<div class="kpi ${highlight ? "highlight" : ""}" style="--kpi-line:${highlight ? "var(--lime)" : "#4f8291"}">
    <div class="kpi-label">${escapeHtml(label)}</div><div class="kpi-value">${escapeHtml(value)}</div>
    <div class="kpi-footer">${escapeHtml(foot)}</div></div>`;
}
function inner(id, html) {
  const el = $(id);
  if (el) el.innerHTML = html;
}
function insertOptions(id, labels) {
  const element = $(id);
  const first = element.options[0].outerHTML;
  element.innerHTML = first + labels.map(x => `<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join("");
}

async function getFeed(name, file, token) {
  const url = `${REPO_BASE}${encodeURIComponent(file)}?ref=${token}`;
  const response = await fetch(url, {cache: "no-store"});
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
  const text = await response.text();
  return file.endsWith(".json") ? JSON.parse(text) : parseCsv(text);
}

async function refreshData() {
  const button = $("refreshButton");
  button.disabled = true;
  $("syncStatus").className = "sync-status";
  $("syncText").textContent = "Actualizando…";
  const token = Date.now().toString();
  const pending = Object.entries(FEEDS).map(async ([key, file]) => ({
    key, value: await getFeed(key, file, token)
  }));
  const responses = await Promise.allSettled(pending);
  const feeds = {}, errors = [];
  responses.forEach((r, i) => {
    const name = Object.keys(FEEDS)[i];
    if (r.status === "fulfilled") feeds[name] = r.value.value;
    else errors.push(name);
  });
  button.disabled = false;
  if (!feeds.predicciones?.length && !feeds.historico_predicciones?.length &&
      !feeds.seguimiento_selecciones?.length) {
    $("syncStatus").className = "sync-status error";
    $("syncText").textContent = "Error al cargar";
    $("errorBanner").hidden = false;
    $("errorBanner").innerHTML = `No hemos podido descargar los datos públicos de GitHub. Comprueba la conexión y pulsa <strong>Actualizar</strong>. ${errors.length ? "Fuentes: " + escapeHtml(errors.join(", ")) : ""}`;
    return;
  }
  // Catálogo independiente del motor: si falla, vuelven las iniciales.
  try {
    const logoResponse = await fetch("./crests.json?v=" + token, {cache: "no-store"});
    const logos = logoResponse.ok ? await logoResponse.json() : null;
    state.crests = logos && typeof logos.teams === "object" ? logos.teams : {};
  } catch {
    state.crests = {};
  }
  state.data = buildModel(feeds);
  state.errors = errors;
  $("errorBanner").hidden = !errors.length;
  if (errors.length) {
    $("errorBanner").textContent = "Algunas fuentes no están disponibles (" + errors.join(", ") + "). Se muestra la información recibida, que puede estar incompleta.";
  }
  $("syncStatus").className = "sync-status" + (errors.length ? " warning" : "");
  $("syncText").textContent = errors.length ? "Datos parciales" : "Datos conectados";
  $("updatedLabel").textContent = "Última publicación: " +
    (state.data.updatedAt ? displayDate(state.data.updatedAt) : "sin fecha");
  $("navMatchCount").textContent = integer(state.data.futureMatches.length);
  renderAll();
}

function renderOverview() {
  const d = state.data;
  inner("kpiGrid",
    kpi("Próximos partidos", integer(d.futureMatches.length), "Pronósticos publicados · 6 ligas") +
    kpi("Top 3 auditado", integer(d.top.evaluated) + " / " + integer(d.top.registered), "Selecciones liquidadas / archivadas") +
    kpi("Acierto Top 3", percent(d.top.accuracy), "Solo resultados verificados", true) +
    kpi("Balance simulado", money(d.simulation.profit), d.simulation.priced + " cuotas liquidadas; no dinero real")
  );
  const max = Math.max(1, ...d.leagues.map(x => x.registered));
  inner("leagueOverview", d.leagues.map(x => `<div class="league-row">
    ${leagueLogo(x.name)}<div class="league-info"><div class="league-name">${escapeHtml(x.name)}</div>
    <div class="league-sub">${integer(x.currentMatches)} próximos · ${integer(x.registered)} selecciones archivadas</div></div>
    <div class="league-track" aria-label="${integer(x.registered)} registros"><span style="width:${Math.round(x.registered/max*100)}%"></span></div>
    <span class="league-meta">${x.evaluated ? percent(x.accuracy) : "sin muestra"}</span></div>`).join(""));
  const validRate = d.top.accuracy;
  inner("accuracyOverview", `<div class="accuracy-ring" style="--angle:${Math.round((validRate ?? 0)*100)}%"><div class="ring-label"><strong>${percent(validRate)}</strong><span>ACIERTOS TOP 3</span></div></div>
    <div class="accuracy-copy"><strong>${integer(d.top.hits)} aciertos</strong>
    <p>De ${integer(d.top.evaluated)} selecciones evaluadas. ${integer(d.top.missing)} pendientes por datos y ${integer(d.top.pending)} todavía pendientes.</p></div>`);
  const withEvaluation = d.leagues.filter(x => x.evaluated);
  inner("accuracyChart", withEvaluation.length ? withEvaluation.map(x => `
    <div class="chart-row"><span>${escapeHtml(x.name)}</span><div class="bar"><div class="bar-fill" style="width:${Math.round((x.accuracy||0)*100)}%"></div></div><b>${percent(x.accuracy)}</b></div>
  `).join("") : empty("Aún no hay partidos liquidados por liga."));
  const upcoming = [...d.futureMatches].sort((a,b)=>a.kickoff-b.kickoff).slice(0,6);
  inner("upcomingList", upcoming.length ? upcoming.map(compactMatch).join("") : empty("No hay encuentros futuros en la ventana actual."));
  const recent = [...d.settledMatches].sort((a,b)=>b.kickoff-a.kickoff).slice(0,6);
  inner("reviewedList", recent.length ? recent.map(compactMatch).join("") : empty("Todavía no hay resultados verificados."));
  inner("oddsOverview", `<div><span class="overline">SCENARIO LAB / CUOTAS +1,50</span>
    <strong>${integer(d.simulation.evaluated)} selecciones liquidadas · ${integer(d.simulation.hits)} aciertos</strong>
    <p>Balance simulado de una unidad por selección a partir de cuotas anotadas; no representa ganancias reales.</p>
    </div><div class="simulation-number">${escapeHtml(money(d.simulation.profit))}</div>
    <button type="button" class="btn btn-outline" data-go="odds">Ver detalle ↗</button>`);
}
function compactMatch(m) {
  const count = m.finishedPicks;
  const meta = count ? `${count}/${m.picks.length} comprobadas` : m.liga;
  return `<button type="button" class="compact-match" data-open-id="${escapeHtml(m.id)}">
    ${leagueLogo(m.liga)}<span class="compact-match-main"><span class="compact-match-title">${teamPair(m)}</span>
    <span class="compact-match-sub">${escapeHtml(displayDate(m.fecha_utc))} · ${escapeHtml(meta)}</span></span>
    <span class="compact-match-right">${m.score ? `<span class="compact-match-score">${escapeHtml(m.score)}</span>` : "<span class='compact-match-score'>↗</span>"}
    <span class="compact-match-sub">${m.status === "FINALIZADO" ? "Liquidado" : m.status === "PARCIAL" ? "Parcial" : "Ver ficha"}</span></span></button>`;
}
function renderMatches() {
  const d = state.data;
  const league = $("leagueFilter").value;
  const status = $("statusFilter").value;
  const period = $("periodFilter").value;
  const search = strip($("matchSearch").value.trim());
  const sort = $("sortFilter").value;
  const now = Date.now();
  const list = d.matches.filter(m => {
    if (league && m.liga !== league) return false;
    if (status && m.status !== status) return false;
    if (period === "next" && (!d.currentIds.has(m.id) || m.kickoff <= now)) return false;
    if (period === "past" && m.kickoff > now) return false;
    if (search && !strip([m.local,m.visitante,m.liga,...m.picks.map(x => x.seleccion+" "+x.mercado)].join(" ")).includes(search)) return false;
    return true;
  }).sort((a,b) => sort === "desc" ? b.kickoff-a.kickoff : a.kickoff-b.kickoff);
  const shown = list.slice(0,state.matchLimit);
  inner("matchCount", `${integer(list.length)} partidos · ${integer(Math.min(shown.length,list.length))} visibles`);
  inner("matchesGrid", shown.length ? shown.map(matchCard).join("") : `<div class="empty-state">Ningún partido coincide con estos filtros.</div>`);
  $("loadMore").hidden = shown.length >= list.length;
}
function matchCard(m) {
  const picks = m.picks.slice(0,3);
  return `<button type="button" data-open-id="${escapeHtml(m.id)}" class="match-card">
    <div class="match-top"><span class="match-kickoff">${escapeHtml(displayDate(m.fecha_utc))} · ${escapeHtml(m.liga)}</span>${matchPill(m)}</div>
    <div class="match-versus">
      <div class="team-side">${teamCrest(m.liga, m.local)}<span class="team-name">${escapeHtml(m.local)}</span></div>
      <span class="versus-label ${m.score?"score":""}">${m.score?escapeHtml(m.score):"VS"}</span>
      <div class="team-side away">${teamCrest(m.liga, m.visitante)}<span class="team-name">${escapeHtml(m.visitante)}</span></div>
    </div><div class="match-picks">
    ${picks.length ? picks.map(x => `<div class="mini-pick"><i class="pick-dot ${outcome(x)}"></i>
      <span>${escapeHtml(x.seleccion)}</span><strong>${percent(numberOrNull(x.probabilidad))}</strong></div>`).join("") : empty("Sin selecciones archivadas")}
    </div><div class="match-footer"><span>${integer(m.finishedPicks)} / ${integer(m.picks.length)} evaluadas ${m.odds.length ? " · "+integer(m.odds.length)+" cuota(s)" : ""}</span><span class="card-arrow">↗</span></div>
  </button>`;
}
function renderHistory() {
  const d = state.data;
  inner("historySummary",
    kpi("Selecciones archivadas", integer(d.top.registered), "Primer pronóstico antes del partido") +
    kpi("Aciertos", integer(d.top.hits), "Liquidaciones confirmadas", true) +
    kpi("Fallos", integer(d.top.losses), "No incluye faltas de datos") +
    kpi("Acierto Top 3", percent(d.top.accuracy), d.top.evaluated + " evaluadas")
  );
  const league = $("historyLeagueFilter").value;
  const market = $("historyMarketFilter").value;
  const status = $("historyStatusFilter").value;
  const search = strip($("historySearch").value);
  const rows = d.archivedPicks.filter(r => {
    if (league && r.liga !== league) return false;
    if (market && r.mercado !== market) return false;
    if (status === "win" && !(settled(r) && r.resultado === "1")) return false;
    if (status === "loss" && !(settled(r) && r.resultado === "0")) return false;
    if (status === "pending" && settled(r)) return false;
    return !search || strip([r.local,r.visitante,r.mercado,r.seleccion].join(" ")).includes(search);
  }).sort((a,b) => String(b.fecha_utc).localeCompare(String(a.fecha_utc)) ||
      String(a.clave).localeCompare(String(b.clave)));
  const shown = rows.slice(0,state.historyLimit);
  $("historyCount").textContent = `${integer(shown.length)} de ${integer(rows.length)}`;
  inner("historyRows", shown.length ? shown.map(r => `<tr><td><div class="main-cell">${teamPair(r)}</div><div class="sub-cell">${escapeHtml(displayDay(r.fecha_utc))}</div></td>
    <td class="muted-cell">${escapeHtml(r.liga)}</td>
    <td class="pick-cell"><div class="main-cell">${escapeHtml(r.mercado)}</div><div class="sub-cell">${escapeHtml(r.seleccion)}</div></td>
    <td><strong>${percent(numberOrNull(r.probabilidad))}</strong></td><td>${resultPill(r)}</td>
    <td><button class="row-link" type="button" data-open-id="${escapeHtml(r.id)}" title="Ver partido" aria-label="Ver ${escapeHtml(r.local)} contra ${escapeHtml(r.visitante)}">↗</button></td></tr>`).join("") :
    `<tr><td colspan="6" class="empty">No hay selecciones con estos filtros.</td></tr>`);
  $("historyMore").hidden = shown.length >= rows.length;
}
function chartProfit(rows) {
  const valid = rows.filter(r => settled(r) && numberOrNull(r.retorno_simulado_unidad) !== null)
    .sort((a,b) => String(a.fecha_utc).localeCompare(String(b.fecha_utc)) ||
      String(a.clave).localeCompare(String(b.clave)));
  if (!valid.length) return empty("Todavía no hay cuotas liquidadas para trazar una evolución.");
  const values = [0], names = ["Inicio"];
  let sum = 0;
  for (const row of valid) {
    sum += numberOrNull(row.retorno_simulado_unidad);
    values.push(sum);
    names.push(row.local + " – " + row.visitante);
  }
  let min = Math.min(...values,0), max = Math.max(...values,0);
  const margin = Math.max(.25,(max-min)*.13);
  min -= margin; max += margin;
  const W=640,H=215,L=45,R=19,T=20,B=34;
  const x = i => L+(i/(values.length-1))*(W-L-R);
  const y = val => T+(max-val)/(max-min)*(H-T-B);
  const d = values.map((val,i) => `${i?"L":"M"} ${x(i).toFixed(2)} ${y(val).toFixed(2)}`).join(" ");
  const area = d+` L ${x(values.length-1).toFixed(2)} ${y(min).toFixed(2)} L ${x(0).toFixed(2)} ${y(min).toFixed(2)} Z`;
  const zeroY=y(0).toFixed(2);
  const dot = values.map((val,i) => `<circle cx="${x(i).toFixed(2)}" cy="${y(val).toFixed(2)}" r="${i===values.length-1?5:3}" fill="#b9f478"><title>${escapeHtml(names[i])}: ${escapeHtml(decimal(val))} u.</title></circle>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Balance hipotético acumulado de 1 unidad por selección, ${values.length-1} liquidadas. Total ${escapeHtml(money(sum))}">
    <defs><linearGradient id="profitFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b9f478" stop-opacity=".23"/><stop offset="1" stop-color="#b9f478" stop-opacity="0"/></linearGradient></defs>
    <line x1="${L}" y1="${zeroY}" x2="${W-R}" y2="${zeroY}" stroke="#667689" stroke-dasharray="4 5"/>
    <line class="axis-grid" x1="${L}" y1="${T}" x2="${L}" y2="${H-B}"/>
    <text class="axis-label" x="5" y="${T+4}">${escapeHtml(decimal(max-margin))}</text>
    <text class="axis-label" x="5" y="${H-B+4}">${escapeHtml(decimal(min+margin))}</text>
    <text class="axis-label" x="${L}" y="${H-8}">Inicio</text>
    <text class="axis-label" x="${W-R}" text-anchor="end" y="${H-8}">${valid.length} liquidadas</text>
    <path d="${area}" fill="url(#profitFill)"/><path d="${d}" fill="none" stroke="#b9f478" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
    ${dot}</svg>`;
}

function realOddsCard(item) {
  const q=item.mejor;
  const dpp=Number(q.diferencia_puntos_pct);
  const pText=(dpp>0?"+":"")+numberFmt.format(dpp)+" pp";
  const ev=Number(q.ev_teorico_unidad);
  const evText=(ev>0?"+":"")+numberFmt.format(ev)+" u./u. (hipotético)";
  const alternatives=item.opciones.length>1 ? `<details class="realodds-alternatives">
    <summary>Otras ${integer(item.opciones.length-1)} cotizaciones <span aria-hidden="true">⌄</span></summary>
    ${item.opciones.slice(1).map(other=>`<div class="realodds-option">
      <strong>${escapeHtml(other.bookmaker)} · ${escapeHtml(other.proveedor)}</strong>
      <span>Cuota ${decimal(other.cuota_real)} · margen ${percent(other.margen_casa)}
        · ${other.marca_tiempo_tipo==="CAPTURA_NO_ACTUALIZACION"?"capturada":"actualizada"} ${escapeHtml(displayDate(other.actualizado_utc))}</span>
    </div>`).join("")}
  </details>` : "";
  const marker=item.posicion_top3>=1 && item.posicion_top3<=3?
    "TOP 3 ORIGINAL":"ESTIMACIÓN ADICIONAL";
  return `<article class="realodds-card">
    <div class="realodds-card-top"><span>${escapeHtml(item.liga)} · ${escapeHtml(displayDate(item.fecha_utc))}</span>
      <span>${marker}</span></div>
    <div class="realodds-teams">
      ${teamCrest(item.liga,item.local,true)}<strong>${escapeHtml(item.local)} – ${escapeHtml(item.visitante)}</strong>
      ${teamCrest(item.liga,item.visitante,true)}</div>
    <div class="realodds-selection"><small>${escapeHtml(({result:"RESULTADO 1X2",goals:"GOLES TOTALES",corners:"CÓRNERS TOTALES",yellow:"AMARILLAS TOTALES",btts:"AMBOS MARCAN"})[item.categoria]||"MERCADO")}</small>
      <strong>${escapeHtml(item.seleccion)}</strong></div>
    <div class="realodds-number-grid">
      <div><span>Prob. del modelo</span><strong>${percent(item.probabilidad_modelo)}</strong></div>
      <div><span>Cuota justa teórica</span><strong>${decimal(1/item.probabilidad_modelo)}</strong></div>
      <div class="realodds-main-price"><span>Cuota observada</span><strong>${decimal(q.cuota_real)}</strong>
        <small>${escapeHtml(q.bookmaker)} · ${escapeHtml(q.proveedor)}</small></div>
    </div>
    <div class="realodds-explanation">
      <div><span>Prob. implícita</span><strong>${percent(q.p_implicita)}</strong></div>
      <div><span>Prob. sin margen¹</span><strong>${percent(q.p_mercado_sin_margen)}</strong></div>
      <div><span>Margen de esta casa</span><strong>${percent(q.margen_casa)}</strong></div>
      <div><span>Diferencia modelo–mercado</span><strong>${escapeHtml(pText)}</strong></div>
    </div>
    <div class="realodds-math"><span>EV teórico con p del modelo: <strong>${escapeHtml(evText)}</strong></span>
      <small>¹ Ajuste calculado con todos los resultados de la misma casa y mercado;
      no predice ganancia ni demuestra calibración.</small></div>
    <div class="realodds-card-foot">
      <div class="realodds-source">${escapeHtml(q.proveedor)} · ${q.marca_tiempo_tipo==="CAPTURA_NO_ACTUALIZACION"?"consulta registrada":"actualización del proveedor"} ${escapeHtml(displayDate(q.actualizado_utc))}
        · capturada ${escapeHtml(displayDate(q.capturado_utc))}</div>
      ${alternatives}
      <button type="button" class="inline-link" data-open-id="${escapeHtml(item.fixture_id)}">Ver ficha del partido ↗</button>
    </div>
  </article>`;
}
function renderRealOdds() {
  if(!state.data)return;
  const filter={
    league:$("realOddsLeague").value,market:$("realOddsMarket").value,
    bookmaker:$("realOddsBookmaker").value,
    minProbability:$("realOddsProbability").value,
    team:$("realOddsTeam").value
  };
  const all=realOddsSnapshot(state.data,{...filter,bookmaker:""});
  const bookSelect=$("realOddsBookmaker");
  const prev=bookSelect.value;
  bookSelect.innerHTML='<option value="">Todas las casas</option>'+
    all.providers.map(x=>`<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join("");
  bookSelect.value=all.providers.includes(prev)?prev:"";
  const view=realOddsSnapshot(state.data,{...filter,bookmaker:bookSelect.value});
  $("realOddsCount").textContent=integer(view.cards.length)+" comparaciones";
  inner("realOddsKpis",
    kpi("Partidos con cuota",integer(view.games),"Solo cruzados con identidad y hora")+
    kpi("Comparaciones",integer(view.cards.length),"Mismo resultado y línea")+
    kpi("Casas observadas",integer(view.providers.length),"Fuente EU · no implica acceso local")+
    kpi("Última captura",view.sourceUpdated?displayDate(view.sourceUpdated):"—",
      "Precios caducan; máximo 24 horas")
  );
  const status={
    SIN_PUBLICAR:"Los archivos de esta fase todavía no se han publicado. Se mostrarán tras ejecutar el motor.",
    DESACTIVADO:"Comparación preparada, pero desactivada. Puedes habilitar 5DollarFootballAPI (gratuito), API-Football o The Odds API mediante claves privadas de GitHub. Sin ellas no se ha consultado ningún bookmaker.",
    SIN_CLAVE:"Hay un proveedor activado sin su clave privada en GitHub Secrets. No hay ofertas verificadas para mostrar.",
    SIN_COINCIDENCIAS:"No hay cuotas actuales verificadas para estos partidos o mercados. No se emplearán cuotas antiguas, teóricas ni aproximadas.",
    PARCIAL:"El proveedor respondió parcialmente o con errores; solo se muestran precios que pasaron todas las verificaciones.",
    CON_CUOTAS:"Precios prepartido de proveedores identificados, cruzados con partidos futuros y líneas exactas. No se garantiza disponibilidad ni rentabilidad.",
    INICIADO:"Consulta pendiente de completar."
  };
  const text=status[view.status]||"No hay precios prepartido verificables para la selección.";
  $("realOddsNotice").innerHTML="<strong>"+escapeHtml(text)+"</strong> "+
    (view.cards.length?"Se muestran primero los encuentros más próximos. ":"")+
    "Solo 1X2, goles, córners, BTTS y amarillas explícitas; mercados sin equivalencia o datos permanecen sin cuota.";
  const rows=view.cards.slice(0,state.realOddsLimit);
  inner("realOddsCards",rows.length?rows.map(realOddsCard).join("") :
    empty(view.configured
      ?"No existen precios válidos con estos filtros. Prueba otro mercado, casa o liga."
      :"Añade la clave de la API y activa la conexión para consultar precios reales, sin inventarlos."));
  $("realOddsMore").hidden=rows.length>=view.cards.length;
}

function renderOdds() {
  const d=state.data, s=d.simulation;
  inner("oddsSummary", kpi("Cuotas registradas", integer(s.registered), "Todas superiores a 1,50") +
    kpi("Acertadas / liquidadas", integer(s.hits)+" / "+integer(s.evaluated), "Solo marcadores comprobados") +
    kpi("Balance simulado", money(s.profit), "1 unidad por selección", true) +
    kpi("ROI simulado", percent(s.roi), s.priced+" cuotas con retorno calculable"));
  inner("oddsChart", chartProfit(d.allOdds));
  const odds = [...d.allOdds].sort((a,b)=>String(b.fecha_utc).localeCompare(String(a.fecha_utc)));
  $("oddsCount").textContent = integer(odds.length)+" cuotas";
  inner("oddsRows", odds.length ? odds.map(r => `<tr>
    <td><div class="main-cell">${teamPair(r)}</div><div class="sub-cell">${escapeHtml(displayDay(r.fecha_utc))} · ${escapeHtml(r.liga)}</div></td>
    <td class="pick-cell"><div class="main-cell">${escapeHtml(r.seleccion)}</div><div class="sub-cell">${escapeHtml(r.tipo_cuota === "INDICATIVA_NO_VERIFICADA"?"Precio indicativo no verificado":r.tipo_cuota)}</div></td>
    <td><strong>${decimal(r.cuota_decimal)}</strong></td><td>${resultPill(r)}</td>
    <td><strong style="color:${numberOrNull(r.retorno_simulado_unidad)>0?"var(--lime)":numberOrNull(r.retorno_simulado_unidad)<0?"var(--red)":"var(--muted)"}">${escapeHtml(money(numberOrNull(r.retorno_simulado_unidad)))}</strong></td>
    <td><button type="button" class="row-link" data-open-id="${escapeHtml(r.id)}" aria-label="Abrir ficha ${escapeHtml(r.local)} – ${escapeHtml(r.visitante)}">↗</button></td></tr>`).join("") : `<tr><td class="empty" colspan="6">No hay cuotas archivadas.</td></tr>`);
}
function marketLineOptions() {
  const market=optionByKey($("marketFilter").value);
  const chosen=$("marketLine").value;
  const label = market.kind==="outcome" ? "RESULTADO" :
    market.kind==="btts" ? "AMBOS MARCAN" : "LÍNEA DE REFERENCIA";
  $("marketLineLabel").textContent=label;
  $("marketLine").innerHTML=market.lines.map(x=>{
    const readable=typeof x==="number" ? numberFmt.format(x).replace(/,00$/,"") : x;
    return `<option value="${escapeHtml(x)}">${escapeHtml(readable)}</option>`;
  }).join("");
  $("marketLine").value=market.lines.some(x=>String(x)===chosen) ? chosen :
    String(market.lines[Math.floor(market.lines.length/2)]);
}
function marketSummaryLabel(market,line) {
  if(market.kind==="outcome"){
    if(line==="1X")return "Local o empate (1X)";
    if(line==="X2")return "Empate o visitante (X2)";
    if(line==="12")return "Local o visitante (12)";
    return "Resultado " + line;
  }
  if(market.kind==="btts")return "Ambos marcan: " + line;
  return "Más de " + numberFmt.format(Number(line)).replace(/,00$/,"");
}
function marketSourceLabel(sources) {
  const found=(sources||[]).map(sourceLink);
  return found.length ? found.join(" · ") : "Sin fuente identificada";
}

function forecastLevel(level) {
  if (level==="BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA")
    return {text:"Backtest retrospectivo",css:"audited",hint:"Superó comprobaciones retrospectivas; aún no validado prospectivamente"};
  if (level==="EXPLORATORIO_NO_VALIDADO")
    return {text:"Exploratorio",css:"experimental",hint:"Modelo de conteos todavía sin validación específica"};
  return {text:"Modelo no calibrado",css:"uncalibrated",hint:"Probabilidad orientativa, sin calibración demostrada"};
}
function forecastMiniPrediction(p, index) {
  const level=forecastLevel(p.nivel);
  return `<div class="future-alternative">
    <div><strong>${escapeHtml(p.seleccion)}</strong><small>${escapeHtml(level.text)}${Number.isInteger(p.posicion_top3)?" · Top 3 #"+p.posicion_top3:""}</small></div>
    <span>${percent(p.probabilidad)} <small>· cuota justa ${decimal(p.cuota_justa)}</small></span>
  </div>`;
}
function marketFutureCard(m) {
  const p=m.best, level=forecastLevel(p.nivel);
  const others=m.pronosticos.slice(1);
  return `<article class="future-market-card">
    <div class="future-card-header">
      <span class="future-kickoff">${escapeHtml(m.liga)} · ${escapeHtml(displayDate(m.fecha_utc))}</span>
      <span class="forecast-state">${Number.isInteger(p.posicion_top3)?"TOP 3 #"+p.posicion_top3:"PREDICCIÓN ADICIONAL"}</span>
    </div>
    <div class="future-teams">
      <div class="future-team">${teamCrest(m.liga,m.local)}<strong>${escapeHtml(m.local)}</strong></div>
      <span class="future-vs">VS</span>
      <div class="future-team away">${teamCrest(m.liga,m.visitante)}<strong>${escapeHtml(m.visitante)}</strong></div>
    </div>
    <div class="future-main-pick">
      <div class="future-pick-info"><small>PRONÓSTICO DEL MERCADO</small><strong>${escapeHtml(p.seleccion)}</strong></div>
      <div class="future-probability"><strong>${percent(p.probabilidad)}</strong><span>Probabilidad estimada</span></div>
    </div>
    <div class="future-card-meta">
      <span class="future-quality ${level.css}" title="${escapeHtml(level.hint)}">${escapeHtml(level.text)}</span>
      <span>Cuota justa teórica: <strong>${decimal(p.cuota_justa)}</strong></span>
    </div>
    <div class="future-card-footer">
      <button type="button" class="inline-link" data-open-id="${escapeHtml(m.id)}">Ver ficha del partido ↗</button>
      ${others.length ? `<details class="future-alternatives"><summary>Otras ${others.length} líneas calculadas <span aria-hidden="true">⌄</span></summary>
        <div class="future-alternatives-list">${others.map(forecastMiniPrediction).join("")}</div></details>` : ""}
    </div>
  </article>`;
}
function renderMarketReliability() {
  const d=state.data;
  if(!d)return;
  const market=$("marketFilter").value,league=$("marketLeagueFilter").value,
    quality=$("marketQualityFilter").value;
  const view=reliabilitySnapshot(d.futureMarketAudit,{market,league,quality});
  const r=view.metrics,n=r.muestra||0;
  $("marketReliabilityNote").textContent="Archivo independiente · sin recalcular el Top 3";
  if(!view.available){
    $("marketReliabilityNotice").innerHTML="<strong>Aún no se ha publicado el registro prospectivo de la Fase 4.</strong> " +
      "La siguiente ejecución del motor creará el archivo inicial; no se reconstruirán resultados anteriores.";
  }else if(!n){
    $("marketReliabilityNotice").innerHTML="<strong>Seguimiento activado, sin partidos liquidados todavía con estos filtros.</strong> " +
      "Hay "+integer(r.registradas)+" selecciones archivadas desde el inicio de la Fase 4. " +
      "El acierto, Brier y calibración aparecerán únicamente tras verificar los resultados de partidos futuros.";
  }else if(!view.uniqueEnough){
    $("marketReliabilityNotice").innerHTML="<strong>Resultados prospectivos disponibles, pero todavía con muestra pequeña.</strong> " +
      "Hay "+integer(n)+" selecciones resueltas de "+integer(r.partidos_unicos)+" partidos distintos. " +
      "Varias líneas de un mismo encuentro están correlacionadas; no se puede afirmar que el modelo esté calibrado.";
  }else{
    $("marketReliabilityNotice").innerHTML="<strong>Evaluación prospectiva observacional.</strong> " +
      integer(n)+" selecciones de "+integer(r.partidos_unicos)+" partidos distintos, " +
      "sin reconstrucciones retrospectivas. No equivale a una ventaja de apuestas.";
  }
  const pct=value=>value===null||value===undefined?"—":numberFmt.format(value)+" %";
  const metric=value=>value===null||value===undefined?"—":
    new Intl.NumberFormat("es-ES",{minimumFractionDigits:3,maximumFractionDigits:3}).format(value);
  inner("marketReliabilityKpis",
    kpi("Líneas archivadas",integer(r.registradas),"Primer snapshot prepartido")+
    kpi("Evaluadas",integer(n),integer(r.partidos_unicos)+" partidos únicos",true)+
    kpi("Acierto observado",pct(r.acierto_pct),r.aciertos+" aciertos · "+integer(r.pendientes)+" pendientes")+
    kpi("Brier / ECE",metric(r.brier)+" / "+metric(r.ece),
      "Menor es mejor · probabilidad media "+pct(r.probabilidad_media_pct))
  );
  $("marketCalibrationSample").textContent=n+" evaluadas";
  inner("marketCalibrationChart",r.calibracion?.length?r.calibracion.map(point=>`
    <div class="calibration-row">
      <span class="calibration-range">${escapeHtml(point.rango)}</span>
      <div class="calibration-bars">
        <span class="calibration-estimated" style="width:${Math.max(0,Math.min(100,point.probabilidad_media_pct))}%"></span>
        <span class="calibration-actual" style="width:${Math.max(0,Math.min(100,point.acierto_pct))}%"></span>
      </div>
      <span class="calibration-value">${pct(point.probabilidad_media_pct)} / ${pct(point.acierto_pct)}
        <small>n=${integer(point.muestra)}</small></span>
    </div>`).join(""):empty("Aún no hay resultados suficientes para representar la calibración."));
  inner("marketReliabilityLeagues",view.leagues.length?
    view.leagues.map(row=>`<div class="league-row">
      ${leagueLogo(row.liga)}
      <div class="league-info">
        <div class="league-name">${escapeHtml(row.liga)}</div>
        <div class="league-sub">${integer(row.muestra)} selecciones · ${integer(row.partidos_unicos)} partidos distintos</div>
      </div>
      <span class="market-mini-percent">${pct(row.acierto_pct)}</span>
    </div>`).join("") :empty("No hay predicciones archivadas de este mercado y liga."));
  inner("marketReliabilityRows",view.recent.length?view.recent.map(row=>{
    const label=row.estado==="FINALIZADO"?
      (String(row.resultado)==="1"?"ACIERTO":"FALLO"):
      row.estado==="ESTADISTICA_NO_DISPONIBLE"?"SIN ESTADÍSTICA":
      row.estado==="RESULTADO_NO_DISPONIBLE"?"SIN MARCADOR":"NO RESUELTA";
    const cls=row.estado!=="FINALIZADO"?"missing":String(row.resultado)==="1"?"final":"loss";
    return `<tr>
      <td><div class="main-cell">${teamPair(row)}</div>
        <div class="sub-cell">${escapeHtml(displayDay(row.fecha_utc))} · ${escapeHtml(row.liga)}</div></td>
      <td><strong>${escapeHtml(row.seleccion)}</strong>
        <div class="sub-cell">${escapeHtml(forecastLevel(row.nivel).text)}
          ${["1","2","3"].includes(String(row.posicion_top3))?" · También Top 3":""}
          ${row.valor_real!==""?" · Observado: "+escapeHtml(row.valor_real):""}
        </div></td>
      <td>${percent(numberOrNull(row.probabilidad))}</td>
      <td><span class="status-pill ${cls}">${label}</span></td></tr>`;
  }).join(""):`<tr><td class="empty" colspan="4">Todavía no hay selecciones evaluadas de este mercado con estos filtros.</td></tr>`);
}

function renderFutureMarkets() {
  const d=state.data;
  if(!d)return;
  const filters={
    market:$("marketFilter").value,
    league:$("marketLeagueFilter").value,
    team:$("marketTeam").value,
    quality:$("marketQualityFilter").value,
    order:$("marketOrder").value,
    minProbability:$("marketMinProbability").value,
    minFair:$("marketMinFair").value
  };
  const result=futureMarketSnapshot(d,filters);
  const {fixtures,market,qualityCounts}=result;
  $("marketFutureTitle").textContent="Próximos partidos · "+market.label;
  $("marketFutureCount").textContent=integer(fixtures.length)+" partidos con pronóstico";
  inner("marketFutureKpis",
    kpi("Próximos partidos",integer(result.futureMatches),"En las competiciones seleccionadas")+
    kpi("Con pronóstico",integer(fixtures.length),integer(result.withoutMarket)+" sin este mercado",true)+
    kpi("Líneas calculadas",integer(result.forecastCount),"Estimaciones futuras, no apuestas")+
    kpi("En Top 3 original",integer(qualityCounts.top3),"El resto no se archiva como Top 3")
  );
  const unsupported=["fouls","red"].includes(market.key);
  const missingFeed=!(d.marketFutures?.length);
  if(missingFeed){
    $("marketFutureNotice").innerHTML="<strong>Los pronósticos por mercado todavía no están disponibles.</strong> " +
      "Comprueba la última ejecución diaria y pulsa Actualizar cuando se haya publicado el nuevo archivo.";
  }else if(unsupported){
    $("marketFutureNotice").innerHTML="<strong>Este mercado todavía no tiene modelo prepartido disponible.</strong> " +
      "No se generarán pronósticos de "+escapeHtml(market.label.toLowerCase())+
      " a partir de estadísticas históricas sin un modelo validable. Puedes consultar los resultados anteriores abajo.";
  }else if(!fixtures.length){
    $("marketFutureNotice").innerHTML="<strong>No hay pronósticos futuros de "+escapeHtml(market.label.toLowerCase())+
      " con estos filtros.</strong> Prueba otra liga o «Todos los disponibles». " +
      "No se sustituyen por cifras históricas ni se inventan probabilidades.";
  }else{
    $("marketFutureNotice").innerHTML="<strong>"+escapeHtml(market.label)+" · "+integer(fixtures.length)+
      " encuentros próximos con estimaciones.</strong> La primera línea de cada ficha es la de mayor probabilidad " +
      "dentro de este mercado; abre «Otras líneas» para ver alternativas calculadas. " +
      "Los pronósticos del Top 3 se identifican por separado.";
  }
  const rows=fixtures.slice(0,state.futureMarketLimit);
  inner("marketFutureGrid",rows.length?rows.map(marketFutureCard).join(""):
    '<div class="empty-state">No hay predicciones prepartido disponibles para este mercado y filtros.</div>');
  $("marketFutureMore").hidden=rows.length>=fixtures.length;
  renderMarketReliability();
}

function renderMarkets() {
  const d=state.data;
  if(!d)return;
  renderFutureMarkets();
  const selection={
    market:$("marketFilter").value,
    league:$("marketLeagueFilter").value,
    days:$("marketPeriod").value,
    line:$("marketLine").value,
    team:$("marketTeam").value
  };
  const view=marketSnapshot(d,selection);
  const market=view.market;
  document.querySelectorAll("[data-market-key]").forEach(button=>{
    button.classList.toggle("active",button.dataset.marketKey===market.key);
    button.setAttribute("aria-pressed",button.dataset.marketKey===market.key?"true":"false");
  });
  const n=view.verified, selectedName=marketSummaryLabel(market,view.line);
  const numeric=market.kind==="count"||market.kind==="goals";
  const avg=n ? numberFmt.format(view.average) : "—";
  inner("marketKpis",
    kpi("Partidos con dato",integer(n),integer(view.missing)+" sin estadística para este mercado")+
    kpi(numeric?"Media por partido":"Resultado observado",numeric?avg:"1 / X / 2",
      numeric&&n?"Mediana: "+numberFmt.format(view.median):"Marcadores contrastados")+
    kpi("Frecuencia histórica",n?percent(view.aboveRate):"—",
      selectedName+" · "+integer(view.above)+" de "+integer(n),true)+
    kpi("Acierto Top 3",percent(view.picks.accuracy),
      integer(view.picks.evaluated)+" evaluadas de "+integer(view.picks.registered)+" archivadas")
  );
  $("marketNotice").innerHTML=n?
    `<strong>${escapeHtml(market.label)}</strong> · ${integer(n)} partidos con información suficiente, de ${integer(view.historicalCount)} disputados en el filtro. ${integer(view.missing)} sin datos para esta métrica. <span>La frecuencia es descriptiva, no un pronóstico.</span>`
    :`<strong>Sin datos suficientes de ${escapeHtml(market.label.toLowerCase())}.</strong> Hay ${integer(view.historicalCount)} partidos disputados en el intervalo, pero no tenemos una fuente completa de esta estadística. No se muestra 0 ni se estiman valores.`;
  $("marketChartTitle").textContent=numeric?"Distribución de "+market.label.toLowerCase():"Resultados observados";
  $("marketChartSample").textContent=integer(n)+" partidos";
  const biggest=Math.max(1,...view.distribution.map(x=>x.count));
  inner("marketHistogram",view.distribution.length?view.distribution.map(item=>{
    const width=Math.round(item.count/biggest*100);
    return `<div class="market-bar-row"><span class="market-bar-label">${escapeHtml(item.label)}</span>
      <div class="market-bar-track"><div class="market-bar-fill" style="width:${width}%"></div></div>
      <span class="market-bar-value">${integer(item.count)} <small>(${n?percent(item.count/n):"—"})</small></span></div>`;
  }).join(""):empty("Aún no existen observaciones verificadas de este mercado."));
  $("marketChartCaption").textContent=numeric?
    "Cantidad total del partido (local + visitante). Solo se incluyen estadísticas completas, no estimadas.":
    "Distribución de los resultados finales. No representa el porcentaje de acierto de una selección apostada.";
  const leagues=LEAGUES.filter(x=>!selection.league||selection.league===x);
  const comparison=leagues.map(league=>{
    const sample=view.byLeague.find(x=>x.liga===league);
    const amount=sample?.partidos||0;
    return `<div class="league-row">${leagueLogo(league)}<div class="league-info">
      <div class="league-name">${escapeHtml(league)}</div>
      <div class="league-sub">${integer(amount)} partidos · ${numeric?"Media "+(sample?.media===null||!amount?"—":numberFmt.format(sample.media)):"Resultados finales"}</div></div>
      <div class="market-mini-track"><span style="width:${Math.round((sample?.ratio||0)*100)}%"></span></div>
      <span class="market-mini-percent">${amount?percent(sample.ratio):"—"}</span></div>`;
  }).join("");
  inner("marketByLeague",comparison||empty("No hay competiciones."));
  $("marketTotalHeading").textContent=numeric?"Total": "Resultado";
  $("marketConditionHeading").textContent=numeric?"¿Supera la línea?":"¿Cumple selección?";
  const rows=view.rows.slice(0,state.marketLimit);
  $("marketCount").textContent=integer(rows.length)+" de "+integer(view.rows.length)+" verificados";
  inner("marketRows",rows.length?rows.map(x=>{
    const r=x.row,obs=x.observation,good=isHit(obs,market,view.line);
    const result=numeric?obs.total:market.kind==="btts"?obs.btts:obs.outcome;
    return `<tr>
      <td><div class="main-cell">${teamPair(r)}</div><div class="sub-cell">${escapeHtml(displayDay(r.fecha))}</div></td>
      <td class="muted-cell">${escapeHtml(r.liga)}</td>
      <td><strong>${escapeHtml(r.goles_local)} – ${escapeHtml(r.goles_visitante)}</strong></td>
      <td class="market-count-cell">${numeric?integer(obs.local):"—"}</td>
      <td class="market-count-cell">${numeric?integer(obs.visitante):"—"}</td>
      <td class="market-count-cell"><strong>${escapeHtml(result)}</strong></td>
      <td><span class="status-pill ${good?"final":"loss"}">${good?"Sí":"No"}</span>
        <div class="market-source-row">${marketSourceLabel(obs.fuentes)}</div></td>
      </tr>`;
  }).join(""):`<tr><td class="empty" colspan="7">No hay partidos con esta estadística y filtros. Prueba otro periodo o competición.</td></tr>`);
  $("marketMore").hidden=rows.length>=view.rows.length;
}

function radarObservation(stat, profile, sideName, observed, category) {
  if(!stat.games) return `<div class="radar-observation"><strong>${escapeHtml(sideName)}</strong><span>Sin partidos anteriores en esta condición</span></div>`;
  const isResult=["double","result","btts"].includes(category);
  const description=isResult
    ?`Victorias ${integer(stat.wins)} · Empates ${integer(stat.draws)} · Derrotas ${integer(stat.losses)}
      ${category==="btts"?" · Ambos marcaron "+integer(stat.bothScored)+"/"+integer(stat.games):""}`
    :`Media por encuentro: <strong>${stat.mean===null?"—":numberFmt.format(stat.mean)}</strong>
      · ${integer(stat.verified)}/${integer(stat.games)} partidos con dato`;
  const frequency=!isResult&&observed
    ?`<small>La línea calculada se cumplió en ${integer(observed.matched)}
        de ${integer(observed.observed)} encuentros previos (${percent(observed.frequency)}).</small>`:"";
  return `<div class="radar-observation"><strong>${escapeHtml(sideName)}</strong><span>${description}</span>
    ${frequency}<small>Último partido incluido: ${stat.latest?escapeHtml(displayDay(stat.latest)):"—"}</small></div>`;
}
function radarCard(item) {
  const p=item.best, r=item.profile, level=forecastLevel(p.nivel);
  const coverage=r.coverage===null?"Sin datos":percent(r.coverage);
  return `<article class="radar-card">
    <div class="radar-card-top"><span>${escapeHtml(item.liga)} · ${escapeHtml(displayDate(item.fecha_utc))}</span>
      <span class="future-quality ${level.css}" title="${escapeHtml(level.hint)}">${escapeHtml(level.text)}</span>
    </div>
    <div class="radar-card-teams">
      <span>${teamCrest(item.liga,item.local,true)}<strong>${escapeHtml(item.local)}</strong></span>
      <small>VS</small>
      <span>${teamCrest(item.liga,item.visitante,true)}<strong>${escapeHtml(item.visitante)}</strong></span>
    </div>
    <div class="radar-card-pick">
      <div><small>PRONÓSTICO DEL MODELO</small><strong>${escapeHtml(p.seleccion)}</strong>
        <span>${Number.isInteger(p.posicion_top3)?"Top 3 original, puesto "+p.posicion_top3:"Línea adicional"}
          · Cuota justa teórica ${decimal(p.cuota_justa)}</span></div>
      <div class="radar-prob"><strong>${percent(p.probabilidad)}</strong><small>Modelo</small></div>
    </div>
    <div class="radar-card-meta">
      <span>COBERTURA <strong>${coverage}</strong></span>
      <span>DATOS <strong>${integer(r.verified)}/${integer(r.sample)}</strong></span>
      <span class="${r.enough?"radar-enough":"radar-limited"}">
        ${r.enough?"Muestra disponible":"Muestra limitada"}</span>
    </div>
    <details class="radar-details">
      <summary>Comparativa previa y explicación <span aria-hidden="true">⌄</span></summary>
      <p>Últimos ${integer(r.period)} encuentros de cada equipo
        (${r.scope==="venue_only"?"local en casa y visitante fuera":"todos los partidos"}),
        anteriores a la fecha del pronóstico.</p>
      <div class="radar-observations">
        ${radarObservation(r.home,r,item.local,r.observedHome,r.market)}
        ${radarObservation(r.away,r,item.visitante,r.observedAway,r.market)}
      </div>
      <p>Las medias, frecuencias y coberturas provienen del histórico, y NO se usan
        para inventar una nueva probabilidad. ${r.enough?"":"Muestra reducida: no extraer conclusiones fuertes."}
        Fuente: Football-Data; los datos ausentes no son ceros.</p>
    </details>
    <div class="radar-card-actions">
      <button type="button" class="btn btn-outline" data-open-id="${escapeHtml(item.id)}">Ficha del partido ↗</button>
      <button type="button" class="inline-link" data-radar-to-market="${escapeHtml(r.market)}">Ver mercado ↗</button>
    </div>
  </article>`;
}
function renderRadar() {
  if(!state.data)return;
  const filters={
    market:$("radarMarketFilter").value,league:$("radarLeagueFilter").value,
    minProbability:$("radarProbability").value,
    quality:$("radarQuality").value,coverage:$("radarCoverage").value,
    minFair:$("radarFair").value,window:$("radarWindow").value,
    scope:$("radarScope").value,order:$("radarOrder").value,
    team:$("radarTeam").value
  };
  const result=radarSnapshot(state.data,filters);
  const available=result.rows.filter(x=>x.profile.coverage!==null);
  const coverage=available.length
    ?available.reduce((sum,x)=>sum+x.profile.coverage,0)/available.length:null;
  $("radarCount").textContent=integer(result.total)+" partidos";
  inner("radarKpis",
    kpi("Partidos futuros",integer(result.futureMatches),"Con pronóstico del mercado")+
    kpi("En el radar",integer(result.total),integer(result.belowCoverage)+" excluidos por cobertura",true)+
    kpi("Cobertura media",percent(coverage),"Porcentaje de partidos anteriores con estadística")+
    kpi("Muestra limitada",integer(result.rows.filter(x=>!x.profile.enough).length),
      "Menos de 3 partidos completos por equipo")
  );
  $("radarNotice").textContent=!state.data.marketFutures?.length
    ?"Sin pronósticos futuros publicados; no se estiman resultados."
    :!result.contextAvailable
    ?"El contexto del radar aún no está publicado. Los pronósticos siguen disponibles, pero sin estadísticas inventadas."
    :!result.total
    ?"Ningún encuentro cumple los filtros o este mercado carece de modelo prepartido. Prueba ampliar los criterios."
    :"Radar de investigación · "+integer(result.total)+" encuentros. Ordenados por "+
      (filters.order==="coverage"?"cobertura":filters.order==="confidence"?"probabilidad":"fecha")+
      ". Esto no es un ranking de valor ni rentabilidad.";
  const cards=result.rows.slice(0,state.radarLimit);
  inner("radarGrid",cards.length?cards.map(radarCard).join("") :
    empty("No hay encuentros que cumplan los criterios; no se completan datos ausentes con estimaciones."));
  $("radarMore").hidden=cards.length>=result.rows.length;
}

function renderModel() {
  const d=state.data;
  inner("modelLeagues", d.leagues.map(x => `<div class="model-league-row">
    ${leagueLogo(x.name)}
    <div class="model-league-progress"><strong>${escapeHtml(x.name)}</strong><small>${integer(x.evaluated)} evaluadas de ${integer(x.registered)} archivadas · ${integer(x.currentMatches)} futuros</small></div>
    <div class="model-league-result">${percent(x.accuracy)}</div></div>`).join(""));
  const last=d.updatedAt ? displayDate(d.updatedAt) : "No disponible";
  const q=[
    ["Última publicación",last],
    ["Ligas cubiertas",d.leagues.length],
    ["Pronósticos actuales",integer(d.countForecasts)],
    ["Top 3 archivado",integer(d.top.registered)],
    ["Top 3 verificado",integer(d.top.evaluated)],
    ["Cuotas en seguimiento",integer(d.simulation.registered)],
    ["Partidos con conteos completos",d.evaluations.postmatch?.auditoria_estadisticas ?
      integer(d.evaluations.postmatch.auditoria_estadisticas.completos || 0) + " / " +
      integer(d.evaluations.postmatch.auditoria_estadisticas.objetivos_conteo || 0) : "—"],
    ["Importación",state.errors.length?"Parcial":"Todos los archivos disponibles"],
    ["Repositorio","Público · GitHub Actions"]
  ];
  inner("modelQuality", q.map(([k,v]) => `<div class="quality-row"><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`).join(""));
}
function renderAll() {
  if (!state.data) return;
  const markets=[...new Set(state.data.archivedPicks.map(r=>r.mercado))].filter(Boolean).sort((a,b)=>a.localeCompare(b,"es"));
  for (const id of ["leagueFilter","historyLeagueFilter","marketLeagueFilter","radarLeagueFilter","realOddsLeague"]) {
    const prior=$(id).value;
    insertOptions(id,LEAGUES);
    $(id).value=prior;
  }
  const oldMarket=$("historyMarketFilter").value;
  insertOptions("historyMarketFilter",markets);
  $("historyMarketFilter").value=oldMarket;
  renderOverview();
  renderMatches();
  renderHistory();
  renderOdds();
  renderRealOdds();
  renderMarkets();
  renderRadar();
  renderModel();
}
function dialogPick(row, index, detail = null) {
  const status=resultText(row);
  const finished=settled(row);
  return `<div class="dialog-pick">
    <div class="dialog-pick-top"><span class="overline">SELECCIÓN ${String(index+1).padStart(2,"0")} / ${escapeHtml(row.mercado)}</span>${resultPill(row)}</div>
    <strong>${escapeHtml(row.seleccion)}</strong>
    <p>${escapeHtml(row.nivel || row.origen || "Pronóstico experimental")}</p>
    ${detail?.explicacion ? `<p class="pick-explanation">${escapeHtml(detail.explicacion)}</p>` : ""}
    ${detail?.fuentes?.length ? `<div class="evidence-links">${detail.fuentes.map(sourceLink).join(" · ")}</div>` : ""}
    <div class="dialog-stats"><span>Probabilidad: <b>${percent(numberOrNull(row.probabilidad))}</b></span>
    <span>Cuota justa: <b>${decimal(row.cuota_justa)}</b></span>
    ${finished ? `<span>Valor observado: <b>${escapeHtml(textOrDash(row.valor_real))}</b></span>` : ""}
    </div></div>`;
}
function sourceLink(source) {
  const url = String(source || "");
  if (/^https:\/\/(site\.api\.espn\.com|www\.laliga\.com|www\.football-data\.co\.uk)\//.test(url)) {
    const name = url.includes("espn") ? "ESPN · estadística" :
      url.includes("laliga") ? "LaLiga · resultado" : "Football-Data · histórico";
    return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${name} ↗</a>`;
  }
  return `<span>${escapeHtml(url)}</span>`;
}
function matchStatistics(detail) {
  if (!detail) return "";
  const keys = ["shots","on_target","corners","yellow","red"];
  const stats = detail.estadisticas || {};
  const items = keys.map(key => {
    const s = stats[key];
    if (!s) return "";
    const hasTotal = s.total !== null && s.total !== undefined;
    const local = s.local === null || s.local === undefined ? "—" : s.local;
    const away = s.visitante === null || s.visitante === undefined ? "—" : s.visitante;
    return `<div class="postmatch-stat-row">
      <span class="postmatch-stat-name">${escapeHtml(s.nombre || key)}</span>
      <strong>${escapeHtml(local)}</strong>
      <strong class="${hasTotal ? "stat-verified" : "stat-unavailable"}">${hasTotal ? escapeHtml(s.total) : "—"}</strong>
      <strong>${escapeHtml(away)}</strong>
      ${s.fuentes?.length ? `<small class="stat-source">${s.fuentes.map(sourceLink).join(" · ")}</small>` : ""}
    </div>`;
  }).join("");
  return `<div class="dialog-section">
    <h3>Estadísticas finales verificadas</h3>
    <div class="stat-grid-head"><span>MÉTRICA</span><span>LOCAL</span><span>TOTAL</span><span>VISITANTE</span></div>
    <div class="postmatch-stats">${items}</div>
    <p class="dialog-message">Los guiones indican datos no disponibles, no ceros. ${detail.marcador ?
       "Marcador " + escapeHtml(detail.marcador) + " · " + (detail.fuente_marcador ? sourceLink(detail.fuente_marcador) : "") : "Marcador aún sin verificar."}</p>
  </div>`;
}
function openMatch(id) {
  if (!state.data) return;
  const m=state.data.matches.find(x=>x.id===id);
  if (!m) return;
  state.lastFocus=document.activeElement;
  const forecast=m.historicalForecast || m.forecast;
  const dateOriginal=forecast?.fecha_analisis_utc || forecast?.fecha_pronostico_utc || "";
  const modelForecast=forecast && ["prob_local","prob_empate","prob_visitante"].some(x=>numberOrNull(forecast[x])!==null)
    ? `<div class="dialog-highlight"><strong>Pronóstico 1X2 original · ${escapeHtml(forecast.modelo||"Modelo")}</strong>
      <div class="dialog-stats"><span>Local <b>${percent(numberOrNull(forecast.prob_local))}</b></span>
      <span>Empate <b>${percent(numberOrNull(forecast.prob_empate))}</b></span>
      <span>Visitante <b>${percent(numberOrNull(forecast.prob_visitante))}</b></span></div>
      <small>${dateOriginal?"Archivado: "+escapeHtml(displayDate(dateOriginal)):"Modelo prepartido"}</small></div>`
    : "";
  inner("dialogBody", `<div class="dialog-title-row">
      ${teamCrest(m.liga, m.local)}
      <h2 id="dialogTitle" class="dialog-match-title">${escapeHtml(m.local)} <span style="color:var(--lime)">vs</span> ${escapeHtml(m.visitante)}</h2>
      ${teamCrest(m.liga, m.visitante)}
    </div>
    <p class="dialog-sub">${escapeHtml(m.liga)} · ${escapeHtml(displayDate(m.fecha_utc))}
      ${m.score ? ` · Resultado: <strong>${escapeHtml(m.score)}</strong>` : " · Marcador pendiente"} · ${integer(m.finishedPicks)} de ${integer(m.picks.length)} selecciones liquidadas</p>
    ${modelForecast}
    <div class="dialog-section"><h3>Las tres selecciones por partido</h3>
      ${m.picks.length ? m.picks.slice(0,3).map((row,i) => dialogPick(
         row,i,m.breakdown?.selecciones?.find(x => x.clave === row.clave)
      )).join("") : empty("No se ha archivado todavía el Top 3 de este encuentro.")}
      <div class="dialog-message">Estos son los primeros mercados archivados, no recálculos posteriores. Si falta una estadística, el mercado permanece sin liquidar.</div>
    </div>
    ${matchStatistics(m.breakdown)}
    ${m.odds.length ? `<div class="dialog-section"><h3>Cuotas +1,50 registradas por separado</h3>
      ${m.odds.map(r=>`<div class="dialog-offer"><strong>${escapeHtml(r.seleccion)}</strong>
        <div class="dialog-stats"><span>Cuota <b>${decimal(r.cuota_decimal)}</b></span>
        <span>${resultPill(r)}</span><span>Balance hipotético <b>${escapeHtml(money(numberOrNull(r.retorno_simulado_unidad)))}</b></span></div>
        <span>${escapeHtml(r.tipo_cuota === "INDICATIVA_NO_VERIFICADA" ? "Cuota no verificada · solo simulación" : textOrDash(r.tipo_cuota))}</span></div>`).join("")}
    </div>` : ""}
    <div class="dialog-section"><p class="dialog-message">Fuente de datos: <a href="${GITHUB_URL}/tree/main/output" target="_blank" rel="noopener noreferrer">CSV históricos de Football AI Lab ↗</a>. Las cuotas justas no son ofertas de casas de apuestas. El análisis es experimental.</p></div>`);
  $("dialogBackdrop").hidden=false;
  document.body.style.overflow="hidden";
  $("matchDialog").focus();
}
function closeDialog() {
  $("dialogBackdrop").hidden=true;
  document.body.style.overflow="";
  if (state.lastFocus?.focus) state.lastFocus.focus();
}
function changeView(view) {
  if (!["overview","matches","radar","markets","history","odds","realodds","model"].includes(view)) return;
  state.view=view;
  document.querySelectorAll(".view").forEach(x=>x.hidden=x.id!==`view-${view}`);
  document.querySelectorAll("[data-view]").forEach(x=>{
    const active=x.dataset.view===view;
    x.classList.toggle("active",active);
    if(active) x.setAttribute("aria-current","page");
    else x.removeAttribute("aria-current");
  });
  if (location.hash !== "#"+view) history.replaceState(null,"","#"+view);
  window.scrollTo({top:0,behavior:"instant"});
}

function wire() {
  // Una imagen ausente nunca deja el icono roto en pantalla.
  document.addEventListener("error", e => {
    const image = e.target;
    if (!image.classList?.contains("team-crest")) return;
    image.closest(".crest-shell")?.classList.remove("has-crest");
    image.remove();
  }, true);
  document.addEventListener("click",e=>{
    const radarToMarket=e.target.closest("[data-radar-to-market]");
    if(radarToMarket){
      $("marketFilter").value=radarToMarket.dataset.radarToMarket;
      $("marketLine").value="";
      marketLineOptions();renderMarkets();changeView("markets");return;
    }
    const marketButton=e.target.closest("[data-market-key]");
    if(marketButton){
      $("marketFilter").value=marketButton.dataset.marketKey;
      $("marketLine").value="";
      marketLineOptions();state.marketLimit=35;state.futureMarketLimit=18;renderMarkets();return;
    }
    const viewBtn=e.target.closest("[data-view],[data-go]");
    if(viewBtn){changeView(viewBtn.dataset.view||viewBtn.dataset.go);return;}
    const open=e.target.closest("[data-open-id]");
    if(open){openMatch(open.dataset.openId);return;}
  });
  $("radarMarketFilter").innerHTML=MARKET_OPTIONS.map(x=>
    `<option value="${escapeHtml(x.key)}">${escapeHtml(x.label)}</option>`).join("");
  $("radarMarketFilter").value="corners";
  for(const id of ["radarMarketFilter","radarLeagueFilter","radarProbability",
      "radarQuality","radarCoverage","radarFair","radarWindow","radarScope",
      "radarOrder","radarTeam"]){
    $(id).addEventListener(id==="radarTeam"?"input":"change",()=>{
      state.radarLimit=20;renderRadar();
    });
  }
  $("radarMore").addEventListener("click",()=>{
    state.radarLimit+=20;renderRadar();
  });
  $("marketFilter").innerHTML=MARKET_OPTIONS.map(x=>
    `<option value="${escapeHtml(x.key)}">${escapeHtml(x.label)}</option>`).join("");
  $("marketFilter").value="corners";
  inner("marketQuick",MARKET_OPTIONS.map(x=>
    `<button class="market-chip ${x.key==="corners"?"active":""}" type="button"
      data-market-key="${escapeHtml(x.key)}" aria-pressed="${x.key==="corners"}">${escapeHtml(x.label)}</button>`).join(""));
  marketLineOptions();
  for(const id of ["marketFilter","marketLeagueFilter","marketPeriod","marketLine","marketTeam","marketQualityFilter","marketOrder","marketMinProbability","marketMinFair"]){
    $(id).addEventListener(id==="marketTeam"?"input":"change",()=>{
      if(id==="marketFilter")marketLineOptions();
      state.marketLimit=35;state.futureMarketLimit=18;renderMarkets();
    });
  }
  $("marketMore").addEventListener("click",()=>{state.marketLimit+=35;renderMarkets()});
  $("marketFutureMore").addEventListener("click",()=>{state.futureMarketLimit+=18;renderFutureMarkets()});

  for(const id of ["realOddsLeague","realOddsMarket","realOddsBookmaker",
                   "realOddsProbability","realOddsTeam"]){
    $(id).addEventListener(id==="realOddsTeam"?"input":"change",()=>{
      state.realOddsLimit=24;renderRealOdds();
    });
  }
  $("realOddsMore").addEventListener("click",()=>{state.realOddsLimit+=24;renderRealOdds();});
  $("refreshButton").addEventListener("click",refreshData);
  $("dialogClose").addEventListener("click",closeDialog);
  $("dialogBackdrop").addEventListener("click",e=>{if(e.target===$("dialogBackdrop"))closeDialog()});
  document.addEventListener("keydown",e=>{
    if(e.key==="Escape" && !$("dialogBackdrop").hidden)closeDialog();
  });
  for (const id of ["matchSearch","leagueFilter","statusFilter","periodFilter","sortFilter"]) {
    $(id).addEventListener(id==="matchSearch"?"input":"change",()=>{state.matchLimit=24;renderMatches()});
  }
  for (const id of ["historyLeagueFilter","historyMarketFilter","historyStatusFilter","historySearch"]) {
    $(id).addEventListener(id==="historySearch"?"input":"change",()=>{state.historyLimit=40;renderHistory()});
  }
  $("loadMore").addEventListener("click",()=>{state.matchLimit+=24;renderMatches()});
  $("historyMore").addEventListener("click",()=>{state.historyLimit+=40;renderHistory()});
  window.addEventListener("hashchange",()=>{
    const view=location.hash.replace("#","");
    if(["overview","matches","radar","markets","history","odds","realodds","model"].includes(view))changeView(view);
  });
  const initial=location.hash.replace("#","");
  if(["overview","matches","radar","markets","history","odds","realodds","model"].includes(initial))changeView(initial);
}
wire();
refreshData();
