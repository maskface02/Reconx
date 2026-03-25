#!/bin/bash
#
# reconx System Tools Setup (REQUIRES SUDO)
#

clear
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_DIR="/usr/local/bin"
OPT_DIR="/opt"
GO_VERSION="1.22.0"
GO_INSTALL_DIR="/usr/local"
WORDLIST_DIR="/usr/share/wordlists"

declare -i INSTALLED=0
declare -i SKIPPED=0

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; INSTALLED=$((INSTALLED + 1)); }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; SKIPPED=$((SKIPPED + 1)); }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

detect_system() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        OS=$(uname -s)
        VER=$(uname -r)
    fi
    ARCH=$(uname -m)
    case $ARCH in
        x86_64) GO_ARCH="amd64" ;;
        aarch64|arm64) GO_ARCH="arm64" ;;
        *) GO_ARCH="amd64" ;;
    esac
    log_info "Detected: $OS $VER ($ARCH)"
}

update_packages() {
    log_info "Updating package lists..."
    if command -v apt-get &> /dev/null; then
        apt-get update -qq || true
    elif command -v yum &> /dev/null; then
        yum check-update || true
    elif command -v pacman &> /dev/null; then
        pacman -Sy
    fi
}

install_dependencies() {
    log_section "Installing System Dependencies"
    local packages="git curl wget python3 python3-pip python3-venv build-essential
    libpcap-dev libssl-dev zlib1g-dev libxml2-dev libxslt1-dev
    libffi-dev libsqlite3-dev libcurl4-openssl-dev libjpeg-dev
    libpng-dev pkg-config cmake unzip jq perl libnet-ssleay-perl
    libauthen-pam-perl libio-pty-perl apt-utils python3-tk
    chromium chromium-driver
    libjson-perl libxml-writer-perl"  # Added for nikto
    
    if command -v apt-get &> /dev/null; then
        apt-get install -y -qq $packages 2>/dev/null || apt-get install -y $packages
    elif command -v yum &> /dev/null; then
        yum groupinstall -y "Development Tools"
        yum install -y ${packages//build-essential/"gcc gcc-c++ make"}
    elif command -v pacman &> /dev/null; then
        pacman -S --noconfirm base-devel git python python-pip cmake
    fi
    log_success "System dependencies installed"
}

install_go() {
    log_section "Installing Go"
    if command -v go &> /dev/null; then
        GO_CURRENT=$(go version | awk '{print $3}' | sed 's/go//')
        log_info "Go $GO_CURRENT already installed"
        export PATH=$PATH:$GO_INSTALL_DIR/go/bin:$HOME/go/bin
        return 0
    fi
    
    log_info "Downloading Go $GO_VERSION..."
    cd /tmp
    wget -q --show-progress "https://go.dev/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
    rm -rf ${GO_INSTALL_DIR}/go
    tar -C ${GO_INSTALL_DIR} -xzf "go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
    rm "go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
    
    export PATH=$PATH:$GO_INSTALL_DIR/go/bin:$HOME/go/bin
    if [ -d /etc/profile.d ]; then
        echo "export PATH=\$PATH:$GO_INSTALL_DIR/go/bin:\$HOME/go/bin" > /etc/profile.d/go.sh
        chmod +x /etc/profile.d/go.sh
    fi
    
    if command -v go &> /dev/null; then
        log_success "Go $(go version | awk '{print $3}') installed"
    else
        log_error "Go installation failed"
        return 1
    fi
}

install_go_tool() {
    local binary_name=$1
    if [ -f "$HOME/go/bin/$binary_name" ]; then
        cp "$HOME/go/bin/$binary_name" "$INSTALL_DIR/"
        log_success "$binary_name installed"
    else
        log_error "$binary_name installation failed"
    fi
}

install_subfinder() { log_info "Installing subfinder..."; go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest 2>/dev/null; install_go_tool "subfinder"; }
install_amass() { log_info "Installing amass..."; go install -v github.com/owasp-amass/amass/v4/...@master 2>/dev/null; install_go_tool "amass";}
install_assetfinder() { log_info "Installing assetfinder..."; go install -v github.com/tomnomnom/assetfinder@latest 2>/dev/null; install_go_tool "assetfinder"; }
install_dnsx() { log_info "Installing dnsx..."; go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest 2>/dev/null; install_go_tool "dnsx"; }
install_httpx() { log_info "Installing httpx..."; go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest 2>/dev/null; install_go_tool "httpx"; }
install_katana() { log_info "Installing katana..."; go install -v github.com/projectdiscovery/katana/cmd/katana@latest 2>/dev/null ; install_go_tool "katana"; }
install_ffuf() { log_info "Installing ffuf..."; go install -v github.com/ffuf/ffuf@latest 2>/dev/null; install_go_tool "ffuf"; }
install_dalfox() { log_info "Installing dalfox..."; go install -v github.com/hahwul/dalfox/v2@latest 2>/dev/null; install_go_tool "dalfox"; }
install_waybackurls() { log_info "Installing waybackurls..."; go install -v github.com/tomnomnom/waybackurls@latest 2>/dev/null; install_go_tool "waybackurls"; }
install_gau() { log_info "Installing gau..."; go install -v github.com/lc/gau/v2/cmd/gau@latest 2>/dev/null; install_go_tool "gau"; }
install_gospider() { log_info "Installing gospider..."; go install -v github.com/jaeles-project/gospider@latest 2>/dev/null; install_go_tool "gospider"; }
install_hakrawler() { log_info "Installing hakrawler..."; go install -v github.com/hakluke/hakrawler@latest 2>/dev/null; install_go_tool "hakrawler"; }
install_nuclei() { 
    log_info "Installing nuclei..."; 
    go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest; 
    install_go_tool "nuclei";
    nuclei -update-templates 2>/dev/null || true
}
install_gf() {
    log_info "Installing gf..."
    go install -v github.com/tomnomnom/gf@latest
    if [ -f "$HOME/go/bin/gf" ]; then
        cp "$HOME/go/bin/gf" "$INSTALL_DIR/"
        mkdir -p ~/.gf
        cd /tmp && rm -rf Gf-Patterns
        git clone --depth 1 https://github.com/1ndianl33t/Gf-Patterns 2>/dev/null || true
        cp Gf-Patterns/*.json ~/.gf/ 2>/dev/null || true
        rm -rf Gf-Patterns
        log_success "gf installed"
    fi
}

git_clone_or_update() {
    local repo_url=$1
    local dest_dir=$2
    local name=$(basename $dest_dir)
    if [ -d "$dest_dir/.git" ]; then
        log_info "Updating $name..."
        cd "$dest_dir" && git pull --depth 1 || true
    else
        log_info "Cloning $name..."
        rm -rf "$dest_dir"
        git clone --depth 1 "$repo_url" "$dest_dir" || { log_error "Failed to clone $name"; return 1; }
    fi
}

install_sqlmap() {
    git_clone_or_update "https://github.com/sqlmapproject/sqlmap.git" "$OPT_DIR/sqlmap" || return 0
    cat > "$INSTALL_DIR/sqlmap" << 'EOF'
#!/bin/bash
python3 /opt/sqlmap/sqlmap.py "$@"
EOF
    chmod +x "$INSTALL_DIR/sqlmap"
    log_success "sqlmap installed"
}

install_paramspider() {
    log_info "Installing paramspider..."
    git_clone_or_update "https://github.com/devanshbatham/ParamSpider.git" "$OPT_DIR/ParamSpider" || return 0
    
    cd "$OPT_DIR/ParamSpider"
    pip3 install -e . 2>/dev/null || pip3 install -r requirements.txt 2>/dev/null || true
    
    # Create wrapper that handles package structure
    cat > "$INSTALL_DIR/paramspider" << 'EOF'
#!/bin/bash
cd /opt/ParamSpider && python3 -m paramspider "$@"
EOF
    chmod +x "$INSTALL_DIR/paramspider"
    log_success "paramspider installed"
}

install_secretfinder() {
    git_clone_or_update "https://github.com/m4ll0k/SecretFinder.git" "$OPT_DIR/SecretFinder" || return 0
    cd "$OPT_DIR/SecretFinder"
    pip3 install -r requirements.txt 2>/dev/null || true
    
    cat > "$INSTALL_DIR/secretfinder" << 'EOF'
#!/bin/bash
python3 /opt/SecretFinder/SecretFinder.py "$@"
EOF
    chmod +x "$INSTALL_DIR/secretfinder"
    log_success "secretfinder installed"
}

install_wafw00f() {
    git_clone_or_update "https://github.com/EnableSecurity/wafw00f.git" "$OPT_DIR/wafw00f" || return 0
    cd "$OPT_DIR/wafw00f"
    python3 setup.py install 2>/dev/null || pip3 install . 2>/dev/null || true
    ln -sf "$OPT_DIR/wafw00f/wafw00f.py" "$INSTALL_DIR/wafw00f"
    chmod +x "$INSTALL_DIR/wafw00f" 2>/dev/null 
    log_success "wafw00f installed"
}

install_nikto() {
    git_clone_or_update "https://github.com/sullo/nikto.git" "$OPT_DIR/nikto" || return 0
    cat > "$INSTALL_DIR/nikto" << 'EOF'
#!/bin/bash
perl /opt/nikto/program/nikto.pl "$@"
EOF
    chmod +x "$INSTALL_DIR/nikto"
    log_success "nikto installed"
}

install_linkfinder() {
    git_clone_or_update "https://github.com/GerbenJavado/LinkFinder.git" "$OPT_DIR/LinkFinder" || return 0
    cd "$OPT_DIR/LinkFinder"
    pip3 install -r requirements.txt 2>/dev/null || true
    cat > "$INSTALL_DIR/linkfinder" << 'EOF'
#!/bin/bash
python3 /opt/LinkFinder/linkfinder.py "$@"
EOF
    chmod +x "$INSTALL_DIR/linkfinder"
    log_success "linkfinder installed"
}

install_xsstrike() {
    git_clone_or_update "https://github.com/s0md3v/XSStrike.git" "$OPT_DIR/XSStrike" || return 0
    cd "$OPT_DIR/XSStrike"
    pip3 install -r requirements.txt 2>/dev/null || true
    cat > "$INSTALL_DIR/xsstrike" << 'EOF'
#!/bin/bash
python3 /opt/XSStrike/xsstrike.py "$@"
EOF
    chmod +x "$INSTALL_DIR/xsstrike"
    log_success "xsstrike installed"
}

install_jwt_tool() {
    git_clone_or_update "https://github.com/ticarpi/jwt_tool.git" "$OPT_DIR/jwt_tool" || return 0
    cd "$OPT_DIR/jwt_tool"
    pip3 install -r requirements.txt 2>/dev/null || true
    cat > "$INSTALL_DIR/jwt-tool" << 'EOF'
#!/bin/bash
python3 /opt/jwt_tool/jwt_tool.py "$@"
EOF
    chmod +x "$INSTALL_DIR/jwt-tool"
    log_success "jwt-tool installed"
}

install_gitdorker() {
    git_clone_or_update "https://github.com/obheda12/GitDorker.git" "$OPT_DIR/GitDorker" || return 0
    cd "$OPT_DIR/GitDorker"
    pip3 install -r requirements.txt 2>/dev/null || true
    
    # Create wrapper that suppresses SyntaxWarning (Python 3.12+)
    cat > "$INSTALL_DIR/gitdorker" << 'EOF'
#!/bin/bash
python3 -W ignore /opt/GitDorker/GitDorker.py "$@"
EOF
    chmod +x "$INSTALL_DIR/gitdorker"
    log_success "gitdorker installed"
}

install_ghauri() {
    log_info "Installing ghauri..."
    git_clone_or_update "https://github.com/r0oth3x49/ghauri.git" "$OPT_DIR/ghauri" || return 0
    cd "$OPT_DIR/ghauri"
    pip3 install -q --upgrade setuptools 2>/dev/null || true
    pip3 install -q --upgrade -r requirements.txt 2>/dev/null || true
    
    # Fix requests library version mismatch that causes dependency warnings
    pip3 install -q 'urllib3<2.0' 'charset-normalizer<3.0' 2>/dev/null || true
    
    # Create wrapper that suppresses all warnings using -W ignore
    cat > "$INSTALL_DIR/ghauri" << 'EOF'
#!/bin/bash
export PYTHONWARNINGS="ignore"
export PYTHONDONTWRITEBYTECODE=1
cd /opt/ghauri && python3 -W ignore -c "
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

install_masscan() {
    if command -v masscan &> /dev/null; then
        log_warning "masscan already installed"
        return 0
    fi
    git_clone_or_update "https://github.com/robertdavidgraham/masscan.git" "$OPT_DIR/masscan" || return 0
    cd "$OPT_DIR/masscan" && make -j$(nproc) 2>/dev/null || make
    cp bin/masscan "$INSTALL_DIR/"
    log_success "masscan installed"
}

install_nmap() {
    if command -v nmap &> /dev/null; then
        log_warning "nmap already installed"
        return 0
    fi
    apt-get install -y -qq nmap 2>/dev/null || yum install -y nmap 2>/dev/null || true
    log_success "nmap installed"
}

install_feroxbuster() {
    if command -v feroxbuster &> /dev/null; then
        log_warning "feroxbuster already installed"
        return 0
    fi
    
    cd /tmp
    
    case $ARCH in
        x86_64) 
            FEROX_FILE="x86_64-linux-feroxbuster.tar.gz"
            ;;
        aarch64|arm64) 
            FEROX_FILE="aarch64-linux-feroxbuster.zip"
            ;;
        *) 
            log_warning "Architecture $ARCH not supported for feroxbuster"
            return 1
            ;;
    esac
    
    log_info "Downloading feroxbuster..."
    local download_url="https://github.com/epi052/feroxbuster/releases/latest/download/${FEROX_FILE}"
    
    if ! curl -fsSL "$download_url" -o "$FEROX_FILE"; then
        log_error "Failed to download feroxbuster from $download_url"
        return 1
    fi
    
    # Extract based on file type
    if [[ "$FEROX_FILE" == *.tar.gz ]]; then
        if ! tar xzf "$FEROX_FILE"; then
            log_error "Failed to extract feroxbuster"
            rm -f "$FEROX_FILE"
            return 1
        fi
    elif [[ "$FEROX_FILE" == *.zip ]]; then
        if ! unzip -o "$FEROX_FILE"; then
            log_error "Failed to extract feroxbuster"
            rm -f "$FEROX_FILE"
            return 1
        fi
    fi
    
    if [ ! -f "feroxbuster" ]; then
        log_error "feroxbuster binary not found after extraction"
        rm -f "$FEROX_FILE"
        return 1
    fi
    
    chmod +x "feroxbuster"
    mv "feroxbuster" "$INSTALL_DIR/"
    rm -f "$FEROX_FILE"
    
    if command -v feroxbuster &> /dev/null; then
        log_success "feroxbuster installed"
    else
        log_error "feroxbuster installation verification failed"
        return 1
    fi
}

install_x8() {
    if command -v x8 &> /dev/null; then
        log_warning "x8 already installed"
        return 0
    fi
    
    cd /tmp
    
    case $ARCH in
        x86_64) 
            X8_ARCH="x86_64"
            ;;
        aarch64) 
            X8_ARCH="aarch64"
            ;;
        *) 
            log_warning "Architecture $ARCH not supported for x8"
            return 1
            ;;
    esac
    
    log_info "Fetching latest x8 release..."
    local latest_tag
    latest_tag=$(curl -s "https://api.github.com/repos/Sh1Yo/x8/releases/latest" | grep -o '"tag_name": "[^"]*"' | cut -d'"' -f4)
    
    if [ -z "$latest_tag" ]; then
        log_error "Could not determine latest x8 version"
        return 1
    fi
    
    local download_url="https://github.com/Sh1Yo/x8/releases/download/${latest_tag}/${X8_ARCH}-linux-x8.gz"
    local temp_file="${X8_ARCH}-linux-x8.gz"
    
    log_info "Downloading from: $download_url"
    
    if ! curl -fsSL "$download_url" -o "$temp_file"; then
        log_error "Failed to download x8"
        return 1
    fi
    
    # x8 is gzipped binary, not tar
    if ! gunzip -f "$temp_file"; then
        log_error "Failed to decompress x8"
        rm -f "$temp_file"
        return 1
    fi
    
    # After gunzip, file is named "x8" or "x8-linux" or "x86_64-linux-x8"
    local binary_name="x8"
    if [ ! -f "$binary_name" ]; then
        if [ -f "${X8_ARCH}-linux-x8" ]; then
            binary_name="${X8_ARCH}-linux-x8"
        else
            log_error "x8 binary not found after decompression"
            ls -la
            return 1
        fi
    fi
    
    chmod +x "$binary_name"
    mv "$binary_name" "$INSTALL_DIR/x8"
    
    if command -v x8 &> /dev/null; then
        log_success "x8 installed"
    else
        log_error "x8 installation verification failed"
        return 1
    fi
}

install_wordlists() {
    log_section "Installing Wordlists"
    mkdir -p "$WORDLIST_DIR"
    
    if [ ! -d "$WORDLIST_DIR/SecLists" ]; then
        git clone --depth 1 https://github.com/danielmiessler/SecLists.git "$WORDLIST_DIR/SecLists" 2>/dev/null || log_warning "SecLists clone failed"
        [ -d "$WORDLIST_DIR/SecLists" ] && log_success "SecLists installed"
    else
        cd "$WORDLIST_DIR/SecLists" && git pull --depth 1 2>/dev/null || true
        log_success "SecLists updated"
    fi
    
    if [ ! -d "$WORDLIST_DIR/PayloadsAllTheThings" ]; then
        git clone --depth 1 https://github.com/swisskyrepo/PayloadsAllTheThings.git "$WORDLIST_DIR/PayloadsAllTheThings" 2>/dev/null || log_warning "PayloadsAllTheThings clone failed"
        [ -d "$WORDLIST_DIR/PayloadsAllTheThings" ] && log_success "PayloadsAllTheThings installed"
    fi
}

print_banner() {
    echo -e "${GREEN}"
    echo '    ____                      __   __'
    echo '   |  _ \ ___  ___ ___  _ __ / /\ / /'
    echo '   | |_) / _ \/ __/ _ \| '"'\\'"'_ \ \/  \/ /'
    echo '   |  _ <  __/ (_| (_) | | | ) \  / /'
    echo '   |_| \_\___|\___\___/|_| |_\/  \/'
    echo ''
    echo '   System Tools Setup (Sudo Required)'
    echo -e "${NC}"
}

print_summary() {
    log_section "Installation Summary"
    echo -e "Successfully installed: ${GREEN}$INSTALLED${NC}"
    echo -e "Skipped: ${YELLOW}$SKIPPED${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Run: python3 setup_python_tools.py (without sudo, in your venv)"
    echo "  2. source /etc/profile.d/go.sh (or restart terminal)"
    echo ""
}

main() {
    print_banner
    check_root
    detect_system
    update_packages
    install_dependencies
    install_go
    
    log_section "Installing Go-Based Tools"
    install_subfinder || true; install_amass || true; install_assetfinder || true
    install_dnsx || true; install_httpx || true; install_katana || true
    install_ffuf || true; install_dalfox || true; install_gf || true
    install_waybackurls || true; install_gau || true; install_gospider || true
    install_hakrawler || true; install_nuclei || true
    
    log_section "Installing Compiled Tools"
    install_nmap || true; install_masscan || true; install_feroxbuster || true; install_x8 || true
    
    log_section "Installing Git-Based Tools"
    install_sqlmap || true; install_paramspider || true; install_secretfinder || true
    install_wafw00f || true; install_nikto || true; install_linkfinder || true
    install_xsstrike || true; install_jwt_tool || true; install_gitdorker || true
    install_ghauri || true
    
    install_wordlists
    print_summary
}

main "$@"
