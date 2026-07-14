"""
indices.py
Descarga indicadores económicos y financieros de Chile:
  - mindicador.cl (sin API key): valores actuales + históricos mensuales
  - api.cmfchile.cl (requiere CMF_API_KEY): TIP/TMC actuales + históricos
 
Escribe todo a datos.json, que luego consume build_site.py.
 
Uso local:
    export CMF_API_KEY="tu_api_key"
    python3 indices.py
"""
 
import json
import os
import time
from datetime import datetime, timezone
import urllib.request
import urllib.error
 
CMF_API_KEY = os.environ.get("CMF_API_KEY", "")
AHORA = datetime.now()
ANIO_ACTUAL = AHORA.year
N_ANIOS_HISTORICO = 5  # cuántos años hacia atrás traer para los gráficos
 
MACRO_INDICADORES = [
    "dolar", "euro", "uf", "utm", "ipc", "tpm",
    "imacec", "tasa_desempleo", "libra_cobre", "bitcoin",
]
 
# Indicadores que se publican día a día vs. una vez al mes —
# determina si "los últimos N datos" se muestran por día o por mes.
INDICADORES_DIARIOS = {"dolar", "euro", "uf", "libra_cobre", "bitcoin"}
N_RECIENTES = 5
 
# Tipos de operación TIP/TMC más relevantes para "costo del crédito".
# Ver documentación: https://api.cmfchile.cl/documentacion/TIP.html
TIPOS_RELEVANTES = {
    14: "Hipotecario UF (>1 año, sobre 2.000 UF)",
    24: "Hipotecario UF (>1 año, hasta 2.000 UF)",
    9:  "Consumo en pesos (largo plazo, montos altos)",
    35: "Consumo en pesos (largo plazo, montos medios)",
    37: "Consumo en pesos (corto plazo)",
}
 
 
def http_get_json(url, timeout=12, reintentos=2):
    """GET con reintentos cortos: si falla, falla rápido (no queremos que
    una API lenta haga que el job entero se demore 20+ minutos)."""
    ultimo_error = None
    for intento in range(1, reintentos + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "heuristika-indicadores/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            ultimo_error = e
            if intento < reintentos:
                print(f"  aviso: intento {intento} falló ({type(e).__name__}: {e}), reintentando...")
                time.sleep(1.5)
    raise ultimo_error
 
 
# ---------------------------------------------------------------------------
# mindicador.cl
# ---------------------------------------------------------------------------
 
def get_mindicador_actual():
    print("Descargando valores actuales de mindicador.cl ...")
    data = http_get_json("https://mindicador.cl/api")
    out = {}
    for campo in MACRO_INDICADORES:
        if campo in data:
            out[campo] = {
                "nombre": data[campo]["nombre"],
                "unidad": data[campo]["unidad_medida"],
                "valor": data[campo]["valor"],
                "fecha": data[campo]["fecha"],
            }
    return out
 
 
def get_mindicador_historico():
    """Trae la serie de cada indicador para los últimos N años y la
    agrega a promedio mensual (para que los gráficos no sean gigantes).
    De paso guarda los últimos N_RECIENTES puntos "crudos" (por día para
    los indicadores diarios, por mes para los mensuales) para la vista
    de tarjetas con el valor destacado + últimos períodos."""
    print(f"Descargando histórico ({N_ANIOS_HISTORICO} años) de mindicador.cl ...")
    anios = range(ANIO_ACTUAL - N_ANIOS_HISTORICO + 1, ANIO_ACTUAL + 1)
    resultado = {}
    recientes = {}
 
    for indicador in MACRO_INDICADORES:
        puntos_por_mes = {}
        puntos_crudos = {}  # fecha -> valor, sin agregar
        for anio in anios:
            url = f"https://mindicador.cl/api/{indicador}/{anio}"
            try:
                data = http_get_json(url)
            except Exception as e:
                print(f"  aviso: no se pudo traer {indicador} {anio}: {e}")
                continue
            for punto in data.get("serie", []):
                fecha = punto.get("fecha", "")
                valor = punto.get("valor")
                if not fecha or valor is None:
                    continue
                mes = fecha[:7]  # "YYYY-MM"
                puntos_por_mes.setdefault(mes, []).append(valor)
                puntos_crudos[fecha] = valor
            time.sleep(0.1)  # ser amable con la API
 
        serie_mensual = [
            {"periodo": mes, "valor": round(sum(vals) / len(vals), 4)}
            for mes, vals in sorted(puntos_por_mes.items())
        ]
        resultado[indicador] = serie_mensual
 
        if indicador in INDICADORES_DIARIOS:
            ultimos = sorted(puntos_crudos.items())[-N_RECIENTES:]
            recientes[indicador] = {
                "tipo": "diario",
                "puntos": [{"etiqueta": f, "valor": v} for f, v in ultimos],
            }
        else:
            ultimos = serie_mensual[-N_RECIENTES:]
            recientes[indicador] = {
                "tipo": "mensual",
                "puntos": [{"etiqueta": p["periodo"], "valor": p["valor"]} for p in ultimos],
            }
 
    return resultado, recientes
 
 
# ---------------------------------------------------------------------------
# api.cmfchile.cl (TIP / TMC)
# ---------------------------------------------------------------------------
 
def _extraer_items(data, clave, recurso):
    """La API a veces entrega la lista directa bajo 'TIPs'/'TMCs',
    y a veces anidada bajo una subclave 'TIP'/'TMC'. Manejamos ambos casos."""
    bloque = data.get(clave, [])
    if isinstance(bloque, list):
        return bloque
    if isinstance(bloque, dict):
        sub = bloque.get(recurso.upper(), [])
        return sub if isinstance(sub, list) else ([sub] if sub else [])
    return []
 
 
CMF_PAUSA = 1.2  # segundos entre llamadas a la API de CMF, para no gatillar su límite de tasa
 
 
def _cmf_get(recurso, anio):
    """Wrapper para llamar a un recurso de CMF (tip/tmc/ipc) para un año.
    Devuelve None si falla, sin cortar el resto del proceso."""
    url = (
        f"https://api.cmfchile.cl/api-sbifv3/recursos_api/{recurso}/{anio}"
        f"?apikey={CMF_API_KEY}&formato=json"
    )
    try:
        data = http_get_json(url)
    except Exception as e:
        print(f"  aviso: no se pudo traer {recurso} {anio} desde CMF ({type(e).__name__}: {e})")
        return None
    finally:
        time.sleep(CMF_PAUSA)
    return data
 
 
def get_cmf_historico():
    """Trae TIP y TMC para los últimos N años, filtrado a los tipos
    relevantes, y arma una serie de tiempo por tipo de operación."""
    if not CMF_API_KEY:
        print("AVISO: no hay CMF_API_KEY definida, se omiten tasas bancarias (TIP/TMC).")
        return {"tip": {}, "tmc": {}}
 
    print(f"Descargando tasas CMF (TIP/TMC), últimos {N_ANIOS_HISTORICO} años ...")
    anios = range(ANIO_ACTUAL - N_ANIOS_HISTORICO + 1, ANIO_ACTUAL + 1)
    series = {"tip": {}, "tmc": {}}
 
    for recurso in ("tip", "tmc"):
        clave = "TIPs" if recurso == "tip" else "TMCs"
        for anio in anios:
            data = _cmf_get(recurso, anio)
            if data is None:
                continue
 
            items = _extraer_items(data, clave, recurso)
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    tipo = int(item.get("Tipo"))
                except (TypeError, ValueError):
                    continue
                if tipo not in TIPOS_RELEVANTES:
                    continue
                try:
                    valor = float(item.get("Valor"))
                except (TypeError, ValueError):
                    continue
                fecha = item.get("Fecha")
                if not fecha:
                    continue
                series[recurso].setdefault(tipo, {})[fecha] = valor
 
    # convertir dict fecha->valor a lista ordenada por fecha
    salida = {"tip": {}, "tmc": {}}
    for recurso in ("tip", "tmc"):
        for tipo, puntos in series[recurso].items():
            serie = [{"fecha": f, "valor": v} for f, v in sorted(puntos.items())]
            salida[recurso][str(tipo)] = {
                "etiqueta": TIPOS_RELEVANTES[tipo],
                "serie": serie,
            }
    return salida
 
 
def get_cmf_ipc():
    """IPC directo desde CMF (que a su vez toma el dato oficial del INE).
    Se usa como reemplazo del IPC de mindicador.cl, que suele atrasarse."""
    if not CMF_API_KEY:
        return []
 
    print(f"Descargando IPC (CMF/INE), últimos {N_ANIOS_HISTORICO} años ...")
    anios = range(ANIO_ACTUAL - N_ANIOS_HISTORICO + 1, ANIO_ACTUAL + 1)
    puntos = {}
 
    for anio in anios:
        data = _cmf_get("ipc", anio)
        if data is None:
            continue
 
        bloque = data.get("IPCs", [])
        if isinstance(bloque, list):
            items = bloque
        elif isinstance(bloque, dict):
            sub = bloque.get("IPC", [])
            items = sub if isinstance(sub, list) else ([sub] if sub else [])
        else:
            items = []
 
        for item in items:
            if not isinstance(item, dict):
                continue
            fecha = item.get("Fecha")
            valor_raw = item.get("Valor")
            if not fecha or valor_raw is None:
                continue
            try:
                valor = float(str(valor_raw).replace(",", "."))
            except ValueError:
                continue
            puntos[fecha] = valor
 
    return [{"fecha": f, "periodo": f[:7], "valor": v} for f, v in sorted(puntos.items())]
 
 
def main():
    historico_macro, recientes = get_mindicador_historico()
    salida = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "macro": get_mindicador_actual(),
        "historico_macro": historico_macro,
        "recientes": recientes,
        "tasas": get_cmf_historico(),
    }
 
    # El IPC de mindicador.cl suele atrasarse; si CMF tiene datos, los usamos.
    ipc_cmf = get_cmf_ipc()
    if ipc_cmf:
        salida["historico_macro"]["ipc"] = [
            {"periodo": p["periodo"], "valor": p["valor"]} for p in ipc_cmf
        ]
        ultimo = ipc_cmf[-1]
        salida["macro"]["ipc"] = {
            "nombre": "Indice de Precios al Consumidor (IPC)",
            "unidad": "Porcentaje",
            "valor": ultimo["valor"],
            "fecha": ultimo["fecha"],
        }
        salida["recientes"]["ipc"] = {
            "tipo": "mensual",
            "puntos": [
                {"etiqueta": p["periodo"], "valor": p["valor"]}
                for p in ipc_cmf[-N_RECIENTES:]
            ],
        }
        print(f"  IPC actualizado desde CMF: {ultimo['valor']}% ({ultimo['fecha']})")
 
    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
 
    # Aviso visible si algo quedó vacío, para detectarlo altiro en el log.
    if not salida["tasas"]["tip"] and not salida["tasas"]["tmc"]:
        print("AVISO: tasas TIP/TMC quedaron vacías esta corrida (CMF no respondió).")
    if not ipc_cmf:
        print("AVISO: no se pudo actualizar IPC desde CMF esta corrida, se mantuvo el de mindicador.cl.")
 
    print("OK -> datos.json")
 
 
if __name__ == "__main__":
    main()
 
