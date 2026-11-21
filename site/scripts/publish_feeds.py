"""Build a same-origin public feed snapshot for the GitHub Pages PWA.

Only explicitly allowlisted, already-public output artifacts are shipped.
Do not publish Secrets, environmental values or whole output directory.
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = (
    "predicciones.csv",
    "calendario_partidos.csv",
    "historico_predicciones.csv",
    "selecciones.csv",
    "historico_selecciones.csv",
    "seguimiento_selecciones.csv",
    "seguimiento.csv",
    "seguimiento_oportunidades_150.csv",
    "seguimiento_adicionales_teoricas.csv",
    "evaluacion_selecciones.json",
    "evaluacion_oportunidades_150.json",
    "evaluacion_real.json",
    "desglose_postpartido.json",
    "mercados_historicos.json",
    "pronosticos_mercados_futuros.json",
    "fiabilidad_mercados_futuros.json",
    "radar_contexto_equipos.json",
    "cuotas_reales_verificadas.json",
    "comparacion_cuotas_reales.json",
    "seguimiento_cuotas_top3.csv",
    "evaluacion_cuotas_top3.json",
)


def publish(root: Path = ROOT) -> dict:
    source = root / "output"
    destination = root / "site" / "published"
    destination.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for name in FILES:
        path = source / name
        if not path.is_file():
            raise FileNotFoundError(f"Falta la fuente pública: {name}")
        if name.endswith(".json"):
            json.loads(path.read_text(encoding="utf-8-sig"))
        else:
            with path.open(encoding="utf-8-sig", newline="") as fp:
                if not next(csv.reader(fp), []):
                    raise ValueError(f"CSV sin cabecera: {name}")
        shutil.copyfile(path, destination / name)
        sizes[name] = (destination / name).stat().st_size
    # The deployment artifact contains ONLY known public feeds; the source
    # remains in output/ and secrets never enter site/published/.
    print(f"Publicados {len(sizes)} feeds en GitHub Pages ({sum(sizes.values())} bytes)")
    return sizes


if __name__ == "__main__":
    publish()
