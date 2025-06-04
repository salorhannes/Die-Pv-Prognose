import pandas as pd
import numpy as np
import pvlib
from datetime import datetime, timedelta
import requests
import matplotlib.pyplot as plt

LAT, LON = 48.13, 11.58  # Beispielkoordinaten (München)

def lade_wetterdaten(start, end):
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": "temperature_2m,direct_normal_irradiance,diffuse_radiation,global_radiation",
        "timezone": "auto"
    }
    response = requests.get("https://api.open-meteo.com/v1/forecast", params=params)
    data = response.json()
    if "hourly" not in data:
        raise ValueError("❌ Fehler beim Abrufen der Wetterdaten:\n" + str(data))
    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)
    df.rename(columns={
        "global_radiation": "ghi",
        "direct_normal_irradiance": "dni",
        "diffuse_radiation": "dhi",
        "temperature_2m": "temp_air"
    }, inplace=True)
    df = df.dropna(subset=["ghi", "dni", "dhi", "temp_air"])
    return df

def berechne_ertrag(wetter, azimut, neigung, kwp, bias=1.0):
    solpos = pvlib.solarposition.get_solarposition(
        time=wetter.index,
        latitude=LAT,
        longitude=LON
    )
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=neigung,
        surface_azimuth=azimut,
        dni=wetter["dni"],
        ghi=wetter["ghi"],
        dhi=wetter["dhi"],
        solar_zenith=solpos["apparent_zenith"],
        solar_azimuth=solpos["azimuth"]
    )
    irrad = poa["poa_global"]
    temp_mod = wetter["temp_air"] + (45 - 20) / 800 * irrad
    leistung = irrad / 1000 * kwp * bias
    return leistung, temp_mod

if __name__ == "__main__":
    heute = datetime.now().date()
    ende = heute + timedelta(days=1)
    wetter = lade_wetterdaten(heute, ende)
    leistung, temp_mod = berechne_ertrag(wetter, 180, 30, 5)
    wetter["Leistung_kW"] = leistung
    wetter["Modul_Temp_C"] = temp_mod
    wetter[["Leistung_kW", "Modul_Temp_C"]].plot(title="PV-Ertrag & Modultemperatur")
    plt.tight_layout()
    plt.savefig("ertrag_plot.png")
    wetter.to_csv("ertrag_bericht.csv")