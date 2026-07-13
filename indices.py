"""
indices.py
Descarga indicadores económicos y financieros de Chile desde:
  - mindicador.cl (sin API key): dolar, euro, uf, utm, ipc, tpm, imacec, desempleo, cobre, bitcoin
  - api.cmfchile.cl (requiere CMF_API_KEY): TIP (tasa de interés promedio) y TMC (tasa máxima convencional)
 
Escribe todo a datos.json, que luego consume build_site.py.
 
Uso local:
    export CMF_API_KEY="tu_api_key"
    python3 indices.py
"""
 
import json
import os
import sys
from datetime import datetime, timezone
import urllib.request
import urllib.error
 
CMF_API_KEY = os.environ.get("CMF_API_KEY", "")
 
# Tipos de operación TIP/TMC más relevantes para "costo del crédito".
# Ver documentación: https://api.cmfchile.cl/documentacion/TIP.html
TIPOS_RELEVANTES = {
    14: "Hipotecario UF (>1 año, sobre 2.000 UF)",
    24: "Hipotecario UF (>1 año, hasta 2.000 UF)",
    9:  "Consumo en pesos (largo plazo, montos altos)",
    35: "Consumo en pesos (largo plazo, montos medios)",
    37: "Consumo en pesos (corto plazo)",
}
 
 
def http_get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "heuristika-indicadores/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))
 
 
def get_mindicador():
    print("Descargando mindicador.cl ...")
    data = http_get_json("https://mindicador.cl/api")
    campos = [
        "uf", "utm", "dolar", "euro", "ipc", "tpm",
        "imacec", "tasa_desempleo", "libra_cobre", "bitcoin",
    ]
    out = {}
    for campo in campos:
        if campo in data:
            out[campo] = {
                "nombre": data[campo]["nombre"],
                "unidad": data[campo]["unidad_medida"],
                "valor": data[campo]["valor"],
                "fecha": data[campo]["fecha"],
            }
    return out
 
 
def get_cmf_tip_tmc(year):
    if not CMF_API_KEY:
        print("AVISO: no hay CMF_API_KEY definida, se omiten tasas bancarias (TIP/TMC).")
        return {"tip": [], "tmc": []}
 
    print(f"Descargando tasas CMF (TIP/TMC) para {year} ...")
    resultado = {"tip": [], "tmc": []}
 
    for recurso in ("tip", "tmc"):
        url = (
            f"https://api.cmfchile.cl/api-sbifv3/recursos_api/{recurso}/{year}"
            f"?apikey={CMF_API_KEY}&formato=json"
        )
        try:
            data = http_get_json(url)
        except urllib.error.HTTPError as e:
            print(f"  error HTTP en {recurso}: {e}")
            continue
        except Exception as e:
            print(f"  error en {recurso}: {e}")
            continue
 
        clave = "TIPs" if recurso == "tip" else "TMCs"
        bloque = data.get(clave, [])
 
        # La API a veces entrega la lista directa bajo "TIPs"/"TMCs",
        # y a veces anidada bajo una subclave "TIP"/"TMC". Manejamos ambos casos.
        if isinstance(bloque, list):
            items = bloque
        elif isinstance(bloque, dict):
            sub = bloque.get(recurso.upper(), [])
            items = sub if isinstance(sub, list) else ([sub] if sub else [])
        else:
            items = []
 
        if not items:
            print(f"  AVISO: no se encontraron items en '{clave}'. "
                  f"Claves recibidas: {list(data.keys())}")
 
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                tipo = int(item.get("Tipo"))
            except (TypeError, ValueError):
                continue
            if tipo not in TIPOS_RELEVANTES:
                continue
            resultado[recurso].append({
                "tipo": tipo,
                "etiqueta": TIPOS_RELEVANTES[tipo],
                "titulo": item.get("Titulo"),
                "subtitulo": item.get("SubTitulo"),
                "valor": float(item.get("Valor")),
                "fecha": item.get("Fecha"),
                "hasta": item.get("Hasta", ""),
            })
 
    # Nos quedamos solo con el registro más reciente por tipo.
    for recurso in ("tip", "tmc"):
        ultimos = {}
        for item in resultado[recurso]:
            t = item["tipo"]
            if t not in ultimos or item["fecha"] > ultimos[t]["fecha"]:
                ultimos[t] = item
        resultado[recurso] = sorted(ultimos.values(), key=lambda x: x["tipo"])
 
    return resultado
 
 
def main():
    ahora = datetime.now(timezone.utc).isoformat()
    year = datetime.now().year
 
    salida = {
        "generado": ahora,
        "macro": get_mindicador(),
        "tasas": get_cmf_tip_tmc(year),
    }
 
    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
 
    print("OK -> datos.json")
 
 
if __name__ == "__main__":
    main()
 
