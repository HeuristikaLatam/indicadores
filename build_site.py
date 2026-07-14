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
 
macro = DATA.get("macro", {})
historico_macro = DATA.get("historico_macro", {})
recientes = DATA.get("recientes", {})
tasas = DATA.get("tasas", {"tip": {}, "tmc": {}})
 
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
    # cargado, al menos mostramos el valor actual como único punto.
    if not puntos:
        puntos = [{"etiqueta": d["fecha"][:10], "valor": d["valor"]}]
 
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
 
    macro_cards += f"""
    <div class="card-wide">
      <div class="card-name">{label}</div>
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
    <h1>Costo del crédito</h1>
    <div class="tables">
      <div class="tbox">
        <div class="tbox-title">Tasa de interés promedio (TIP)</div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Tipo de operación</th><th>Tasa</th><th>Vigencia desde</th></tr></thead>
            <tbody>{tip_rows}</tbody>
          </table>
        </div>
      </div>
      <div class="tbox">
        <div class="tbox-title">Tasa máxima convencional (TMC)</div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Tipo de operación</th><th>Tasa</th><th>Vigencia desde</th></tr></thead>
            <tbody>{tmc_rows}</tbody>
          </table>
        </div>
      </div>
    </div>
    """
 
# ---------------------------------------------------------------------------
# Gráficos históricos — macro (Chart.js)
# ---------------------------------------------------------------------------
 
CHART_COLOR = "#e2792f"
CHART_GRID = "#242830"
CHART_TEXT = "#8a8f98"
CHART_BG = "#1a1d22"
 
charts_js = []
macro_chart_cards = ""
 
for key, label in MACRO_ORDEN:
    serie = historico_macro.get(key, [])
    if not serie:
        continue
    canvas_id = f"chart_{key}"
    labels = [p["periodo"] for p in serie]
    valores = [p["valor"] for p in serie]
    minimo = min(valores)
    maximo = max(valores)
 
    macro_chart_cards += f"""
    <div class="chart-card">
      <div class="chart-title">{label}</div>
      <div class="chart-canvas-wrap"><canvas id="{canvas_id}"></canvas></div>
      <div class="chart-range">mín {minimo:,.2f} · máx {maximo:,.2f}</div>
    </div>"""
 
    charts_js.append(f"""
    new Chart(document.getElementById('{canvas_id}'), {{
      type: 'line',
      data: {{
        labels: {json.dumps(labels)},
        datasets: [{{
          data: {json.dumps(valores)},
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
    }});""")
 
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
        labels = [p["fecha"] for p in serie]
        valores = [p["valor"] for p in serie]
 
        tasas_chart_cards += f"""
        <div class="chart-card">
          <div class="chart-title">{info['etiqueta']} · {titulo}</div>
          <div class="chart-canvas-wrap"><canvas id="{canvas_id}"></canvas></div>
        </div>"""
 
        charts_js.append(f"""
        new Chart(document.getElementById('{canvas_id}'), {{
          type: 'line',
          data: {{
            labels: {json.dumps(labels)},
            datasets: [{{
              data: {json.dumps(valores)},
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
        }});""")
 
historicos_seccion = ""
if macro_chart_cards:
    historicos_seccion += f"""
    <h1>Históricos · Macro</h1>
    <div class="chart-grid">{macro_chart_cards}
    </div>
    """
if tasas_chart_cards:
    historicos_seccion += f"""
    <h1>Históricos · Costo del crédito</h1>
    <div class="chart-grid">{tasas_chart_cards}
    </div>
    """
 
CHARTS_JS = "\n".join(charts_js)
 
generado = fecha_legible(DATA.get("generado", ""))
 
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
 
  .brand{{display:flex; align-items:center; gap:14px; margin-bottom:2px;}}
  .brand-mark{{flex-shrink:0;}}
  .brand-name{{font-size:22px; font-weight:700; letter-spacing:.06em;}}
  .brand-name .k{{color:var(--orange);}}
  .brand-tagline{{
    font-size:11px; color:var(--muted); letter-spacing:.12em; text-transform:uppercase;
    display:flex; align-items:center; gap:10px; margin:10px 0 18px 0;
  }}
  .brand-tagline .dash{{display:inline-block; width:22px; height:1px; background:var(--orange);}}
  .brand-tag{{font-size:11px; color:var(--muted); letter-spacing:.08em; text-transform:uppercase; margin:0 0 8px 0;}}
  .update-note{{font-size:11px; color:var(--muted); line-height:1.6; margin-bottom:28px;}}
 
  h1{{font-size:14px; font-weight:600; color:var(--muted); text-transform:uppercase;
     letter-spacing:.08em; margin:32px 0 14px;}}
  h1:first-of-type{{margin-top:0;}}
 
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
  .card-name{{font-size:12px; color:var(--muted); margin-bottom:12px;}}
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
  .tbox-title{{font-size:13px; font-weight:600; margin-bottom:10px; color:var(--text);}}
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
  .chart-title{{font-size:14px; color:var(--text); font-weight:600; margin-bottom:12px;}}
  .chart-canvas-wrap{{position:relative; width:100%; height:280px;}}
  .chart-range{{font-size:11px; color:var(--muted); margin-top:10px;}}
 
  .footer{{margin-top:36px; font-size:11px; color:var(--muted); line-height:1.6;}}
  .footer a{{color:var(--orange); text-decoration:none;}}
 
  @media (max-width: 480px){{
    body{{padding:20px 14px 44px;}}
    .brand-mark{{width:32px; height:32px;}}
    .brand-name{{font-size:18px;}}
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
    <svg class="brand-mark" width="40" height="40" viewBox="0 0 112 120" xmlns="http://www.w3.org/2000/svg">
      <rect x="20" y="8"  width="22" height="40" rx="3" fill="#eef0f2"/>
      <rect x="20" y="72" width="22" height="40" rx="3" fill="#eef0f2"/>
      <rect x="68" y="8"  width="22" height="40" rx="3" fill="#eef0f2"/>
      <path d="M68,72 H90 V112 Q68,112 68,90 Z" fill="#eef0f2"/>
      <rect x="2"  y="48" width="16" height="16" rx="2" fill="#8a8f98"/>
      <rect x="48" y="48" width="16" height="16" rx="2" fill="#e2792f"/>
      <rect x="94" y="48" width="16" height="16" rx="2" fill="#8a8f98"/>
    </svg>
    <div class="brand-name">HEURISTI<span class="k">K</span>A</div>
  </div>
  <div class="brand-tagline"><span class="dash"></span>Capacidad Humana Amplificada<span class="dash"></span></div>
  <div class="brand-tag">Indicadores económicos · Chile</div>
  <div class="update-note">Esta data se actualiza de forma automática a las 5:00 AM y 5:00 PM hora de Chile, todos los días.<br>Generado automáticamente el {generado}.</div>
 
  <h1>Macro</h1>
  <div class="grid">{macro_cards}
  </div>
 
  {tasas_seccion}
 
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
 
{CHARTS_JS}
 
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
 
