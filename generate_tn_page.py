#!/usr/bin/env python3
"""
Génère la page HTML des Tn (températures minimales nocturnes) pour le réseau
de stations "trous à froid de France".

Sources gérées automatiquement :
  - Infoclimat (scraping HTML de la page temps réel)
  - Météoravanel (scraping HTML)
  - Ecowitt (API officielle /device/history)
  - Datacake (API officielle REST historic_data, par device + token)

Secrets attendus en variables d'environnement (voir README.md) :
  - ECOWITT_APPLICATION_KEY, ECOWITT_API_KEY
  - DATACAKE_TOKENS_JSON  (JSON: {"<device_id>": "<token>", ...})

Sortie : docs/index.html (prêt pour GitHub Pages)
"""

import os
import re
import json
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

PARIS = ZoneInfo("Europe/Paris")
UTC = timezone.utc

# ----------------------------------------------------------------------------
# 1. Config des stations
# ----------------------------------------------------------------------------

# Fenêtre "nuit écoulée" : de 18h la veille à l'heure d'exécution (typiquement 9h)
def night_window():
    now_paris = datetime.now(PARIS)
    start = (now_paris - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    end = now_paris
    return start, end


INFOCLIMAT_STATIONS = [
    {"name": "St Christol d'Albion", "meta": "Vaucluse (84) · 824 m",
     "url": "https://www.infoclimat.fr/observations-meteo/temps-reel/saint-christol/STATIC0257.html"},
    {"name": "Lachapelle-Graillouse – Moulin de Courbet", "meta": "Ardèche (07) · 1134 m",
     "url": "https://www.infoclimat.fr/observations-meteo/temps-reel/lachapelle-graillouse-moulin-de-courbet/STATIC0407.html"},
    {"name": "Combe de l'Oscence", "meta": "La Chapelle-en-Vercors (26) · 975 m",
     "url": "https://www.infoclimat.fr/observations-meteo/temps-reel/la-chapelle-en-vercors-combe-de-l-oscence/000UF.html"},
    {"name": "Combe de Darbounouse", "meta": "La Chapelle-en-Vercors (26) · 1282 m",
     "url": "https://www.infoclimat.fr/observations-meteo/temps-reel/la-chapelle-en-vercors-combe-de-darbounouse/STATIC0213.html"},
    {"name": "Doline de Solaison", "meta": "Brizon (74) · 1479 m",
     "url": "https://www.infoclimat.fr/observations-meteo/temps-reel/brizon-doline-de-solaison/STATIC0305.html"},
    {"name": "Reculfoz", "meta": "Doubs (25) · 1010 m",
     "url": "https://www.infoclimat.fr/observations-meteo/temps-reel/reculfoz-combe/STATIC0015.html"},
]

METEORAVANEL_STATIONS = [
    {"name": "Gréolières les Neiges", "meta": "Doline, 06 · 1388 m",
     "url": "https://www.meteoravanel.it/stationID282C0240FD84/Station_ID282C0240FD84_Greolieres_les_Neiges.php"},
]

# device_id Datacake = l'UUID qu'on trouve dans l'URL app.datacake.de/pd/<uuid>
DATACAKE_STATIONS = [
    {"name": "Beuil Cumba Clava", "meta": "", "device_id": "4141f1e8-3a9a-4503-a84d-eb6999f53171"},
    {"name": "Issanlas", "meta": "Plateau ardéchois (07) · 1180 m", "device_id": "c21a6a3f-174d-46ff-8237-c61cedb15b45"},
    {"name": "Causse Méjean – Doline du Fraisse", "meta": "48", "device_id": "6158e91a-e71b-4280-be9e-d6842768c467"},
    {"name": "Tignes – Pramécou", "meta": "", "device_id": "d75df345-b0f9-4da5-bed2-74153c0ffd15"},
    {"name": "Le Dévoluy – Vallon d'Ane", "meta": "", "device_id": "49d8e76b-d3b1-4f96-9ce6-b6602bcf8036"},
    {"name": "Chaud Clapier", "meta": "", "device_id": "d4b23fdc-eca0-4658-9d0b-66829a0b9890"},
    {"name": "Le Praz de Lys – Lac de Roy", "meta": "", "device_id": "08d595dc-2848-4b91-ab7c-2295f3df85c6"},
    {"name": "La Pesse – Le Cernétrou", "meta": "", "device_id": "1e79ad96-29b0-4c76-a7ed-7be780dac89c"},
]

ECOWITT_STATIONS = [
    {"name": "Lussan La Lèque", "meta": "", "mac": os.environ.get("ECOWITT_MAC", "")},
]


# ----------------------------------------------------------------------------
# 2. Récupération des Tn par source
# ----------------------------------------------------------------------------

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def fetch_infoclimat_tn(url: str):
    """Extrait la 'Température minimale' du jour depuis la page temps réel Infoclimat."""
    try:
        headers = dict(BROWSER_HEADERS)
        headers["Referer"] = "https://www.infoclimat.fr/"
        session = requests.Session()
        r = session.get(url, timeout=20, headers=headers)
        r.raise_for_status()
        html = r.text
        # Le bloc "Température minimale" est suivi d'une valeur (avec ou sans balises HTML autour)
        m = re.search(r"Temp[ée]rature minimale.{0,600}?(-?\d+(?:[.,]\d+)?)\s*°C", html, re.S)
        if m:
            return float(m.group(1).replace(",", ".")), "ok"
        return None, f"valeur introuvable sur la page (longueur html={len(html)}, statut={r.status_code})"
    except requests.exceptions.HTTPError as e:
        return None, f"erreur HTTP: {e} — statut {e.response.status_code if e.response is not None else '?'}"
    except Exception as e:
        return None, f"erreur: {e}"


def fetch_meteoravanel_tn(url: str):
    """Extrait 'Température minimale aujourd'hui: X.X°C' depuis la page Météoravanel."""
    try:
        r = requests.get(url, timeout=20, headers=BROWSER_HEADERS)
        r.raise_for_status()
        html = r.text
        m = re.search(
            r"Temp[ée]rature minimale.{0,60}?[Aa]ujourd.{0,3}hui.{0,60}?(-?\d+(?:[.,]\d+)?)\s*°C",
            html, re.S,
        )
        if m:
            return float(m.group(1).replace(",", ".")), "ok"
        return None, f"valeur introuvable sur la page (longueur html={len(html)}, statut={r.status_code})"
    except requests.exceptions.HTTPError as e:
        return None, f"erreur HTTP: {e} — statut {e.response.status_code if e.response is not None else '?'}"
    except Exception as e:
        return None, f"erreur: {e}"


def fetch_ecowitt_tn(mac: str, app_key: str, api_key: str):
    """Interroge l'API Ecowitt /device/history et calcule le minimum de température."""
    if not (mac and app_key and api_key):
        return None, "clés/mac Ecowitt manquants"
    start, end = night_window()
    params = {
        "application_key": app_key,
        "api_key": api_key,
        "mac": mac,
        "start_date": start.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "end_date": end.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "cycle_type": "5min",
        "call_back": "outdoor",
        "temp_unitid": 1,  # 1 = Celsius
    }
    try:
        r = requests.get("https://api.ecowitt.net/api/v3/device/history", params=params, timeout=20)
        data = r.json()
        if data.get("code") != 0:
            return None, f"API erreur: {data.get('msg')}"
        temp_series = (
            data.get("data", {})
            .get("outdoor", {})
            .get("temperature", {})
            .get("list", {})
        )
        values = [float(v) for v in temp_series.values() if v not in (None, "")]
        if not values:
            return None, "aucune donnée sur la fenêtre nocturne"
        return min(values), "ok"
    except Exception as e:
        return None, f"erreur: {e}"


def fetch_datacake_field_name(device_id: str, token: str):
    """Trouve le nom du champ température actif sur le device (ex: TEMPERATURE, TEMPC_SHT...)."""
    query = f'''
    query {{
      device(deviceId: "{device_id}") {{
        currentMeasurements(allActiveFields: true) {{
          value
          field {{ fieldName verboseFieldName }}
        }}
      }}
    }}
    '''
    try:
        r = requests.post(
            "https://api.datacake.co/graphql/",
            json={"query": query},
            headers={"Authorization": f"Token {token}", "Content-Type": "application/json"},
            timeout=20,
        )
        data = r.json()
        measurements = data.get("data", {}).get("device", {}).get("currentMeasurements", []) or []
        for m in measurements:
            fname = m["field"]["fieldName"]
            if "TEMP" in fname.upper():
                return fname
    except Exception:
        pass
    return "TEMPERATURE"  # valeur par défaut la plus courante


def fetch_datacake_tn(device_id: str, token: str):
    """Récupère l'historique du champ température et calcule le minimum sur la nuit."""
    if not token:
        return None, "token Datacake manquant"
    field = fetch_datacake_field_name(device_id, token)
    start, end = night_window()
    url = (
        f"https://api.datacake.co/v1/devices/{device_id}/historic_data/"
        f"?fields={field}&resolution=5m"
        f"&timeframe_start={start.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%S')}Z"
        f"&timeframe_end={end.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%S')}Z"
    )
    try:
        r = requests.get(url, headers={"Authorization": f"Token {token}"}, timeout=20)
        try:
            data = r.json()
        except ValueError:
            return None, f"réponse non-JSON (statut {r.status_code}): {r.text[:200]!r}"

        if isinstance(data, dict) and ("detail" in data or "error" in data):
            return None, f"API erreur (statut {r.status_code}): {data}"

        # La forme exacte de la réponse peut varier ; on cherche toute valeur numérique,
        # y compris quand l'API la renvoie sous forme de chaîne ("12.3").
        values = []

        def maybe_number(v):
            if isinstance(v, bool):
                return None
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                try:
                    return float(v)
                except ValueError:
                    return None
            return None

        def collect(obj, key_hint=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    # on ignore les champs qui ressemblent à des identifiants/temps, pas des mesures
                    if k.lower() in ("id", "timestamp", "time", "date"):
                        continue
                    collect(v, k)
            elif isinstance(obj, list):
                for v in obj:
                    collect(v, key_hint)
            else:
                n = maybe_number(obj)
                if n is not None:
                    values.append(n)

        collect(data)
        if not values:
            return None, f"aucune donnée exploitable (statut {r.status_code}, extrait: {str(data)[:200]!r})"
        return min(values), "ok"
    except Exception as e:
        return None, f"erreur: {e}"


# ----------------------------------------------------------------------------
# 3. Génération du HTML
# ----------------------------------------------------------------------------

def tn_bucket_color(tn):
    if tn is None:
        return None
    if tn <= -2:
        return "var(--cold-1)"
    if tn <= 0:
        return "var(--cold-2)"
    if tn <= 5:
        return "var(--mild)"
    if tn <= 10:
        return "var(--warm-1)"
    return "var(--warm-2)"


def render_row(name, meta, src_label, tn, status):
    if tn is None:
        pill = f'<span class="tn-pill na" title="{status}">à saisir</span>'
    else:
        color = tn_bucket_color(tn)
        text_color = "#1a2233" if color == "var(--mild)" else "#0c1420"
        sign = "−" if tn < 0 else ""
        pill = (
            f'<span class="tn-pill" style="background:{color};color:{text_color}">'
            f'{sign}{abs(tn):.1f}°</span>'
        )
    return f"""
      <tr>
        <td>
          <div class="station">{name}</div>
          <div class="meta">{meta}</div>
          <span class="src">{src_label}</span>
        </td>
        <td class="tn-cell">{pill}</td>
      </tr>"""


TEMPLATE_HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tn — Trous à froid de France</title>
<style>
  :root{{
    --bg:#0c1420; --bg-panel:#111d2e; --line:#22334a; --text:#eaf1f8; --muted:#7d92aa;
    --cold-1:#3aa0e0; --cold-2:#4fc3d9; --mild:#e8e2c9; --warm-1:#e0a94f; --warm-2:#d9603a;
    --badge:#1a2942;
  }}
  *{{box-sizing:border-box;}}
  body{{margin:0;background:radial-gradient(ellipse 900px 400px at 15% -10%, #14263d 0%, transparent 60%),var(--bg);
    color:var(--text);font-family:"Segoe UI",system-ui,-apple-system,sans-serif;padding:32px 18px 60px;}}
  .wrap{{max-width:760px;margin:0 auto;}}
  .eyebrow{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;letter-spacing:.14em;
    text-transform:uppercase;color:var(--cold-2);margin:0 0 8px;}}
  h1{{margin:0 0 6px;font-size:28px;font-weight:700;letter-spacing:-0.01em;}}
  .sub{{color:var(--muted);font-size:14px;margin:0;line-height:1.5;}}
  .datebar{{display:flex;justify-content:space-between;align-items:baseline;margin-top:18px;padding-top:14px;
    border-top:1px solid var(--line);font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;color:var(--muted);}}
  table{{width:100%;border-collapse:collapse;margin-top:22px;}}
  thead th{{text-align:left;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
    font-weight:600;padding:0 10px 10px;border-bottom:1px solid var(--line);}}
  thead th.tn-col{{text-align:center;}}
  tbody td{{padding:12px 10px;border-bottom:1px solid var(--line);vertical-align:middle;}}
  tbody tr:hover{{background:rgba(255,255,255,0.02);}}
  .station{{font-weight:600;font-size:14.5px;}}
  .meta{{color:var(--muted);font-size:12px;margin-top:2px;}}
  .src{{display:inline-block;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:10px;letter-spacing:.03em;
    color:var(--muted);background:var(--badge);padding:2px 6px;border-radius:4px;margin-top:5px;}}
  .tn-cell{{text-align:center;}}
  .tn-pill{{display:inline-block;min-width:64px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:17px;
    font-weight:700;padding:6px 10px;border-radius:8px;color:#0c1420;}}
  .tn-pill.na{{background:transparent;border:1px dashed var(--line);color:var(--muted);font-size:12px;
    font-weight:400;font-style:italic;}}
  .legend{{display:flex;gap:14px;flex-wrap:wrap;margin-top:26px;font-size:11px;color:var(--muted);align-items:center;}}
  .legend .chip{{width:12px;height:12px;border-radius:3px;display:inline-block;margin-right:5px;vertical-align:-2px;}}
  footer{{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px;line-height:1.6;}}
  footer b{{color:var(--text);}}
  code{{background:var(--badge);padding:1px 5px;border-radius:4px;font-size:11.5px;}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="eyebrow">Réseau · Trous à froid de France</p>
    <h1>Tn de la nuit écoulée</h1>
    <p class="sub">Températures minimales relevées cette nuit sur les 15 stations suivies. Générée automatiquement.</p>
    <div class="datebar">
      <span>{date_str}</span>
      <span>{ok_count} / {total_count} stations lues automatiquement</span>
    </div>
  </header>
  <table>
    <thead><tr><th>Station</th><th class="tn-col">Tn</th></tr></thead>
    <tbody>{rows}
    </tbody>
  </table>
  <div class="legend">
    <span><span class="chip" style="background:var(--cold-1)"></span>≤ −2°</span>
    <span><span class="chip" style="background:var(--cold-2)"></span>−2° à 0°</span>
    <span><span class="chip" style="background:var(--mild)"></span>0° à 5°</span>
    <span><span class="chip" style="background:var(--warm-1)"></span>5° à 10°</span>
    <span><span class="chip" style="background:var(--warm-2)"></span>&gt; 10°</span>
  </div>
  <footer>
    Page générée automatiquement le {gen_time} (heure de Paris) par <code>generate_tn_page.py</code>.
  </footer>
</div>
</body>
</html>
"""


def main():
    app_key = os.environ.get("ECOWITT_APPLICATION_KEY", "")
    api_key = os.environ.get("ECOWITT_API_KEY", "")
    datacake_tokens = json.loads(os.environ.get("DATACAKE_TOKENS_JSON", "{}"))

    rows_html = []
    ok_count = 0
    total = len(INFOCLIMAT_STATIONS) + len(METEORAVANEL_STATIONS) + len(DATACAKE_STATIONS) + len(ECOWITT_STATIONS)

    for st in INFOCLIMAT_STATIONS:
        tn, status = fetch_infoclimat_tn(st["url"])
        if tn is not None:
            ok_count += 1
        else:
            print(f"[warn] {st['name']}: {status}", file=sys.stderr)
        rows_html.append(render_row(st["name"], st["meta"], "INFOCLIMAT", tn, status))

    for st in METEORAVANEL_STATIONS:
        tn, status = fetch_meteoravanel_tn(st["url"])
        if tn is not None:
            ok_count += 1
        else:
            print(f"[warn] {st['name']}: {status}", file=sys.stderr)
        rows_html.append(render_row(st["name"], st["meta"], "MÉTÉORAVANEL", tn, status))

    for st in DATACAKE_STATIONS:
        token = datacake_tokens.get(st["device_id"])
        tn, status = fetch_datacake_tn(st["device_id"], token)
        if tn is not None:
            ok_count += 1
        else:
            print(f"[warn] {st['name']}: {status}", file=sys.stderr)
        rows_html.append(render_row(st["name"], st["meta"], "DATACAKE", tn, status))

    for st in ECOWITT_STATIONS:
        tn, status = fetch_ecowitt_tn(st["mac"], app_key, api_key)
        if tn is not None:
            ok_count += 1
        else:
            print(f"[warn] {st['name']}: {status}", file=sys.stderr)
        rows_html.append(render_row(st["name"], st["meta"], "ECOWITT", tn, status))

    now_paris = datetime.now(PARIS)
    html = TEMPLATE_HEAD.format(
        date_str=now_paris.strftime("%d %B %Y"),
        ok_count=ok_count,
        total_count=total,
        rows="".join(rows_html),
        gen_time=now_paris.strftime("%d/%m/%Y %H:%M"),
    )

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK — {ok_count}/{total} stations lues, page écrite dans docs/index.html")


if __name__ == "__main__":
    main()
