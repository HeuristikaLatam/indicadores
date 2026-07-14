"""
indices.py
Descarga indicadores económicos y financieros de Chile:
  - mindicador.cl (sin API key): valores actuales + históricos mensuales
  - api.cmfchile.cl (requiere CMF_API_KEY): TIP/TMC actuales + históricos
  - api.cne.cl (requiere CNE_EMAIL/CNE_PASSWORD): precios de combustibles líquidos

Escribe todo a datos.json, que luego consume build_site.py.

Uso local:
    export CMF_API_KEY="tu_api_key"
    export CNE_EMAIL="tu_email"
    export CNE_PASSWORD="tu_password"
    python3 indices.py
"""

import json
import os
import time
from datetime import datetime, timezone
import urllib.request
import urllib.error
import urllib.parse

CMF_API_KEY = os.environ.get("CMF_API_KEY", "")
CNE_EMAIL = os.environ.get("CNE_EMAIL", "")
CNE_PASSWORD = os.environ.get("CNE_PASSWORD", "")
AHORA = datetime.now()
ANIO_ACTUAL = AHORA.year
N_ANIOS_HISTORICO = 5  # cuántos años hacia atrás traer para los gráficos

MACRO_INDICADORES = [
    "dolar", "euro", "uf", "utm", "ipc", "tpm",
    "imacec", "tasa_desempleo", "libra_cobre", "bitcoin",
]

# Tipos de operación TIP/TMC más relevantes para "costo del crédito".
# Ver documentación: https://api.cmfchile.cl/documentacion/TIP.html
TIPOS_RELEVANTES = {
    14: "Hipotecario UF (>1 año, sobre 2.000 UF)",
    24: "Hipotecario UF (>1 año, hasta 2.000 UF)",
    9:  "Consumo en pesos (largo plazo, montos altos)",
    35: "Consumo en pesos (largo plazo, montos medios)",
    37: "Consumo en pesos (corto plazo)",
}


def http_get_json(url, timeout=25, reintentos=3, headers=None):
    """GET con reintentos: las APIs públicas a veces se cuelgan un momento,
    y este script corre solo todos los días sin nadie mirando."""
    ultimo_error = None
    base_headers = {"User-Agent": "heuristika-indicadores/1.0"}
    if headers:
        base_headers.update(headers)
    for intento in range(1, reintentos + 1):
        try:
            req = urllib.request.Request(url, headers=base_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            ultimo_error = e
            if intento < reintentos:
                print(f"  aviso: intento {intento} falló ({e}), reintentando...")
                time.sleep(2 * intento)
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
    agrega a promedio mensual (para que los gráficos no sean gigantes)."""
    print(f"Descargando histórico ({N_ANIOS_HISTORICO} años) de mindicador.cl ...")
    anios = range(ANIO_ACTUAL - N_ANIOS_HISTORICO + 1, ANIO_ACTUAL + 1)
    resultado = {}

    for indicador in MACRO_INDICADORES:
        puntos_por_mes = {}
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
            time.sleep(0.1)  # ser amable con la API

        serie_mensual = [
            {"periodo": mes, "valor": round(sum(vals) / len(vals), 4)}
            for mes, vals in sorted(puntos_por_mes.items())
        ]
        resultado[indicador] = serie_mensual

    return resultado


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
            url = (
                f"https://api.cmfchile.cl/api-sbifv3/recursos_api/{recurso}/{anio}"
                f"?apikey={CMF_API_KEY}&formato=json"
            )
            try:
                data = http_get_json(url)
            except urllib.error.HTTPError as e:
                print(f"  error HTTP en {recurso} {anio}: {e}")
                continue
            except Exception as e:
                print(f"  error en {recurso} {anio}: {e}")
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
            time.sleep(0.1)

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
        url = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/ipc/{anio}?apikey={CMF_API_KEY}&formato=json"
        try:
            data = http_get_json(url)
        except Exception as e:
            print(f"  aviso: no se pudo traer IPC {anio}: {e}")
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
        time.sleep(0.1)

    return [{"fecha": f, "periodo": f[:7], "valor": v} for f, v in sorted(puntos.items())]


# ---------------------------------------------------------------------------
# api.cne.cl (precios de combustibles líquidos)
# ---------------------------------------------------------------------------

def get_cne_token():
    """La API de la CNE no usa API key fija: hay que loguearse con
    email/password (POST /api/login) y usar el token que devuelve como
    Bearer en cada request. Lo hacemos una vez por corrida."""
    if not (CNE_EMAIL and CNE_PASSWORD):
        return None

    print("Autenticando con API CNE ...")
    body = urllib.parse.urlencode({"email": CNE_EMAIL, "password": CNE_PASSWORD}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.cne.cl/api/login",
        data=body,
        headers={
            "User-Agent": "heuristika-indicadores/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            token = data.get("token")
            if not token:
                print("  aviso: login CNE respondió sin token.")
            return token
    except Exception as e:
        print(f"  aviso: no se pudo autenticar con CNE: {e}")
        return None


def get_cne_combustibles():
    """Precio promedio mensual por litro, por tipo de combustible, desde
    la API de Energía Abierta de la CNE (/api/ea/precio/combustibleliquido).

    Devuelve:
      - "nacional": {tipo_combustible: [{"periodo": "YYYY-MM", "valor": n}, ...]}
        (promedio simple de todas las regiones reportadas ese mes)
      - "regional": {tipo_combustible: {region_nombre: {"periodo": ..., "valor": ...}}}
        (último valor disponible por región, para la tabla de la sección)

    NOTA: el endpoint está marcado "en desarrollo" en la documentación de la
    CNE — si cambian los nombres de campo o de tipo_combustible, revisar
    aquí primero antes que en build_site.py.
    """
    token = get_cne_token()
    if not token:
        print("AVISO: no hay CNE_EMAIL/CNE_PASSWORD (o falló el login), se omiten combustibles.")
        return {"nacional": {}, "regional": {}}

    print("Descargando precios de combustibles líquidos (CNE) ...")
    try:
        data = http_get_json(
            "https://api.cne.cl/api/ea/precio/combustibleliquido",
            headers={"Authorization": f"Bearer {token}"},
        )
    except Exception as e:
        print(f"  aviso: no se pudo traer combustibles CNE: {e}")
        return {"nacional": {}, "regional": {}}

    filas = data.get("data", [])
    if not filas:
        print("  aviso: la API CNE no devolvió filas de combustibles.")

    nacional_puntos = {}          # tipo -> periodo -> [precios de cada región]
    regional_ultimo = {}          # (tipo, region) -> {"periodo", "valor"}

    for f in filas:
        tipo = f.get("tipo_combustible")
        anio = f.get("anio")
        mes = f.get("mes")
        region = f.get("region_nombre")
        try:
            precio = float(f.get("precio_por_litro"))
        except (TypeError, ValueError):
            continue
        if not tipo or not anio or not mes:
            continue
        periodo = f"{int(anio):04d}-{int(mes):02d}"

        nacional_puntos.setdefault(tipo, {}).setdefault(periodo, []).append(precio)

        if region:
            clave = (tipo, region)
            actual = regional_ultimo.get(clave)
            if not actual or periodo >= actual["periodo"]:
                regional_ultimo[clave] = {"periodo": periodo, "valor": precio}

    nacional = {}
    for tipo, puntos_por_mes in nacional_puntos.items():
        serie = [
            {"periodo": p, "valor": round(sum(vals) / len(vals), 1)}
            for p, vals in sorted(puntos_por_mes.items())
        ]
        nacional[tipo] = serie

    regional = {}
    for (tipo, region), punto in regional_ultimo.items():
        regional.setdefault(tipo, {})[region] = punto

    return {"nacional": nacional, "regional": regional}


def main():
    salida = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "macro": get_mindicador_actual(),
        "historico_macro": get_mindicador_historico(),
        "tasas": get_cmf_historico(),
        "combustibles": get_cne_combustibles(),
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
        print(f"  IPC actualizado desde CMF: {ultimo['valor']}% ({ultimo['fecha']})")

    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print("OK -> datos.json")


if __name__ == "__main__":
    main()
