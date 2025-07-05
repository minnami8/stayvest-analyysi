from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import requests

app = FastAPI()

# Constants for WMS/WFS base URLs
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
        "maaperaluokka": "(tuki tulossa)",
        "tulvariski": "(tuki tulossa)"
    }

    # 1. Hae korkeus WMS:llä
    try:
        bbox = f"{lon},{lat},{lon+0.0005},{lat+0.0005}"
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
        r = requests.get(MML_WMS_KORKEUS, params=params)
        result["korkeus"] = r.text.strip()
    except Exception as e:
        result["korkeus"] = f"Virhe: {str(e)}"

    # 2. Kiinteistötieto WFS:llä
    try:
        wfs_params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "kiinteisto:Kiinteistotunnus",
            "outputFormat": "application/json",
            "bbox": f"{lat},{lon},{lat+0.0005},{lon+0.0005},EPSG:4326"
        }
        r = requests.get(MML_WFS_KIINTEISTO, params=wfs_params)
        if r.status_code == 200:
            gjson = r.json()
            if gjson['features']:
                result['kiinteisto'] = gjson['features'][0]['properties']
    except Exception as e:
        result["kiinteisto"] = f"Virhe: {str(e)}"

    # Rakenna HTML-analyysinäkymä
    kiinteisto_html = "".join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in (result['kiinteisto'] or {}).items()])

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
                    <ul>{kiinteisto_html or '<li>Ei saatavilla</li>'}</ul>
                </li>
                <li><strong>Maaperä:</strong> {result['maaperaluokka']}</li>
                <li><strong>Tulvariski:</strong> {result['tulvariski']}</li>
            </ul>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)

# Tämä tekee Renderissä käynnistyksestä toimivan
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
