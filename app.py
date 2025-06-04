
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pvlib
from datetime import datetime, timedelta

# 📂 Feedback laden
def lade_feedback():
    try:
        return pd.read_csv("feedback.csv", parse_dates=["datum"])
    except FileNotFoundError:
        return pd.DataFrame(columns=["datum", "tatsaechlicher_ertrag_kwh"])

# ☀ Wetterdaten simulieren (Platzhalter)
def lade_wetterdaten():
    index = pd.date_range(datetime.now(), periods=48, freq="H")
    return pd.DataFrame({
        "time": index,
        "ghi": np.random.uniform(0, 800, size=48),
        "temp_air": np.random.uniform(15, 30, size=48)
    }).set_index("time")

# 📊 Berechnung
def berechne_ertrag(wetter, kwp, neigung, azimut):
    solpos = pvlib.solarposition.get_solarposition(
        time=wetter.index,
        latitude=50.6,
        longitude=6.3
    )
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=neigung,
        surface_azimuth=azimut,
        dni=None,
        ghi=wetter["ghi"],
        dhi=None,
        solar_zenith=solpos["zenith"],
        solar_azimuth=solpos["azimuth"]
    )
    irrad = poa["poa_global"]
    temp_modul = wetter["temp_air"] + (45 - 20) / 800 * irrad
    eta = 0.85 - 0.004 * (temp_modul - 25)
    leistung = kwp * irrad * eta / 1000  # in kW
    return leistung, temp_modul

# 📈 App
st.title("PV Ertragsprognose ☀️")
wetter = lade_wetterdaten()
leistung, temp_modul = berechne_ertrag(wetter, 11.7, 35, 220)
gesamt = leistung.resample("D").sum()

st.line_chart(leistung, use_container_width=True)
st.write(f"🔋 Prognose Tagesertrag: {gesamt.values[0]:.2f} kWh")
st.write(f"🌡️ Max. Modultemperatur: {temp_modul.max():.1f} °C")

# ✍ Feedback
feedback = lade_feedback()
st.subheader("📬 Feedback eintragen")
heute = datetime.now().date()
tats = st.number_input("Tatsächlicher Ertrag heute (kWh)", min_value=0.0, step=0.1)
if st.button("Speichern"):
    neu = pd.DataFrame([[heute, tats]], columns=["datum", "tatsaechlicher_ertrag_kwh"])
    feedback = pd.concat([feedback, neu], ignore_index=True)
    feedback.to_csv("feedback.csv", index=False)
    st.success("Feedback gespeichert!")
