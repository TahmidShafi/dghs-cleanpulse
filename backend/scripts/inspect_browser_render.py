import os
import subprocess

cmd = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new",
    "--disable-gpu",
    "--virtual-time-budget=6000",
    "--dump-dom",
    "http://localhost:3000"
]

print("Launching Chrome headless to inspect http://localhost:3000...")
proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
html = proc.stdout
print("Rendered HTML character length:", len(html))

checks = [
    "DGHS-CleanPulse",
    "Live Government Data Firewall Inspector",
    "Monsoon Rainfall",
    "105,316",
    "452",
    "0.43%",
    "QUARANTINED_EXCEL_DATE",
    "42309",
    "46301",
    "06-10",
    "21-25",
    "Live FastAPI + DuckDB Connected",
    "Static Gold Snapshot Mode",
    "14 Days",
    "0.8102"
]

for c in checks:
    print(f"'{c}': {c in html}")

# Also test Tab 2 (Lag Explorer) via hash navigation
print("\nInspecting Tab 2 (Lag Explorer)...")
cmd_lags = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new",
    "--disable-gpu",
    "--virtual-time-budget=6000",
    "--dump-dom",
    "http://localhost:3000/#lags"
]
proc_lags = subprocess.run(cmd_lags, capture_output=True, text=True, encoding="utf-8")
html_lags = proc_lags.stdout

tab2_checks = [
    "Empirical Pearson Correlation Curve",
    "180-Day Epidemic Timeline",
    "10-Zone Surveillance Summary Table",
    "Chattogram",
    "DSCC",
    "DNCC",
    "Climate Shift Offset",
    "Biological Incubation Window: 14–18 Days"
]

for c in tab2_checks:
    print(f"Tab 2 '{c}': {c in html_lags}")

# Capture screenshots for both tabs
screenshot1 = os.path.abspath("docs/dashboard_tab1.png")
cmd_ss1 = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new",
    "--disable-gpu",
    "--virtual-time-budget=6000",
    "--window-size=1440,1200",
    f"--screenshot={screenshot1}",
    "http://localhost:3000/#firewall"
]
subprocess.run(cmd_ss1, capture_output=True)

screenshot2 = os.path.abspath("docs/dashboard_tab2.png")
cmd_ss2 = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new",
    "--disable-gpu",
    "--virtual-time-budget=6000",
    "--window-size=1440,1400",
    f"--screenshot={screenshot2}",
    "http://localhost:3000/#lags"
]
subprocess.run(cmd_ss2, capture_output=True)

print(f"Tab 1 Screenshot: {screenshot1} ({os.path.getsize(screenshot1)} bytes)")
print(f"Tab 2 Screenshot: {screenshot2} ({os.path.getsize(screenshot2)} bytes)")

