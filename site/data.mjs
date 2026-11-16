/**
 * Football AI Lab · modelo de datos (sin dependencias).
 * El histórico congelado es la fuente de verdad para las selecciones originales.
 */
export const LEAGUES = Object.freeze([
  "LaLiga", "Segunda División", "Premier League",
  "Bundesliga", "Serie A", "Ligue 1"
]);

export const FEEDS = Object.freeze({
  predicciones: "predicciones.csv",
  historico_predicciones: "historico_predicciones.csv",
  selecciones: "selecciones.csv",
  historico_selecciones: "historico_selecciones.csv",
  seguimiento_selecciones: "seguimiento_selecciones.csv",
  seguimiento: "seguimiento.csv",
  cuotas: "seguimiento_oportunidades_150.csv",
  evaluacion_selecciones: "evaluacion_selecciones.json",
  evaluacion_cuotas: "evaluacion_oportunidades_150.json",
  evaluacion_real: "evaluacion_real.json"
});

/** CSV RFC4180: comillas dobles, comas y saltos de línea dentro de celdas. */
export function parseCsv(text) {
  if (typeof text !== "string") throw new TypeError("CSV debe ser texto");
  const input = text.replace(/^\uFEFF/, "");
  const rows = [];
  let current = [], cell = "", quoted = false;
  for (let i = 0; i < input.length; i++) {
    const ch = input[i];
    if (quoted) {
      if (ch === '"') {
        if (input[i + 1] === '"') { cell += '"'; i++; }
        else quoted = false;
      } else cell += ch;
      continue;
    }
    if (ch === '"' && !cell) { quoted = true; continue; }
    if (ch === ",") { current.push(cell); cell = ""; continue; }
    if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && input[i + 1] === "\n") i++;
      current.push(cell);
      if (current.some(v => v !== "")) rows.push(current);
      current = []; cell = "";
      continue;
    }
    cell += ch;
  }
  if (quoted) throw new Error("CSV con comillas sin cerrar");
  current.push(cell);
  if (current.some(v => v !== "")) rows.push(current);
  const [headers = [], ...items] = rows;
  return items.map(values => Object.fromEntries(headers.map((key, index) => [key.trim(), values[index] ?? ""])));
}

export function numberOrNull(input) {
  if (input === null || input === undefined || String(input).trim() === "") return null;
  const value = Number(String(input).trim());
  return Number.isFinite(value) ? value : null;
}
export const settled = row =>
  Boolean(row && row.estado === "FINALIZADO" && (String(row.resultado) === "0" || String(row.resultado) === "1"));

export function calculateMetrics(rows) {
  const all = Array.isArray(rows) ? rows : [];
  const evaluated = all.filter(settled);
  const hits = evaluated.filter(row => String(row.resultado) === "1").length;
  return {
    registered: all.length,
    evaluated: evaluated.length,
    hits,
    losses: evaluated.length - hits,
    pending: all.filter(row => row.estado === "PENDIENTE").length,
    missing: all.filter(row => row.estado === "RESULTADO_NO_DISPONIBLE" || row.estado === "ESTADISTICA_NO_DISPONIBLE").length,
    accuracy: evaluated.length ? hits / evaluated.length : null
  };
}

export function calculateOdds(rows) {
  const basic = calculateMetrics(rows);
  const completed = (rows || []).filter(settled);
  const valid = completed.filter(row => numberOrNull(row.retorno_simulado_unidad) !== null);
  const profit = valid.length
    ? valid.reduce((sum, row) => sum + numberOrNull(row.retorno_simulado_unidad), 0)
    : null;
  return { ...basic, priced: valid.length, profit, roi: valid.length ? profit / valid.length : null };
}

function groupBy(rows, key) {
  const groups = new Map();
  for (const row of rows) {
    const id = row[key];
    if (!id) continue;
    if (!groups.has(id)) groups.set(id, []);
    groups.get(id).push(row);
  }
  return groups;
}

export function matchStatus(match) {
  const picks = match.picks || [];
  const done = picks.filter(settled).length;
  const missing = picks.some(x => x.estado === "RESULTADO_NO_DISPONIBLE" || x.estado === "ESTADISTICA_NO_DISPONIBLE");
  if (picks.length && done === picks.length) return "FINALIZADO";
  if (done > 0) return "PARCIAL";
  if (missing) return "SIN_DATOS";
  if (match.followup?.estado === "FINALIZADO") return "PARCIAL";
  return "PENDIENTE";
}

function pickSorted(rows) {
  return [...rows].sort((a, b) => (numberOrNull(a.posicion) ?? 100) - (numberOrNull(b.posicion) ?? 100));
}

/** Une fuentes sin duplicar las cuotas del Top 3, ni reemplazar picks archivados. */
export function buildModel(feeds, now = new Date()) {
  const source = name => Array.isArray(feeds[name]) ? feeds[name] : [];
  const current = source("predicciones");
  const historical = source("historico_predicciones");
  const liveSelections = groupBy(source("selecciones"), "id");
  const archived = groupBy(source("historico_selecciones"), "id");
  const evaluated = groupBy(source("seguimiento_selecciones"), "id");
  const odds = groupBy(source("cuotas"), "id");
  const followups = new Map(source("seguimiento").map(x => [x.id, x]));
  const map = new Map();

  function add(row, kind) {
    if (!row?.id) return;
    if (!map.has(row.id)) map.set(row.id, {
      id: row.id, liga: row.liga, local: row.local, visitante: row.visitante,
      fecha_utc: row.fecha_utc, historicalForecast: null, forecast: null,
      picks: [], odds: [], followup: null
    });
    const m = map.get(row.id);
    for (const field of ["liga", "local", "visitante", "fecha_utc"]) {
      if (!m[field] && row[field]) m[field] = row[field];
    }
    if (kind === "historicalForecast") m.historicalForecast = row;
    if (kind === "forecast") m.forecast = row;
  }
  historical.forEach(x => add(x, "historicalForecast"));
  current.forEach(x => add(x, "forecast"));
  for (const row of source("seguimiento_selecciones")) add(row, "pick");
  for (const row of source("historico_selecciones")) add(row, "pick");
  for (const row of source("seguimiento")) add(row, "followup");
  for (const row of source("cuotas")) add(row, "odds");
  for (const row of source("selecciones")) add(row, "pick");

  const matches = [...map.values()].map(m => {
    // Registrado primero antes del partido: nunca sustituir por recálculos.
    m.picks = pickSorted(evaluated.get(m.id) || archived.get(m.id) || liveSelections.get(m.id) || []);
    m.odds = odds.get(m.id) || [];
    m.followup = followups.get(m.id) || null;
    m.status = matchStatus(m);
    m.finishedPicks = m.picks.filter(settled).length;
    m.hitPicks = m.picks.filter(x => settled(x) && String(x.resultado) === "1").length;
    m.score = m.followup?.estado === "FINALIZADO"
      ? [m.followup.resultado_local, m.followup.resultado_visitante].join(" – ")
      : (m.picks.find(x => x.partidos_fuente)?.partidos_fuente ||
         m.odds.find(x => x.partidos_fuente)?.partidos_fuente || "");
    m.kickoff = Date.parse(m.fecha_utc) || 0;
    return m;
  }).sort((a, b) => a.kickoff - b.kickoff);

  const currentIds = new Set(current.map(row => row.id));
  const archivedPicks = source("seguimiento_selecciones").length
    ? source("seguimiento_selecciones")
    : source("historico_selecciones");
  const allOdds = source("cuotas");
  const top = calculateMetrics(archivedPicks);
  const simulation = calculateOdds(allOdds);
  const settledMatches = matches.filter(x => x.status === "FINALIZADO" || x.status === "PARCIAL");
  const futureMatches = matches.filter(x => currentIds.has(x.id) && x.kickoff > now.getTime());

  return {
    matches, futureMatches, settledMatches, currentIds, archivedPicks, allOdds,
    top, simulation, countForecasts: currentIds.size,
    updatedAt: feeds.evaluacion_selecciones?.calculado_utc ||
      feeds.evaluacion_cuotas?.generado_utc ||
      current[0]?.fecha_analisis_utc || null,
    evaluations: {
      top: feeds.evaluacion_selecciones || null,
      odds: feeds.evaluacion_cuotas || null,
      oneXtwo: feeds.evaluacion_real || null
    },
    leagues: LEAGUES.map(name => {
      const all = archivedPicks.filter(row => row.liga === name);
      const s = calculateMetrics(all);
      return { name, ...s, currentMatches: futureMatches.filter(x => x.liga === name).length };
    })
  };
}
