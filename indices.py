"""
indices.py
Descarga indicadores económicos y financieros de Chile:
  - mindicador.cl (sin API key): valores actuales + históricos mensuales
  - api.cmfchile.cl (requiere CMF_API_KEY): TIP/TMC actuales + históricos
  - api.cne.cl (requiere CNE_EMAIL/CNE_PASSWORD): precios de combustibles líquidos
  - datos.odepa.gob.cl (sin API key): precios mayoristas y al consumidor de alimentos

Escribe todo a datos.json, que luego consume build_site.py.

Uso local:
    export CMF_API_KEY="tu_api_key"
    export CNE_EMAIL="tu_email"
    export CNE_PASSWORD="tu_password"
    python3 indices.py
"""

import gzip
import json
import os
import re
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
N_ANIOS_HISTORICO = 20  # cuántos años hacia atrás traer para los gráficos
                        # (el sitio ofrece rangos de 5/10/20 años — si esto
                        # es menor a 20, los botones de 10 y 20 años no
                        # tienen más datos que mostrar y no "hacen nada")

MACRO_INDICADORES = [
    "dolar", "euro", "uf", "utm", "ipc", "tpm",
    "imacec", "tasa_desempleo", "libra_cobre", "bitcoin",
]

# Indicadores que mindicador.cl publica con frecuencia mensual — es solo
# informativo (guarda el "tipo" en recientes), NO afecta el formato de la
# fecha: mindicador.cl siempre entrega una fecha completa, incluso para
# estos. OJO: la TPM se ve "mensual" conceptualmente, pero mindicador.cl la
# reporta con fecha diaria (repite el mismo valor día a día hasta que el
# Banco Central la cambia), así que va como diaria.
INDICADORES_MENSUALES = {"utm", "ipc", "imacec", "tasa_desempleo"}

# Tipos de operación TIP/TMC más relevantes para "costo del crédito".
# Ver documentación: https://api.cmfchile.cl/documentacion/TIP.html
TIPOS_RELEVANTES = {
    14: "Hipotecario UF (>1 año, sobre 2.000 UF)",
    24: "Hipotecario UF (>1 año, hasta 2.000 UF)",
    9:  "Consumo en pesos (largo plazo, montos altos)",
    35: "Consumo en pesos (largo plazo, montos medios)",
    37: "Consumo en pesos (corto plazo)",
}


def http_get_json(url, timeout=40, reintentos=5, headers=None):
    """GET con reintentos: las APIs públicas a veces se cuelgan un momento,
    y este script corre solo todos los días sin nadie mirando.

    Timeout y reintentos más generosos que antes: detectamos que mindicador.cl
    estaba dando timeout consistentemente (3 corridas seguidas) solo desde
    los runners de GitHub Actions, no desde otros orígenes — probablemente
    un tema de rate-limiting o filtrado hacia IPs de datacenter. Un
    User-Agent más "de navegador" (en vez de uno que se identifica como bot)
    y más margen de tiempo/reintentos con backoff más largo ayudan a
    absorber ese tipo de bloqueo intermitente."""
    ultimo_error = None
    base_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    }
    if headers:
        base_headers.update(headers)
    for intento in range(1, reintentos + 1):
        try:
            req = urllib.request.Request(url, headers=base_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                # Algunas respuestas grandes (ej. combustibles CNE) llegan
                # comprimidas en gzip aunque no lo pidamos explícitamente —
                # urllib no las descomprime solo. Detectamos por el header
                # o por la firma de gzip (\x1f\x8b) como respaldo.
                content_encoding = resp.headers.get("Content-Encoding", "").lower()
                if content_encoding == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode("utf-8"))
        except Exception as e:
            ultimo_error = e
            if intento < reintentos:
                espera = min(10 * intento, 60)
                print(f"  aviso: intento {intento} falló ({e}), reintentando en {espera}s...")
                time.sleep(espera)
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


def get_mindicador_recientes(macro_actual, n_puntos=6):
    """Serie corta 'reciente' de cada indicador — mindicador.cl entrega los
    últimos ~30 valores en el endpoint sin año (a diferencia de /api/{ind}/{año},
    que trae el año completo). Esto es lo que alimenta la fila de valores
    recientes de cada tarjeta en Macro y las flechas ▲▼＝ del Resumen.

    OJO: el endpoint "serie corta" (/api/{indicador}) y el endpoint "actual"
    (/api, usado en get_mindicador_actual) a veces NO están sincronizados —
    ej. Imacec o Bitcoin pueden aparecer más recientes en uno que en el
    otro. Por eso recibimos macro_actual y, si su fecha es más nueva que el
    último punto de la serie corta, lo agregamos — así la tarjeta siempre
    termina en el mismo dato que ya se muestra como "hoy"."""
    print("Descargando valores recientes de mindicador.cl ...")
    resultado = {}
    for indicador in MACRO_INDICADORES:
        try:
            data = http_get_json(f"https://mindicador.cl/api/{indicador}")
        except Exception as e:
            print(f"  aviso: no se pudo traer recientes de {indicador}: {e}")
            continue

        serie = data.get("serie", [])
        es_mensual = indicador in INDICADORES_MENSUALES
        puntos = []
        # La serie viene del más reciente al más antiguo; la damos vuelta
        # para que quede de más antiguo (izquierda) a más reciente (derecha).
        # La etiqueta es siempre la fecha completa (dd/mm/aaaa se formatea
        # después, en build_site.py) — mindicador.cl entrega fecha completa
        # incluso para indicadores mensuales.
        for punto in reversed(serie[:n_puntos]):
            fecha = punto.get("fecha", "")
            valor = punto.get("valor")
            if not fecha or valor is None:
                continue
            puntos.append({"etiqueta": fecha[:10], "valor": valor})

        actual = macro_actual.get(indicador)
        if actual and actual.get("fecha"):
            etiqueta_actual = actual["fecha"][:10]
            if not puntos or puntos[-1]["etiqueta"] != etiqueta_actual:
                puntos.append({"etiqueta": etiqueta_actual, "valor": actual["valor"]})
                puntos = puntos[-n_puntos:]

        if puntos:
            resultado[indicador] = {"tipo": "mensual" if es_mensual else "diario", "puntos": puntos}

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

def get_cne_token(reintentos=4):
    """La API de la CNE no usa API key fija: hay que loguearse con
    email/password (POST /api/login) y usar el token que devuelve como
    Bearer en cada request. Lo hacemos una vez por corrida.

    La API de CNE aplica rate-limit (429) si se llama muy seguido — pasa
    fácil si se corre el workflow manualmente varias veces en poco rato.
    Por eso reintentamos con espera creciente antes de rendirnos."""
    if not (CNE_EMAIL and CNE_PASSWORD):
        return None

    print("Autenticando con API CNE ...")
    body = urllib.parse.urlencode({"email": CNE_EMAIL, "password": CNE_PASSWORD}).encode("utf-8")

    ultimo_error = None
    for intento in range(1, reintentos + 1):
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
        except urllib.error.HTTPError as e:
            ultimo_error = e
            if e.code == 429 and intento < reintentos:
                espera = 20 * intento  # 20s, 40s, 60s...
                print(f"  aviso: CNE devolvió 429 (rate limit), reintento {intento} en {espera}s...")
                time.sleep(espera)
                continue
            print(f"  aviso: no se pudo autenticar con CNE: {e}")
            return None
        except Exception as e:
            ultimo_error = e
            print(f"  aviso: no se pudo autenticar con CNE: {e}")
            return None

    print(f"  aviso: no se pudo autenticar con CNE tras {reintentos} intentos: {ultimo_error}")
    return None


# Tipos de combustible que nos interesa mostrar, y cómo agrupar las
# variantes de autoservicio ("A93" = 93 autoservicio) con su tipo base —
# para los promedios no distinguimos asistido vs. autoservicio.
# (Dejamos fuera GLP/GNC: la sección se enfoca en bencina/diésel/kerosene.)
CNE_TIPO_BASE = {
    "93": "93", "A93": "93",
    "95": "95", "A95": "95",
    "97": "97", "A97": "97",
    "KE": "KE", "AKE": "KE",
    "DI": "DI", "ADI": "DI",
}


def get_cne_combustibles():
    """Precios de combustibles HOY, calculados a partir del precio vigente
    de cada estación de servicio (/api/v4/estaciones): promedio nacional
    por tipo, y promedio por tipo y región.

    A diferencia del endpoint de Energía Abierta (que solo tenía datos
    hasta mediados de 2025), este trae el precio que cada distribuidor
    reportó más recientemente por estación — el más cercano a "cuánto
    cuesta la bencina hoy" que ofrece la API de la CNE.

    Devuelve:
      - "nacional": {tipo_base: {"promedio": n, "n_estaciones": n, "fecha": "YYYY-MM-DD"}}
      - "regional": {nombre_region: {tipo_base: promedio}}
    """
    token = get_cne_token()
    if not token:
        print("AVISO: no hay CNE_EMAIL/CNE_PASSWORD (o falló el login), se omiten combustibles.")
        return {"nacional": {}, "regional": {}}

    print("Descargando precios de combustibles (estaciones CNE) ...")
    try:
        estaciones = http_get_json(
            "https://api.cne.cl/api/v4/estaciones",
            headers={"Authorization": f"Bearer {token}"},
        )
    except Exception as e:
        print(f"  aviso: no se pudo traer estaciones CNE: {e}")
        return {"nacional": {}, "regional": {}}

    precios_por_tipo = {}            # tipo_base -> [precios]
    precios_por_region = {}          # (region, tipo_base) -> [precios]
    fecha_reciente = {}              # tipo_base -> "YYYY-MM-DD" más reciente visto

    for est in estaciones:
        if est.get("en_mantenimiento"):
            continue
        region = (est.get("ubicacion") or {}).get("nombre_region")
        for tipo, info in (est.get("precios") or {}).items():
            base = CNE_TIPO_BASE.get(tipo)
            if not base or not isinstance(info, dict):
                continue
            try:
                precio = float(str(info.get("precio", "")).replace(",", "."))
            except (TypeError, ValueError):
                continue
            if precio <= 0:
                continue

            precios_por_tipo.setdefault(base, []).append(precio)
            if region:
                precios_por_region.setdefault((region, base), []).append(precio)

            fecha = info.get("fecha_actualizacion", "")
            if fecha and fecha > fecha_reciente.get(base, ""):
                fecha_reciente[base] = fecha

    if not precios_por_tipo:
        print("  aviso: la API CNE no devolvió precios utilizables.")

    nacional = {}
    for base, precios in precios_por_tipo.items():
        nacional[base] = {
            "promedio": round(sum(precios) / len(precios)),
            "n_estaciones": len(precios),
            "fecha": fecha_reciente.get(base, ""),
        }

    regional = {}
    for (region, base), precios in precios_por_region.items():
        regional.setdefault(region, {})[base] = round(sum(precios) / len(precios))

    return {"nacional": nacional, "regional": regional}


# ---------------------------------------------------------------------------
# datos.odepa.gob.cl (precios mayoristas y al consumidor de alimentos)
# ---------------------------------------------------------------------------
# Portal CKAN público, sin API key. ODEPA publica un recurso (CSV/datastore)
# nuevo cada año, así que no podemos hardcodear el resource_id: lo resolvemos
# por nombre en cada corrida vía package_show.

ODEPA_MAYORISTA_PRODUCTOS = ["Palta", "Tomate", "Papa", "Cebolla", "Plátano", "Manzana"]

ODEPA_CONSUMIDOR_ITEMS = [
    ("Pan", "Marraqueta"),
    ("Carne bovina", "Asado Carnicero"),
    ("Carne de Cerdo - Ave - Cordero", "Pollo Entero"),
    ("Lácteos - Huevos - Margarinas", "Huevo blanco - Extra"),
    ("Lácteos - Huevos - Margarinas", "Leche Fluida Entera"),
]


def _normalizar_precio_odepa(precio, unidad):
    """ODEPA reporta el precio por caja/malla/bandeja/docena — no siempre
    por kilo o unidad — y el tamaño del envase varía por producto y mercado.
    Promediar el precio "en bruto" mezclaría cajas de 10 kilos con cajas de
    20, así que normalizamos todo a $/kilo, $/litro o $/unidad según lo que
    indique el texto de la unidad de comercialización.

    Devuelve (precio_normalizado, "kg"|"L"|"un") o (None, None) si el texto
    no trae una cantidad reconocible (ej. "sin especificar")."""
    u = (unidad or "").lower()
    if u.startswith("$/kilo"):
        return precio, "kg"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*litro", u)
    if m:
        factor = float(m.group(1).replace(",", "."))
        return (precio / factor if factor else None), "L"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*kilos?", u)
    if m:
        factor = float(m.group(1).replace(",", "."))
        return (precio / factor if factor else None), "kg"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*unidad", u)
    if m:
        factor = float(m.group(1).replace(",", "."))
        return (precio / factor if factor else None), "un"
    return None, None


def odepa_resource_id(dataset_slug, anio):
    try:
        data = http_get_json(f"https://datos.odepa.gob.cl/api/3/action/package_show?id={dataset_slug}")
    except Exception as e:
        print(f"  aviso: no se pudo consultar el dataset ODEPA '{dataset_slug}': {e}")
        return None
    for r in data.get("result", {}).get("resources", []):
        if str(anio) in (r.get("name") or ""):
            return r.get("id")
    return None


def odepa_datastore_search(resource_id, filters=None, sort=None, limit=500):
    params = {"resource_id": resource_id, "limit": str(limit)}
    if filters:
        params["filters"] = json.dumps(filters, ensure_ascii=False)
    if sort:
        params["sort"] = sort
    qs = urllib.parse.urlencode(params)
    data = http_get_json(f"https://datos.odepa.gob.cl/api/3/action/datastore_search?{qs}")
    return data.get("result", {}).get("records", [])


def get_odepa_mayoristas():
    """Precio mayorista ($/kilo, normalizado) del día hábil más reciente
    para una canasta chica de frutas/hortalizas.

    Devuelve:
      - "nacional": {producto: {"promedio": n, "fecha": "YYYY-MM-DD"}}
      - "regional": {region: {producto: promedio}}  (solo regiones con mercado mayorista)
    """
    anio = datetime.now().year
    resource_id = odepa_resource_id("precios-mayoristas-de-frutas-y-hortalizas", anio)
    if not resource_id:
        print("AVISO: no se encontró el recurso ODEPA de precios mayoristas para este año.")
        return {"nacional": {}, "regional": {}}

    print("Descargando precios mayoristas ODEPA ...")
    nacional = {}
    regional = {}
    for producto in ODEPA_MAYORISTA_PRODUCTOS:
        try:
            filas = odepa_datastore_search(
                resource_id, filters={"Producto": producto}, sort='"Fecha" desc', limit=500,
            )
        except Exception as e:
            print(f"  aviso: no se pudo traer '{producto}' (ODEPA mayorista): {e}")
            continue
        if not filas:
            continue

        fecha_reciente = max((f.get("Fecha") for f in filas if f.get("Fecha")), default=None)
        if not fecha_reciente:
            continue

        precios_nacional = []
        precios_region = {}
        for f in filas:
            if f.get("Fecha") != fecha_reciente:
                continue
            try:
                precio_bruto = float(str(f.get("Precio promedio", "")).replace(",", "."))
            except (TypeError, ValueError):
                continue
            precio, _unidad = _normalizar_precio_odepa(precio_bruto, f.get("Unidad de comercializacion"))
            if precio is None or precio <= 0:
                continue
            precios_nacional.append(precio)
            region = f.get("Region")
            if region:
                precios_region.setdefault(region, []).append(precio)

        if precios_nacional:
            nacional[producto] = {
                "promedio": round(sum(precios_nacional) / len(precios_nacional)),
                "fecha": fecha_reciente,
            }
        for region, precios in precios_region.items():
            regional.setdefault(region, {})[producto] = round(sum(precios) / len(precios))

    if not nacional:
        print("  aviso: ODEPA no devolvió precios mayoristas utilizables.")

    return {"nacional": nacional, "regional": regional}


def get_odepa_consumidor():
    """Precio al consumidor ($/kilo, $/litro o $/unidad según corresponda,
    normalizado) de la semana más reciente, para una canasta chica: pan,
    carne, pollo, huevos y leche.

    Devuelve:
      - "nacional": {producto: {"promedio": n, "fecha": "YYYY-MM-DD", "unidad": "kg"|"L"|"un"}}
      - "regional": {region: {producto: promedio}}  (mismas 9 regiones que mayoristas)
    """
    anio = datetime.now().year
    resource_id = odepa_resource_id("precios-consumidor", anio)
    if not resource_id:
        print("AVISO: no se encontró el recurso ODEPA de precios consumidor para este año.")
        return {"nacional": {}, "regional": {}}

    print("Descargando precios al consumidor ODEPA ...")
    nacional = {}
    regional = {}
    for grupo, producto in ODEPA_CONSUMIDOR_ITEMS:
        try:
            filas = odepa_datastore_search(
                resource_id,
                filters={"Grupo": grupo, "Producto": producto},
                sort='"Fecha termino" desc',
                limit=500,
            )
        except Exception as e:
            print(f"  aviso: no se pudo traer '{producto}' (ODEPA consumidor): {e}")
            continue
        if not filas:
            continue

        fecha_reciente = max((f.get("Fecha termino") for f in filas if f.get("Fecha termino")), default=None)
        if not fecha_reciente:
            continue

        precios_nacional = []
        precios_region = {}
        unidad_norm = None
        for f in filas:
            if f.get("Fecha termino") != fecha_reciente:
                continue
            try:
                precio_bruto = float(str(f.get("Precio promedio", "")).replace(",", "."))
            except (TypeError, ValueError):
                continue
            precio, unidad = _normalizar_precio_odepa(precio_bruto, f.get("Unidad"))
            if precio is None or precio <= 0:
                continue
            precios_nacional.append(precio)
            unidad_norm = unidad_norm or unidad
            region = f.get("Region")
            if region:
                precios_region.setdefault(region, []).append(precio)

        if precios_nacional:
            nacional[producto] = {
                "promedio": round(sum(precios_nacional) / len(precios_nacional)),
                "fecha": fecha_reciente,
                "unidad": unidad_norm or "kg",
            }
        for region, precios in precios_region.items():
            regional.setdefault(region, {})[producto] = round(sum(precios) / len(precios))

    if not nacional:
        print("  aviso: ODEPA no devolvió precios al consumidor utilizables.")

    return {"nacional": nacional, "regional": regional}


# ---------------------------------------------------------------------------
# ODEPA — tendencia mensual (últimos ~9 meses) de cada producto de la canasta
# ---------------------------------------------------------------------------
# ODEPA sí tiene trazabilidad real (a diferencia de la CNE), así que acá
# podemos mostrar variación real mes a mes: el precio del último día (o
# última semana, para consumidor) CON DATOS de cada uno de los últimos
# meses — no un promedio del mes completo, sino el corte más reciente de
# cada mes, para que la serie termine en el mismo valor que ya se muestra
# como "hoy" en los KPIs de arriba.

ODEPA_MESES_TENDENCIA = 9


def _ultimos_n_meses(n):
    """Los últimos n meses (incluido el actual), como 'YYYY-MM', ordenados
    del más antiguo al más reciente."""
    hoy = datetime.now()
    meses = []
    anio, mes = hoy.year, hoy.month
    for _ in range(n):
        meses.append(f"{anio:04d}-{mes:02d}")
        mes -= 1
        if mes == 0:
            mes = 12
            anio -= 1
    return list(reversed(meses))


def get_odepa_mayoristas_tendencia():
    """Serie mensual (últimos ODEPA_MESES_TENDENCIA meses) del precio
    mayorista nacional normalizado, un punto por mes = el último día hábil
    con datos de ese mes."""
    meses = _ultimos_n_meses(ODEPA_MESES_TENDENCIA)
    anios = sorted({int(m.split("-")[0]) for m in meses})
    resources = {a: odepa_resource_id("precios-mayoristas-de-frutas-y-hortalizas", a) for a in anios}

    print(f"Descargando tendencia mayorista ODEPA ({len(meses)} meses) ...")
    tendencia = {}
    for producto in ODEPA_MAYORISTA_PRODUCTOS:
        filas_totales = []
        for anio in anios:
            rid = resources.get(anio)
            if not rid:
                continue
            try:
                filas_totales.extend(
                    odepa_datastore_search(rid, filters={"Producto": producto}, sort='"Fecha" desc', limit=20000)
                )
            except Exception as e:
                print(f"  aviso: no se pudo traer histórico de '{producto}' ({anio}) ODEPA: {e}")

        ultima_fecha_por_mes = {}
        for f in filas_totales:
            fecha = f.get("Fecha", "")
            mes = fecha[:7]
            if mes not in meses:
                continue
            if fecha > ultima_fecha_por_mes.get(mes, ""):
                ultima_fecha_por_mes[mes] = fecha

        serie = []
        for mes in meses:
            fecha_corte = ultima_fecha_por_mes.get(mes)
            if not fecha_corte:
                continue
            precios = []
            for f in filas_totales:
                if f.get("Fecha") != fecha_corte:
                    continue
                try:
                    precio_bruto = float(str(f.get("Precio promedio", "")).replace(",", "."))
                except (TypeError, ValueError):
                    continue
                precio, _u = _normalizar_precio_odepa(precio_bruto, f.get("Unidad de comercializacion"))
                if precio is not None and precio > 0:
                    precios.append(precio)
            if precios:
                serie.append({"periodo": mes, "fecha": fecha_corte, "valor": round(sum(precios) / len(precios))})

        if serie:
            tendencia[producto] = serie

    return tendencia


def get_odepa_consumidor_tendencia():
    """Igual que get_odepa_mayoristas_tendencia, pero para la canasta de
    consumidor: un punto por mes = la última semana con datos de ese mes."""
    meses = _ultimos_n_meses(ODEPA_MESES_TENDENCIA)
    anios = sorted({int(m.split("-")[0]) for m in meses})
    resources = {a: odepa_resource_id("precios-consumidor", a) for a in anios}

    print(f"Descargando tendencia consumidor ODEPA ({len(meses)} meses) ...")
    tendencia = {}
    for grupo, producto in ODEPA_CONSUMIDOR_ITEMS:
        filas_totales = []
        for anio in anios:
            rid = resources.get(anio)
            if not rid:
                continue
            try:
                filas_totales.extend(
                    odepa_datastore_search(
                        rid, filters={"Grupo": grupo, "Producto": producto},
                        sort='"Fecha termino" desc', limit=5000,
                    )
                )
            except Exception as e:
                print(f"  aviso: no se pudo traer histórico de '{producto}' ({anio}, consumidor) ODEPA: {e}")

        ultima_fecha_por_mes = {}
        for f in filas_totales:
            fecha = f.get("Fecha termino", "")
            mes = fecha[:7]
            if mes not in meses:
                continue
            if fecha > ultima_fecha_por_mes.get(mes, ""):
                ultima_fecha_por_mes[mes] = fecha

        serie = []
        for mes in meses:
            fecha_corte = ultima_fecha_por_mes.get(mes)
            if not fecha_corte:
                continue
            precios = []
            for f in filas_totales:
                if f.get("Fecha termino") != fecha_corte:
                    continue
                try:
                    precio_bruto = float(str(f.get("Precio promedio", "")).replace(",", "."))
                except (TypeError, ValueError):
                    continue
                precio, _u = _normalizar_precio_odepa(precio_bruto, f.get("Unidad"))
                if precio is not None and precio > 0:
                    precios.append(precio)
            if precios:
                serie.append({"periodo": mes, "fecha": fecha_corte, "valor": round(sum(precios) / len(precios))})

        if serie:
            tendencia[producto] = serie

    return tendencia


# ---------------------------------------------------------------------------
# Detector de anomalías — un dato destacado por categoría (Macro, Crédito,
# Alimentos), calculado sobre datos que ya descargamos, sin llamadas extra.
#
# Criterio: no destacamos "el cambio más grande en términos absolutos" (eso
# casi siempre sería Bitcoin en Macro, porque es naturalmente volátil), sino
# el cambio más INUSUAL para CADA indicador según su propia historia — un
# z-score del último cambio % contra la volatilidad de sus cambios previos.
# Así un movimiento chico en algo que normalmente no se mueve (ej. la UF)
# puede ganarle a un movimiento grande en algo que siempre es volátil.
# ---------------------------------------------------------------------------

def _anomalia_por_zscore(valores_cronologicos):
    """valores_cronologicos: lista de valores numéricos, del más antiguo al
    más reciente. Devuelve {"cambio_pct": n, "zscore": n} del último cambio,
    o None si no hay suficientes puntos para una comparación confiable."""
    valores = [v for v in valores_cronologicos if v is not None]
    if len(valores) < 5:
        return None

    cambios_pct = []
    for i in range(1, len(valores)):
        anterior = valores[i - 1]
        if not anterior:
            continue
        cambios_pct.append((valores[i] - anterior) / abs(anterior) * 100)

    if len(cambios_pct) < 4:
        return None

    ultimo = cambios_pct[-1]
    historicos = cambios_pct[:-1]
    media = sum(historicos) / len(historicos)
    varianza = sum((c - media) ** 2 for c in historicos) / len(historicos)
    desviacion = varianza ** 0.5
    if desviacion == 0:
        return None

    return {"cambio_pct": round(ultimo, 2), "zscore": round((ultimo - media) / desviacion, 2)}


def get_anomalia_macro(historico_macro):
    candidatos = []
    for indicador, serie in historico_macro.items():
        if not serie:
            continue
        resultado = _anomalia_por_zscore([p["valor"] for p in serie])
        if resultado:
            candidatos.append({
                "clave": indicador,
                "periodo": serie[-1]["periodo"],
                "valor_actual": serie[-1]["valor"],
                **resultado,
            })
    if not candidatos:
        return None
    return max(candidatos, key=lambda c: abs(c["zscore"]))


def get_anomalia_credito(tasas):
    candidatos = []
    for recurso in ("tip", "tmc"):
        for tipo, info in tasas.get(recurso, {}).items():
            serie = info.get("serie", [])
            if not serie:
                continue
            resultado = _anomalia_por_zscore([p["valor"] for p in serie])
            if resultado:
                candidatos.append({
                    "recurso": recurso,
                    "tipo": tipo,
                    "etiqueta": info.get("etiqueta", tipo),
                    "fecha": serie[-1]["fecha"],
                    "valor_actual": serie[-1]["valor"],
                    **resultado,
                })
    if not candidatos:
        return None
    return max(candidatos, key=lambda c: abs(c["zscore"]))


def get_anomalia_alimentos(tendencia_mayoristas, tendencia_consumidor):
    candidatos = []
    for producto, serie in tendencia_mayoristas.items():
        if not serie:
            continue
        resultado = _anomalia_por_zscore([p["valor"] for p in serie])
        if resultado:
            candidatos.append({
                "tipo_canasta": "mayorista",
                "producto": producto,
                "fecha": serie[-1]["fecha"],
                "valor_actual": serie[-1]["valor"],
                **resultado,
            })
    for producto, serie in tendencia_consumidor.items():
        if not serie:
            continue
        resultado = _anomalia_por_zscore([p["valor"] for p in serie])
        if resultado:
            candidatos.append({
                "tipo_canasta": "consumidor",
                "producto": producto,
                "fecha": serie[-1]["fecha"],
                "valor_actual": serie[-1]["valor"],
                **resultado,
            })
    if not candidatos:
        return None
    return max(candidatos, key=lambda c: abs(c["zscore"]))


# ---------------------------------------------------------------------------
# Índice de costo de vida Heuristika — pensado para una familia promedio
# chilena (2 padres + 1 hijo, ingreso ~$1.500.000/mes, que calza casi exacto
# con el hogar promedio nacional según la IX Encuesta de Presupuestos
# Familiares del INE: ingreso $1.413.349, gasto $1.451.782). Combina 4
# componentes ponderados por su peso real en el gasto de ese hogar:
#   - Alimentos (consumidor) 62% — lo que más pesa en el gasto mensual real.
#   - Bencina 93 10% — combustible que efectivamente compra esa familia
#     (no el peso agregado de "transporte" del IPC, que mezcla hogares con
#     y sin auto).
#   - UF 16% — presión sobre créditos hipotecarios/arriendos indexados.
#   - Dólar 12% — presión sobre precios de bienes importados.
#
# Arranca en 100 el día que se activó esta función (INDICE_COSTO_VIDA_BASE),
# sin historia retroactiva. La base queda fija en el código (no solo en
# datos.json) para que nunca se pierda aunque datos.json se resetee o un
# commit falle — ver conversación de diseño del 14-jul-2026.
# ---------------------------------------------------------------------------

INDICE_COSTO_VIDA_BASE = {
    "fecha": "2026-07-14",
    "dolar": 928.84,
    "uf": 40844.79,
    "bencina_93": 1413,
    "alimentos_consumidor": {
        "Marraqueta": 2293,
        "Asado Carnicero": 10516,
        "Pollo Entero": 3824,
        "Huevo blanco - Extra": 220,
        "Leche Fluida Entera": 1205,
    },
}

INDICE_COSTO_VIDA_PESOS = {"alimentos": 0.62, "bencina": 0.10, "uf": 0.16, "dolar": 0.12}


def get_indice_costo_vida(macro, combustibles, alimentos):
    base = INDICE_COSTO_VIDA_BASE
    pesos = INDICE_COSTO_VIDA_PESOS

    dolar_hoy = macro.get("dolar", {}).get("valor")
    uf_hoy = macro.get("uf", {}).get("valor")
    bencina_hoy = combustibles.get("nacional", {}).get("93", {}).get("promedio")
    consumidor_hoy = alimentos.get("consumidor", {}).get("nacional", {})

    # Si falta algún dato hoy (ej. la CNE no respondió), tratamos ese
    # componente como "sin cambio" en vez de romper el cálculo del índice.
    cambio_dolar = (dolar_hoy - base["dolar"]) / base["dolar"] * 100 if dolar_hoy else 0.0
    cambio_uf = (uf_hoy - base["uf"]) / base["uf"] * 100 if uf_hoy else 0.0
    cambio_bencina = (
        (bencina_hoy - base["bencina_93"]) / base["bencina_93"] * 100 if bencina_hoy else 0.0
    )

    cambios_alimentos = []
    for producto, valor_base in base["alimentos_consumidor"].items():
        info_hoy = consumidor_hoy.get(producto)
        if info_hoy and valor_base:
            cambios_alimentos.append((info_hoy["promedio"] - valor_base) / valor_base * 100)
    cambio_alimentos = sum(cambios_alimentos) / len(cambios_alimentos) if cambios_alimentos else 0.0

    impacto = (
        pesos["alimentos"] * cambio_alimentos
        + pesos["bencina"] * cambio_bencina
        + pesos["uf"] * cambio_uf
        + pesos["dolar"] * cambio_dolar
    )
    valor_indice = round(100 + impacto, 2)
    hoy = datetime.now().strftime("%Y-%m-%d")

    # Recuperamos el historial de corridas anteriores desde el datos.json que
    # ya está commiteado en el repo. Si no existe o viene vacío, no importa:
    # el valor de hoy sigue siendo correcto porque se calculó contra
    # INDICE_COSTO_VIDA_BASE (fijo en el código) — solo se pierde la curva
    # visual de días anteriores, no la precisión del índice.
    historial = []
    try:
        with open("datos.json", "r", encoding="utf-8") as f:
            anterior = json.load(f)
        historial = anterior.get("indice_costo_vida", {}).get("historial", [])
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    if historial and historial[-1]["fecha"] == hoy:
        historial[-1] = {"fecha": hoy, "valor": valor_indice}
    else:
        historial.append({"fecha": hoy, "valor": valor_indice})

    return {
        "base": base,
        "pesos": pesos,
        "valor": valor_indice,
        "fecha": hoy,
        "componentes": {
            "alimentos": round(cambio_alimentos, 2),
            "bencina": round(cambio_bencina, 2),
            "uf": round(cambio_uf, 2),
            "dolar": round(cambio_dolar, 2),
        },
        "historial": historial,
    }


def main():
    macro_actual = get_mindicador_actual()
    salida = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "macro": macro_actual,
        "historico_macro": get_mindicador_historico(),
        "recientes": get_mindicador_recientes(macro_actual),
        "tasas": get_cmf_historico(),
        "combustibles": get_cne_combustibles(),
        "alimentos": {
            "mayoristas": get_odepa_mayoristas(),
            "consumidor": get_odepa_consumidor(),
            "tendencia_mayoristas": get_odepa_mayoristas_tendencia(),
            "tendencia_consumidor": get_odepa_consumidor_tendencia(),
        },
    }

    # El IPC de mindicador.cl suele atrasarse (a veces varios meses); si CMF
    # tiene datos más recientes los usamos — tanto para el valor "hoy" como
    # para la tarjeta de recientes, para que ambos queden consistentes y no
    # se vea la tarjeta pegada en una fecha vieja mientras el KPI de arriba
    # ya muestra el dato nuevo.
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
        puntos_ipc_cmf = [
            {"etiqueta": p["fecha"][:10], "valor": p["valor"]} for p in ipc_cmf[-6:]
        ]
        salida["recientes"]["ipc"] = {"tipo": "mensual", "puntos": puntos_ipc_cmf}
        print(f"  IPC actualizado desde CMF: {ultimo['valor']}% ({ultimo['fecha']})")

    print("Calculando anomalías (Macro, Crédito, Alimentos) ...")
    salida["anomalias"] = {
        "macro": get_anomalia_macro(salida["historico_macro"]),
        "credito": get_anomalia_credito(salida["tasas"]),
        "alimentos": get_anomalia_alimentos(
            salida["alimentos"]["tendencia_mayoristas"],
            salida["alimentos"]["tendencia_consumidor"],
        ),
    }

    print("Calculando índice de costo de vida Heuristika ...")
    salida["indice_costo_vida"] = get_indice_costo_vida(
        salida["macro"], salida["combustibles"], salida["alimentos"]
    )
    print(f"  Índice hoy: {salida['indice_costo_vida']['valor']}")

    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print("OK -> datos.json")


if __name__ == "__main__":
    main()
