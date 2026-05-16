import subprocess
import sys
import time

def run_bot(script_name):
    print(f"Starting {script_name}...")
    return subprocess.Popen([sys.executable, script_name])

if __name__ == "__main__":
    p1 = run_bot("generator_bot.py")
    p2 = run_bot("management_bot.py")
    p3 = run_bot("ticket_bot.py")
    p4 = run_bot("messenger_bot.py")
    p5 = run_bot("boost_bot.py")

    print("\nAll 5 bots are running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
            if p1.poll() is not None:
                print("Generator bot stopped. Restarting...")
                p1 = run_bot("generator_bot.py")
            if p2.poll() is not None:
                print("Management bot stopped. Restarting...")
                p2 = run_bot("management_bot.py")
            if p3.poll() is not None:
                print("Ticket bot stopped. Restarting...")
                p3 = run_bot("ticket_bot.py")
            if p4.poll() is not None:
                print("Messenger bot stopped. Restarting...")
                p4 = run_bot("messenger_bot.py")
            if p5.poll() is not None:
                print("Boost bot stopped. Restarting...")
                p5 = run_bot("boost_bot.py")
    except KeyboardInterrupt:
        print("\nStopping bots...")
        p1.terminate()
        p2.terminate()
        p3.terminate()
        p4.terminate()
        p5.terminate()
        print("Done.")
