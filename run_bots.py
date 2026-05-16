import subprocess
import sys
import time

def run_bot(script_name):
    print(f"Starting {script_name}...")
    return subprocess.Popen([sys.executable, script_name])

if __name__ == "__main__":
    p1 = run_bot("generator_bot.py")
    p2 = run_bot("management_bot.py")

    print("\nBoth bots are running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
            if p1.poll() is not None:
                print("Generator bot stopped. Restarting...")
                p1 = run_bot("generator_bot.py")
            if p2.poll() is not None:
                print("Management bot stopped. Restarting...")
                p2 = run_bot("management_bot.py")
    except KeyboardInterrupt:
        print("\nStopping bots...")
        p1.terminate()
        p2.terminate()
        print("Done.")
