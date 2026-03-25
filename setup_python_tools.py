#!/usr/bin/env python3
"""
reconx Python Tools Setup
Installs pip-based tools into the current venv.
Run AFTER setup_system_tools.sh (which handles git clones and sudo steps).
https://github.com/YOUR_USERNAME/reconx  <-- update this
"""

import subprocess
import sys
import os
import shutil

# ── Colors ────────────────────────────────────────────────────────────────────
RED    = '\033[0;31m'
GREEN  = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE   = '\033[0;34m'
CYAN   = '\033[0;36m'
NC     = '\033[0m'

installed = 0
failed    = 0

# ── Logging ───────────────────────────────────────────────────────────────────
def log_info(msg):    print(f"{BLUE}[INFO]{NC}    {msg}")
def log_success(msg):
    global installed
    print(f"{GREEN}[SUCCESS]{NC} {msg}")
    installed += 1
def log_warning(msg): print(f"{YELLOW}[WARNING]{NC} {msg}")
def log_error(msg):
    global failed
    print(f"{RED}[ERROR]{NC}   {msg}")
    failed += 1
def log_section(msg):
    print(f"\n{CYAN}{'='*50}{NC}")
    print(f"{CYAN}  {msg}{NC}")
    print(f"{CYAN}{'='*50}{NC}\n")

# ── Helpers ───────────────────────────────────────────────────────────────────
def cmd_exists(name):
    return shutil.which(name) is not None

def python_pkg_installed(import_name):
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False

def pip_install(package):
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", package],
        capture_output=True
    )
    return result.returncode == 0

# ── Requirements Check ────────────────────────────────────────────────────────
def check_requirements():
    log_section("Checking Requirements")
    ok = True
    for tool in ["git", "python3", "pip3"]:
        if cmd_exists(tool):
            log_success(f"{tool} found")
        else:
            log_error(f"{tool} not found -- please install it first")
            ok = False
    return ok

# ── Python Dependencies ───────────────────────────────────────────────────────

def install_dependencies():
    log_section("Installing Python Dependencies")
    deps = [
        ("termcolor",     "termcolor"),
        ("jsbeautifier",  "jsbeautifier"),
        ("pycryptodomex", "Cryptodome"),
        ("lxml",          "lxml"),
        ("requests",      "requests"),
        ("colorama",      "colorama"),
    ]
    for package, import_name in deps:
        if python_pkg_installed(import_name):
            log_warning(f"{package} already installed -- skipping")
        else:
            log_info(f"Installing {package}...")
            if pip_install(package):
                log_success(f"{package} installed")
            else:
                log_error(f"{package} failed")

# ── Arjun ─────────────────────────────────────────────────────────────────────
# pip-only tool, not handled by setup_system_tools.sh

def install_arjun():
    log_section("Installing Arjun (HTTP Parameter Discovery)")
    if cmd_exists("arjun"):
        log_warning("arjun already installed -- skipping")
        return
    log_info("Installing arjun...")
    if pip_install("arjun"):
        log_success("arjun installed")
    else:
        log_error("arjun failed")

# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    print(f"{GREEN}")
    print(r"    ____                      __   __")
    print(r"   |  _ \ ___  ___ ___  _ __ / /\ / /")
    print(r"   | |_) / _ \/ __/ _ \| '_ \ \/  \/ /")
    print(r"   |  _ <  __/ (_| (_) | | | ) \  / /")
    print(r"   |_| \_\___|\___\___/|_| |_\/  \/")
    print("")
    print("   Python Tools Setup -- github.com/YOUR_USERNAME/reconx")
    print(f"{NC}")

    if os.geteuid() == 0:
        log_warning("Running as root -- consider running in your venv instead")

    if not check_requirements():
        print(f"\n{RED}Aborting: missing required system tools.{NC}")
        sys.exit(1)

    install_dependencies()
    install_arjun()

    log_section("Summary")
    print(f"  Installed : {GREEN}{installed}{NC}")
    if failed > 0:
        print(f"  Failed    : {RED}{failed}{NC}")
        print(f"\n{YELLOW}Some tools failed. Check errors above.{NC}")
    else:
        print(f"\n{GREEN}All done!{NC}")

if __name__ == "__main__":
    main()
