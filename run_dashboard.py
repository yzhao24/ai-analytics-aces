"""
Launcher for the Energy Anomaly Explainer dashboard.

Streamlit calls os.getcwd() while loading its config, which fails if the parent
process hands us a working directory we cannot stat. os.chdir() takes an absolute
path and does not need getcwd() first, so resetting the cwd here makes the app
launchable from any environment, including sandboxed preview runners.

Usage:
    python3 run_dashboard.py [--server.port 8520] [...streamlit flags]
"""

import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
APP_FILE = os.path.join(APP_DIR, "energy_anomaly_dashboard.py")

# Must happen before importing streamlit — its config loader calls Path.cwd().
os.chdir(APP_DIR)

DEFAULT_FLAGS = [
    "--server.headless=true",
    "--server.fileWatcherType=none",
    "--browser.gatherUsageStats=false",
]


def main():
    from streamlit.web import cli as stcli

    passed = sys.argv[1:]
    # Let caller-supplied flags win over our defaults.
    supplied = {a.split("=")[0].lstrip("-") for a in passed if a.startswith("--")}
    flags = [f for f in DEFAULT_FLAGS if f.split("=")[0].lstrip("-") not in supplied]

    if not any(a.startswith("--server.port") for a in passed):
        flags.append("--server.port=8520")

    sys.argv = ["streamlit", "run", APP_FILE, *flags, *passed]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
