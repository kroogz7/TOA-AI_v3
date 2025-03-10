import os
import sys
import subprocess
import shutil

def check_python_version():
    """Check if Python version is sufficient."""
    required_version = (3, 6)
    current_version = sys.version_info
    
    if current_version < required_version:
        print(f"Error: Python {required_version[0]}.{required_version[1]} or higher is required.")
        print(f"Current version is {current_version[0]}.{current_version[1]}")
        return False
    
    return True

def check_dependencies():
    """Check and install required dependencies."""
    required_packages = ['flask', 'requests']
    to_install = []
    
    print("Checking dependencies...")
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is already installed")
        except ImportError:
            print(f"✗ {package} needs to be installed")
            to_install.append(package)
    
    if to_install:
        print("\nInstalling missing packages...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + to_install)
        print("All dependencies installed successfully.")
    else:
        print("All dependencies are already installed.")
    
    return True

def setup_web_files():
    """Ensure all web files are in the correct location."""
    # Define directory paths
    web_dir = os.path.join("TOA-AI", "web")
    templates_dir = os.path.join(web_dir, "templates")
    static_dir = os.path.join(web_dir, "static")
    css_dir = os.path.join(static_dir, "css")
    js_dir = os.path.join(static_dir, "js")
    img_dir = os.path.join(static_dir, "img")
    
    # Create directories if they don't exist
    for directory in [templates_dir, css_dir, js_dir, img_dir]:
        os.makedirs(directory, exist_ok=True)
    
    print("Web directories set up correctly.")
    return True

def check_web_app_py():
    """Check if web_app.py exists and is valid."""
    web_app_path = os.path.join("TOA-AI", "web_app.py")
    
    if not os.path.exists(web_app_path):
        print(f"Error: {web_app_path} not found.")
        return False
    
    # Very basic content check
    with open(web_app_path, 'r') as f:
        content = f.read()
        if "from flask import" not in content or "app.run" not in content:
            print(f"Warning: {web_app_path} may not be a valid Flask application.")
            if input("Continue anyway? (y/n): ").lower() != 'y':
                return False
    
    print(f"{web_app_path} found and appears valid.")
    return True

def check_html_templates():
    """Check if index.html exists in the templates directory."""
    index_path = os.path.join("TOA-AI", "web", "templates", "index.html")
    
    if not os.path.exists(index_path):
        print(f"Error: {index_path} not found.")
        return False
    
    print(f"{index_path} found.")
    return True

def main():
    """Main setup function."""
    print("=" * 60)
    print("TOA-AI Web Interface Setup")
    print("=" * 60)
    
    # Run checks
    if not check_python_version():
        sys.exit(1)
    
    if not check_dependencies():
        sys.exit(1)
    
    if not setup_web_files():
        sys.exit(1)
    
    if not check_web_app_py():
        sys.exit(1)
    
    if not check_html_templates():
        sys.exit(1)
    
    # All checks passed
    print("\nSetup completed successfully!")
    print("\nTo start the TOA-AI Web Interface:")
    print("1. Ensure the TOA-AI API is running:")
    print("   python TOA-AI/api.py")
    print("2. Start the web interface:")
    print("   python TOA-AI/web_app.py")
    print("3. Or use the combined starter:")
    print("   python TOA-AI/start_web_ui.py")
    print("\nThe web interface will be available at: http://localhost:5000")
    print("=" * 60)

if __name__ == "__main__":
    main() 