#!/bin/bash
#
# reconx Tools Setup Script
# Clones and builds all penetration testing tools from source
# Works on Ubuntu/Debian and other Linux distributions
#

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/usr/local/bin"
OPT_DIR="/opt"
GO_VERSION="1.22.0"
GO_INSTALL_DIR="/usr/local"
WORDLIST_DIR="/usr/share/wordlists"

# Counters
INSTALLED=0
FAILED=0
SKIPPED=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    ((INSTALLED++))
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    ((SKIPPED++))
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((FAILED++))
}

log_section() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Detect OS and architecture
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
        i386|i686) GO_ARCH="386" ;;
        *) GO_ARCH="amd64" ;;
    esac
    
    log_info "Detected: $OS $VER ($ARCH)"
    log_info "Go architecture: $GO_ARCH"
}

# Update package lists
update_packages() {
    log_info "Updating package lists..."
    if command -v apt-get &> /dev/null; then
        apt-get update -qq
    elif command -v yum &> /dev/null; then
        yum check-update || true
    elif command -v pacman &> /dev/null; then
        pacman -Sy
    fi
}

# Install system dependencies
install_dependencies() {
    log_section "Installing System Dependencies"
    
    local packages="git curl wget python3 python3-pip python3-venv build-essential
                    libpcap-dev libssl-dev zlib1g-dev libxml2-dev libxslt1-dev
                    libffi-dev libsqlite3-dev libcurl4-openssl-dev libjpeg-dev
                    libpng-dev pkg-config cmake unzip jq perl libnet-ssleay-perl
                    libauthen-pam-perl libio-pty-perl apt-utils python3-tk
                    chromium-browser chromium-chromedriver"
    
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

# Install Go from source
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
    
    log_info "Installing Go..."
    rm -rf ${GO_INSTALL_DIR}/go
    tar -C ${GO_INSTALL_DIR} -xzf "go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
    rm "go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
    
    # Set up environment
    export PATH=$PATH:$GO_INSTALL_DIR/go/bin:$HOME/go/bin
    
    # Make permanent
    echo "export PATH=\$PATH:$GO_INSTALL_DIR/go/bin:\$HOME/go/bin" > /etc/profile.d/go.sh
    chmod +x /etc/profile.d/go.sh
    
    # Verify
    if command -v go &> /dev/null; then
        log_success "Go $(go version | awk '{print $3}') installed"
    else
        log_error "Go installation failed"
        return 1
    fi
}

# Clone or update a git repository
git_clone_or_update() {
    local repo_url=$1
    local dest_dir=$2
    local name=$(basename $dest_dir)
    
    if [ -d "$dest_dir/.git" ]; then
        log_info "Updating $name..."
        cd "$dest_dir"
        git pull --depth 1
    else
        log_info "Cloning $name..."
        rm -rf "$dest_dir"
        git clone --depth 1 "$repo_url" "$dest_dir"
    fi
}

# ==================== GO-BASED TOOLS ====================

install_subfinder() {
    log_info "Installing subfinder..."
    go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
    if [ -f "$HOME/go/bin/subfinder" ]; then
        cp "$HOME/go/bin/subfinder" "$INSTALL_DIR/"
        log_success "subfinder installed"
    else
        log_error "subfinder installation failed"
    fi
}

install_amass() {
    log_info "Installing amass..."
    go install -v github.com/owasp-amass/amass/v4/...@master
    if [ -f "$HOME/go/bin/amass" ]; then
        cp "$HOME/go/bin/amass" "$INSTALL_DIR/"
        log_success "amass installed"
    else
        log_error "amass installation failed"
    fi
}

install_assetfinder() {
    log_info "Installing assetfinder..."
    go install -v github.com/tomnomnom/assetfinder@latest
    if [ -f "$HOME/go/bin/assetfinder" ]; then
        cp "$HOME/go/bin/assetfinder" "$INSTALL_DIR/"
        log_success "assetfinder installed"
    else
        log_error "assetfinder installation failed"
    fi
}

install_dnsx() {
    log_info "Installing dnsx..."
    go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest
    if [ -f "$HOME/go/bin/dnsx" ]; then
        cp "$HOME/go/bin/dnsx" "$INSTALL_DIR/"
        log_success "dnsx installed"
    else
        log_error "dnsx installation failed"
    fi
}

install_httpx() {
    log_info "Installing httpx..."
    go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
    if [ -f "$HOME/go/bin/httpx" ]; then
        cp "$HOME/go/bin/httpx" "$INSTALL_DIR/"
        log_success "httpx installed"
    else
        log_error "httpx installation failed"
    fi
}

install_katana() {
    log_info "Installing katana..."
    go install -v github.com/projectdiscovery/katana/cmd/katana@latest
    if [ -f "$HOME/go/bin/katana" ]; then
        cp "$HOME/go/bin/katana" "$INSTALL_DIR/"
        log_success "katana installed"
    else
        log_error "katana installation failed"
    fi
}

install_ffuf() {
    log_info "Installing ffuf..."
    go install -v github.com/ffuf/ffuf@latest
    if [ -f "$HOME/go/bin/ffuf" ]; then
        cp "$HOME/go/bin/ffuf" "$INSTALL_DIR/"
        log_success "ffuf installed"
    else
        log_error "ffuf installation failed"
    fi
}

install_dalfox() {
    log_info "Installing dalfox..."
    go install -v github.com/hahwul/dalfox/v2@latest
    if [ -f "$HOME/go/bin/dalfox" ]; then
        cp "$HOME/go/bin/dalfox" "$INSTALL_DIR/"
        log_success "dalfox installed"
    else
        log_error "dalfox installation failed"
    fi
}

install_gf() {
    log_info "Installing gf..."
    go install -v github.com/tomnomnom/gf@latest
    if [ -f "$HOME/go/bin/gf" ]; then
        cp "$HOME/go/bin/gf" "$INSTALL_DIR/"
        
        # Install gf patterns
        mkdir -p ~/.gf
        cd /tmp
        rm -rf Gf-Patterns
        git clone --depth 1 https://github.com/1ndianl33t/Gf-Patterns
        cp Gf-Patterns/*.json ~/.gf/ 2>/dev/null || true
        rm -rf Gf-Patterns
        
        log_success "gf installed"
    else
        log_error "gf installation failed"
    fi
}

install_waybackurls() {
    log_info "Installing waybackurls..."
    go install -v github.com/tomnomnom/waybackurls@latest
    if [ -f "$HOME/go/bin/waybackurls" ]; then
        cp "$HOME/go/bin/waybackurls" "$INSTALL_DIR/"
        log_success "waybackurls installed"
    else
        log_error "waybackurls installation failed"
    fi
}

install_gau() {
    log_info "Installing gau..."
    go install -v github.com/lc/gau/v2/cmd/gau@latest
    if [ -f "$HOME/go/bin/gau" ]; then
        cp "$HOME/go/bin/gau" "$INSTALL_DIR/"
        log_success "gau installed"
    else
        log_error "gau installation failed"
    fi
}

install_gospider() {
    log_info "Installing gospider..."
    go install -v github.com/jaeles-project/gospider@latest
    if [ -f "$HOME/go/bin/gospider" ]; then
        cp "$HOME/go/bin/gospider" "$INSTALL_DIR/"
        log_success "gospider installed"
    else
        log_error "gospider installation failed"
    fi
}

install_hakrawler() {
    log_info "Installing hakrawler..."
    go install -v github.com/hakluke/hakrawler@latest
    if [ -f "$HOME/go/bin/hakrawler" ]; then
        cp "$HOME/go/bin/hakrawler" "$INSTALL_DIR/"
        log_success "hakrawler installed"
    else
        log_error "hakrawler installation failed"
    fi
}

install_nuclei() {
    log_info "Installing nuclei..."
    go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
    if [ -f "$HOME/go/bin/nuclei" ]; then
        cp "$HOME/go/bin/nuclei" "$INSTALL_DIR/"
        
        # Download nuclei templates
        log_info "Downloading nuclei templates..."
        nuclei -update-templates 2>/dev/null || true
        
        log_success "nuclei installed"
    else
        log_error "nuclei installation failed"
    fi
}

# ==================== PYTHON-BASED TOOLS ====================

install_arjun() {
    log_info "Installing arjun..."
    pip3 install --quiet --upgrade arjun
    if command -v arjun &> /dev/null; then
        log_success "arjun installed"
    else
        log_error "arjun installation failed"
    fi
}

install_ghauri() {
    log_info "Installing ghauri..."
    pip3 install --quiet --upgrade ghauri
    if command -v ghauri &> /dev/null; then
        log_success "ghauri installed"
    else
        log_error "ghauri installation failed"
    fi
}

install_trufflehog() {
    log_info "Installing trufflehog..."
    curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b $INSTALL_DIR
    if command -v trufflehog &> /dev/null; then
        log_success "trufflehog installed"
    else
        log_error "trufflehog installation failed"
    fi
}

# ==================== GIT-BASED TOOLS ====================

install_sqlmap() {
    log_info "Installing sqlmap..."
    git_clone_or_update "https://github.com/sqlmapproject/sqlmap.git" "$OPT_DIR/sqlmap"
    
    cat > "$INSTALL_DIR/sqlmap" << 'EOF'
#!/bin/bash
python3 /opt/sqlmap/sqlmap.py "$@"
EOF
    chmod +x "$INSTALL_DIR/sqlmap"
    log_success "sqlmap installed"
}

install_paramspider() {
    log_info "Installing paramspider..."
    git_clone_or_update "https://github.com/devanshbatham/ParamSpider.git" "$OPT_DIR/ParamSpider"
    
    cd "$OPT_DIR/ParamSpider"
    pip3 install --quiet -e . 2>/dev/null || pip3 install --quiet -r requirements.txt
    
    cat > "$INSTALL_DIR/paramspider" << 'EOF'
#!/bin/bash
cd /opt/ParamSpider && python3 paramspider.py "$@"
EOF
    chmod +x "$INSTALL_DIR/paramspider"
    log_success "paramspider installed"
}

install_secretfinder() {
    log_info "Installing secretfinder..."
    git_clone_or_update "https://github.com/m4ll0k/SecretFinder.git" "$OPT_DIR/SecretFinder"
    
    cd "$OPT_DIR/SecretFinder"
    pip3 install --quiet -r requirements.txt 2>/dev/null || true
    
    cat > "$INSTALL_DIR/secretfinder" << 'EOF'
#!/bin/bash
python3 /opt/SecretFinder/SecretFinder.py "$@"
EOF
    chmod +x "$INSTALL_DIR/secretfinder"
    log_success "secretfinder installed"
}

install_wafw00f() {
    log_info "Installing wafw00f..."
    git_clone_or_update "https://github.com/EnableSecurity/wafw00f.git" "$OPT_DIR/wafw00f"
    
    cd "$OPT_DIR/wafw00f"
    python3 setup.py install --quiet 2>/dev/null || pip3 install --quiet .
    
    ln -sf "$OPT_DIR/wafw00f/wafw00f.py" "$INSTALL_DIR/wafw00f"
    chmod +x "$INSTALL_DIR/wafw00f"
    log_success "wafw00f installed"
}

install_nikto() {
    log_info "Installing nikto..."
    git_clone_or_update "https://github.com/sullo/nikto.git" "$OPT_DIR/nikto"
    
    cat > "$INSTALL_DIR/nikto" << 'EOF'
#!/bin/bash
perl /opt/nikto/program/nikto.pl "$@"
EOF
    chmod +x "$INSTALL_DIR/nikto"
    log_success "nikto installed"
}

install_linkfinder() {
    log_info "Installing linkfinder..."
    git_clone_or_update "https://github.com/GerbenJavado/LinkFinder.git" "$OPT_DIR/LinkFinder"
    
    cd "$OPT_DIR/LinkFinder"
    pip3 install --quiet -r requirements.txt 2>/dev/null || true
    
    cat > "$INSTALL_DIR/linkfinder" << 'EOF'
#!/bin/bash
python3 /opt/LinkFinder/linkfinder.py "$@"
EOF
    chmod +x "$INSTALL_DIR/linkfinder"
    log_success "linkfinder installed"
}

install_xsstrike() {
    log_info "Installing xsstrike..."
    git_clone_or_update "https://github.com/s0md3v/XSStrike.git" "$OPT_DIR/XSStrike"
    
    cd "$OPT_DIR/XSStrike"
    pip3 install --quiet -r requirements.txt 2>/dev/null || true
    
    cat > "$INSTALL_DIR/xsstrike" << 'EOF'
#!/bin/bash
python3 /opt/XSStrike/xsstrike.py "$@"
EOF
    chmod +x "$INSTALL_DIR/xsstrike"
    log_success "xsstrike installed"
}

install_ssrfire() {
    log_info "Installing ssrfire..."
    git_clone_or_update "https://github.com/0xInfection/ssrfire.git" "$OPT_DIR/ssrfire"
    
    chmod +x "$OPT_DIR/ssrfire/ssrfire.sh"
    
    cat > "$INSTALL_DIR/ssrfire" << 'EOF'
#!/bin/bash
cd /opt/ssrfire && bash ssrfire.sh "$@"
EOF
    chmod +x "$INSTALL_DIR/ssrfire"
    log_success "ssrfire installed"
}

install_jwt_tool() {
    log_info "Installing jwt-tool..."
    git_clone_or_update "https://github.com/ticarpi/jwt_tool.git" "$OPT_DIR/jwt_tool"
    
    cd "$OPT_DIR/jwt_tool"
    pip3 install --quiet -r requirements.txt 2>/dev/null || true
    
    cat > "$INSTALL_DIR/jwt-tool" << 'EOF'
#!/bin/bash
python3 /opt/jwt_tool/jwt_tool.py "$@"
EOF
    chmod +x "$INSTALL_DIR/jwt-tool"
    log_success "jwt-tool installed"
}

install_gitdorker() {
    log_info "Installing gitdorker..."
    git_clone_or_update "https://github.com/obheda12/GitDorker.git" "$OPT_DIR/GitDorker"
    
    cd "$OPT_DIR/GitDorker"
    pip3 install --quiet -r requirements.txt 2>/dev/null || true
    
    cat > "$INSTALL_DIR/gitdorker" << 'EOF'
#!/bin/bash
python3 /opt/GitDorker/GitDorker.py "$@"
EOF
    chmod +x "$INSTALL_DIR/gitdorker"
    log_success "gitdorker installed"
}

# ==================== COMPILED TOOLS ====================

install_masscan() {
    log_info "Installing masscan..."
    
    if command -v masscan &> /dev/null; then
        log_warning "masscan already installed via package manager"
        return 0
    fi
    
    git_clone_or_update "https://github.com/robertdavidgraham/masscan.git" "$OPT_DIR/masscan"
    
    cd "$OPT_DIR/masscan"
    make -j$(nproc) 2>/dev/null || make
    
    cp bin/masscan "$INSTALL_DIR/"
    log_success "masscan installed"
}

install_nmap() {
    log_info "Installing nmap..."
    
    if command -v nmap &> /dev/null; then
        log_warning "nmap already installed"
        return 0
    fi
    
    if command -v apt-get &> /dev/null; then
        apt-get install -y -qq nmap
    elif command -v yum &> /dev/null; then
        yum install -y nmap
    elif command -v pacman &> /dev/null; then
        pacman -S --noconfirm nmap
    fi
    
    log_success "nmap installed"
}

install_feroxbuster() {
    log_info "Installing feroxbuster..."
    
    if command -v feroxbuster &> /dev/null; then
        log_warning "feroxbuster already installed"
        return 0
    fi
    
    cd /tmp
    case $ARCH in
        x86_64) FEROX_ARCH="x86_64-linux-musl" ;;
        aarch64) FEROX_ARCH="aarch64-linux-musl" ;;
        *) 
            log_warning "Architecture $ARCH not supported for feroxbuster"
            return 1
            ;;
    esac
    
    FEROX_URL="https://github.com/epi052/feroxbuster/releases/latest/download/feroxbuster-${FEROX_ARCH}.tar.gz"
    curl -sL "$FEROX_URL" | tar xz
    mv feroxbuster "$INSTALL_DIR/"
    
    log_success "feroxbuster installed"
}

install_x8() {
    log_info "Installing x8..."
    
    if command -v x8 &> /dev/null; then
        log_warning "x8 already installed"
        return 0
    fi
    
    cd /tmp
    case $ARCH in
        x86_64) X8_ARCH="x86_64" ;;
        aarch64) X8_ARCH="aarch64" ;;
        *) 
            log_warning "Architecture $ARCH not supported for x8"
            return 1
            ;;
    esac
    
    X8_URL="https://github.com/Sh1Yo/x8/releases/latest/download/x8_linux.tar.gz"
    curl -sL "$X8_URL" | tar xz
    mv x8 "$INSTALL_DIR/"
    
    log_success "x8 installed"
}

# ==================== WORDLISTS ====================

install_wordlists() {
    log_section "Installing Wordlists"
    
    mkdir -p "$WORDLIST_DIR"
    
    # SecLists
    if [ ! -d "$WORDLIST_DIR/SecLists" ]; then
        log_info "Cloning SecLists..."
        git clone --depth 1 https://github.com/danielmiessler/SecLists.git "$WORDLIST_DIR/SecLists"
        log_success "SecLists installed"
    else
        log_info "Updating SecLists..."
        cd "$WORDLIST_DIR/SecLists"
        git pull --depth 1
        log_success "SecLists updated"
    fi
    
    # PayloadsAllTheThings
    if [ ! -d "$WORDLIST_DIR/PayloadsAllTheThings" ]; then
        log_info "Cloning PayloadsAllTheThings..."
        git clone --depth 1 https://github.com/swisskyrepo/PayloadsAllTheThings.git "$WORDLIST_DIR/PayloadsAllTheThings"
        log_success "PayloadsAllTheThings installed"
    fi
}

# ==================== MAIN ====================

print_banner() {
    echo -e "${GREEN}"
    echo "    ____                      __   __"
    echo "   |  _ \ ___  ___ ___  _ __ / /\ / /"
    echo "   | |_) / _ \/ __/ _ \| '_ \\ \/  \/ /"
    echo "   |  _ <  __/ (_| (_) | | | ) \  / /"
    echo "   |_| \_\___|\___\___/|_| |_\/  \/"
    echo ""
    echo "   Penetration Testing Tools Setup"
    echo -e "${NC}"
}

print_summary() {
    log_section "Installation Summary"
    
    echo -e "Successfully installed: ${GREEN}$INSTALLED${NC}"
    echo -e "Skipped (already exists): ${YELLOW}$SKIPPED${NC}"
    echo -e "Failed: ${RED}$FAILED${NC}"
    echo ""
    
    echo "Installed tools location: $INSTALL_DIR"
    echo "Git-based tools location: $OPT_DIR"
    echo "Wordlists location: $WORDLIST_DIR"
    echo ""
    
    echo "To use the tools:"
    echo "  1. Open a new terminal, or run: source /etc/profile.d/go.sh"
    echo "  2. Verify: which subfinder nuclei sqlmap"
    echo ""
    echo "Next steps for reconx:"
    echo "  1. cd /path/to/reconx"
    echo "  2. pip3 install -r requirements.txt"
    echo "  3. python3 main.py init"
    echo "  4. Edit config.yaml"
    echo "  5. python3 main.py run --target example.com"
    echo ""
}

install_all_go_tools() {
    log_section "Installing Go-Based Tools"
    
    install_subfinder
    install_amass
    install_assetfinder
    install_dnsx
    install_httpx
    install_katana
    install_ffuf
    install_dalfox
    install_gf
    install_waybackurls
    install_gau
    install_gospider
    install_hakrawler
    install_nuclei
}

install_all_python_tools() {
    log_section "Installing Python-Based Tools"
    
    install_arjun
    install_ghauri
    install_trufflehog
}

install_all_git_tools() {
    log_section "Installing Git-Based Tools"
    
    install_sqlmap
    install_paramspider
    install_secretfinder
    install_wafw00f
    install_nikto
    install_linkfinder
    install_xsstrike
    install_ssrfire
    install_jwt_tool
    install_gitdorker
}

install_all_compiled_tools() {
    log_section "Installing Compiled Tools"
    
    install_nmap
    install_masscan
    install_feroxbuster
    install_x8
}

main() {
    print_banner
    
    check_root
    detect_system
    
    update_packages
    install_dependencies
    install_go
    
    install_all_go_tools
    install_all_python_tools
    install_all_git_tools
    install_all_compiled_tools
    install_wordlists
    
    print_summary
}

# Handle command line arguments
case "${1:-}" in
    --go)
        check_root
        detect_system
        install_go
        install_all_go_tools
        ;;
    --python)
        check_root
        install_all_python_tools
        ;;
    --git)
        check_root
        install_dependencies
        install_all_git_tools
        ;;
    --wordlists)
        install_wordlists
        ;;
    --help|-h)
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  --go         Install only Go-based tools"
        echo "  --python     Install only Python-based tools"
        echo "  --git        Install only Git-based tools"
        echo "  --wordlists  Install only wordlists"
        echo "  --help       Show this help message"
        echo ""
        echo "Without options, installs all tools."
        exit 0
        ;;
    *)
        main
        ;;
esac
