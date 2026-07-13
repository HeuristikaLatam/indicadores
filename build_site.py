"""
build_site.py
Lee datos.json (generado por indices.py) y escribe index.html:
un sitio estático, autocontenido, con la marca de Heurística.

Uso local:
    python3 indices.py
    python3 build_site.py
    open index.html
"""

import json
from datetime import datetime

with open("datos.json", "r", encoding="utf-8") as f:
    DATA = json.load(f)


def fmt(valor, unidad):
    if unidad == "Porcentaje":
        return f"{valor:.2f}%"
    if unidad == "Dólar":
        return f"US$ {valor:,.2f}".replace(",", ".")
    return f"${valor:,.0f}".replace(",", ".")


def fecha_legible(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d-%m-%Y")
    except Exception:
        return iso


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
tasas = DATA.get("tasas", {"tip": [], "tmc": []})

macro_cards = ""
for key, label in MACRO_ORDEN:
    d = macro.get(key)
    if not d:
        continue
    macro_cards += f"""
    <div class="card">
      <div class="name">{label}</div>
      <div class="val">{fmt(d['valor'], d['unidad'])}</div>
      <div class="date">{fecha_legible(d['fecha'])}</div>
    </div>"""

tip_rows = ""
for item in tasas.get("tip", []):
    tip_rows += f"""
    <tr>
      <td>{item['etiqueta']}</td>
      <td class="num">{item['valor']:.2f}%</td>
      <td class="date-cell">{fecha_legible(item['fecha'])}</td>
    </tr>"""

tmc_rows = ""
for item in tasas.get("tmc", []):
    tmc_rows += f"""
    <tr>
      <td>{item['etiqueta']}</td>
      <td class="num">{item['valor']:.2f}%</td>
      <td class="date-cell">{fecha_legible(item['fecha'])}</td>
    </tr>"""

tasas_seccion = ""
if tip_rows or tmc_rows:
    tasas_seccion = f"""
    <h1>Costo del crédito</h1>
    <div class="tables">
      <div class="tbox">
        <div class="tbox-title">Tasa de interés promedio (TIP)</div>
        <table>
          <thead><tr><th>Tipo de operación</th><th>Tasa</th><th>Vigencia desde</th></tr></thead>
          <tbody>{tip_rows if tip_rows else '<tr><td colspan="3" class="empty">Sin datos — revisa CMF_API_KEY</td></tr>'}</tbody>
        </table>
      </div>
      <div class="tbox">
        <div class="tbox-title">Tasa máxima convencional (TMC)</div>
        <table>
          <thead><tr><th>Tipo de operación</th><th>Tasa</th><th>Vigencia desde</th></tr></thead>
          <tbody>{tmc_rows if tmc_rows else '<tr><td colspan="3" class="empty">Sin datos — revisa CMF_API_KEY</td></tr>'}</tbody>
        </table>
      </div>
    </div>
    """

generado = fecha_legible(DATA.get("generado", ""))

HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Indicadores Económicos · Heurística</title>
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

  .brand{{display:flex; align-items:center; gap:14px; margin-bottom:8px;}}
  .brand-mark{{
    display:grid; grid-template-columns:repeat(3,10px); grid-template-rows:repeat(3,10px);
    gap:3px; flex-shrink:0;
  }}
  .brand-mark div{{background:var(--muted); border-radius:2px;}}
  .brand-mark div:nth-child(1),.brand-mark div:nth-child(3),
  .brand-mark div:nth-child(7),.brand-mark div:nth-child(9){{background:transparent;}}
  .brand-mark div:nth-child(5){{background:var(--orange);}}
  .brand-name{{font-size:20px; font-weight:700; letter-spacing:.04em;}}
  .brand-name .k{{color:var(--orange);}}
  .brand-tag{{font-size:11px; color:var(--muted); letter-spacing:.08em; text-transform:uppercase; margin:2px 0 28px 0;}}

  h1{{font-size:14px; font-weight:600; color:var(--muted); text-transform:uppercase;
     letter-spacing:.08em; margin:32px 0 14px;}}
  h1:first-of-type{{margin-top:0;}}

  .grid{{
    display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
    gap:10px;
  }}
  .card{{
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:14px 16px;
  }}
  .card .name{{font-size:12px; color:var(--muted); margin-bottom:6px;}}
  .card .val{{font-size:20px; font-weight:600; font-variant-numeric:tabular-nums;}}
  .card .date{{font-size:10px; color:var(--muted); margin-top:6px;}}

  .tables{{display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px;}}
  .tbox{{background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px;}}
  .tbox-title{{font-size:13px; font-weight:600; margin-bottom:10px; color:var(--text);}}
  table{{width:100%; border-collapse:collapse; font-size:13px;}}
  th{{text-align:left; color:var(--muted); font-weight:500; font-size:11px;
     text-transform:uppercase; letter-spacing:.04em; padding-bottom:8px; border-bottom:1px solid var(--line);}}
  td{{padding:8px 0; border-bottom:1px solid var(--line);}}
  td.num{{font-variant-numeric:tabular-nums; font-weight:600; color:var(--orange);}}
  td.date-cell{{color:var(--muted); font-size:12px;}}
  td.empty{{color:var(--muted); font-style:italic; text-align:center;}}

  .footer{{margin-top:36px; font-size:11px; color:var(--muted); line-height:1.6;}}
  .footer a{{color:var(--orange); text-decoration:none;}}
</style>
</head>
<body>
<div class="wrap">

  <div class="brand">
    <div class="brand-mark">
      <div></div><div></div><div></div>
      <div></div><div></div><div></div>
      <div></div><div></div><div></div>
    </div>
    <div class="brand-name">HEURISTI<span class="k">K</span>A</div>
  </div>
  <div class="brand-tag">Indicadores económicos · Chile</div>

  <h1>Macro</h1>
  <div class="grid">{macro_cards}
  </div>

  {tasas_seccion}

  <div class="footer">
    Fuentes: <a href="https://mindicador.cl" target="_blank">mindicador.cl</a> (Banco Central de Chile)
    y <a href="https://api.cmfchile.cl" target="_blank">CMF Bancos</a> (Comisión para el Mercado Financiero).
    Generado automáticamente el {generado}.<br>
    Información con fines informativos. No constituye asesoría ni recomendación de inversión.
  </div>

</div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print("OK -> index.html")
