import os
import subprocess
import sys
import time
import socket
import webbrowser
from threading import Thread

def is_port_in_use(port):
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def wait_for_server(port, timeout=30):
    """Wait for server to be available on the specified port."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(1)
    return False

def start_api_server():
    """Start the TOA-AI API server."""
    print("Starting TOA-AI API server...")
    
    # If API server is already running, use it
    if is_port_in_use(8000):
        print("TOA-AI API server is already running on port 8000.")
        return
    
    api_process = subprocess.Popen(
        [sys.executable, "TOA-AI/api.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Wait for API server to start
    if wait_for_server(8000):
        print("TOA-AI API server started successfully.")
    else:
        print("Warning: TOA-AI API server might not have started correctly.")
        print("Output:")
        for line in api_process.stdout.readlines():
            print(f"  {line.strip()}")

def start_web_server():
    """Start the TOA-AI Web UI server."""
    print("Starting TOA-AI Web UI server...")
    
    # If web server is already running, use it
    if is_port_in_use(5000):
        print("TOA-AI Web UI server is already running on port 5000.")
        return
    
    web_process = subprocess.Popen(
        [sys.executable, "TOA-AI/web_app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Wait for web server to start
    if wait_for_server(5000):
        print("TOA-AI Web UI server started successfully.")
    else:
        print("Warning: TOA-AI Web UI server might not have started correctly.")
        print("Output:")
        for line in web_process.stdout.readlines():
            print(f"  {line.strip()}")

def main():
    """Main function to start both servers and open web browser."""
    print("=" * 60)
    print(" TOA-AI Web Interface Starter")
    print("=" * 60)
    
    # Check for required directories
    if not os.path.exists("TOA-AI/web/templates/index.html"):
        print("Error: Web interface files not found. Please ensure all files are in place.")
        return
    
    # Start servers
    api_thread = Thread(target=start_api_server)
    api_thread.daemon = True
    api_thread.start()
    
    # Wait for API server to be ready
    print("Waiting for API server to be ready...")
    if not wait_for_server(8000, timeout=30):
        print("Error: TOA-AI API server failed to start within the timeout period.")
        print("Please check if the API server is properly configured.")
        return
    
    # Start web server
    start_web_server()
    
    # Open web browser
    print("\nOpening browser to TOA-AI Web Interface...")
    webbrowser.open('http://localhost:5000')
    
    print("\nPress CTRL+C to stop the servers.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down TOA-AI Web Interface...")
        # The servers will be terminated when the script exits

if __name__ == "__main__":
    main() 