from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import requests

app = FastAPI()

MML_WMS_KORKEUS = "https://avoin-karttakuva.maanmittauslaitos.fi/maasto/wms"
MML_WFS_KIINTEISTO = "https://avoindata.maanmittauslaitos.fi/geoserver/kiinteisto/wfs"
GTK_WMS_MAAPERA = "https://gtkdata.gtk.fi/arcgis/services/GTKWMS/MapServer/WMSServer"
SYKE_WMS_TULVA = "https://paikkatieto.ymparisto.fi/arcgis/services/INSPIRE/Tulvakartat/MapServer/WMSServer"

@app.get("/analyysi", response_class=HTMLResponse)
def analysoi_tontti(lat: float = Query(...), lon: float = Query(...)):
    result = {
        "input_coords": {"lat": lat, "lon": lon},
        "korkeus": None,
        "kiinteisto": None,
        "maaperaluokka": "(ei haettu)",
        "tulvariski": "(ei haettu)"
    }

    bbox = f"{lon},{lat},{lon+0.0005},{lat+0.0005}"

    # 1. Korkeus
    try:
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": "korkeusmalli_10m",
            "QUERY_LAYERS": "korkeusmalli_10m",
            "SRS": "EPSG:4326",
            "INFO_FORMAT": "text/plain",
            "X": 50,
            "Y": 50,
            "WIDTH": 101,
            "HEIGHT": 101,
            "BBOX": bbox
        }
        r = requests.get(MML_WMS_KORKEUS, params=params, timeout=10)
        result["korkeus"] = r.text.strip()
    except Exception as e:
        result["korkeus"] = f"Virhe: {str(e)}"

    # 2. Kiinteistötieto
    try:
        wfs_params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "kiinteisto:Kiinteistotunnus",
            "outputFormat": "application/json",
            "bbox": f"{lat},{lon},{lat+0.0005},{lon+0.0005},EPSG:4326"
        }
        r = requests.get(MML_WFS_KIINTEISTO, params=wfs_params, timeout=10)
        if r.status_code == 200:
            gjson = r.json()
            if gjson['features']:
                result['kiinteisto'] = gjson['features'][0]['properties']
            else:
                result["kiinteisto"] = None
        else:
            result["kiinteisto"] = f"Virhe: {r.status_code}"
    except Exception as e:
        result["kiinteisto"] = f"Virhe: {str(e)}"

    # 3. Maaperä GTK WMS
    try:
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": "1",
            "QUERY_LAYERS": "1",
            "CRS": "EPSG:4326",
            "INFO_FORMAT": "application/json",
            "BBOX": bbox,
            "WIDTH": 101,
            "HEIGHT": 101,
            "I": 50,
            "J": 50
        }
        r = requests.get(GTK_WMS_MAAPERA, params=params, timeout=10)
        gj = r.json()
        result["maaperaluokka"] = gj["features"][0]["properties"].get("Maa_alue", "Ei saatavilla")
    except Exception:
        result["maaperaluokka"] = "Ei saatavilla"

    # 4. Tulvariski SYKE
    try:
        params["LAYERS"] = params["QUERY_LAYERS"] = "0"
        r = requests.get(SYKE_WMS_TULVA, params=params, timeout=10)
        tj = r.json()
        result["tulvariski"] = "Kyllä" if tj["features"] else "Ei"
    except Exception:
        result["tulvariski"] = "Ei saatavilla"

    # Kiinteistö HTML
    if isinstance(result["kiinteisto"], dict):
        kiinteisto_html = "".join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in result["kiinteisto"].items()])
    elif isinstance(result["kiinteisto"], str):
        kiinteisto_html = f"<li>{result['kiinteisto']}</li>"
    else:
        kiinteisto_html = "<li>Ei saatavilla</li>"

    html = f"""
    <!DOCTYPE html>
    <html lang='fi'>
    <head>
        <meta charset='UTF-8'>
        <title>Tonttianalyysi</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 1em; background: #f9f9f9; color: #333; }}
            h2 {{ color: #004578; }}
            .box {{ background: #fff; padding: 1em; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); max-width: 600px; margin: auto; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ margin: 0.5em 0; }}
        </style>
    </head>
    <body>
        <div class="box">
            <h2>📍 Tontin analyysi</h2>
            <ul>
                <li><strong>Koordinaatit:</strong> {lat:.5f}, {lon:.5f}</li>
                <li><strong>Korkeus (KM10):</strong> {result['korkeus']}</li>
                <li><strong>Kiinteistötiedot:</strong>
                    <ul>{kiinteisto_html}</ul>
                </li>
                <li><strong>Maaperä:</strong> {result['maaperaluokka']}</li>
                <li><strong>Tulvariski:</strong> {result['tulvariski']}</li>
            </ul>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
