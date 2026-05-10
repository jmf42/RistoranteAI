#!/usr/bin/env python3
import subprocess
import json
import sys

PROJECT = "ristorante-ai-20260324-9471"
REGION = "europe-west1"
SERVICE = "ristorante-ai-api"
KNOWN_GOOD_REV = "ristorante-ai-api-00054-26n"

print(f"🔍 Fetching environment from working revision {KNOWN_GOOD_REV}...")
try:
    output = subprocess.check_output([
        "gcloud", "run", "revisions", "describe", KNOWN_GOOD_REV,
        f"--project={PROJECT}", f"--region={REGION}", "--format=json"
    ], text=True)
except Exception as e:
    print("Failed to get revision data.")
    sys.exit(1)

data = json.loads(output)
env_list = data.get("spec", {}).get("containers", [{}])[0].get("env", [])

# Convert to dict
env_dict = {}
for e in env_list:
    if "name" in e and "value" in e:
        env_dict[e["name"]] = e["value"]

print("✅ Extracted original secrets. Updating required overrides...")

# Merge our mandatory properties
env_dict.update({
    "APP_ENV": "production",
    "AUTO_CREATE_SCHEMA": "false",
    "SEED_DEMO": "false",
    "SESSION_COOKIE_SECURE": "true",
    "ALLOWED_ORIGINS": "https://ristorante-ai-dashboard-jc7mvuujwq-ew.a.run.app",
    "PUBLIC_BASE_URL": "https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app",
    "PUBLIC_WEB_BASE_URL": "https://ristorante-ai-dashboard-jc7mvuujwq-ew.a.run.app"
})

# Write to a safe yaml file manually to avoid PyYAML dependency
with open("env_vars.yaml", "w") as f:
    for k, v in env_dict.items():
        # Escape double quotes and backslashes if present
        safe_val = str(v).replace('\\', '\\\\').replace('"', '\\"')
        f.write(f'{k}: "{safe_val}"\n')

print("🚀 Starting deployment using secure env vars file...")
deploy_cmd = [
    "gcloud", "run", "deploy", SERVICE,
    "--source", ".",
    f"--project={PROJECT}",
    f"--region={REGION}",
    "--env-vars-file=env_vars.yaml"
]

subprocess.run(deploy_cmd)
