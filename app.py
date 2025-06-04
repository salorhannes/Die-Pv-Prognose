# 📦 Installation (einmalig notwendig in Colab)
!pip install pvlib matplotlib ipywidgets --quiet

# 📚 Imports
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pvlib
from datetime import datetime, timedelta
import requests
import json
from IPython.display import display
import ipywidgets as widgets
import os

# 📁 Feedback-Datei
FEEDBACK_FILE = "pv_feedback.json"

# 📍 Standortdaten
LAT, LON = 50.599, 6.298  # Simmerath

# ⚙️ Anlagenkonfiguration
anlagen = [
    {"name": "Anlage SW 43°", "azimut": 225, "neigung": 43, "kwp": 6.3},
    {"name": "Anlage SW 23°", "azimut": 225, "neigung": 23, "kwp": 5.4},
]

# 🧠 Bias aus Feedback-Historie berechnen
def lade_bias():
    if not os.path.exists(FEEDBACK_FILE):
        return 1.0
    with open(FEEDBACK_FILE, "r") as f:
        daten = json.load(f)
    if not daten:
        return 1.0
    faktor_liste = [eintrag["ist"] / eintrag["soll"] for eintrag in daten if eintrag["soll"] > 0]
    return np.mean(faktor_liste)

# 🌤 Wetterdaten laden
def lade_wetterdaten(start, end):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={LAT}&longitude={LON}"
        f"&hourly=shortwave_radiation,temperature_2m"
        f"&start_date={start}&end_date={end}&timezone=Europe%2FBerlin"
    )
    response = requests.get(url)
    data = response.json()
    if "hourly" not in data:
        raise ValueError("❌ Fehler beim Abrufen der Wetterdaten:\n" + str(data))
    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)
    df.rename(columns={"shortwave_radiation": "ghi", "temperature_2m": "temp"}, inplace=True)
    df = df.astype(float)
    return df

# 🌡️ Modultemperatur mit Faiman-Modell
def modultemperatur_faiman(irrad, temp_amb, noct=45, windspeed=1):
    return temp_amb + (noct - 20) / 800 * irrad

# ⚡ Ertragsberechnung
def berechne_ertrag(wetter, azimut, neigung, kwp, bias=1.0):
    solpos = pvlib.solarposition.get_solarposition(wetter.index, LAT, LON)
    ghi = wetter["ghi"]
    dhi = ghi * 0.4  # grobe Annäherung
    dni = (ghi - dhi) / np.clip(np.cos(np.radians(solpos["zenith"])), 0.15, 1)

    irrad = pvlib.irradiance.get_total_irradiance(
        surface_tilt=neigung,
        surface_azimuth=azimut,
        dni=dni,
        ghi=ghi,
        dhi=dhi,
        solar_zenith=solpos["zenith"],
        solar_azimuth=solpos["azimuth"]
    )
    poa = irrad["poa_global"].fillna(0)

    temp_mod = modultemperatur_faiman(poa, wetter["temp"])
    eta_temp = 1 - 0.004 * (temp_mod - 25)
    eta_temp = np.clip(eta_temp, 0.8, 1.0)

    leistung = poa / 1000 * kwp * eta_temp * 0.85 * bias
    return wetter.index, leistung, temp_mod

# 🔁 Feedback-Funktion
def frage_feedback(soll):
    print("\n📬 Feedback zur tatsächlichen PV-Erzeugung:")
    ist_slider = widgets.FloatSlider(value=soll, min=0, max=soll*2, step=0.1, description='Ertrag [kWh]')
    speichern_btn = widgets.Button(description="✅ Speichern")

    def on_click(b):
        ist = ist_slider.value
        heute = str(datetime.now().date())
        eintrag = {"datum": heute, "soll": round(soll, 2), "ist": round(ist, 2)}
        if os.path.exists(FEEDBACK_FILE):
            with open(FEEDBACK_FILE, "r") as f:
                daten = json.load(f)
        else:
            daten = []
        daten.append(eintrag)
        with open(FEEDBACK_FILE, "w") as f:
            json.dump(daten, f, indent=2)
        print(f"📦 Feedback gespeichert: {eintrag}")

    speichern_btn.on_click(on_click)
    display(ist_slider, speichern_btn)

# 📊 Prognose ausführen
bias = lade_bias()
print(f"📐 Bias-Faktor aus Feedback-Historie: {bias:.3f}")

heute = datetime.now().date()
ende = heute + timedelta(days=2)
wetter = lade_wetterdaten(heute, ende)

gesamt_kwh = pd.Series(0.0, index=wetter.index)
mod_temp_max = []
zeiten_fuer_kw = []

plt.figure(figsize=(12, 6))
for anlage in anlagen:
    zeiten, leistung, mod_temp = berechne_ertrag(wetter, anlage["azimut"], anlage["neigung"], anlage["kwp"], bias)
    gesamt_kwh += leistung
    mod_temp_max.append(mod_temp.max())
    zeiten_kw = zeiten[leistung > 5]
    zeiten_fuer_kw.append((anlage["name"], zeiten_kw))
    plt.plot(zeiten, leistung, label=anlage["name"])

plt.plot(zeiten, gesamt_kwh, label="Gesamt", color="black", linewidth=2)
plt.xlabel("Zeit")
plt.ylabel("Leistung (kW)")
plt.title("🔆 PV-Leistungsprognose (nächste 2 Tage)")
plt.legend()
plt.grid()
plt.tight_layout()
plt.show()

# 📈 Tagesertrag berechnen
prognose_kwh = gesamt_kwh.resample("D").sum()
print("\n📊 Tagesertrag (kWh):")
print(prognose_kwh)

# 🌡️ Maximale Modultemperatur
for name, t in zip([a["name"] for a in anlagen], mod_temp_max):
    print(f"🌡️ Max. Modultemperatur {name}: {t:.1f} °C")

# ⏱️ Zeitraum mit >5 kW
print("\n⏱️ Zeiträume mit >5 kW Leistung:")
for name, zeiten_kw in zeiten_fuer_kw:
    if len(zeiten_kw) > 0:
        start, end = zeiten_kw[0], zeiten_kw[-1]
        print(f"{name}: {start.strftime('%H:%M')} – {end.strftime('%H:%M')}")
    else:
        print(f"{name}: Keine Stunde über 5 kW")

# 📝 Feedback-Eingabe (für heute)
heute_kwh = prognose_kwh.loc[str(heute)] if str(heute) in prognose_kwh else 0
frage_feedback(heute_kwh)
