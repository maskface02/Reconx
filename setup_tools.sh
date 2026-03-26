#!/bin/bash
#
# ReconX Unified Setup Script
# https://github.com/maskface02/Reconx
#

set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── Configuration ────────────────────────────────────────────────────────────
IS_ROOT=false
[[ $EUID -eq 0 ]] && IS_ROOT=true

if $IS_ROOT; then
    INSTALL_DIR="/usr/local/bin"
    OPT_DIR="/opt"
    WORDLIST_DIR="/usr/share/wordlists"
    GO_INSTALL_DIR="/usr/local"
else
    INSTALL_DIR="$HOME/.local/bin"
    OPT_DIR="$HOME/.local/opt"
    WORDLIST_DIR="$HOME/.local/share/wordlists"
    GO_INSTALL_DIR="$HOME/.local"
    mkdir -p "$INSTALL_DIR" "$OPT_DIR" "$WORDLIST_DIR"
fi

GO_VERSION="1.22.0"
ARCH=$(uname -m)
case $ARCH in
    x86_64) GO_ARCH="amd64" ;;
    aarch64|arm64) GO_ARCH="arm64" ;;
    *) GO_ARCH="amd64" ;;
esac

# Package manager detection
PKG_MANAGER=""
PKG_UPDATE=""
PKG_INSTALL=""

# Counters
declare -i INSTALLED=0
declare -i SKIPPED=0
declare -i FAILED=0

# ── Logging ──────────────────────────────────────────────────────────────────
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; INSTALLED=$((INSTALLED + 1)); }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; SKIPPED=$((SKIPPED + 1)); }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; FAILED=$((FAILED + 1)); }
log_section() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

# ── Helpers ──────────────────────────────────────────────────────────────────
command_exists() { command -v "$1" >/dev/null 2>&1; }

python_pkg_installed() {
    python3 -c "import $1" 2>/dev/null
}

is_arch_based() {
    [[ "$PKG_MANAGER" == "pacman" ]]
}

get_pip_flags() {
    if [ -f "/usr/lib/python3.11/EXTERNALLY-MANAGED" ] || \
       [ -f "/usr/lib/python3.12/EXTERNALLY-MANAGED" ] || \
       [ -f "/usr/lib/python3.13/EXTERNALLY-MANAGED" ]; then
        echo "--break-system-packages"
    else
        echo ""
    fi
}

pip_install() {
    local package=$1
    local flags=$(get_pip_flags)
    
    if python3 -m pip install --quiet $flags "$package" 2>/dev/null; then
        return 0
    fi
    
    # If pip fails on Arch, try pacman for common python packages
    if is_arch_based && $IS_ROOT; then
        local pacman_pkg=""
        case "$package" in
            termcolor) pacman_pkg="python-termcolor" ;;
            jsbeautifier) pacman_pkg="python-jsbeautifier" ;;
            pycryptodomex) pacman_pkg="python-pycryptodomex" ;;
            lxml) pacman_pkg="python-lxml" ;;
            requests) pacman_pkg="python-requests" ;;
            colorama) pacman_pkg="python-colorama" ;;
            pipx) pacman_pkg="python-pipx" ;;
        esac
        
        if [ -n "$pacman_pkg" ]; then
            log_info "Trying pacman for $pacman_pkg..."
            if pacman -S --noconfirm --needed "$pacman_pkg" 2>/dev/null; then
                return 0
            fi
        fi
    fi
    
    return 1
}

# ── Package Manager Detection ───────────────────────────────────────────────
detect_pkg_manager() {
    if command_exists apt-get; then
        PKG_MANAGER="apt-get"
        PKG_UPDATE="apt-get update -qq"
        PKG_INSTALL="apt-get install -y -qq"
    elif command_exists pacman; then
        PKG_MANAGER="pacman"
        PKG_UPDATE="pacman -Sy --noconfirm"
        PKG_INSTALL="pacman -S --noconfirm --needed"
    elif command_exists dnf; then
        PKG_MANAGER="dnf"
        PKG_UPDATE="dnf check-update || true"
        PKG_INSTALL="dnf install -y"
    elif command_exists yum; then
        PKG_MANAGER="yum"
        PKG_UPDATE="yum check-update || true"
        PKG_INSTALL="yum install -y"
    elif command_exists brew; then
        PKG_MANAGER="brew"
        PKG_UPDATE="brew update"
        PKG_INSTALL="brew install"
    elif command_exists zypper; then
        PKG_MANAGER="zypper"
        PKG_UPDATE="zypper refresh"
        PKG_INSTALL="zypper install -y"
    fi
}

# ── Requirement Installation ────────────────────────────────────────────────
install_requirement() {
    local tool=$1
    local package=${2:-$1}
    
    log_info "Installing $tool..."
    
    if [ -z "$PKG_MANAGER" ]; then
        log_error "No supported package manager found. Please install $tool manually."
        return 1
    fi
    
    # Handle special cases for package names
    case $tool in
        pip3)
            case $PKG_MANAGER in
                apt-get) package="python3-pip" ;;
                yum|dnf) package="python3-pip" ;;
                pacman) package="python-pip" ;;
                brew) package="python3" ;;
            esac
            ;;
        python3)
            case $PKG_MANAGER in
                pacman) package="python" ;;
                *) package="python3" ;;
            esac
            ;;
        pipx)
            case $PKG_MANAGER in
                apt-get) package="pipx" ;;
                pacman) package="python-pipx" ;;
                yum|dnf) package="pipx" ;;
                brew) package="pipx" ;;
            esac
            ;;
    esac
    
    if $IS_ROOT || [ "$PKG_MANAGER" = "brew" ]; then
        $PKG_INSTALL $package 2>/dev/null || {
            log_error "Failed to install $tool via $PKG_MANAGER"
            return 1
        }
    else
        log_error "Cannot install $tool without sudo. Run with sudo or install manually:"
        echo "  sudo $PKG_INSTALL $package"
        return 1
    fi
    
    if command_exists "$tool"; then
        log_success "$tool installed successfully"
        return 0
    else
        log_error "$tool installation verification failed"
        return 1
    fi
}

check_requirements() {
    log_section "Checking Requirements"
    
    detect_pkg_manager
    if [ -n "$PKG_MANAGER" ]; then
        log_info "Package manager detected: $PKG_MANAGER"
        log_info "Updating package database..."
        $PKG_UPDATE 2>/dev/null || true
    else
        log_warning "No standard package manager found"
    fi
    
    # Added pipx to required tools
    local required_tools=("git" "python3" "pip3" "pipx" "curl" "wget")
    local all_good=true
    
    for tool in "${required_tools[@]}"; do
        if command_exists "$tool"; then
            log_success "$tool found"
        else
            log_warning "$tool not found - attempting installation..."
            if install_requirement "$tool"; then
                : # Success
            else
                all_good=false
            fi
        fi
    done
    
    # Ensure pipx path is set up
    if command_exists pipx; then
        pipx ensurepath 2>/dev/null || true
    fi
    
    if ! $all_good; then
        echo ""
        log_error "Some requirements could not be installed. Please install them manually and retry."
        exit 1
    fi
}

detect_system() {
    local os_name="Unknown"
    local os_version="unknown"
    
    if [ -f /etc/os-release ]; then
        while IFS='=' read -r key value; do
            case "$key" in
                NAME) os_name="${value//\"/}" ;;
                VERSION_ID) os_version="${value//\"/}" ;;
            esac
        done < /etc/os-release
        
        if [ -z "$os_version" ] || [ "$os_version" = "unknown" ]; then
            os_version="rolling"
        fi
        
        log_info "Detected: $os_name $os_version ($ARCH)"
    else
        log_info "Detected: $(uname -s) $(uname -r) ($ARCH)"
    fi
}

# ── System Dependencies ──────────────────────────────────────────────────────
install_system_deps() {
    $IS_ROOT || { log_warning "Skipping system packages (requires sudo)"; return 0; }
    
    log_section "Installing System Dependencies"
    
    local packages=""
    case $PKG_MANAGER in
        apt-get)
            packages="build-essential libpcap-dev libssl-dev zlib1g-dev libxml2-dev libxslt1-dev libffi-dev libsqlite3-dev libcurl4-openssl-dev libjpeg-dev libpng-dev pkg-config cmake unzip jq perl libnet-ssleay-perl libauthen-pam-perl libio-pty-perl apt-utils python3-tk chromium chromium-driver libjson-perl libxml-writer-perl pipx"
            ;;
        pacman)
            packages="base-devel libpcap openssl zlib libxml2 libxslt libffi sqlite curl libjpeg-turbo libpng pkgconf cmake unzip jq perl perl-net-ssleay tk chromium python-pipx"
            ;;
        yum|dnf)
            packages="gcc gcc-c++ make libpcap-devel openssl-devel zlib-devel libxml2-devel libxslt-devel libffi-devel sqlite-devel libcurl-devel libjpeg-devel libpng-devel pkgconfig cmake unzip jq perl perl-Net-SSLeay perl-Authen-Pam perl-IO-Tty python3-tkinter chromium pipx"
            ;;
        *)
            log_warning "Unknown package manager, skipping system dependencies"
            return 0
            ;;
    esac
    
    $PKG_INSTALL $packages 2>/dev/null && log_success "System dependencies installed" || \
        log_warning "Some system packages failed to install (non-critical)"
}

# ── Go Installation ─────────────────────────────────────────────────────────
install_go() {
    log_section "Installing Go"
    
    if command_exists go; then
        local current=$(go version | awk '{print $3}' | sed 's/go//')
        log_success "Go $current already installed"
        export PATH="$PATH:$GO_INSTALL_DIR/go/bin:$HOME/go/bin"
        return 0
    fi
    
    $IS_ROOT || { log_error "Go requires sudo to install system-wide"; return 1; }
    
    log_info "Downloading Go $GO_VERSION..."
    cd /tmp
    wget -q --show-progress "https://go.dev/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
    rm -rf "${GO_INSTALL_DIR}/go"
    tar -C "${GO_INSTALL_DIR}" -xzf "go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
    rm "go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
    
    export PATH="$PATH:$GO_INSTALL_DIR/go/bin:$HOME/go/bin"
    echo "export PATH=\$PATH:$GO_INSTALL_DIR/go/bin:\$HOME/go/bin" > /etc/profile.d/go.sh
    chmod +x /etc/profile.d/go.sh
    
    command_exists go && log_success "Go $(go version | awk '{print $3}') installed" || log_error "Go installation failed"
}

install_go_tool() {
    local binary=$1
    local src="$HOME/go/bin/$binary"
    
    if [ -f "$src" ]; then
        cp "$src" "$INSTALL_DIR/" 2>/dev/null || {
            mkdir -p "$INSTALL_DIR"
            cp "$src" "$INSTALL_DIR/" 2>/dev/null || {
                log_warning "Could not copy $binary to $INSTALL_DIR, using ~/go/bin/"
                return 0
            }
        }
        log_success "$binary installed"
    else
        log_error "$binary binary not found"
    fi
}

install_go_tools() {
    log_section "Installing Go-Based Tools"
    export PATH="$PATH:$GO_INSTALL_DIR/go/bin:$HOME/go/bin"
    
    declare -A tools=(
        ["github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"]="subfinder"
        ["github.com/owasp-amass/amass/v4/...@master"]="amass"
        ["github.com/tomnomnom/assetfinder@latest"]="assetfinder"
        ["github.com/projectdiscovery/dnsx/cmd/dnsx@latest"]="dnsx"
        ["github.com/projectdiscovery/httpx/cmd/httpx@latest"]="httpx"
        ["github.com/projectdiscovery/katana/cmd/katana@latest"]="katana"
        ["github.com/ffuf/ffuf@latest"]="ffuf"
        ["github.com/hahwul/dalfox/v2@latest"]="dalfox"
        ["github.com/tomnomnom/waybackurls@latest"]="waybackurls"
        ["github.com/lc/gau/v2/cmd/gau@latest"]="gau"
        ["github.com/jaeles-project/gospider@latest"]="gospider"
        ["github.com/hakluke/hakrawler@latest"]="hakrawler"
        ["github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"]="nuclei"
        ["github.com/tomnomnom/gf@latest"]="gf"
    )
    
    for url in "${!tools[@]}"; do
        local name=${tools[$url]}
        log_info "Installing $name..."
        if go install -v "$url" 2>/dev/null; then
            install_go_tool "$name"
        else
            log_error "$name installation failed"
        fi
    done
    
    if command_exists nuclei; then
        nuclei -update-templates 2>/dev/null || true
    fi
    
    if [ -f "$INSTALL_DIR/gf" ] || [ -f "$HOME/go/bin/gf" ]; then
        mkdir -p ~/.gf
        rm -rf /tmp/Gf-Patterns
        git clone --depth 1 https://github.com/1ndianl33t/Gf-Patterns.git /tmp/Gf-Patterns 2>/dev/null || true
        cp /tmp/Gf-Patterns/*.json ~/.gf/ 2>/dev/null || true
        rm -rf /tmp/Gf-Patterns
    fi
}

# ── Compiled Tools ──────────────────────────────────────────────────────────
install_nmap() {
    if command_exists nmap; then
        log_warning "nmap already installed"
        return
    fi
    
    $IS_ROOT || { log_warning "nmap requires sudo"; return; }
    
    log_info "Installing nmap..."
    
    case $PKG_MANAGER in
        pacman)
            if pacman -S --noconfirm --needed nmap 2>/dev/null; then
                log_success "nmap installed"
            else
                log_warning "Retrying with overwrite flag (handling lua conflicts)..."
                pacman -S --noconfirm --needed --overwrite '*' nmap 2>/dev/null && \
                    log_success "nmap installed (conflicts resolved)" || \
                    log_error "nmap installation failed"
            fi
            ;;
        apt-get)
            apt-get install -y -qq nmap 2>/dev/null && \
                log_success "nmap installed" || \
                log_error "nmap failed"
            ;;
        yum|dnf)
            $PKG_INSTALL nmap 2>/dev/null && \
                log_success "nmap installed" || \
                log_error "nmap failed"
            ;;
        *)
            log_error "Unsupported package manager for nmap installation"
            return
            ;;
    esac
}

install_masscan() {
    if command_exists masscan; then
        log_warning "masscan already installed"
        return
    fi
    
    log_info "Building masscan..."
    rm -rf /tmp/masscan
    git clone --depth 1 https://github.com/robertdavidgraham/masscan.git /tmp/masscan 2>/dev/null || {
        log_error "Failed to clone masscan"
        return
    }
    
    cd /tmp/masscan
    make -j$(nproc) 2>/dev/null || make
    cp bin/masscan "$INSTALL_DIR/" 2>/dev/null || {
        log_error "Failed to install masscan (permission?)"
        return
    }
    rm -rf /tmp/masscan
    log_success "masscan installed"
}

install_feroxbuster() {
    if command_exists feroxbuster; then
        log_warning "feroxbuster already installed"
        return
    fi
    
    cd /tmp
    case $ARCH in
        x86_64) local file="x86_64-linux-feroxbuster.tar.gz" ;;
        aarch64|arm64) local file="aarch64-linux-feroxbuster.zip" ;;
        *) log_error "Unsupported arch for feroxbuster: $ARCH"; return ;;
    esac
    
    log_info "Downloading feroxbuster..."
    curl -fsSL "https://github.com/epi052/feroxbuster/releases/latest/download/${file}" -o "$file" 2>/dev/null || {
        log_error "Failed to download feroxbuster"
        return
    }
    
    if [[ "$file" == *.tar.gz ]]; then
        tar xzf "$file"
    else
        unzip -o "$file"
    fi
    
    chmod +x feroxbuster
    mv feroxbuster "$INSTALL_DIR/" 2>/dev/null || {
        log_error "Failed to install feroxbuster"
        rm -f "$file" feroxbuster
        return
    }
    rm -f "$file"
    log_success "feroxbuster installed"
}

install_x8() {
    if command_exists x8; then
        log_warning "x8 already installed"
        return
    fi
    
    cd /tmp
    case $ARCH in
        x86_64) local arch="x86_64" ;;
        aarch64) local arch="aarch64" ;;
        *) log_error "Unsupported arch for x8: $ARCH"; return ;;
    esac
    
    log_info "Fetching x8 release..."
    local tag=$(curl -s "https://api.github.com/repos/Sh1Yo/x8/releases/latest" | grep -o '"tag_name": "[^"]*"' | cut -d'"' -f4)
    [ -z "$tag" ] && { log_error "Could not get x8 version"; return; }
    
    local file="${arch}-linux-x8.gz"
    curl -fsSL "https://github.com/Sh1Yo/x8/releases/download/${tag}/${file}" -o "$file" 2>/dev/null || {
        log_error "Failed to download x8"
        return
    }
    
    gunzip -f "$file"
    local bin="${arch}-linux-x8"
    [ -f "$bin" ] || bin="x8"
    
    chmod +x "$bin"
    mv "$bin" "$INSTALL_DIR/x8" 2>/dev/null || {
        log_error "Failed to install x8"
        return
    }
    log_success "x8 installed"
}

install_compiled_tools() {
    log_section "Installing Compiled Tools"
    install_nmap
    install_masscan
    install_feroxbuster
    install_x8
}

# ── Git-Based Tools ─────────────────────────────────────────────────────────
git_clone_or_update() {
    local repo=$1
    local dest=$2
    local name=$(basename "$dest")
    
    if [ -d "$dest/.git" ]; then
        log_info "Updating $name..."
        cd "$dest" && git pull --depth 1 2>/dev/null || true
    else
        log_info "Cloning $name..."
        rm -rf "$dest"
        git clone --depth 1 "$repo" "$dest" 2>/dev/null || {
            log_error "Failed to clone $name"
            return 1
        }
    fi
}

create_wrapper() {
    local name=$1
    local cmd=$2
    local file="$INSTALL_DIR/$name"
    
    echo "#!/bin/bash" > "$file"
    echo "$cmd \"\$@\"" >> "$file"
    chmod +x "$file"
}

install_sqlmap() {
    git_clone_or_update "https://github.com/sqlmapproject/sqlmap.git" "$OPT_DIR/sqlmap"
    create_wrapper "sqlmap" "python3 $OPT_DIR/sqlmap/sqlmap.py"
    log_success "sqlmap installed"
}

install_paramspider() {
    git_clone_or_update "https://github.com/devanshbatham/ParamSpider.git" "$OPT_DIR/ParamSpider"
    cd "$OPT_DIR/ParamSpider"
    pip3 install -e . 2>/dev/null || pip_install "-r requirements.txt" || true
    
    cat > "$INSTALL_DIR/paramspider" << 'EOF'
#!/bin/bash
cd /opt/ParamSpider && python3 -m paramspider "$@"
EOF
    chmod +x "$INSTALL_DIR/paramspider"
    log_success "paramspider installed"
}

install_secretfinder() {
    git_clone_or_update "https://github.com/m4ll0k/SecretFinder.git" "$OPT_DIR/SecretFinder"
    cd "$OPT_DIR/SecretFinder"
    pip_install "-r requirements.txt" || true
    create_wrapper "secretfinder" "python3 $OPT_DIR/SecretFinder/SecretFinder.py"
    log_success "secretfinder installed"
}

install_wafw00f() {
    git_clone_or_update "https://github.com/EnableSecurity/wafw00f.git" "$OPT_DIR/wafw00f"
    cd "$OPT_DIR/wafw00f"
    pip3 install -r requirements.txt 2>/dev/null || pip_install "-r requirements.txt" || true
    
    cat > "$INSTALL_DIR/wafw00f" << 'EOF'
#!/bin/bash
cd /opt/wafw00f && python3 -W ignore ./wafw00f.py "$@"
EOF
    chmod +x "$INSTALL_DIR/wafw00f"
    log_success "wafw00f installed"
}

install_nikto() {
    git_clone_or_update "https://github.com/sullo/nikto.git" "$OPT_DIR/nikto"
    create_wrapper "nikto" "perl $OPT_DIR/nikto/program/nikto.pl"
    log_success "nikto installed"
}

install_linkfinder() {
    git_clone_or_update "https://github.com/GerbenJavado/LinkFinder.git" "$OPT_DIR/LinkFinder"
    cd "$OPT_DIR/LinkFinder"
    pip_install "-r requirements.txt" || true
    create_wrapper "linkfinder" "python3 $OPT_DIR/LinkFinder/linkfinder.py"
    log_success "linkfinder installed"
}

install_xsstrike() {
    git_clone_or_update "https://github.com/s0md3v/XSStrike.git" "$OPT_DIR/XSStrike"
    cd "$OPT_DIR/XSStrike"
    pip_install "-r requirements.txt" || true
    create_wrapper "xsstrike" "python3 $OPT_DIR/XSStrike/xsstrike.py"
    log_success "xsstrike installed"
}

install_jwt_tool() {
    git_clone_or_update "https://github.com/ticarpi/jwt_tool.git" "$OPT_DIR/jwt_tool"
    cd "$OPT_DIR/jwt_tool"
    pip_install "-r requirements.txt" || true
    create_wrapper "jwt-tool" "python3 $OPT_DIR/jwt_tool/jwt_tool.py"
    log_success "jwt-tool installed"
}

install_ghauri() {
    git_clone_or_update "https://github.com/r0oth3x49/ghauri.git" "$OPT_DIR/ghauri"
    cd "$OPT_DIR/ghauri"
    pip3 install -q --upgrade setuptools 2>/dev/null || true
    pip_install "-r requirements.txt" || true
    pip_install "'urllib3<2.0' 'charset-normalizer<3.0'" || true
    
    cat > "$INSTALL_DIR/ghauri" << 'EOF'
#!/bin/bash
export PYTHONWARNINGS="ignore"
export PYTHONDONTWRITEBYTECODE=1
python3 -W ignore -c "
import sys
sys.path.insert(0, '/opt/ghauri')
from ghauri.scripts.ghauri import main
if __name__ == '__main__':
    main()
" "$@"
EOF
    chmod +x "$INSTALL_DIR/ghauri"
    log_success "ghauri installed"
}

install_gitdorker() {
    git_clone_or_update "https://github.com/obheda12/GitDorker.git" "$OPT_DIR/GitDorker"
    cd "$OPT_DIR/GitDorker"
    pip_install "-r requirements.txt" || true
    
    cat > "$INSTALL_DIR/gitdorker" << 'EOF'
#!/bin/bash
python3 -W ignore /opt/GitDorker/GitDorker.py "$@"
EOF
    chmod +x "$INSTALL_DIR/gitdorker"
    log_success "gitdorker installed"
}

install_git_tools() {
    log_section "Installing Git-Based Tools"
    install_sqlmap
    install_paramspider
    install_secretfinder
    install_wafw00f
    install_nikto
    install_linkfinder
    install_xsstrike
    install_jwt_tool
    install_ghauri
    install_gitdorker
}

# ── Python Tools ────────────────────────────────────────────────────────────
install_python_deps() {
    log_section "Installing Python Dependencies"
    
    pip_install "--upgrade pip" || true
    
    if is_arch_based && $IS_ROOT; then
        log_info "Arch detected: Using pacman for Python packages..."
        local arch_python_pkgs="python-termcolor python-jsbeautifier python-pycryptodomex python-lxml python-requests python-colorama"
        pacman -S --noconfirm --needed $arch_python_pkgs 2>/dev/null && \
            log_success "Python packages installed via pacman" || \
            log_warning "Some packages not in repos, falling back to pip..."
    fi
    
    local deps=(
        "termcolor:termcolor"
        "jsbeautifier:jsbeautifier"
        "pycryptodomex:Cryptodome"
        "lxml:lxml"
        "requests:requests"
        "colorama:colorama"
    )
    
    for item in "${deps[@]}"; do
        local pkg=${item%%:*}
        local mod=${item##*:}
        
        if python_pkg_installed "$mod"; then
            log_warning "$pkg already installed"
        else
            log_info "Installing $pkg..."
            pip_install "$pkg" && log_success "$pkg installed" || log_error "$pkg failed"
        fi
    done
}

# Updated install_arjun using pipx
install_arjun() {
    log_section "Installing Arjun (via pipx)"
    
    if command_exists arjun; then
        log_warning "arjun already installed"
        return
    fi
    
    # Ensure pipx is installed first
    if ! command_exists pipx; then
        log_warning "pipx not found, attempting to install..."
        if install_requirement "pipx"; then
            pipx ensurepath 2>/dev/null || true
            export PATH="$HOME/.local/bin:$PATH"
        else
            log_error "Cannot install arjun without pipx"
            return
        fi
    fi
    
    # Install arjun via pipx (use user's directory even with sudo)
    log_info "Installing arjun via pipx..."
    if PIPX_HOME="/home/$SUDO_USER/.local/share/pipx" \
       PIPX_BIN_DIR="/home/$SUDO_USER/.local/bin" \
       pipx install arjun 2>/dev/null; then
        log_success "arjun installed via pipx"
        
        # Create symlink in INSTALL_DIR if it's not in PATH
        if [ ! -f "$INSTALL_DIR/arjun" ] && [ -f "/home/$SUDO_USER/.local/bin/arjun" ]; then
            ln -sf "/home/$SUDO_USER/.local/bin/arjun" "$INSTALL_DIR/arjun" 2>/dev/null || true
        fi
    else
        log_error "arjun installation via pipx failed"
    fi
}

# ── Wordlists ───────────────────────────────────────────────────────────────
install_wordlists() {
    log_section "Installing Wordlists"
    mkdir -p "$WORDLIST_DIR"
    
    if [ -d "$WORDLIST_DIR/SecLists/.git" ]; then
        cd "$WORDLIST_DIR/SecLists" && git pull --depth 1 2>/dev/null || true
        log_success "SecLists updated"
    else
        git clone --depth 1 https://github.com/danielmiessler/SecLists.git "$WORDLIST_DIR/SecLists" 2>/dev/null && \
            log_success "SecLists installed" || log_warning "SecLists clone failed"
    fi
    
    if [ ! -d "$WORDLIST_DIR/PayloadsAllTheThings" ]; then
        git clone --depth 1 https://github.com/swisskyrepo/PayloadsAllTheThings.git "$WORDLIST_DIR/PayloadsAllTheThings" 2>/dev/null && \
            log_success "PayloadsAllTheThings installed" || log_warning "PayloadsAllTheThings clone failed"
    fi
}

# ── Main ────────────────────────────────────────────────────────────────────
print_banner() {
    echo -e "${GREEN}"
    echo '    ____                      __   __'
    echo '   |  _ \ ___  ___ ___  _ __ / /\ / /'
    echo '   | |_) / _ \/ __/ _ \| '"'\\'"'_ \ \/  \/ /'
    echo '   |  _ <  __/ (_| (_) | | | ) \  / /'
    echo '   |_| \_\___|\___\___/|_| |_\/  \/'
    echo ''
    echo '   Unified Tools Setup Script'
    echo '   https://github.com/maskface02/Reconx'
    echo -e "${NC}"
    echo ""
}

print_summary() {
    log_section "Installation Summary"
    echo -e "Installed: ${GREEN}$INSTALLED${NC}"
    echo -e "Skipped: ${YELLOW}$SKIPPED${NC}"
    echo -e "Failed: ${RED}$FAILED${NC}"
    echo ""
    
    if ! $IS_ROOT; then
        echo "Add to your ~/.bashrc or ~/.zshrc:"
        echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
        echo "  export PATH=\"\$HOME/go/bin:\$PATH\""
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\"  # For pipx tools"
        echo ""
    fi
    
    [ -f /etc/profile.d/go.sh ] && echo "Run: source /etc/profile.d/go.sh"
}

main() {
    print_banner
    check_requirements
    detect_system
    install_system_deps
    install_go
    install_go_tools
    install_compiled_tools
    install_git_tools
    install_python_deps
    install_arjun
    install_wordlists
    print_summary
}

main "$@"
