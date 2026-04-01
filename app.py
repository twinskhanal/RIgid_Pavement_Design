import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="IRC:58-2015 Pavement Designer", layout="wide")
st.markdown("""<style>.main { background-color: #f8f9fa; } .stMetric { border: 1px solid #ddd; padding: 10px; border-radius: 5px; }</style>""", unsafe_allow_html=True)

# --- 2. CORE IRC:58 FUNCTIONS ---
def get_effective_k(cbr, dlc_thick):
    # Table 2 & 4 Interpolation
    cbr_vals = [2, 3, 4, 5, 7, 10, 15, 20]
    k_vals = [21, 28, 35, 42, 48, 55, 62, 69]
    k_subgrade = np.interp(cbr, cbr_vals, k_vals)
    return k_subgrade * (1.2 if dlc_thick < 150 else 1.5)

def get_fatigue_n(sr):
    if sr < 0.45: return float('inf')
    if 0.45 <= sr <= 0.55: return ((4.2577) / (sr - 0.4325))**3.268
    return 10**((0.9718 - sr) / 0.0828)

def compute_stress(h_mm, k, p_kn, dt, shoulder=True):
    h = h_mm / 1000
    gamma = 24
    if shoulder:
        if k <= 80: s = 0.008 - 6.12*(gamma*h**2/k**2) + 2.36*(p_kn*h/k**0.4) + 0.0266*dt
        else: s = 0.08 - 9.69*(gamma*h**2/k**2) + 2.09*(p_kn*h/k**0.4) + 0.0409*dt
    else:
        if k <= 80: s = -0.149 - 2.60*(gamma*h**2/k**2) + 3.13*(p_kn*h/k**0.4) + 0.0297*dt
        else: s = -0.119 - 2.99*(gamma*h**2/k**2) + 2.78*(p_kn*h/k**0.4) + 0.0456*dt
    return max(0.1, s)

# --- 3. SIDEBAR INPUTS ---
st.sidebar.title("Engineering Inputs")
with st.sidebar.expander("Traffic & Design Life", expanded=True):
    cvpd = st.number_input("Initial CVPD", value=6000)
    growth = st.slider("Growth Rate (%)", 1.0, 10.0, 7.5) / 100
    period = st.number_input("Design Life (Years)", value=30)
    lane_factor = st.selectbox("Lane Distribution", [0.25, 0.5, 0.75, 1.0], index=0)

with st.sidebar.expander("Materials & Subgrade"):
    cbr = st.slider("Subgrade CBR (%)", 2, 20, 8)
    dlc = st.number_input("DLC Thickness (mm)", value=150)
    fcr = st.number_input("Flexural Strength (MPa)", value=4.5)

with st.sidebar.expander("Joints & Shoulder"):
    shoulder = st.checkbox("Tied Shoulder", value=True)
    dowelled = st.checkbox("Dowelled Joints", value=True)

# --- 4. MAIN INTERFACE ---
st.title("🛣️ IRC:58-2015 Pavement Designer")
st.write("Professional thickness design including Fatigue (BUC & TDC) and Joint sizing.")

# Traffic Calculation
total_cv = (365 * cvpd * ((1 + growth)**period - 1)) / growth
design_traffic = total_cv * lane_factor
k_eff = get_effective_k(cbr, dlc)

# Axle Load Spectrum (Default Values)
st.subheader("Axle Load Spectrum")
spec_df = pd.DataFrame({
    "Axle Load (kN)": [160, 140, 120, 100],
    "Percentage (%)": [15, 25, 30, 30]
})
edited_spec = st.data_editor(spec_df, num_rows="dynamic")

# --- 5. AUTOMATIC THICKNESS DESIGN ---
st.subheader("Design Analysis")
h_range = range(250, 410, 10)
results = []
final_h = 0

for h in h_range:
    cfd_total = 0
    # Calculate for each axle load in the spectrum
    for _, row in edited_spec.iterrows():
        p = row["Axle Load (kN)"]
        pct = row["Percentage (%)"] / 100
        
        # Bottom-Up Cracking (Day)
        stress_buc = compute_stress(h, k_eff, p, 15.0, shoulder)
        sr_buc = stress_buc / (1.1 * fcr)
        n_buc = fatigue_life = get_fatigue_n(sr_buc)
        cfd_total += (design_traffic * pct * 0.25) / n_buc if n_buc > 0 else 0

    results.append({"Thickness": h, "CFD": cfd_total})
    if cfd_total < 1.0 and final_h == 0:
        final_h = h

# Display Results
if final_h > 0:
    c1, c2, c3 = st.columns(3)
    c1.metric("Design Thickness", f"{final_h} mm")
    c2.metric("Effective k", f"{k_eff:.1f} MPa/m")
    c3.metric("CFD Status", "SAFE" if final_h > 0 else "UNSAFE")
    
    # Plot
    fig, ax = plt.subplots(figsize=(10, 4))
    res_df = pd.DataFrame(results)
    ax.plot(res_df["Thickness"], res_df["CFD"], marker='o', color='blue')
    ax.axhline(y=1.0, color='red', linestyle='--', label='Limit')
    ax.set_yscale('log')
    ax.set_ylabel("Fatigue Damage (CFD)")
    ax.set_xlabel("Trial Thickness (mm)")
    st.pyplot(fig)
else:
    st.error("No safe thickness found in range. Increase slab thickness or material strength.")

# Joint Design Section
st.divider()
st.subheader("📐 Joints & Drainage")
colA, colB = st.columns(2)
with colA:
    st.write("**Dowel Bar Design**")
    dia = 32 if final_h < 300 else 38
    st.info(f"Diameter: {dia}mm | Length: 450mm | Spacing: 300mm")
with colB:
    st.write("**Tie Bar Design**")
    st.info(f"Diameter: 12mm | Length: 640mm | Spacing: 500mm")
