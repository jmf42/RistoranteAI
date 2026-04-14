#!/usr/bin/env python3
import subprocess
import sys
import os
import time

# Unified Deployment Configuration
PROJECT = "ristorante-ai-20260324-9471"
REGION = "europe-west1"
BACKEND_SERVICE = "ristorante-ai-api"
DASHBOARD_SERVICE = "ristorante-ai-dashboard"
BACKEND_URL = "https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app"

def run_step(name, path, script):
    print(f"\n{'='*60}")
    print(f"🚀 STEP: {name}")
    print(f"{'='*60}")
    
    original_dir = os.getcwd()
    try:
        if path:
            os.chdir(path)
        
        # We run the Python scripts we already built
        process = subprocess.run([sys.executable, script], check=True)
        return True
    except Exception as e:
        print(f"\n❌ ERROR in {name}: {e}")
        return False
    finally:
        os.chdir(original_dir)

def main():
    start_time = time.time()
    print("🌟 Ristorante AI - Full Stack Production Deployment")
    print(f"Target Project: {PROJECT}")
    print(f"Target Region:  {REGION}")
    
    # Ensure we are in the root
    if not os.path.exists("backend") or not os.path.exists("dashboard"):
        print("Error: Please run this script from the project root directory.")
        sys.exit(1)

    # 1. Deploy Backend
    if not run_step("Backend API Deployment", "backend", "auto_deploy.py"):
        sys.exit(1)

    # 2. Deploy Dashboard
    if not run_step("Dashboard Deployment", "dashboard", "auto_deploy_dashboard.py"):
        sys.exit(1)

    duration = time.time() - start_time
    print(f"\n{'='*60}")
    print("✅ FULL STACK DEPLOYMENT COMPLETE!")
    print(f"Total Time: {duration:.1f}s")
    print(f"Backend:   {BACKEND_URL}")
    print(f"Dashboard: https://ristorante-ai-dashboard-jc7mvuujwq-ew.a.run.app")
    print(f"{'='*60}\n")
    print("Next step: Run 'make smoke-test' to verify everything is live.")

if __name__ == "__main__":
    main()
