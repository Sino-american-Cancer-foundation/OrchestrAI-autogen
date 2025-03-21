import os
import shutil
import zipfile
import threading
import time
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import subprocess

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

DEPLOYMENTS_DIR = Path("deployments")
DEPLOYMENTS_DIR.mkdir(exist_ok=True)

active_deployment = {"folder": None, "processes": []}
lock = threading.Lock()

def stop_existing_deployment():
    with lock:
        if active_deployment["processes"]:
            for process in active_deployment["processes"]:
                process.terminate()
            active_deployment["processes"].clear()
            print("Previous deployment stopped.")

def run_script(script_path, process_list):
    process = subprocess.Popen(["python3", "-u", script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with lock:
        process_list.append(process)

    for line in iter(process.stdout.readline, b''):
        print(line.decode().strip())  

@app.post("/deployClient")
async def deploy_client(file: UploadFile = File(...)):
    stop_existing_deployment()

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    deployment_folder = DEPLOYMENTS_DIR / f"deployment-{timestamp}"
    deployment_folder.mkdir(parents=True, exist_ok=True)

    zip_path = deployment_folder / file.filename
    with zip_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(deployment_folder)

    execution_worker_path = deployment_folder / "execution-worker" / "execution-worker.py"
    team_script_path = deployment_folder / "chat-team" / "team.py"

    processes = []
    if execution_worker_path.exists():
        thread1 = threading.Thread(target=run_script, args=(execution_worker_path, processes))
        thread1.daemon = True
        thread1.start()

    if team_script_path.exists():
        thread2 = threading.Thread(target=run_script, args=(team_script_path, processes))
        thread2.daemon = True
        thread2.start()

    with lock:
        active_deployment["folder"] = str(deployment_folder)
        active_deployment["processes"] = processes

    return {
        "message": "Deployment started successfully.",
        "deployment_folder": str(deployment_folder),
        "execution_worker_running": execution_worker_path.exists(),
        "team_running": team_script_path.exists()
    }

@app.post("/stopDeployment")
async def stop_deployment():
    stop_existing_deployment()
    return {"message": "Deployment stopped successfully."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=1234)