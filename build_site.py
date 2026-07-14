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


def fmt_litro(valor):
    return f"${valor:,.0f}".replace(",", ".")


def fmt_alimento(valor, unidad="kg"):
    return f"${valor:,.0f}".replace(",", ".") + f" /{unidad}"


def anomalia_card_html(descripcion_html):
    """Tarjeta destacada para el dato más 'inusual' de una categoría (ver
    _anomalia_por_zscore en indices.py) — visualmente distinta de las
    tarjetas normales para que se note que es un hallazgo, no un dato más."""
    return f"""
    <div class="anomaly-card">
      <div class="anomaly-icon">⚡</div>
      <div class="anomaly-body">
        <div class="anomaly-title">Lo más inusual</div>
        <div class="anomaly-desc">{descripcion_html}</div>
      </div>
    </div>"""


def fecha_legible(iso):
    """Formato único para todas las fechas del sitio: dd/mm/aaaa."""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        return iso


def fecha_hora_legible(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y a las %H:%M")
    except Exception:
        return iso


def etiqueta_dia(iso):
    """Fecha completa dd/mm/aaaa para los puntos de las tarjetas — antes
    mostraba solo día-mes sin año; ahora siempre la fecha exacta que entrega
    la fuente (mindicador.cl da fecha completa incluso para indicadores
    mensuales, así que ya no hace falta truncarla a "mes año")."""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y")
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
combustibles = DATA.get("combustibles", {"nacional": {}, "regional": {}})
anomalias = DATA.get("anomalias", {})
_alimentos_resumen = DATA.get("alimentos", {})
_consumidor_nacional_resumen = _alimentos_resumen.get("consumidor", {}).get("nacional", {})

# ---------------------------------------------------------------------------
# Resumen: KPIs destacados arriba de todo, con flecha de variación vs. el
# período anterior. Se arma solo con lo que ya tenemos en "macro"/"recientes",
# así que cuando sumemos alimentos basta con agregar sus keys acá.
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

# Dos KPIs extra en el Resumen que no vienen de mindicador.cl (no tienen la
# misma serie "reciente" para la flecha, así que van sin comparación).
_gasolina_93 = combustibles.get("nacional", {}).get("93")
if _gasolina_93:
    resumen_cards += f"""
    <div class="kpi">
      <div class="kpi-main">
        <div class="kpi-label">Bencina 93</div>
        <div class="kpi-val">{fmt_litro(_gasolina_93['promedio'])}</div>
      </div>
    </div>"""

_pan = _consumidor_nacional_resumen.get("Marraqueta")
if _pan:
    resumen_cards += f"""
    <div class="kpi">
      <div class="kpi-main">
        <div class="kpi-label">Pan (marraqueta)</div>
        <div class="kpi-val">{fmt_alimento(_pan['promedio'], _pan.get('unidad', 'kg'))}</div>
      </div>
    </div>"""

# ---------------------------------------------------------------------------
# Tarjetas de valor actual: destacado + últimos N períodos al costado
# ---------------------------------------------------------------------------

macro_cards = ""
for key, label in MACRO_ORDEN:
    d = macro.get(key)
    if not d:
        continue

    rec = recientes.get(key, {"puntos": []})
    puntos = rec.get("puntos", [])

    # Fila cronológica: el más antiguo a la izquierda, el más reciente
    # (destacado, en naranjo) a la derecha. Si no hay histórico "reciente"
    # cargado (ej. la corrida de hoy no logró traer datos de este
    # indicador), al menos mostramos el valor actual como único punto.
    # La etiqueta siempre es la fecha completa (dd/mm/aaaa) — mindicador.cl
    # entrega fecha completa incluso para indicadores mensuales.
    if not puntos:
        puntos = [{"etiqueta": d["fecha"][:10], "valor": d["valor"]}]

    puntos_html = ""
    total = len(puntos)
    for i, p in enumerate(puntos):
        etiqueta = etiqueta_dia(p["etiqueta"])
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

# --- Anomalía destacada de Macro --------------------------------------------

anomalia_macro_html = ""
_am = anomalias.get("macro")
if _am:
    _am_label = dict(MACRO_ORDEN).get(_am["clave"], _am["clave"])
    _am_unidad = macro.get(_am["clave"], {}).get("unidad", "")
    _am_signo = "+" if _am["cambio_pct"] > 0 else ""
    anomalia_macro_html = anomalia_card_html(
        f"<strong>{_am_label}</strong> tuvo el movimiento más inusual de la categoría: "
        f"{_am_signo}{_am['cambio_pct']:.2f}% el {fecha_legible(_am['periodo'])} "
        f"(valor actual: {fmt(_am['valor_actual'], _am_unidad, _am['clave'])})."
    )

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

# --- Anomalía destacada de Crédito ------------------------------------------

anomalia_credito_html = ""
_ac = anomalias.get("credito")
if _ac:
    _ac_signo = "+" if _ac["cambio_pct"] > 0 else ""
    anomalia_credito_html = anomalia_card_html(
        f"<strong>{_ac['etiqueta']}</strong> ({_ac['recurso'].upper()}) tuvo el movimiento más inusual "
        f"de la categoría: {_ac_signo}{_ac['cambio_pct']:.2f}% al {fecha_legible(_ac['fecha'])} "
        f"(tasa actual: {_ac['valor_actual']:.2f}%)."
    )

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
    {anomalia_credito_html}
    </section>
    """

# ---------------------------------------------------------------------------
# Combustibles (CNE) — precio promedio de HOY, calculado sobre el precio
# vigente de cada estación de servicio (/api/v4/estaciones). Tres bloques:
#   1) 5 KPIs con el promedio nacional por tipo de combustible.
#   2) Tabla con el promedio por región (filas) y tipo (columnas).
#   3) 5 tarjetas de zonas destacadas, con los 5 tipos cada una.
# ---------------------------------------------------------------------------

COMBUSTIBLE_ETIQUETAS = {
    "93": "Gasolina 93",
    "95": "Gasolina 95",
    "97": "Gasolina 97",
    "KE": "Kerosene",
    "DI": "Diésel",
}
COMBUSTIBLE_ORDEN = ["93", "95", "97", "KE", "DI"]

combustibles_nacional = combustibles.get("nacional", {})
combustibles_regional = combustibles.get("regional", {})

# --- 1) KPIs nacionales -----------------------------------------------------

combustibles_kpis = ""
fechas_combustibles = []
for tipo in COMBUSTIBLE_ORDEN:
    info = combustibles_nacional.get(tipo)
    if not info:
        continue
    fechas_combustibles.append(info.get("fecha", ""))
    combustibles_kpis += f"""
    <div class="kpi">
      <div class="kpi-main">
        <div class="kpi-label">{COMBUSTIBLE_ETIQUETAS[tipo]}</div>
        <div class="kpi-val">{fmt_litro(info['promedio'])}</div>
      </div>
    </div>"""

fecha_combustibles_dato = max(fechas_combustibles) if fechas_combustibles else ""

# --- 2) Tabla por región -----------------------------------------------------
# Orden geográfico oficial norte -> sur (no alfabético), con nombres cortos
# para la tabla. La clave es el nombre_region tal como lo entrega la CNE.

REGIONES_ORDEN = [
    ("Arica y Parinacota", "Arica y Parinacota"),
    ("Tarapacá", "Tarapacá"),
    ("Antofagasta", "Antofagasta"),
    ("Atacama", "Atacama"),
    ("Coquimbo", "Coquimbo"),
    ("Valparaíso", "Valparaíso"),
    ("Metropolitana de Santiago", "Metropolitana"),
    ("Del Libertador Gral. Bernardo O’Higgins", "O’Higgins"),
    ("Del Maule", "Maule"),
    ("Ñuble", "Ñuble"),
    ("Del Biobío", "Biobío"),
    ("De la Araucanía", "Araucanía"),
    ("De los Ríos", "Los Ríos"),
    ("De los Lagos", "Los Lagos"),
    ("Aysén del Gral. Carlos Ibáñez del Campo", "Aysén"),
    ("Magallanes y de la Antártica Chilena", "Magallanes"),
]

combustibles_tabla_filas = ""
for nombre_api, etiqueta in REGIONES_ORDEN:
    valores = combustibles_regional.get(nombre_api)
    if not valores:
        continue
    celdas = "".join(
        f'<td class="num">{fmt_litro(valores[t]) if t in valores else "—"}</td>'
        for t in COMBUSTIBLE_ORDEN
    )
    combustibles_tabla_filas += f"<tr><td>{etiqueta}</td>{celdas}</tr>"

combustibles_tabla = ""
if combustibles_tabla_filas:
    encabezados = "".join(f"<th>{COMBUSTIBLE_ETIQUETAS[t]}</th>" for t in COMBUSTIBLE_ORDEN)
    combustibles_tabla = f"""
    <div class="tbox">
      <div class="tbox-head">
        <span class="card-name">Precio promedio por región</span>
        <span class="card-desc">Promedio de las estaciones de cada región, por tipo de combustible.</span>
      </div>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Región</th>{encabezados}</tr></thead>
          <tbody>{combustibles_tabla_filas}</tbody>
        </table>
      </div>
    </div>"""

# --- 3) Zonas destacadas -----------------------------------------------------
# Cada tarjeta muestra los 5 tipos de combustible para esa región (o el país
# completo). "Chile completo" reutiliza el promedio nacional ya calculado.

ZONAS_DESTACADAS = [
    ("Antofagasta", "Antofagasta"),
    ("Valparaíso", "Valparaíso"),
    ("Concepción, Región del Biobío", "Del Biobío"),
    ("Región Metropolitana", "Metropolitana de Santiago"),
    ("Chile completo", None),  # None -> usa el promedio nacional
]

combustibles_zonas = ""
for etiqueta, nombre_api in ZONAS_DESTACADAS:
    if nombre_api is None:
        valores = {t: info["promedio"] for t, info in combustibles_nacional.items()}
    else:
        valores = combustibles_regional.get(nombre_api, {})
    if not valores:
        continue
    filas_tipo = ""
    for t in COMBUSTIBLE_ORDEN:
        if t not in valores:
            continue
        filas_tipo += f"""
        <div class="pt">
          <div class="pt-label">{COMBUSTIBLE_ETIQUETAS[t]}</div>
          <div class="pt-val">{fmt_litro(valores[t])}</div>
        </div>"""
    combustibles_zonas += f"""
    <div class="card-wide">
      <div class="card-head">
        <span class="card-name">{etiqueta}</span>
      </div>
      <div class="card-timeline">{filas_tipo}</div>
    </div>"""

# --- Ensamblado final ---------------------------------------------------

if combustibles_kpis:
    combustibles_seccion_body = f"""
    <div class="kpis">{combustibles_kpis}</div>
    <div class="section-sub" style="margin-top:10px;">Promedio por litro, calculado sobre el precio vigente informado por cada estación de servicio (dato más reciente: {fecha_legible(fecha_combustibles_dato) if fecha_combustibles_dato else 's/i'}).</div>
    <div class="subhead">Por región</div>
    <div class="tables">{combustibles_tabla}</div>
    <div class="subhead">Zonas destacadas</div>
    <div class="grid">{combustibles_zonas}
    </div>"""
else:
    combustibles_seccion_body = f"""
    <div class="card-wide placeholder">
      <div class="card-head">
        <span class="card-name">Bencina y diésel</span>
        <span class="card-desc">Precio promedio nacional por litro, según la CNE.</span>
      </div>
      <div class="placeholder-text">Próximamente.</div>
    </div>"""

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

def placeholder_seccion(titulo, descripcion):
    return f"""
    <div class="card-wide placeholder">
      <div class="card-head">
        <span class="card-name">{titulo}</span>
        <span class="card-desc">{descripcion}</span>
      </div>
      <div class="placeholder-text">Próximamente.</div>
    </div>"""


# ---------------------------------------------------------------------------
# Alimentos (ODEPA) — misma lógica que Combustibles: canasta chica, precio
# de hoy/esta semana, sin ahogar la página en las cientos de variedades que
# ODEPA reporta. Dos bloques: mayoristas (diario, con tabla por región) y
# consumidor (semanal, canasta básica).
# ---------------------------------------------------------------------------

alimentos = DATA.get("alimentos", {})
mayoristas_nacional = alimentos.get("mayoristas", {}).get("nacional", {})
mayoristas_regional = alimentos.get("mayoristas", {}).get("regional", {})
consumidor_nacional = alimentos.get("consumidor", {}).get("nacional", {})
consumidor_regional = alimentos.get("consumidor", {}).get("regional", {})

MAYORISTA_ORDEN = ["Palta", "Tomate", "Papa", "Cebolla", "Plátano", "Manzana"]

# Solo las regiones que efectivamente tienen mercado mayorista de fruta y
# hortaliza (9 de las 16) — mismo criterio de orden norte -> sur que en
# Combustibles, pero con los nombres tal como los entrega ODEPA.
ODEPA_REGIONES_ORDEN = [
    ("Región de Arica y Parinacota", "Arica y Parinacota"),
    ("Región de Coquimbo", "Coquimbo"),
    ("Región de Valparaíso", "Valparaíso"),
    ("Región Metropolitana de Santiago", "Metropolitana"),
    ("Región del Maule", "Maule"),
    ("Región de Ñuble", "Ñuble"),
    ("Región del Biobío", "Biobío"),
    ("Región de La Araucanía", "Araucanía"),
    ("Región de Los Lagos", "Los Lagos"),
]

CONSUMIDOR_ETIQUETAS = {
    "Marraqueta": "Pan (marraqueta)",
    "Asado Carnicero": "Carne (asado carnicero)",
    "Pollo Entero": "Pollo entero",
    "Huevo blanco - Extra": "Huevos",
    "Leche Fluida Entera": "Leche entera",
}
CONSUMIDOR_ORDEN = ["Marraqueta", "Asado Carnicero", "Pollo Entero", "Huevo blanco - Extra", "Leche Fluida Entera"]

# --- Mayoristas: KPIs -------------------------------------------------------

mayoristas_kpis = ""
fechas_mayoristas = []
for producto in MAYORISTA_ORDEN:
    info = mayoristas_nacional.get(producto)
    if not info:
        continue
    fechas_mayoristas.append(info.get("fecha", ""))
    mayoristas_kpis += f"""
    <div class="kpi">
      <div class="kpi-main">
        <div class="kpi-label">{producto}</div>
        <div class="kpi-val">{fmt_alimento(info['promedio'])}</div>
      </div>
    </div>"""

# --- Mayoristas: tabla por región -------------------------------------------

mayoristas_tabla_filas = ""
for nombre_api, etiqueta in ODEPA_REGIONES_ORDEN:
    valores = mayoristas_regional.get(nombre_api)
    if not valores:
        continue
    celdas = "".join(
        f'<td class="num">{fmt_alimento(valores[p]) if p in valores else "—"}</td>'
        for p in MAYORISTA_ORDEN
    )
    mayoristas_tabla_filas += f"<tr><td>{etiqueta}</td>{celdas}</tr>"

mayoristas_tabla = ""
if mayoristas_tabla_filas:
    encabezados = "".join(f"<th>{p}</th>" for p in MAYORISTA_ORDEN)
    mayoristas_tabla = f"""
    <div class="tbox">
      <div class="tbox-head">
        <span class="card-name">Precio mayorista por región</span>
        <span class="card-desc">Promedio de los mercados mayoristas de cada región (solo regiones con mercado mayorista).</span>
      </div>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Región</th>{encabezados}</tr></thead>
          <tbody>{mayoristas_tabla_filas}</tbody>
        </table>
      </div>
    </div>"""

# --- Consumidor: KPIs --------------------------------------------------------

consumidor_kpis = ""
fechas_consumidor = []
for producto in CONSUMIDOR_ORDEN:
    info = consumidor_nacional.get(producto)
    if not info:
        continue
    fechas_consumidor.append(info.get("fecha", ""))
    consumidor_kpis += f"""
    <div class="kpi">
      <div class="kpi-main">
        <div class="kpi-label">{CONSUMIDOR_ETIQUETAS.get(producto, producto)}</div>
        <div class="kpi-val">{fmt_alimento(info['promedio'], info.get('unidad', 'kg'))}</div>
      </div>
    </div>"""

# --- Consumidor: tabla por región --------------------------------------------

consumidor_tabla_filas = ""
for nombre_api, etiqueta in ODEPA_REGIONES_ORDEN:
    valores = consumidor_regional.get(nombre_api)
    if not valores:
        continue
    celdas = "".join(
        f'<td class="num">{fmt_alimento(valores[p], (consumidor_nacional.get(p) or {}).get("unidad", "kg")) if p in valores else "—"}</td>'
        for p in CONSUMIDOR_ORDEN
    )
    consumidor_tabla_filas += f"<tr><td>{etiqueta}</td>{celdas}</tr>"

consumidor_tabla = ""
if consumidor_tabla_filas:
    encabezados = "".join(f"<th>{CONSUMIDOR_ETIQUETAS.get(p, p)}</th>" for p in CONSUMIDOR_ORDEN)
    consumidor_tabla = f"""
    <div class="tbox">
      <div class="tbox-head">
        <span class="card-name">Precio al consumidor por región</span>
        <span class="card-desc">Promedio de supermercados, ferias, carnicerías y panaderías de cada región.</span>
      </div>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Región</th>{encabezados}</tr></thead>
          <tbody>{consumidor_tabla_filas}</tbody>
        </table>
      </div>
    </div>"""

# --- Ensamblado final ---------------------------------------------------

if mayoristas_kpis or consumidor_kpis:
    fecha_mayoristas_dato = max(fechas_mayoristas) if fechas_mayoristas else ""
    fecha_consumidor_dato = max(fechas_consumidor) if fechas_consumidor else ""
    alimentos_seccion_body = ""
    if mayoristas_kpis:
        alimentos_seccion_body += f"""
    <div class="subhead">Mayoristas (hoy)</div>
    <div class="kpis">{mayoristas_kpis}</div>
    <div class="section-sub" style="margin-top:10px;">Precio promedio mayorista por kilo, día hábil más reciente: {fecha_legible(fecha_mayoristas_dato) if fecha_mayoristas_dato else 's/i'}.</div>"""
    if mayoristas_tabla:
        alimentos_seccion_body += f"""
    <div class="tables" style="margin-top:14px;">{mayoristas_tabla}</div>"""
    if consumidor_kpis:
        alimentos_seccion_body += f"""
    <div class="subhead">Consumidor (semanal)</div>
    <div class="kpis">{consumidor_kpis}</div>
    <div class="section-sub" style="margin-top:10px;">Precio promedio al consumidor (supermercados, ferias, carnicerías y panaderías), semana que termina el {fecha_legible(fecha_consumidor_dato) if fecha_consumidor_dato else 's/i'}.</div>"""
    if consumidor_tabla:
        alimentos_seccion_body += f"""
    <div class="tables" style="margin-top:14px;">{consumidor_tabla}</div>"""

    # --- Tendencia mensual (últimos ~9 meses) de cada producto de la canasta ---
    # Un punto por mes: el último día (o última semana, para consumidor) con
    # datos de ese mes, terminando en el mismo valor que ya se ve en los KPIs
    # de arriba — para revisar la variación reciente de cada producto.

    tendencia_mayoristas = alimentos.get("tendencia_mayoristas", {})
    tendencia_consumidor = alimentos.get("tendencia_consumidor", {})

    def _tendencia_card(nombre, serie, unidad="kg"):
        if not serie:
            return ""
        puntos_html = ""
        total = len(serie)
        for i, p in enumerate(serie):
            es_destacado = (i == total - 1)
            clase = "pt pt-destacado" if es_destacado else "pt"
            puntos_html += f"""
            <div class="{clase}">
              <div class="pt-label">{fecha_legible(p.get('fecha', p['periodo']))}</div>
              <div class="pt-val">{fmt_alimento(p['valor'], unidad)}</div>
            </div>"""
        return f"""
    <div class="card-wide">
      <div class="card-head">
        <span class="card-name">{nombre}</span>
        <span class="card-desc">Precio del último día con datos de cada mes.</span>
      </div>
      <div class="card-timeline">{puntos_html}</div>
    </div>"""

    tendencia_cards = ""
    for producto in MAYORISTA_ORDEN:
        tendencia_cards += _tendencia_card(f"{producto} (mayorista)", tendencia_mayoristas.get(producto, []))
    for producto in CONSUMIDOR_ORDEN:
        unidad_producto = (consumidor_nacional.get(producto) or {}).get("unidad", "kg")
        tendencia_cards += _tendencia_card(
            f"{CONSUMIDOR_ETIQUETAS.get(producto, producto)} (consumidor)",
            tendencia_consumidor.get(producto, []),
            unidad_producto,
        )

    if tendencia_cards:
        alimentos_seccion_body += f"""
    <div class="subhead">Tendencia mensual</div>
    <div class="grid">{tendencia_cards}
    </div>"""

    # --- Anomalía destacada de Alimentos ------------------------------------

    _aa = anomalias.get("alimentos")
    if _aa:
        if _aa["tipo_canasta"] == "mayorista":
            _aa_nombre = f"{_aa['producto']} (mayorista)"
            _aa_unidad = "kg"
        else:
            _aa_nombre = f"{CONSUMIDOR_ETIQUETAS.get(_aa['producto'], _aa['producto'])} (consumidor)"
            _aa_unidad = (consumidor_nacional.get(_aa["producto"]) or {}).get("unidad", "kg")
        _aa_signo = "+" if _aa["cambio_pct"] > 0 else ""
        alimentos_seccion_body += anomalia_card_html(
            f"<strong>{_aa_nombre}</strong> tuvo el movimiento más inusual de la categoría: "
            f"{_aa_signo}{_aa['cambio_pct']:.2f}% al {fecha_legible(_aa['fecha'])} "
            f"(precio actual: {fmt_alimento(_aa['valor_actual'], _aa_unidad)})."
        )
else:
    alimentos_seccion_body = placeholder_seccion(
        "Precios de alimentos",
        "Precios mayoristas y al consumidor de frutas y verduras, según ODEPA.",
    )


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

  .header-center{{display:flex; flex-direction:column; align-items:center; text-align:center;}}
  .brand{{display:flex; align-items:center; justify-content:center; gap:16px; margin-bottom:2px;}}
  .brand-mark{{flex-shrink:0;}}
  .brand-titles{{display:flex; flex-direction:column; gap:4px; align-items:center;}}
  .page-title{{font-size:26px; font-weight:700; letter-spacing:.01em;}}
  .page-title .flag{{font-size:22px;}}
  .brand-name{{font-size:13px; font-weight:600; letter-spacing:.08em; color:var(--muted);}}
  .brand-name .k{{color:var(--orange);}}
  .brand-tagline{{
    font-size:11px; color:var(--muted); letter-spacing:.12em; text-transform:uppercase;
    display:flex; align-items:center; justify-content:center; gap:10px; margin:14px 0 10px 0;
  }}
  .brand-tagline .dash{{display:inline-block; width:22px; height:1px; background:var(--orange);}}
  .site-link{{font-size:12px; margin-bottom:14px;}}
  .site-link a{{color:var(--orange); text-decoration:none;}}
  .site-link a:hover{{text-decoration:underline;}}
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

  .anomaly-card{{
    display:flex; align-items:flex-start; gap:12px;
    background:linear-gradient(135deg, rgba(255,140,0,0.10), rgba(255,140,0,0.03));
    border:1px solid var(--orange); border-radius:10px;
    padding:14px 18px; margin-top:16px;
  }}
  .anomaly-icon{{font-size:20px; line-height:1; flex:0 0 auto;}}
  .anomaly-body{{min-width:0;}}
  .anomaly-title{{font-size:11px; font-weight:700; color:var(--orange); text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px;}}
  .anomaly-desc{{font-size:13px; color:var(--text); line-height:1.5;}}
  .anomaly-desc strong{{color:var(--orange);}}

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

  <div class="header-center">
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
    <div class="site-link"><a href="https://www.heuristika.pro" target="_blank">www.heuristika.pro</a></div>
    <div class="update-note">La información que estás viendo fue cargada el {cargado_en}.</div>
  </div>

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
    {anomalia_macro_html}
  </section>

  {tasas_seccion}

  <section id="combustibles" class="section">
    <h1>Combustibles</h1>
    <div class="section-sub">Precios de bencina y diésel, según la CNE.</div>
    {combustibles_seccion_body}
  </section>

  <section id="alimentos" class="section">
    <h1>Alimentos</h1>
    <div class="section-sub">Precios de una canasta chica de alimentos, según ODEPA.</div>
    {alimentos_seccion_body}
  </section>

  {historicos_seccion}

  <div class="footer">
    Fuentes: <a href="https://mindicador.cl" target="_blank">mindicador.cl</a> (Banco Central de Chile),
    <a href="https://api.cmfchile.cl" target="_blank">CMF Bancos</a> (Comisión para el Mercado Financiera),
    <a href="https://api.cne.cl" target="_blank">CNE</a> (Comisión Nacional de Energía)
    y <a href="https://datos.odepa.gob.cl" target="_blank">ODEPA</a> (Oficina de Estudios y Políticas Agrarias).
    Información con fines informativos. No constituye asesoría ni recomendación de inversión.
    <br><br>
    <a href="https://www.heuristika.pro" target="_blank">www.heuristika.pro</a> / <a href="mailto:contacto@heuristika.pro">contacto@heuristika.pro</a>
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
