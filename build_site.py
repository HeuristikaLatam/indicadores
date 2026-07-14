"""
build_site.py
Lee datos.json (generado por indices.py) y escribe index.html:
un sitio estático, autocontenido, con la marca de Heurística,
tarjetas de valores actuales y gráficos históricos (Chart.js vía CDN).

Uso local:
    python3 indices.py
    python3 build_site.py
    open index.html
"""

import json
from datetime import datetime

with open("datos.json", "r", encoding="utf-8") as f:
    DATA = json.load(f)


def fmt(valor, unidad, key=None):
    if unidad == "Porcentaje":
        return f"{valor:.2f}%"
    if unidad == "Dólar":
        return f"US$ {valor:,.2f}".replace(",", ".")
    if key == "uf":
        # La UF cambia a diario en centavos — con 0 decimales se ve "congelada".
        return f"${valor:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"${valor:,.0f}".replace(",", ".")


def fecha_legible(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d-%m-%Y")
    except Exception:
        return iso


def fecha_hora_legible(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d-%m-%Y a las %H:%M")
    except Exception:
        return iso


def etiqueta_dia(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d-%m")
    except Exception:
        return iso


MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def etiqueta_mes(periodo):
    try:
        anio, mes = periodo.split("-")
        return f"{MESES_CORTOS[int(mes) - 1]} {anio[2:]}"
    except Exception:
        return periodo


MACRO_ORDEN = [
    ("dolar", "Dólar obs."),
    ("euro", "Euro"),
    ("uf", "UF"),
    ("utm", "UTM"),
    ("ipc", "IPC"),
    ("tpm", "TPM"),
    ("imacec", "Imacec"),
    ("tasa_desempleo", "Desempleo"),
    ("libra_cobre", "Cobre (lb)"),
    ("bitcoin", "Bitcoin"),
]

MACRO_DESCRIPCIONES = {
    "dolar": "Valor del dólar observado, publicado por el Banco Central.",
    "euro": "Valor del euro respecto al peso chileno.",
    "uf": "Unidad de Fomento, reajustada a diario según la inflación.",
    "utm": "Unidad Tributaria Mensual, usada para impuestos y multas.",
    "ipc": "Variación mensual del Índice de Precios al Consumidor (inflación).",
    "tpm": "Tasa de política monetaria fijada por el Banco Central.",
    "imacec": "Índice mensual de actividad económica del país.",
    "tasa_desempleo": "Tasa de desocupación nacional, medida por el INE.",
    "libra_cobre": "Precio de la libra de cobre en el mercado internacional.",
    "bitcoin": "Precio de bitcoin, convertido a pesos chilenos.",
}

# Descripciones para los gráficos históricos — un poco más largas que las
# de las tarjetas de arriba, porque acá hay más espacio y vale la pena dar
# contexto de qué está mostrando la tendencia.
CHART_DESCRIPCIONES = {
    "dolar": "Promedio mensual del dólar observado a lo largo del tiempo, para ver la tendencia más allá del vaivén diario.",
    "euro": "Promedio mensual del valor del euro en pesos chilenos.",
    "uf": "Evolución mensual de la Unidad de Fomento, que sigue de cerca la inflación acumulada.",
    "utm": "Evolución de la Unidad Tributaria Mensual, usada para calcular impuestos, multas y otros trámites legales.",
    "ipc": "Variación mensual de precios (inflación), mes a mes.",
    "tpm": "Historial de la tasa de política monetaria, fijada por el Banco Central en cada reunión.",
    "imacec": "Evolución mensual del índice de actividad económica, un adelanto del crecimiento del PIB.",
    "tasa_desempleo": "Evolución de la tasa de desocupación nacional, medida por el INE.",
    "libra_cobre": "Promedio mensual del precio del cobre en el mercado internacional.",
    "bitcoin": "Promedio mensual del precio de bitcoin, convertido a pesos chilenos.",
}

TASAS_DESCRIPCIONES = {
    "tip": "Historial de la tasa de interés promedio cobrada por la banca, por tipo de crédito.",
    "tmc": "Historial de la tasa máxima que la banca puede cobrar por ley, por tipo de crédito.",
}

macro = DATA.get("macro", {})
historico_macro = DATA.get("historico_macro", {})
recientes = DATA.get("recientes", {})
tasas = DATA.get("tasas", {"tip": {}, "tmc": {}})

# ---------------------------------------------------------------------------
# Resumen: KPIs destacados arriba de todo, con flecha de variación vs. el
# período anterior. Se arma solo con lo que ya tenemos en "macro"/"recientes",
# así que cuando sumemos combustibles/alimentos basta con agregar sus keys acá.
# ---------------------------------------------------------------------------

RESUMEN_ORDEN = [
    ("dolar", "Dólar obs."),
    ("uf", "UF"),
    ("tpm", "TPM"),
    ("ipc", "IPC (mensual)"),
    ("imacec", "Imacec"),
]


def variacion(key):
    puntos = recientes.get(key, {}).get("puntos", [])
    if len(puntos) < 2:
        return None
    return puntos[-1]["valor"] - puntos[-2]["valor"]


resumen_cards = ""
for key, label in RESUMEN_ORDEN:
    d = macro.get(key)
    if not d:
        continue
    delta = variacion(key)
    if delta is None or abs(delta) < 1e-9:
        flecha, clase_flecha = "＝", "kpi-flat"
    elif delta > 0:
        flecha, clase_flecha = "▲", "kpi-up"
    else:
        flecha, clase_flecha = "▼", "kpi-down"
    resumen_cards += f"""
    <div class="kpi">
      <div class="kpi-main">
        <div class="kpi-label">{label}</div>
        <div class="kpi-val">{fmt(d['valor'], d['unidad'], key)}</div>
      </div>
      <div class="kpi-delta {clase_flecha}">{flecha}</div>
    </div>"""

# ---------------------------------------------------------------------------
# Tarjetas de valor actual: destacado + últimos N períodos al costado
# ---------------------------------------------------------------------------

macro_cards = ""
for key, label in MACRO_ORDEN:
    d = macro.get(key)
    if not d:
        continue

    rec = recientes.get(key, {"tipo": "diario", "puntos": []})
    es_diario = rec.get("tipo") != "mensual"
    puntos = rec.get("puntos", [])

    # Fila cronológica: el más antiguo a la izquierda, el más reciente
    # (destacado, en naranjo) a la derecha. Si no hay histórico "reciente"
    # cargado (ej. la corrida de hoy no logró traer datos de este
    # indicador), al menos mostramos el valor actual como único punto,
    # con el formato de fecha que corresponda (día completo vs. período).
    if not puntos:
        etiqueta_respaldo = d["fecha"][:10] if es_diario else d["fecha"][:7]
        puntos = [{"etiqueta": etiqueta_respaldo, "valor": d["valor"]}]

    puntos_html = ""
    total = len(puntos)
    for i, p in enumerate(puntos):
        etiqueta = etiqueta_dia(p["etiqueta"]) if es_diario else etiqueta_mes(p["etiqueta"])
        es_destacado = (i == total - 1)
        clase = "pt pt-destacado" if es_destacado else "pt"
        puntos_html += f"""
        <div class="{clase}">
          <div class="pt-label">{etiqueta}</div>
          <div class="pt-val">{fmt(p['valor'], d['unidad'], key)}</div>
        </div>"""

    descripcion = MACRO_DESCRIPCIONES.get(key, "")
    macro_cards += f"""
    <div class="card-wide">
      <div class="card-head">
        <span class="card-name">{label}</span>
        <span class="card-desc">{descripcion}</span>
      </div>
      <div class="card-timeline">{puntos_html}</div>
    </div>"""

# ---------------------------------------------------------------------------
# Tabla de tasas (valor más reciente de cada tipo)
# ---------------------------------------------------------------------------

def ultimo_valor(serie):
    return serie[-1] if serie else None


def tabla_tasas(bloque):
    filas = ""
    for tipo, info in sorted(bloque.items(), key=lambda kv: kv[0]):
        ultimo = ultimo_valor(info["serie"])
        if not ultimo:
            continue
        filas += f"""
        <tr>
          <td>{info['etiqueta']}</td>
          <td class="num">{ultimo['valor']:.2f}%</td>
          <td class="date-cell">{fecha_legible(ultimo['fecha'])}</td>
        </tr>"""
    return filas or '<tr><td colspan="3" class="empty">Sin datos — revisa CMF_API_KEY</td></tr>'


tip_rows = tabla_tasas(tasas.get("tip", {}))
tmc_rows = tabla_tasas(tasas.get("tmc", {}))

tasas_seccion = ""
if tasas.get("tip") or tasas.get("tmc"):
    tasas_seccion = f"""
    <section id="credito" class="section">
    <h1>Costo del crédito</h1>
    <div class="section-sub">Tasas bancarias vigentes, según la CMF.</div>
    <div class="tables">
      <div class="tbox">
        <div class="tbox-head">
          <span class="card-name">Tasa de interés promedio (TIP)</span>
          <span class="card-desc">Tasa de interés promedio cobrada por la banca en créditos vigentes.</span>
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Tipo de operación</th><th>Tasa</th><th>Vigencia desde</th></tr></thead>
            <tbody>{tip_rows}</tbody>
          </table>
        </div>
      </div>
      <div class="tbox">
        <div class="tbox-head">
          <span class="card-name">Tasa máxima convencional (TMC)</span>
          <span class="card-desc">Tasa máxima que la banca puede cobrar por ley en cada tipo de crédito.</span>
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Tipo de operación</th><th>Tasa</th><th>Vigencia desde</th></tr></thead>
            <tbody>{tmc_rows}</tbody>
          </table>
        </div>
      </div>
    </div>
    </section>
    """

# ---------------------------------------------------------------------------
# Gráficos históricos — macro (Chart.js)
# ---------------------------------------------------------------------------

CHART_COLOR = "#e2792f"
CHART_GRID = "#242830"
CHART_TEXT = "#8a8f98"
CHART_BG = "#1a1d22"

ANIO_ACTUAL_CHART = datetime.now().year
RANGOS_DISPONIBLES = (20, 10, 5)
RANGO_INICIAL = 5  # con cuántos años parte cada gráfico al cargar la página


def corte_anio(anios):
    return f"{ANIO_ACTUAL_CHART - anios + 1}-01"


def slice_por_anios(labels, valores, anios):
    corte = corte_anio(anios)
    idx = next((i for i, l in enumerate(labels) if l >= corte), len(labels))
    return labels[idx:], valores[idx:]


def botones_rango(canvas_id):
    btns = ""
    for anios in RANGOS_DISPONIBLES:
        clase = "range-btn active" if anios == RANGO_INICIAL else "range-btn"
        btns += f'<button class="{clase}" data-canvas="{canvas_id}" data-years="{anios}">{anios} años</button>'
    return f'<div class="range-btns">{btns}</div>'


charts_js = []
macro_chart_cards = ""

for key, label in MACRO_ORDEN:
    serie = historico_macro.get(key, [])
    if not serie:
        continue
    canvas_id = f"chart_{key}"
    labels_full = [p["periodo"] for p in serie]
    valores_full = [p["valor"] for p in serie]
    labels_ini, valores_ini = slice_por_anios(labels_full, valores_full, RANGO_INICIAL)
    minimo = min(valores_full)
    maximo = max(valores_full)

    macro_chart_cards += f"""
    <div class="chart-card">
      <div class="chart-head">
        <span class="chart-title">{label}</span>
        <span class="chart-desc">{CHART_DESCRIPCIONES.get(key, '')}</span>
      </div>
      {botones_rango(canvas_id)}
      <div class="chart-canvas-wrap"><canvas id="{canvas_id}"></canvas></div>
      <div class="chart-range">mín {minimo:,.2f} · máx {maximo:,.2f} (todo el histórico disponible)</div>
    </div>"""

    charts_js.append(f"""
    (function() {{
      const chart = new Chart(document.getElementById('{canvas_id}'), {{
        type: 'line',
        data: {{
          labels: {json.dumps(labels_ini)},
          datasets: [{{
            data: {json.dumps(valores_ini)},
            borderColor: '{CHART_COLOR}',
            backgroundColor: '{CHART_COLOR}22',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 5,
            pointHoverBackgroundColor: '{CHART_COLOR}',
            pointHitRadius: 12,
            tension: 0.25,
            fill: true,
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          interaction: {{ mode: 'index', intersect: false }},
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              backgroundColor: '{CHART_BG}',
              borderColor: '{CHART_GRID}',
              borderWidth: 1,
              titleColor: '{CHART_COLOR}',
              bodyColor: '#eef0f2',
              padding: 10,
              displayColors: false,
            }},
          }},
          scales: {{
            x: {{
              ticks: {{ color: '{CHART_TEXT}', font: {{ size: CHART_FONT_SIZE }}, maxTicksLimit: CHART_MAX_TICKS, maxRotation: 0 }},
              grid: {{ display: false }},
            }},
            y: {{
              ticks: {{ color: '{CHART_TEXT}', font: {{ size: CHART_FONT_SIZE }} }},
              grid: {{ color: '{CHART_GRID}' }},
            }}
          }}
        }}
      }});
      CHARTS_REGISTRY['{canvas_id}'] = {{ chart: chart, labels: {json.dumps(labels_full)}, valores: {json.dumps(valores_full)} }};
    }})();""")

# ---------------------------------------------------------------------------
# Gráficos históricos — tasas de crédito
# ---------------------------------------------------------------------------

tasas_chart_cards = ""
for recurso, titulo in (("tip", "TIP"), ("tmc", "TMC")):
    bloque = tasas.get(recurso, {})
    for tipo, info in sorted(bloque.items(), key=lambda kv: kv[0]):
        serie = info["serie"]
        if not serie:
            continue
        canvas_id = f"chart_{recurso}_{tipo}"
        labels_full = [p["fecha"] for p in serie]
        valores_full = [p["valor"] for p in serie]
        # Las tasas bancarias solo llegan a CMF_ANIOS_HISTORICO años (ver
        # nota en indices.py), así que acá el rango inicial puede coincidir
        # con "todo lo disponible" — los botones igual quedan, por si más
        # adelante estiramos también esta fuente.
        labels_ini, valores_ini = slice_por_anios(labels_full, valores_full, RANGO_INICIAL)

        tasas_chart_cards += f"""
        <div class="chart-card">
          <div class="chart-head">
            <span class="chart-title">{info['etiqueta']} · {titulo}</span>
            <span class="chart-desc">{TASAS_DESCRIPCIONES.get(recurso, '')}</span>
          </div>
          {botones_rango(canvas_id)}
          <div class="chart-canvas-wrap"><canvas id="{canvas_id}"></canvas></div>
        </div>"""

        charts_js.append(f"""
        (function() {{
          const chart = new Chart(document.getElementById('{canvas_id}'), {{
            type: 'line',
            data: {{
              labels: {json.dumps(labels_ini)},
              datasets: [{{
                data: {json.dumps(valores_ini)},
                borderColor: '{CHART_COLOR}',
                backgroundColor: '{CHART_COLOR}22',
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 5,
                pointHoverBackgroundColor: '{CHART_COLOR}',
                pointHitRadius: 12,
                tension: 0.1,
                stepped: true,
                fill: true,
              }}]
            }},
            options: {{
              responsive: true,
              maintainAspectRatio: false,
              interaction: {{ mode: 'index', intersect: false }},
              plugins: {{
                legend: {{ display: false }},
                tooltip: {{
                  backgroundColor: '{CHART_BG}',
                  borderColor: '{CHART_GRID}',
                  borderWidth: 1,
                  titleColor: '{CHART_COLOR}',
                  bodyColor: '#eef0f2',
                  padding: 10,
                  displayColors: false,
                  callbacks: {{
                    label: function(ctx) {{ return ctx.parsed.y.toFixed(2) + '%'; }}
                  }}
                }},
              }},
              scales: {{
                x: {{
                  ticks: {{ color: '{CHART_TEXT}', font: {{ size: CHART_FONT_SIZE }}, maxTicksLimit: CHART_MAX_TICKS, maxRotation: 0 }},
                  grid: {{ display: false }},
                }},
                y: {{
                  ticks: {{ color: '{CHART_TEXT}', font: {{ size: CHART_FONT_SIZE }} }},
                  grid: {{ color: '{CHART_GRID}' }},
                }}
              }}
            }}
          }});
          CHARTS_REGISTRY['{canvas_id}'] = {{ chart: chart, labels: {json.dumps(labels_full)}, valores: {json.dumps(valores_full)} }};
        }})();""")

# ---------------------------------------------------------------------------
# Secciones "próximamente" — combustibles (CNE) y alimentos (ODEPA), listas
# para reemplazar por datos reales apenas conectemos esas fuentes.
# ---------------------------------------------------------------------------

def placeholder_seccion(titulo, descripcion):
    return f"""
    <div class="card-wide placeholder">
      <div class="card-head">
        <span class="card-name">{titulo}</span>
        <span class="card-desc">{descripcion}</span>
      </div>
      <div class="placeholder-text">Próximamente.</div>
    </div>"""


historicos_seccion = ""
if macro_chart_cards or tasas_chart_cards:
    historicos_seccion = (
        '<section id="historicos" class="section"><h1>Históricos</h1>'
        '<div class="section-sub">Hasta 20 años atrás — usa los botones de cada gráfico para cambiar el rango.</div>'
    )
    if macro_chart_cards:
        historicos_seccion += f"""
        <div class="subhead">Macro</div>
        <div class="chart-grid">{macro_chart_cards}
        </div>
        """
    if tasas_chart_cards:
        historicos_seccion += f"""
        <div class="subhead">Costo del crédito</div>
        <div class="chart-grid">{tasas_chart_cards}
        </div>
        """
    historicos_seccion += "</section>"

CHARTS_JS = "\n".join(charts_js)

cargado_en = fecha_hora_legible(DATA.get("generado", ""))

HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Indicadores Económicos · Heurística</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.0/chart.umd.min.js"></script>
<style>
  :root{{
    --bg:#0b0d10; --card:#14171b; --line:#242830; --text:#eef0f2;
    --muted:#8a8f98; --orange:#e2792f; --navy:#1a2b42;
  }}
  *{{box-sizing:border-box;}}
  body{{
    margin:0; background:var(--bg); color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    padding:32px 24px 60px;
  }}
  .wrap{{max-width:1100px; margin:0 auto;}}

  .brand{{display:flex; align-items:center; gap:16px; margin-bottom:2px;}}
  .brand-mark{{flex-shrink:0;}}
  .brand-titles{{display:flex; flex-direction:column; gap:4px;}}
  .page-title{{font-size:26px; font-weight:700; letter-spacing:.01em;}}
  .page-title .flag{{font-size:22px;}}
  .brand-name{{font-size:13px; font-weight:600; letter-spacing:.08em; color:var(--muted);}}
  .brand-name .k{{color:var(--orange);}}
  .brand-tagline{{
    font-size:11px; color:var(--muted); letter-spacing:.12em; text-transform:uppercase;
    display:flex; align-items:center; gap:10px; margin:14px 0 18px 0;
  }}
  .brand-tagline .dash{{display:inline-block; width:22px; height:1px; background:var(--orange);}}
  .update-note{{font-size:11px; color:var(--muted); line-height:1.6; margin-bottom:28px;}}

  h1{{font-size:14px; font-weight:600; color:var(--muted); text-transform:uppercase;
     letter-spacing:.08em; margin:0 0 4px;}}
  .section-sub{{font-size:12px; color:var(--muted); margin:0 0 18px;}}

  .section{{padding:34px 0; border-top:1px solid var(--line); scroll-margin-top:64px;}}
  .section:first-of-type{{border-top:none; padding-top:0;}}

  .nav{{
    position:sticky; top:0; z-index:10; display:flex; gap:4px; overflow-x:auto;
    background:rgba(11,13,16,.92); backdrop-filter:blur(6px);
    margin:0 -24px 28px; padding:12px 24px; border-bottom:1px solid var(--line);
    scrollbar-width:none;
  }}
  .nav::-webkit-scrollbar{{display:none;}}
  .nav a{{
    flex:0 0 auto; font-size:12px; color:var(--muted); text-decoration:none;
    padding:6px 12px; border-radius:20px; white-space:nowrap;
  }}
  .nav a:hover{{color:var(--text); background:var(--card);}}

  .kpis{{
    display:flex; gap:12px; overflow-x:auto; scrollbar-width:none; margin-bottom:6px;
  }}
  .kpis::-webkit-scrollbar{{display:none;}}
  .kpi{{
    flex:0 0 auto; min-width:130px; background:var(--card); border:1px solid var(--line);
    border-radius:10px; padding:14px 16px; display:flex; align-items:center; justify-content:space-between; gap:10px;
  }}
  .kpi-label{{font-size:11px; color:var(--muted); margin-bottom:6px;}}
  .kpi-val{{font-size:17px; font-weight:700; font-variant-numeric:tabular-nums;}}
  .kpi-delta{{font-size:13px; font-weight:700;}}
  .kpi-up{{color:#3ecf6e;}}
  .kpi-down{{color:#ef5350;}}
  .kpi-flat{{color:var(--muted);}}

  .placeholder{{opacity:.55;}}
  .placeholder-text{{font-size:12px; color:var(--muted); font-style:italic;}}

  .grid{{
    display:grid; grid-template-columns:repeat(2, 1fr);
    gap:14px;
  }}
  @media (max-width: 720px){{
    .grid{{grid-template-columns:1fr;}}
  }}
  .card-wide{{
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:16px 20px 18px;
  }}
  .card-head{{display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:12px;}}
  .card-name{{font-size:13px; font-weight:700; color:var(--orange);}}
  .card-desc{{font-size:11px; color:var(--muted);}}
  .card-timeline{{
    display:flex; align-items:flex-end; justify-content:space-between; gap:10px;
    max-width:440px;
    overflow-x:auto; scrollbar-width:none; -webkit-overflow-scrolling:touch;
  }}
  .card-timeline::-webkit-scrollbar{{display:none;}}
  .pt{{text-align:center; flex:0 0 auto; min-width:44px;}}
  .pt-label{{font-size:10px; color:var(--muted); margin-bottom:4px; white-space:nowrap;}}
  .pt-val{{font-size:12px; font-weight:600; color:var(--text); font-variant-numeric:tabular-nums; white-space:nowrap;}}
  .pt-destacado .pt-label{{color:var(--orange); font-weight:600;}}
  .pt-destacado .pt-val{{font-size:20px; font-weight:700; color:var(--orange);}}

  .tables{{display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px;}}
  .tbox{{background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px;}}
  .tbox-head{{display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:10px;}}
  .table-scroll{{overflow-x:auto; -webkit-overflow-scrolling:touch;}}
  table{{width:100%; min-width:280px; border-collapse:collapse; font-size:13px;}}
  th{{text-align:left; color:var(--muted); font-weight:500; font-size:11px;
     text-transform:uppercase; letter-spacing:.04em; padding-bottom:8px; border-bottom:1px solid var(--line); white-space:nowrap;}}
  td{{padding:8px 0; border-bottom:1px solid var(--line); white-space:nowrap;}}
  td.num{{font-variant-numeric:tabular-nums; font-weight:600; color:var(--orange);}}
  td.date-cell{{color:var(--muted); font-size:12px;}}
  td.empty{{color:var(--muted); font-style:italic; text-align:center; white-space:normal;}}

  .chart-grid{{
    display:flex; flex-direction:column; gap:16px;
  }}
  .chart-card{{
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:20px 24px;
  }}
  .subhead{{font-size:12px; color:var(--orange); text-transform:uppercase; letter-spacing:.08em; margin:24px 0 12px;}}
  .subhead:first-of-type{{margin-top:0;}}
  .chart-head{{display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:12px;}}
  .chart-title{{font-size:14px; color:var(--text); font-weight:600;}}
  .chart-desc{{font-size:12px; color:var(--muted);}}
  .chart-canvas-wrap{{position:relative; width:100%; height:280px;}}
  .chart-range{{font-size:11px; color:var(--muted); margin-top:10px;}}
  .range-btns{{display:flex; gap:6px; margin-bottom:12px;}}
  .range-btn{{
    font:inherit; font-size:11px; color:var(--muted); background:var(--bg);
    border:1px solid var(--line); border-radius:20px; padding:4px 12px; cursor:pointer;
  }}
  .range-btn:hover{{color:var(--text);}}
  .range-btn.active{{color:var(--orange); border-color:var(--orange); font-weight:600;}}

  .footer{{margin-top:36px; font-size:11px; color:var(--muted); line-height:1.6;}}
  .footer a{{color:var(--orange); text-decoration:none;}}

  @media (max-width: 480px){{
    body{{padding:20px 14px 44px;}}
    .brand-mark{{width:32px; height:32px;}}
    .page-title{{font-size:19px;}}
    .page-title .flag{{font-size:16px;}}
    .brand-name{{font-size:11px;}}
    .nav{{margin:0 -14px 22px; padding:10px 14px;}}
    .kpi{{min-width:112px; padding:12px 12px;}}
    .card-wide{{padding:14px 14px 16px;}}
    .card-timeline{{max-width:none;}}
    /* En pantalla angosta mostramos solo los últimos 3 puntos (2 anteriores
       + el destacado de hoy) para que quepan sin necesitar swipe. */
    .pt:nth-last-child(n+4){{display:none;}}
    .chart-card{{padding:16px 12px;}}
    .chart-canvas-wrap{{height:260px;}}
  }}
</style>
</head>
<body>
<div class="wrap">

  <div class="brand">
    <svg class="brand-mark" width="48" height="48" viewBox="0 0 112 120" xmlns="http://www.w3.org/2000/svg">
      <rect x="20" y="8"  width="22" height="40" rx="3" fill="#eef0f2"/>
      <rect x="20" y="72" width="22" height="40" rx="3" fill="#eef0f2"/>
      <rect x="68" y="8"  width="22" height="40" rx="3" fill="#eef0f2"/>
      <path d="M68,72 H90 V112 Q68,112 68,90 Z" fill="#eef0f2"/>
      <rect x="2"  y="48" width="16" height="16" rx="2" fill="#8a8f98"/>
      <rect x="48" y="48" width="16" height="16" rx="2" fill="#e2792f"/>
      <rect x="94" y="48" width="16" height="16" rx="2" fill="#8a8f98"/>
    </svg>
    <div class="brand-titles">
      <div class="page-title">Indicadores Económicos Chile <span class="flag">🇨🇱</span></div>
      <div class="brand-name">HEURISTI<span class="k">K</span>A</div>
    </div>
  </div>
  <div class="brand-tagline"><span class="dash"></span>Capacidad Humana Amplificada<span class="dash"></span></div>
  <div class="update-note">La información que estás viendo fue cargada el {cargado_en}.</div>

  <nav class="nav">
    <a href="#resumen">Resumen</a>
    <a href="#macro">Macro</a>
    <a href="#credito">Crédito</a>
    <a href="#combustibles">Combustibles</a>
    <a href="#alimentos">Alimentos</a>
    <a href="#historicos">Históricos</a>
  </nav>

  <section id="resumen" class="section">
    <h1>Resumen</h1>
    <div class="section-sub">Lo más relevante, de un vistazo. La flecha compara con el período anterior.</div>
    <div class="kpis">{resumen_cards}</div>
  </section>

  <section id="macro" class="section">
    <h1>Macro</h1>
    <div class="section-sub">Todos los indicadores, con su historial reciente.</div>
    <div class="grid">{macro_cards}
    </div>
  </section>

  {tasas_seccion}

  <section id="combustibles" class="section">
    <h1>Combustibles</h1>
    <div class="section-sub">Precios de bencina y diésel (CNE) — en construcción.</div>
    {placeholder_seccion("Bencina y diésel", "Precios por región y tipo de combustible, según la CNE.")}
  </section>

  <section id="alimentos" class="section">
    <h1>Alimentos</h1>
    <div class="section-sub">Precios agrícolas (ODEPA) — en construcción.</div>
    {placeholder_seccion("Precios de alimentos", "Precios mayoristas y al consumidor de frutas y verduras, según ODEPA.")}
  </section>

  {historicos_seccion}

  <div class="footer">
    Fuentes: <a href="https://mindicador.cl" target="_blank">mindicador.cl</a> (Banco Central de Chile)
    y <a href="https://api.cmfchile.cl" target="_blank">CMF Bancos</a> (Comisión para el Mercado Financiero).
    Información con fines informativos. No constituye asesoría ni recomendación de inversión.
  </div>

</div>

<script>
// En pantallas angostas los gráficos usan letra más grande y menos marcas
// en el eje X para que no se amontonen (en mobile, con CSS ya mostramos
// solo los últimos 3 puntos por tarjeta, así que no dependemos de scroll).
const CHART_FONT_SIZE = window.innerWidth < 480 ? 11 : 10;
const CHART_MAX_TICKS = window.innerWidth < 480 ? 6 : 12;

// Cada gráfico se registra acá con su serie COMPLETA (hasta 20 años para
// macro), aunque al cargar la página solo se dibujan los últimos 5 — los
// botones de rango recortan/expanden sobre estos mismos datos, sin
// necesidad de volver a pedir nada al servidor.
const CHARTS_REGISTRY = {{}};

{CHARTS_JS}

function aplicarRango(canvasId, anios) {{
  const info = CHARTS_REGISTRY[canvasId];
  if (!info) return;
  const anioActual = new Date().getFullYear();
  const corte = String(anioActual - anios + 1) + '-01';
  let idx = info.labels.findIndex(function(l) {{ return l >= corte; }});
  if (idx === -1) idx = info.labels.length;
  info.chart.data.labels = info.labels.slice(idx);
  info.chart.data.datasets[0].data = info.valores.slice(idx);
  info.chart.update();
}}

document.querySelectorAll('.range-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    const canvasId = btn.dataset.canvas;
    const anios = parseInt(btn.dataset.years, 10);
    aplicarRango(canvasId, anios);
    document.querySelectorAll('.range-btn[data-canvas="' + canvasId + '"]').forEach(function(b) {{
      b.classList.toggle('active', b === btn);
    }});
  }});
}});

// Respaldo: si en algún navegador la fila de indicador no cupiera entera,
// la dejamos desplazada hasta el valor destacado (el de hoy, a la derecha).
document.querySelectorAll('.card-timeline').forEach(function(row) {{
  row.scrollLeft = row.scrollWidth;
}});
</script>

</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print("OK -> index.html")
