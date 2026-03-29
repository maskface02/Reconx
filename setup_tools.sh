#!/bin/bash
clear
set -euo pipefail



# Resolve the real user (not root) who invoked sudo
export SUDO_USER_NAME="${SUDO_USER:-$USER}"
export SUDO_USER_HOME
SUDO_USER_HOME=$(eval echo ~"$SUDO_USER_NAME")

if [ "$SUDO_USER_NAME" = "root" ]; then
  echo "Warning: Could not detect the invoking user. Run with 'sudo', not as root directly."
fi

# ── Directory Layout (everything inside ~/.local/) ───────────────────────────
export INSTALL_DIR="$SUDO_USER_HOME/.local/bin"       # compiled/linked binaries
export OPT_DIR="$SUDO_USER_HOME/.local/opt"           # cloned git repos
export WORDLIST_DIR="$SUDO_USER_HOME/.local/share/wordlists"
export GO_DIR="$SUDO_USER_HOME/.local/go"             # Go compiler tarball
export GO_CACHE="$SUDO_USER_HOME/.local/go_cache"     # GOPATH (module cache, inside .local)

mkdir -p "$INSTALL_DIR" "$OPT_DIR" "$WORDLIST_DIR" "$GO_CACHE"
chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$SUDO_USER_HOME/.local"

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'

# ── Banner ──────────────────────────────────────────────────────────────────
show_banner() {
  echo -e "${CYAN}"
  echo '    ____                      __   __'
  echo '   |  _ \ ___  ___ ___  _ __ / /\ / /'
  echo "   | |_) / _ \/ __/ _ \| '\''_ \\ \\/  \\/ /"
  echo '   |  _ <  __/ (_| (_) | | | ) \  / /'
  echo '   |_| \_\___|\___\___/|_| |_\/  \/'
  echo ''
  echo -e "   ${PURPLE}Unified Reconnaissance Framework${NC}"
  echo -e "   ${BLUE}https://github.com/maskface02/Reconx${NC}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  if [ "$EUID" -ne 0 ]; then
    err "This script must be run with sudo"
    info "Usage: sudo bash setup_tools.sh"
    exit 1
  fi
}

section()     { echo -e "\n${PURPLE}┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n┃${NC} ${BOLD}$1${NC}\n${PURPLE}┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛${NC}"; }
sub_section() { echo -e "${CYAN}▶${NC} ${BOLD}$1${NC}"; }
info()        { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()          { echo -e "${GREEN}[✓]${NC} $1"; }
warn()        { echo -e "${YELLOW}[!]${NC} $1"; }
err()         { echo -e "${RED}[✗]${NC} $1"; }

# ── Detect Distro ────────────────────────────────────────────────────────────
detect_distro() {
  if [ ! -f /etc/os-release ]; then
    echo "unknown"
    return
  fi
  local id id_like combined
  id=$(grep   "^ID="      /etc/os-release | cut -d= -f2 | tr -d '"' | tr '[:upper:]' '[:lower:]')
  id_like=$(grep "^ID_LIKE=" /etc/os-release | cut -d= -f2 | tr -d '"' | tr '[:upper:]' '[:lower:]' 2>/dev/null || echo "")
  combined="$id $id_like"
  case "$combined" in
    *debian*|*ubuntu*|*mint*|*pop*) echo "debian" ;;
    *arch*|*manjaro*|*endeavour*)   echo "arch"   ;;
    *)                               echo "unknown" ;;
  esac
}

DISTRO=$(detect_distro)

# ── Fix Conflicting Shell Aliases ────────────────────────────────────────────
check_aliases() {
  local cfg=""
  [ -f "$SUDO_USER_HOME/.zshrc"  ] && cfg="$SUDO_USER_HOME/.zshrc"
  [ -z "$cfg" ] && [ -f "$SUDO_USER_HOME/.bashrc" ] && cfg="$SUDO_USER_HOME/.bashrc"

  # Remove from current session
  alias gau 2>/dev/null | grep -q "git add"   && { warn "Removing conflicting 'gau' alias"; unalias gau 2>/dev/null || true; }
  alias gf  2>/dev/null | grep -q "git fetch" && { warn "Removing conflicting 'gf' alias";  unalias gf  2>/dev/null || true; }

  if [ -n "$cfg" ]; then
    # Comment them out persistently
    grep -q "^alias gau=" "$cfg" 2>/dev/null && \
      { info "Commenting out 'gau' alias in $cfg"; sed -i 's/^alias gau=/# alias gau=/' "$cfg"; }
    grep -q "^alias gf="  "$cfg" 2>/dev/null && \
      { info "Commenting out 'gf' alias in $cfg";  sed -i 's/^alias gf=/# alias gf=/'   "$cfg"; }

    # Ensure they stay removed in future sessions
    if ! grep -q "unalias gau" "$cfg" 2>/dev/null; then
      printf '\n# ReconX: Remove conflicting aliases\nunalias gau 2>/dev/null || true\nunalias gf 2>/dev/null || true\n' >> "$cfg"
      chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$cfg"
    fi
  fi
}

# ── PATH Configuration ───────────────────────────────────────────────────────
setup_path_auto() {
  section "SHELL CONFIGURATION"

  local cfg=""
  if   [ -f "$SUDO_USER_HOME/.zshrc"  ]; then cfg="$SUDO_USER_HOME/.zshrc"
  elif [ -f "$SUDO_USER_HOME/.bashrc" ]; then cfg="$SUDO_USER_HOME/.bashrc"
  else
    cfg="$SUDO_USER_HOME/.bashrc"
    touch "$cfg"
    chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$cfg"
  fi

  if ! grep -q "ReconX PATH" "$cfg" 2>/dev/null; then
    info "Writing PATH block to $cfg..."
    cat >> "$cfg" << 'EOF'

# ReconX PATH - Added automatically
export PATH="$HOME/.local/bin:$HOME/.local/go/bin:$PATH"
EOF
    chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$cfg"
    ok "PATH added to $cfg"
  else
    info "PATH already configured in $cfg"
  fi

  # Make paths available for the rest of this install session
  export PATH="$INSTALL_DIR:$GO_DIR/bin:$PATH"

  # pipx ensurepath is non-fatal — it may already be done
  command -v pipx &>/dev/null && pipx ensurepath 2>/dev/null || true

  ok "PATH configured for current session"
}

# ── System Dependencies ──────────────────────────────────────────────────────
install_sys_deps() {
  section "SYSTEM DEPENDENCIES"

  case $DISTRO in

  debian)
    info "Updating package lists..."
    apt-get update -qq

    info "Installing build tools and libraries..."
    # bzip2       — needed to unpack nmap .tar.bz2
    # libcap2-bin — provides setcap for nmap / masscan capabilities
    # python3-venv / pipx — for arjun via pipx
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      build-essential libpcap-dev libssl-dev zlib1g-dev \
      libxml2-dev libxslt1-dev libffi-dev libsqlite3-dev \
      libcurl4-openssl-dev libjpeg-dev libpng-dev pkg-config cmake \
      unzip bzip2 jq perl wget curl git \
      python3 python3-pip python3-venv pipx \
      libcap2-bin upx-ucl libjson-perl libxml-writer-perl
    ;;

  arch)
    info "Syncing package database..."
    pacman -Sy --noconfirm

    info "Installing build tools and libraries..."
    # python-pipx — official Arch package for pipx (avoids pip install as root)
    # libcap       — provides setcap
    # bzip2        — for nmap source tarball
    pacman -S --noconfirm --needed \
      base-devel libpcap openssl zlib libxml2 libxslt libffi sqlite \
      curl libjpeg-turbo libpng pkgconf cmake unzip bzip2 jq perl wget git \
      python python-pip python-pipx libcap upx perl-json perl-xml-writer
      ;;

  *)
    err "Unsupported distro. Only Debian/Ubuntu and Arch are supported."
    exit 1
    ;;
  esac

  ok "System dependencies installed"
}

# ── Go Compiler ──────────────────────────────────────────────────────────────
install_go() {
  section "GO COMPILER"

  if [ -x "$GO_DIR/bin/go" ]; then
    info "Go already installed: $("$GO_DIR/bin/go" version)"
    return
  fi

  local arch="amd64"
  [ "$(uname -m)" = "aarch64" ] && arch="arm64"

  info "Fetching latest stable Go version..."
  local go_version
  go_version=$(curl -fsSL "https://go.dev/VERSION?m=text" 2>/dev/null | head -1 | tr -d '[:space:]') \
    || go_version=""
  [ -z "$go_version" ] && go_version="go1.23.4"   # safe known-good fallback
  info "Targeting Go: $go_version"

  local tarball="${go_version}.linux-${arch}.tar.gz"
  local tmp_tar
  tmp_tar=$(mktemp /tmp/go_tarball.XXXXXX.tar.gz)

  info "Downloading $tarball..."
  wget -q --show-progress "https://go.dev/dl/${tarball}" -O "$tmp_tar"

  info "Extracting to $GO_DIR..."
  rm -rf "$GO_DIR"
  tar -C "$SUDO_USER_HOME/.local" -xzf "$tmp_tar"
  chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$GO_DIR"
  rm -f "$tmp_tar"

  export PATH="$GO_DIR/bin:$PATH"
  ok "Go installed: $("$GO_DIR/bin/go" version)"
}

# ── Go-Based Tools ───────────────────────────────────────────────────────────
install_go_tools() {
  section "GO-BASED TOOLS"

  export GOPATH="$GO_CACHE"
  export GOBIN="$INSTALL_DIR"

  declare -A tools=(
    ["subfinder"]="github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
    ["amass"]="github.com/owasp-amass/amass/v4/...@master"
    ["assetfinder"]="github.com/tomnomnom/assetfinder@latest"
    ["dnsx"]="github.com/projectdiscovery/dnsx/cmd/dnsx@latest"
    ["httpx"]="github.com/projectdiscovery/httpx/cmd/httpx@latest"
    ["katana"]="github.com/projectdiscovery/katana/cmd/katana@latest"
    ["ffuf"]="github.com/ffuf/ffuf/v2@latest"
    ["dalfox"]="github.com/hahwul/dalfox/v2@latest"
    ["waybackurls"]="github.com/tomnomnom/waybackurls@latest"
    ["gau"]="github.com/lc/gau/v2/cmd/gau@latest"
    ["gospider"]="github.com/jaeles-project/gospider@latest"
    ["hakrawler"]="github.com/hakluke/hakrawler@latest"
    ["nuclei"]="github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
    ["gf"]="github.com/tomnomnom/gf@latest"
  )

  for name in "${!tools[@]}"; do
    local url="${tools[$name]}"
    sub_section "Installing $name..."

    su - "$SUDO_USER_NAME" -c \
      "export GOPATH='$GOPATH'; export GOBIN='$GOBIN'; '$GO_DIR/bin/go' install '$url'" \
      2>&1 | tail -5 || warn "$name build failed — skipping"

    if [ -f "$INSTALL_DIR/$name" ]; then
      chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$INSTALL_DIR/$name"
      ok "$name → $INSTALL_DIR/$name"
    else
      warn "$name binary not found after install"
    fi
  done

  # Nuclei template update
  if [ -f "$INSTALL_DIR/nuclei" ]; then
    sub_section "Updating Nuclei templates..."
    su - "$SUDO_USER_NAME" -c \
      "export PATH='$INSTALL_DIR:$PATH'; nuclei -update-templates" 2>&1 | tail -3 || true
  fi

  # GF patterns
  if [ -f "$INSTALL_DIR/gf" ]; then
    sub_section "Installing GF patterns..."
    mkdir -p "$SUDO_USER_HOME/.gf"
    git clone --depth 1 https://github.com/1ndianl33t/Gf-Patterns.git /tmp/gf-patterns 2>/dev/null || true
    cp /tmp/gf-patterns/*.json "$SUDO_USER_HOME/.gf/" 2>/dev/null || true
    chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$SUDO_USER_HOME/.gf"
    rm -rf /tmp/gf-patterns
    ok "GF patterns installed"
  fi

  chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$GOPATH" 2>/dev/null || true
}

# ── Static Binaries ──────────────────────────────────────────────────────────
install_static() {
  section "STATIC BINARIES"

  local arch="x86_64"
  [ "$(uname -m)" = "aarch64" ] && arch="aarch64"

  # feroxbuster
  sub_section "Installing feroxbuster..."
  local fb_tmp
  fb_tmp=$(mktemp /tmp/feroxbuster.XXXXXX.tar.gz)
  if wget -q --show-progress \
      "https://github.com/epi052/feroxbuster/releases/latest/download/${arch}-linux-feroxbuster.tar.gz" \
      -O "$fb_tmp"; then
    # Extract only the binary, then move — avoids path ambiguity
    tar xzf "$fb_tmp" -C /tmp feroxbuster 2>/dev/null || tar xzf "$fb_tmp" -C /tmp
    mv /tmp/feroxbuster "$INSTALL_DIR/"
    chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$INSTALL_DIR/feroxbuster"
    ok "feroxbuster installed"
  else
    warn "feroxbuster download failed"
  fi
  rm -f "$fb_tmp"

  # x8
  sub_section "Installing x8..."
  local x8_tag
  x8_tag=$(curl -fsSL "https://api.github.com/repos/Sh1Yo/x8/releases/latest" \
    | grep '"tag_name"' | cut -d'"' -f4) || x8_tag=""
  if [ -n "$x8_tag" ]; then
    local x8_tmp
    x8_tmp=$(mktemp /tmp/x8.XXXXXX.gz)
    if wget -q --show-progress \
        "https://github.com/Sh1Yo/x8/releases/download/${x8_tag}/${arch}-linux-x8.gz" \
        -O "$x8_tmp"; then
      gunzip -f "$x8_tmp"
      local x8_bin="${x8_tmp%.gz}"
      chmod +x "$x8_bin"
      mv "$x8_bin" "$INSTALL_DIR/x8"
      chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$INSTALL_DIR/x8"
      ok "x8 installed"
    else
      warn "x8 download failed"
      rm -f "$x8_tmp"
    fi
  else
    warn "Could not resolve x8 release tag"
  fi
}

# ── Compiled from Source ─────────────────────────────────────────────────────
install_compiled() {
  section "COMPILED TOOLS"

  # ── masscan ────────────────────────────────────────────────────────────────
  sub_section "Building masscan from source..."
  local masscan_tmp
  masscan_tmp=$(mktemp -d /tmp/masscan.XXXXXX)
  git clone --depth 1 https://github.com/robertdavidgraham/masscan.git "$masscan_tmp" 2>/dev/null
  make -C "$masscan_tmp" -j"$(nproc)" >/dev/null 2>&1
  cp "$masscan_tmp/bin/masscan" "$INSTALL_DIR/"
  chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$INSTALL_DIR/masscan"
  rm -rf "$masscan_tmp"
  ok "masscan installed"

  # ── nmap ───────────────────────────────────────────────────────────────────
  sub_section "Building nmap from source..."

  if [ -x "$INSTALL_DIR/nmap" ]; then
    info "nmap already installed at $INSTALL_DIR/nmap — skipping"
  else
    local nmap_ver
    nmap_ver=$(curl -fsSL "https://nmap.org/dist/" \
      | grep -oP 'nmap-\K[0-9]+\.[0-9]+(?=\.tar\.bz2)' \
      | sort -V | tail -1) || nmap_ver=""
    [ -z "$nmap_ver" ] && nmap_ver="7.95"
    info "Version: nmap ${nmap_ver}"

    local nmap_tmp
    nmap_tmp=$(mktemp -d /tmp/nmap.XXXXXX)

    info "Downloading nmap-${nmap_ver}.tar.bz2..."
    wget -q --show-progress \
      "https://nmap.org/dist/nmap-${nmap_ver}.tar.bz2" \
      -O "$nmap_tmp/nmap.tar.bz2"

    info "Extracting source..."
    tar -xjf "$nmap_tmp/nmap.tar.bz2" -C "$nmap_tmp" --strip-components=1

    info "Configuring (prefix: ~/.local)..."
    (
      cd "$nmap_tmp"
      ./configure \
        --prefix="$SUDO_USER_HOME/.local" \
        --with-libdnet=included \
        --with-openssl \
        --without-ndiff \
        --without-zenmap \
        --without-nmap-update \
        --mandir="$SUDO_USER_HOME/.local/share/man" \
        2>&1 | tail -8
    )

    info "Compiling nmap (this takes ~1-2 min)..."
    make -C "$nmap_tmp" -j"$(nproc)" 2>&1 | tail -5

    info "Installing nmap to ~/.local/..."
    make -C "$nmap_tmp" install 2>&1 | tail -5
    rm -rf "$nmap_tmp"

    # Fix ownership — make install runs as root
    chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$INSTALL_DIR/nmap"              2>/dev/null || true
    chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$SUDO_USER_HOME/.local/share/nmap" 2>/dev/null || true
    chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$SUDO_USER_HOME/.local/lib/nmap"   2>/dev/null || true

    # Cap raw sockets so SYN scans work without re-running as root
    if command -v setcap &>/dev/null; then
      setcap cap_net_raw,cap_net_admin+eip "$INSTALL_DIR/nmap" 2>/dev/null \
        && ok "  capabilities set (cap_net_raw,cap_net_admin)" \
        || warn "  setcap failed — SYN scans will need sudo"
    else
      warn "  setcap not found — SYN scans will need sudo"
    fi

    ok "nmap ${nmap_ver} installed → $INSTALL_DIR/nmap"
  fi
}

# ── Python Tools ─────────────────────────────────────────────────────────────
install_python() {
  section "PYTHON TOOLS"

  su - "$SUDO_USER_NAME" -c "mkdir -p ~/.local/bin"

  sub_section "Ensuring pipx..."
  # On Arch: python-pipx is already installed system-wide via pacman — just use it.
  # On Debian: pipx is installed via apt (Debian 12+) or falls back to pip --user.
  if ! su - "$SUDO_USER_NAME" -c "command -v pipx" &>/dev/null; then
    info "pipx not found on PATH — installing via pip --user..."
    su - "$SUDO_USER_NAME" -c \
      "python3 -m pip install --user pipx" 2>/dev/null \
    || su - "$SUDO_USER_NAME" -c \
      "python3 -m pip install --user --break-system-packages pipx" \
    || warn "pipx install failed"
  fi

  # ensurepath is non-fatal; it just adds ~/.local/bin to the shell config
  su - "$SUDO_USER_NAME" -c \
    "export PATH=\"\$HOME/.local/bin:\$PATH\"; python3 -m pipx ensurepath" \
    2>/dev/null || true

  sub_section "Installing arjun via pipx..."
  su - "$SUDO_USER_NAME" -c \
    "export PATH=\"\$HOME/.local/bin:\$PATH\"; pipx install arjun --force" 2>/dev/null \
  || su - "$SUDO_USER_NAME" -c \
    "export PATH=\"\$HOME/.local/bin:\$PATH\"; python3 -m pipx install arjun --force" \
  || warn "arjun install failed"

  if [ -f "$SUDO_USER_HOME/.local/bin/arjun" ]; then
    chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$SUDO_USER_HOME/.local/bin/arjun"
    ok "arjun → $SUDO_USER_HOME/.local/bin/arjun"
  else
    warn "arjun binary not found after install"
  fi

  sub_section "Installing Python libraries to user site-packages..."
  local pkgs="termcolor jsbeautifier pycryptodomex lxml colorama requests"
  su - "$SUDO_USER_NAME" -c "python3 -m pip install --user $pkgs" 2>/dev/null \
  || su - "$SUDO_USER_NAME" -c \
    "python3 -m pip install --user --break-system-packages $pkgs" \
  || warn "Some Python packages failed"

  ok "Python tools installed to ~/.local/"
}

# ── Git-Based Tools ──────────────────────────────────────────────────────────
#
# DESIGN: every Python tool gets its own venv at $OPT_DIR/<name>/.venv/
# so dependency installs are fully isolated — no system Python pollution,
# no PEP 668 conflicts, and no runtime "module not found" errors.
#
# install_py_tool <name> <user/repo> <entrypoint>
#   entrypoint can be:
#     "some/script.py"   → run with venv python3
#     "console:<cmd>"    → run installed console-script from venv/bin/<cmd>
#                          (for packages with setup.py / pyproject.toml)
#
install_git_tools() {
  section "GIT-BASED TOOLS"

  install_py_tool() {
    local name="$1"
    local repo="$2"
    local entrypoint="$3"

    sub_section "Installing $name..."

    local tool_dir="$OPT_DIR/$name"
    local venv_dir="$tool_dir/.venv"
    local wrapper="$INSTALL_DIR/$name"
    local pip="$venv_dir/bin/pip"
    local python="$venv_dir/bin/python3"

    # ── 1. Clone ──────────────────────────────────────────────────────────
    rm -rf "$tool_dir"
    git clone --depth 1 "https://github.com/$repo.git" "$tool_dir" 2>&1 | tail -3

    # Clone runs as root -- hand ownership to the real user immediately so
    # the venv step (which runs as that user) can write into the directory.
    chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$tool_dir"
    # ── 2. Create isolated venv (run as the real user) ────────────────────
    su - "$SUDO_USER_NAME" -c "python3 -m venv '$venv_dir' --clear" 2>&1 | tail -2

    # ── 3. Upgrade pip silently ────────────────────────────────────────────
    su - "$SUDO_USER_NAME" -c "'$pip' install --upgrade pip --quiet" 2>/dev/null || true

    # ── 4. Install the package itself (if it has a build descriptor) ───────
    if [ -f "$tool_dir/setup.py" ] || \
       [ -f "$tool_dir/pyproject.toml" ] || \
       [ -f "$tool_dir/setup.cfg" ]; then
      info "  pip install -e (package) ..."
      su - "$SUDO_USER_NAME" -c \
        "'$pip' install -e '$tool_dir' --quiet 2>&1 | tail -3" \
        || warn "  package install had errors for $name"
    fi

    # ── 5. Install requirements.txt if present ─────────────────────────────
    if [ -f "$tool_dir/requirements.txt" ]; then
      info "  pip install -r requirements.txt ..."
      su - "$SUDO_USER_NAME" -c \
        "'$pip' install -r '$tool_dir/requirements.txt' --quiet 2>&1 | tail -3" \
        || warn "  requirements install had errors for $name"
    fi

    # Fix ownership of the whole tool dir (venv was created as the user but
    # the clone was done as root)
    chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$tool_dir"

    # ── 6. Write wrapper ───────────────────────────────────────────────────
    if [[ "$entrypoint" == console:* ]]; then
      local cmd="${entrypoint#console:}"
      printf '#!/bin/bash\nexec "%s/bin/%s" "$@"\n' \
        "$venv_dir" "$cmd" > "$wrapper"
    elif [[ "$entrypoint" == *.py ]]; then
      printf '#!/bin/bash\nexec "%s" "%s/%s" "$@"\n' \
        "$python" "$tool_dir" "$entrypoint" > "$wrapper"
    fi

    chmod +x "$wrapper"
    chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$wrapper"
    ok "$name → $wrapper  (venv: $venv_dir)"
  }

  # ── Tool list ─────────────────────────────────────────────────────────────
  #
  # sqlmap      — bundles its own libs; venv is still used so any future
  #               dep change doesn't touch system Python.
  install_py_tool "sqlmap"       "sqlmapproject/sqlmap"      "sqlmap.py"

  # ghauri      — has setup.py + requirements.txt; the "console:ghauri"
  #               mode uses the entry-point installed by pip install -e .
  #               which correctly resolves all internal imports + ua_generator.
  install_py_tool "ghauri"       "r0oth3x49/ghauri"          "console:ghauri"

  # gitdorker   — plain script + requirements.txt
  install_py_tool "gitdorker"    "obheda12/GitDorker"        "GitDorker.py"

  # paramspider — installable package (setup.py); provides "paramspider"
  #               console script → no __main__ headaches.
  install_py_tool "paramspider"  "devanshbatham/ParamSpider" "console:paramspider"

  # wafw00f     — installable package (setup.py); entrypoint is the
  #               console script, NOT wafw00f.py which doesn't exist at root.
  install_py_tool "wafw00f"      "EnableSecurity/wafw00f"    "console:wafw00f"

  # linkfinder  — plain script + requirements.txt
  install_py_tool "linkfinder"   "GerbenJavado/LinkFinder"   "linkfinder.py"

  # xsstrike    — plain script + requirements.txt; deps (fuzzywuzzy etc.)
  #               are installed into the venv so the runtime self-installer
  #               is never triggered.
  install_py_tool "xsstrike"     "s0md3v/XSStrike"           "xsstrike.py"

  # jwt-tool    — plain script + requirements.txt
  install_py_tool "jwt-tool"     "ticarpi/jwt_tool"          "jwt_tool.py"

  # secretfinder — plain script + requirements.txt (requests_file etc.)
  install_py_tool "secretfinder" "m4ll0k/SecretFinder"       "SecretFinder.py"

  # ── nikto (Perl — no venv needed) ────────────────────────────────────────
  sub_section "Installing nikto..."
  rm -rf "${OPT_DIR:?}/nikto"
  git clone --depth 1 "https://github.com/sullo/nikto.git" "$OPT_DIR/nikto" 2>&1 | tail -3
  chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$OPT_DIR/nikto"
  printf '#!/bin/bash\nexec perl "%s/program/nikto.pl" "$@"\n' \
    "$OPT_DIR/nikto" > "$INSTALL_DIR/nikto"
  chmod +x "$INSTALL_DIR/nikto"
  chown "$SUDO_USER_NAME:$SUDO_USER_NAME" "$INSTALL_DIR/nikto"
  ok "nikto → $INSTALL_DIR/nikto"
}

# ── Wordlists ────────────────────────────────────────────────────────────────
install_wordlists() {
  section "WORDLISTS"

  sub_section "SecLists..."
  if [ ! -d "$WORDLIST_DIR/SecLists" ]; then
    git clone --depth 1 https://github.com/danielmiessler/SecLists.git \
      "$WORDLIST_DIR/SecLists" 2>&1 | tail -5
  else
    info "SecLists exists, pulling updates..."
    git -C "$WORDLIST_DIR/SecLists" pull --depth 1 2>&1 | tail -3
  fi
  chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$WORDLIST_DIR/SecLists"
  ok "SecLists ready"

  sub_section "PayloadsAllTheThings..."
  if [ ! -d "$WORDLIST_DIR/PayloadsAllTheThings" ]; then
    git clone --depth 1 https://github.com/swisskyrepo/PayloadsAllTheThings.git \
      "$WORDLIST_DIR/PayloadsAllTheThings" 2>&1 | tail -5
    chown -R "$SUDO_USER_NAME:$SUDO_USER_NAME" "$WORDLIST_DIR/PayloadsAllTheThings"
  fi
  ok "PayloadsAllTheThings ready"
}

# ── Summary ──────────────────────────────────────────────────────────────────
show_summary() {
  section "INSTALLATION COMPLETE"

  local total_size
  total_size=$(du -sh "$SUDO_USER_HOME/.local" 2>/dev/null | cut -f1)

  echo -e "${GREEN}✓${NC} Installation successful!"
  echo ""
  echo -e "${BOLD}Layout (everything inside ~/.local/):${NC}"
  echo -e "  ├── bin/           ${CYAN}${INSTALL_DIR}${NC}  — all tool binaries & wrappers"
  echo -e "  ├── opt/           ${CYAN}${OPT_DIR}${NC}  — cloned git repos"
  echo -e "  ├── go/            ${CYAN}${GO_DIR}${NC}  — Go compiler"
  echo -e "  ├── go_cache/      ${CYAN}${GO_CACHE}${NC}  — Go module cache"
  echo -e "  └── share/wordlists ${CYAN}${WORDLIST_DIR}${NC}"
  echo ""
  echo -e "  Total size: ${CYAN}${total_size}${NC}"
  echo ""

  echo -e "${BOLD}To uninstall, run:${NC}"
  echo -e "  ${YELLOW}./uninstall.sh${NC}"
  echo ""
  echo "  (The script will prompt for sudo password when needed for go_cache)"
  echo ""

  echo -e "${BOLD}Activate PATH in your current shell:${NC}"
  echo -e "  ${YELLOW}source ~/.zshrc${NC}   or   ${YELLOW}source ~/.bashrc${NC}"
  echo ""

  echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}Happy Reconnaissance!${NC}"
  echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  show_banner

  if [ "$DISTRO" = "unknown" ]; then
    err "Could not detect distro. Only Debian/Ubuntu and Arch Linux are supported."
    exit 1
  fi

  info "Detected: ${BOLD}${DISTRO}${NC}-based system"
  info "Installing for user: ${BOLD}${SUDO_USER_NAME}${NC}"
  info "Install root: ${BOLD}${SUDO_USER_HOME}/.local/${NC}"
  echo ""

  check_aliases
  setup_path_auto
  install_sys_deps
  install_go
  install_go_tools
  install_static
  install_compiled
  install_python
  install_git_tools
  install_wordlists
  show_summary
}

main
