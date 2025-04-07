#!/usr/bin/env python3
import subprocess
import sys
import os
import platform

def run_command(command):
    """Run a shell command and return the output and success status."""
    try:
        result = subprocess.run(command, shell=True, check=False, text=True, 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.strip(), result.stderr.strip(), result.returncode == 0
    except Exception as e:
        return "", str(e), False

def check_command_exists(command):
    """Check if a command exists in the system PATH."""
    if platform.system() == "Windows":
        check_cmd = f"where {command}"
    else:
        check_cmd = f"which {command}"
    
    _, _, success = run_command(check_cmd)
    return success

def install_postgres_tools():
    """Install PostgreSQL client tools based on the operating system."""
    system = platform.system().lower()
    
    print("\n=== Installing PostgreSQL Client Tools ===\n")
    
    if system == "linux":
        # Detect the Linux distribution
        if os.path.exists("/etc/debian_version") or os.path.exists("/etc/ubuntu_version"):
            # Debian/Ubuntu
            print("Detected Debian/Ubuntu system")
            commands = [
                "sudo apt-get update",
                "sudo apt-get install -y postgresql-client"
            ]
        elif os.path.exists("/etc/fedora-release") or os.path.exists("/etc/redhat-release"):
            # Fedora/RHEL/CentOS
            print("Detected Fedora/RHEL/CentOS system")
            commands = [
                "sudo dnf install -y postgresql"
            ]
        elif os.path.exists("/etc/arch-release"):
            # Arch Linux
            print("Detected Arch Linux system")
            commands = [
                "sudo pacman -Sy --noconfirm postgresql"
            ]
        else:
            print("Unsupported Linux distribution. Please install PostgreSQL client tools manually.")
            return False
    elif system == "darwin":
        # macOS
        print("Detected macOS system")
        commands = [
            "brew update",
            "brew install libpq",
            "brew link --force libpq"
        ]
    elif system == "windows":
        print("On Windows, we recommend installing PostgreSQL tools through the official installer.")
        print("Please visit: https://www.postgresql.org/download/windows/")
        print("After installation, make sure to add the bin directory to your PATH.")
        return False
    else:
        print(f"Unsupported operating system: {system}")
        return False
    
    # Run the installation commands
    for cmd in commands:
        print(f"Running: {cmd}")
        stdout, stderr, success = run_command(cmd)
        
        if not success:
            print(f"Command failed: {cmd}")
            print(f"Error: {stderr}")
            return False
        
        if stdout:
            print(stdout)
    
    return True

def check_python_dependencies():
    """Check and install required Python dependencies."""
    required_packages = ["python-dotenv"]
    
    try:
        import pkg_resources
        
        # Check if packages are installed
        missing_packages = []
        for package in required_packages:
            try:
                pkg_resources.get_distribution(package)
            except pkg_resources.DistributionNotFound:
                missing_packages.append(package)
        
        # Install missing packages
        if missing_packages:
            print(f"\n=== Installing missing Python packages: {', '.join(missing_packages)} ===\n")
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
            print("Python dependencies installed successfully.")
        else:
            print("All required Python packages are already installed.")
            
        return True
    except Exception as e:
        print(f"Error checking/installing Python dependencies: {e}")
        return False

def main():
    print("=== Checking Prerequisites for Supabase Schema Sync ===\n")
    
    # Check for psql command
    print("Checking for PostgreSQL client tools...")
    psql_exists = check_command_exists("psql")
    pg_dump_exists = check_command_exists("pg_dump")
    
    if psql_exists and pg_dump_exists:
        print("✅ PostgreSQL client tools (psql and pg_dump) are already installed.")
    else:
        print("❌ PostgreSQL client tools are missing.")
        if not psql_exists:
            print("  - psql command not found")
        if not pg_dump_exists:
            print("  - pg_dump command not found")
        
        # Try to install PostgreSQL tools
        print("\nAttempting to install PostgreSQL client tools...")
        if install_postgres_tools():
            print("\n✅ PostgreSQL client tools installed successfully.")
        else:
            print("\n❌ Failed to install PostgreSQL client tools automatically.")
            print("Please install them manually according to your operating system instructions.")
            print("For more information, visit: https://www.postgresql.org/download/")
    
    # Check Python dependencies
    print("\nChecking Python dependencies...")
    if check_python_dependencies():
        print("✅ All Python dependencies are properly installed.")
    else:
        print("❌ Failed to install required Python dependencies.")
        print("Please run: pip install python-dotenv")
    
    print("\n=== Prerequisite check completed ===")

if __name__ == "__main__":
    main()