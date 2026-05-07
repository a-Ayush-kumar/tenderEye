#!/usr/bin/env python3
"""
Local development runner for VIGIL Prototype.
No Docker required - uses SQLite, local filesystem, and mock Ollama.
"""
import os
import sys
import asyncio
import subprocess
import time

# Set local dev environment - use absolute path to ensure correct DB is used
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(PROJECT_DIR, 'vigil.db')}"
os.environ["USE_LOCAL_STORAGE"] = "true"
os.environ["PYTHONUNBUFFERED"] = "1"

# Paths
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "backend")
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")

def run_backend():
    """Install deps and start FastAPI backend."""
    print("=== Starting VIGIL Backend ===")
    
    # Install dependencies
    print("Installing backend dependencies...")
    req_file = os.path.join(BACKEND_DIR, "requirements_local.txt")
    if not os.path.exists(req_file):
        req_file = os.path.join(BACKEND_DIR, "requirements.txt")
    
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_file],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Warning: pip install had issues: {result.stderr[:500]}")
    else:
        print("Backend dependencies installed.")
    
    # Seed database
    print("Seeding database...")
    seed_script = os.path.join(BACKEND_DIR, "scripts", "seed.py")
    if os.path.exists(seed_script):
        subprocess.run([sys.executable, seed_script], cwd=BACKEND_DIR)
    
    # Start uvicorn
    print("Starting FastAPI server on http://localhost:8000")
    print("API docs: http://localhost:8000/docs")
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=BACKEND_DIR
    )

def run_frontend():
    """Install deps and start Next.js frontend."""
    print("=== Starting VIGIL Frontend ===")
    
    is_windows = os.name == 'nt'
    npm_cmd = "npm.cmd" if is_windows else "npm"
    
    # Check if node_modules exists
    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.exists(node_modules):
        print("Installing frontend dependencies...")
        subprocess.run([npm_cmd, "install"], cwd=FRONTEND_DIR)
    else:
        print("Frontend dependencies already installed.")
    
    print("Starting Next.js dev server on http://localhost:3000")
    subprocess.run(
        [npm_cmd, "run", "dev"],
        cwd=FRONTEND_DIR,
        env={**os.environ, "NEXT_PUBLIC_API_URL": "http://localhost:8000"}
    )

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", action="store_true", help="Run backend only")
    parser.add_argument("--frontend", action="store_true", help="Run frontend only")
    args = parser.parse_args()
    
    if args.backend:
        run_backend()
    elif args.frontend:
        run_frontend()
    else:
        print("Usage:")
        print("  python run_local.py --backend    # Start FastAPI backend")
        print("  python run_local.py --frontend   # Start Next.js frontend")
        print("\nRun both in separate terminals for full stack.")
