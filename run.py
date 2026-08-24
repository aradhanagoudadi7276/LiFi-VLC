import subprocess
import sys
import time
import os
import threading

def log_stream(stream, prefix):
    """Reads lines from a subprocess stdout/stderr and prints them with a tag."""
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            print(f"[{prefix}] {line.strip()}")
    except Exception:
        pass

def main():
    print("==================================================")
    print("  LiFi Visible Light Communication Project Manager")
    print("==================================================")
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    frontend_dir = os.path.join(root_dir, "frontend")
    
    print("\n[1/3] Launching FastAPI Backend on http://127.0.0.1:8000 ...")
    try:
        # Run uvicorn app.main:app --host 127.0.0.1 --port 8000
        backend_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    except Exception as e:
        print(f"ERROR: Failed to launch backend: {e}")
        return

    # Start threads to stream backend console logs
    t_back_out = threading.Thread(target=log_stream, args=(backend_process.stdout, "BACKEND"))
    t_back_err = threading.Thread(target=log_stream, args=(backend_process.stderr, "BACKEND_ERR"))
    t_back_out.daemon = True
    t_back_err.daemon = True
    t_back_out.start()
    t_back_err.start()

    # Sleep slightly for backend startup
    time.sleep(2)
    
    print("\n[2/3] Launching React Dev Server on http://localhost:5173 ...")
    try:
        # Run npm run dev inside frontend directory
        frontend_process = subprocess.Popen(
            "npm run dev",
            cwd=frontend_dir,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    except Exception as e:
        print(f"ERROR: Failed to launch React dev server: {e}")
        backend_process.terminate()
        return

    # Start threads to stream frontend logs
    t_front_out = threading.Thread(target=log_stream, args=(frontend_process.stdout, "FRONTEND"))
    t_front_err = threading.Thread(target=log_stream, args=(frontend_process.stderr, "FRONTEND_ERR"))
    t_front_out.daemon = True
    t_front_err.daemon = True
    t_front_out.start()
    t_front_err.start()

    print("\n[3/3] System is running!")
    print("  - Backend API Gateway: http://127.0.0.1:8000")
    print("  - Frontend Dashboard: http://localhost:5173")
    print("\nKeep this console window open. Press CTRL+C to terminate both servers.")
    print("==================================================")

    try:
        while True:
            # Poll both processes to check if they are running
            if backend_process.poll() is not None:
                print("\n[SYSTEM] FastAPI Backend terminated unexpectedly.")
                break
            if frontend_process.poll() is not None:
                print("\n[SYSTEM] React Frontend terminated unexpectedly.")
                break
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[SYSTEM] Terminating servers...")
    finally:
        # Gracefully kill processes
        try:
            backend_process.terminate()
        except Exception:
            pass
        try:
            frontend_process.terminate()
        except Exception:
            pass
        print("[SYSTEM] Both processes closed. Goodbye!")

if __name__ == "__main__":
    main()
