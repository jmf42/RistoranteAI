#!/usr/bin/env python3
import subprocess
import json
import sys
import os

PROJECT = "ristorante-ai-20260324-9471"
REGION = "europe-west1"
SERVICE = "ristorante-ai-dashboard"
# The backend URL the dashboard talks to
BACKEND_URL = "https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app"

print(f"🚀 Preparing dashboard deployment for project {PROJECT}...")

# Check if we are in the root or dashboard folder
current_dir = os.path.basename(os.getcwd())
if current_dir != "dashboard":
    if os.path.exists("dashboard"):
        print("Changing directory to dashboard/...")
        os.chdir("dashboard")
    else:
        print("Error: Could not find 'dashboard' directory. Run this from the project root or dashboard folder.")
        sys.exit(1)

deploy_cmd = [
    "gcloud", "run", "deploy", SERVICE,
    "--source", ".",
    f"--project={PROJECT}",
    f"--region={REGION}",
    f"--build-arg=NEXT_PUBLIC_API_BASE_URL={BACKEND_URL}",
    "--update-env-vars", f"NEXT_PUBLIC_API_BASE_URL={BACKEND_URL}"
]

print(f"🛠️ Running deployment: {' '.join(deploy_cmd)}")
try:
    subprocess.run(deploy_cmd, check=True)
    print("\n✅ Dashboard deployment triggered successfully!")
except subprocess.CalledProcessError as e:
    print(f"\n❌ Deployment failed with exit code {e.returncode}")
    sys.exit(e.returncode)
