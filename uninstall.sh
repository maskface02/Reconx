#!/bin/bash
#
# ReconX Uninstall Script
# Removes all installed tools, wordlists, and dependencies
#

set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Variables ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOVED=0
DRY_RUN=false
VERIFY_MODE=false

# ── Auto-Detection: Sudo vs User Installation ───────────────────────────────
# Detect if tools were installed with sudo or as user
if [ "$(id -u)" -eq 0 ]; then
    INSTALL_MODE="sudo"
    SUDO_PREFIX="sudo"
    # When using sudo, pipx installs to the ORIGINAL USER's directory
    # (not root), so we need to detect the user who ran sudo
    ORIGINAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo '')}"
    if [ -z "$ORIGINAL_USER" ]; then
        echo -e "${RED}[ERROR]${NC} Could not determine original user. Are you running with sudo?${NC}"
        exit 1
    fi
    ORIGINAL_HOME=$(getent passwd "$ORIGINAL_USER" | cut -d: -f6)
else
    INSTALL_MODE="user"
    SUDO_PREFIX=""
    ORIGINAL_USER="$USER"
    ORIGINAL_HOME="$HOME"
fi

# Set paths based on installation mode
if [ "$INSTALL_MODE" = "sudo" ]; then
    # Sudo-installed tools (via sudo bash setup_tools.sh)
    # Note: pipx and wordlists go to the original user's directory
    GO_BIN_DIR="/usr/local/bin"
    GIT_TOOLS_DIR="/opt"
    PIPX_HOME="$ORIGINAL_HOME/.local/share/pipx"
    PIPX_BIN="$ORIGINAL_HOME/.local/bin"
    GO_RUNTIME="/usr/local/go"
    USER_BIN="$ORIGINAL_HOME/.local/bin"
    WORDLISTS_DIR="$ORIGINAL_HOME/.local/share/wordlists"
else
    # User-installed tools (via bash setup_tools.sh)
    GO_BIN_DIR="/usr/local/bin"
    GIT_TOOLS_DIR="$HOME/.local/opt"
    PIPX_HOME="$HOME/.local/share/pipx"
    PIPX_BIN="$HOME/.local/bin"
    GO_RUNTIME="$HOME/.local/go"
    USER_BIN="$HOME/.local/bin"
    WORDLISTS_DIR="$HOME/.local/share/wordlists"
fi

# ── Logging ──────────────────────────────────────────────────────────────────
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; REMOVED=$((REMOVED + 1)); }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_skip() { echo -e "${CYAN}[SKIP]${NC} $1"; }

# ── Helpers ─────────────────────────────────────────────────────────────────
get_size() {
    local path="$1"
    if [ -e "$path" ]; then
        du -sh "$path" 2>/dev/null | cut -f1 || echo "0B"
    else
        echo "-"
    fi
}

get_size_bytes() {
    local path="$1"
    if [ -e "$path" ]; then
        du -sb "$path" 2>/dev/null | cut -f1 || echo 0
    else
        echo 0
    fi
}

format_bytes() {
    local bytes=$1
    if [ "$bytes" -gt 1073741824 ]; then
        echo "$(awk "BEGIN {printf \"%.1f\", $bytes/1073741824}")GB"
    elif [ "$bytes" -gt 1048576 ]; then
        echo "$(awk "BEGIN {printf \"%.1f\", $bytes/1048576}")MB"
    elif [ "$bytes" -gt 1024 ]; then
        echo "$(awk "BEGIN {printf \"%.1f\", $bytes/1024}")KB"
    else
        echo "${bytes}B"
    fi
}

# ── Banner ───────────────────────────────────────────────────────────────────
show_banner() {
    echo -e "${CYAN}"
    echo "    ____                      __   __"
    echo "   |  _ \\ ___  ___ ___  _ __ / /\\ / /"
    echo "   | |_) / _ \\/ __/ _ \\| '_ \\ \\/  \\/ /"
    echo "   |  _ <  __/ (_| (_) | | | ) \\  / /"
    echo "   |_| \\_\\___|\\___\\___/|_| |_\\/  \\/"
    echo -e "${NC}"
    echo -e "${BOLD}Uninstall Script${NC} - Remove all ReconX tools"
    echo ""
}

# ── Detection Info ────────────────────────────────────────────────────────────
show_detection_info() {
    if [ "$INSTALL_MODE" = "sudo" ]; then
        echo -e "${YELLOW}Detected: Tools installed with sudo${NC}"
        echo "  Mode: sudo (root-installed tools)"
        echo "  User: $ORIGINAL_USER (pipx/wordlists go to user's home)"
        echo "  Paths: /usr/local/bin/, /opt/, $ORIGINAL_HOME/.local/"
    else
        echo -e "${GREEN}Detected: Tools installed as user${NC}"
        echo "  Mode: user (user-installed tools)"
        echo "  Paths: ~/.local/bin/, ~/.local/opt/, ~/.local/share/"
    fi
    echo ""
}
show_help() {
    show_banner
    echo -e "${BOLD}USAGE:${NC}"
    echo "  $0 [OPTIONS]"
    echo ""
    echo -e "${BOLD}OPTIONS:${NC}"
    echo "  --full        Remove everything (tools, wordlists, Go, configs)"
    echo "  --tools       Remove tools only (keep wordlists + Go)"
    echo "  --wordlists   Remove wordlists only [all|seclists|payloads]"
    echo "  --go          Remove Go runtime only"
    echo "  --config      Remove config files only (go.sh, .gf)"
    echo "  --dry-run     Preview only (show what would be removed)"
    echo "  --list        List installed components with sizes"
    echo "  --verify      Verify installation state"
    echo "  --help        Show this help message"
    echo ""
    echo -e "${BOLD}EXAMPLES:${NC}"
    echo "  $0 --full                     # Remove everything"
    echo "  $0 --tools                    # Remove tools only"
    echo "  $0 --wordlists                # Remove all wordlists"
    echo "  $0 --wordlists seclists       # Remove only SecLists"
    echo "  $0 --wordlists payloads       # Remove only PayloadsAllTheThings"
    echo "  $0 --go                       # Remove Go runtime"
    echo "  $0 --config                   # Remove config files"
    echo "  $0 --dry-run                  # Preview what would be removed"
    echo "  $0 --list                     # List installed components"
    echo "  $0 --verify                   # Verify installation state"
    echo ""
    echo -e "${BOLD}WARNING:${NC}"
    echo "  This script requires sudo for removing system-wide installations."
    echo ""
}

# ── Print Dry Run ─────────────────────────────────────────────────────────────
print_dry_run() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${CYAN}[DRY-RUN]${NC} Would remove: $1"
    fi
}

# ── List Installed ───────────────────────────────────────────────────────────
list_installed() {
    show_banner
    show_detection_info
    
    echo -e "${BOLD}=== INSTALLED COMPONENTS ===${NC}"
    echo ""
    
    local total_size=0
    
    # Go binaries
    echo -e "${BOLD}Go Binaries in $GO_BIN_DIR/:${NC}"
    local go_tools=(
        "subfinder" "amass" "assetfinder" "dnsx" "httpx" "katana"
        "ffuf" "dalfox" "waybackurls" "gau" "gospider" "hakrawler"
        "nuclei" "gf" "masscan" "feroxbuster" "x8"
    )
    local go_size=0
    local go_found=false
    for tool in "${go_tools[@]}"; do
        if [ -f "$GO_BIN_DIR/$tool" ]; then
            echo "  - $tool"
            go_found=true
            go_size=$((go_size + $(stat -c%s "$GO_BIN_DIR/$tool" 2>/dev/null || echo 0)))
        fi
    done
    if [ "$go_found" = true ]; then
        echo "  Size: $(format_bytes $go_size)"
        total_size=$((total_size + go_size))
    else
        echo "  (none found)"
    fi
    echo ""
    
    # Pipx tools
    echo -e "${BOLD}Pipx Tools in $PIPX_HOME/:${NC}"
    if command -v pipx &>/dev/null; then
        local pipx_list=$(pipx list 2>/dev/null | grep "package" || true)
        if [ -n "$pipx_list" ]; then
            echo "$pipx_list" | while read line; do
                echo "  - $line"
            done
            local pipx_size=$(get_size_bytes "$PIPX_HOME" 2>/dev/null || echo 0)
            echo "  Size: $(format_bytes $pipx_size)"
            total_size=$((total_size + pipx_size))
        else
            echo "  (none found)"
        fi
    else
        echo "  (pipx not found)"
    fi
    echo ""
    
    # Git tools
    echo -e "${BOLD}Git Tools in $GIT_TOOLS_DIR/:${NC}"
    
    declare -A git_tool_names=(
        ["sqlmap"]="sqlmap"
        ["paramspider"]="ParamSpider"
        ["secretfinder"]="SecretFinder"
        ["wafw00f"]="wafw00f"
        ["nikto"]="nikto"
        ["linkfinder"]="LinkFinder"
        ["xsstrike"]="XSStrike"
        ["jwt_tool"]="jwt_tool"
        ["ghauri"]="ghauri"
        ["gitdorker"]="GitDorker"
    )
    
    local git_size=0
    local git_found=false
    
    for tool in "${!git_tool_names[@]}"; do
        local dir="$GIT_TOOLS_DIR/${git_tool_names[$tool]}"
        if [ -d "$dir" ]; then
            local size=$(get_size "$dir")
            echo "  - ${git_tool_names[$tool]} ($dir, $size)"
            git_found=true
            git_size=$((git_size + $(get_size_bytes "$dir")))
        fi
    done
    
    if [ "$git_found" = false ]; then
        echo "  (none found)"
    fi
    echo ""
    
    # Wordlists
    echo -e "${BOLD}Wordlists in $WORDLISTS_DIR/:${NC}"
    if [ -d "$WORDLISTS_DIR" ]; then
        local wl_size=$(get_size_bytes "$WORDLISTS_DIR")
        ls "$WORDLISTS_DIR" 2>/dev/null | head -5 | while read wl; do
            echo "  - $wl"
        done
        echo "  Size: $(format_bytes $wl_size)"
        total_size=$((total_size + wl_size))
    else
        echo "  (none found)"
    fi
    echo ""
    
    # Go runtime
    echo -e "${BOLD}Go Runtime in $GO_RUNTIME/:${NC}"
    local go_runtime_size=0
    if [ -d "$GO_RUNTIME" ]; then
        go_runtime_size=$(get_size_bytes "$GO_RUNTIME")
        echo "  - $GO_RUNTIME ($(format_bytes $go_runtime_size))"
        total_size=$((total_size + go_runtime_size))
    else
        echo "  (none found)"
    fi
    echo ""
    
    # Config files
    echo -e "${BOLD}Config Files:${NC}"
    local config_found=false
    if [ -f "/etc/profile.d/go.sh" ]; then
        echo "  - /etc/profile.d/go.sh"
        config_found=true
    fi
    
    # Check for ~/.gf patterns
    if [ -d "$HOME/.gf" ]; then
        echo "  - $HOME/.gf (gf patterns)"
        config_found=true
    fi
    
    if [ "$config_found" = false ]; then
        echo "  (none found)"
    fi
    echo ""
    
    # Broken symlinks
    echo -e "${BOLD}Broken Symlinks in $GO_BIN_DIR/:${NC}"
    local broken_found=false
    while IFS= read -r link; do
        if [ -L "$link" ] && [ ! -e "$link" ]; then
            echo "  - $(basename "$link") (broken)"
            broken_found=true
        fi
    done < <(find "$GO_BIN_DIR" -maxdepth 1 -type l 2>/dev/null)
    
    if [ "$broken_found" = false ]; then
        echo "  (none found)"
    fi
    echo ""
    
    # Summary
    echo -e "${BOLD}────────────────────────────────────────${NC}"
    echo -e "Total: ${GREEN}$(format_bytes $total_size)${NC}"
    echo ""
    
    # System packages (Arch pacman / Debian apt)
    echo -e "${BOLD}System Packages:${NC}"
    echo "  (These are installed via system package manager)"
    echo ""
    
    local system_found=false
    
    # Check pacman (Arch)
    if command -v pacman &>/dev/null; then
        local packages=("nmap" "masscan")
        for pkg in "${packages[@]}"; do
            if pacman -Q "$pkg" &>/dev/null; then
                local size=$(pacman -Qi "$pkg" 2>/dev/null | grep "Installed Size" | sed 's/.*: *//' | sed 's/^ *//' || echo "unknown")
                echo "  - $pkg (pacman, $size)"
                system_found=true
            fi
        done
    fi
    
    # Check apt (Debian/Ubuntu)
    if command -v dpkg &>/dev/null; then
        local packages=("nmap" "masscan")
        for pkg in "${packages[@]}"; do
            if dpkg -l "$pkg" &>/dev/null | grep -q "^ii"; then
                local size=$(dpkg -s "$pkg" 2>/dev/null | grep "Installed-Size" | awk '{print $2}' || echo "unknown")
                echo "  - $pkg (dpkg/apt, $size KB)"
                system_found=true
            fi
        done
    fi
    
    if [ "$system_found" = false ]; then
        echo "  (none found)"
    fi
    echo ""
}

# ── Warning Prompt ───────────────────────────────────────────────────────────
show_warning() {
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                    ⚠️  WARNING                         ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "This will remove:"
    echo ""
    
    [ -d "$GO_BIN_DIR" ] && echo "  - Go binaries from $GO_BIN_DIR/"
    [ -d "$PIPX_HOME" ] && echo "  - Pipx tools ($PIPX_HOME/)"
    [ -d "$GIT_TOOLS_DIR" ] && echo "  - Git tools from $GIT_TOOLS_DIR/"
    [ -d "$WORDLISTS_DIR" ] && echo "  - Wordlists ($WORDLISTS_DIR/)"
    [ -d "$GO_RUNTIME" ] && echo "  - Go runtime ($GO_RUNTIME/)"
    [ -f "/etc/profile.d/go.sh" ] && echo "  - /etc/profile.d/go.sh"
    
    echo ""
    echo -e "${YELLOW}Are you sure you want to continue?${NC}"
    echo ""
    read -p "Type 'yes' to confirm: " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        exit 0
    fi
}

# ── Removal Functions ─────────────────────────────────────────────────────────

remove_go_binaries() {
    echo ""
    log_info "Removing Go binaries from $GO_BIN_DIR..."
    
    local go_tools=(
        "subfinder" "amass" "assetfinder" "dnsx" "httpx" "katana"
        "ffuf" "dalfox" "waybackurls" "gau" "gospider" "hakrawler"
        "nuclei" "gf" "masscan" "feroxbuster" "x8"
    )
    
    local removed_count=0
    for tool in "${go_tools[@]}"; do
        if [ -f "$GO_BIN_DIR/$tool" ]; then
            if [ "$DRY_RUN" = true ]; then
                print_dry_run "$GO_BIN_DIR/$tool"
            else
                $SUDO_PREFIX rm -f "$GO_BIN_DIR/$tool"
                echo "  Removed: $tool"
                removed_count=$((removed_count + 1))
            fi
        fi
    done
    
    if [ "$DRY_RUN" = false ] && [ "$removed_count" -gt 0 ]; then
        log_success "Removed $removed_count Go binaries"
    fi
}

remove_pipx_tools() {
    echo ""
    log_info "Removing pipx tools from $PIPX_HOME..."
    
    # Check if pipx exists
    if ! command -v pipx &>/dev/null; then
        log_skip "pipx not found"
        return
    fi
    
    # Check if pipx home directory exists
    if [ ! -d "$PIPX_HOME" ]; then
        log_skip "pipx home directory not found"
        return
    fi
    
    # Try to list packages, handle corruption gracefully
    if [ "$INSTALL_MODE" = "sudo" ]; then
        local pipx_list_output=$(sudo -u "$ORIGINAL_USER" pipx list 2>&1 || true)
    else
        local pipx_list_output=$(pipx list 2>&1 || true)
    fi
    
    # Check for errors/corruption in pipx output
    if echo "$pipx_list_output" | grep -qi "error\|corrupt\|failed\|exception"; then
        log_warning "pipx database may have issues, attempting cleanup"
    fi
    
    # Extract package list
    local pipx_packages=""
    if [ -n "$pipx_list_output" ]; then
        pipx_packages=$(echo "$pipx_list_output" | grep "^package" | awk '{print $2}' || true)
    fi
    
    if [ -z "$pipx_packages" ]; then
        log_skip "No pipx packages found"
        return
    fi
    
    local removed_count=0
    for pkg in $pipx_packages; do
        if [ "$DRY_RUN" = true ]; then
            print_dry_run "pipx uninstall $pkg"
        else
            if [ "$INSTALL_MODE" = "sudo" ]; then
                sudo -u "$ORIGINAL_USER" pipx uninstall "$pkg" 2>/dev/null || true
            else
                pipx uninstall "$pkg" 2>/dev/null || true
            fi
            echo "  Uninstalled: $pkg"
            removed_count=$((removed_count + 1))
        fi
    done
    
    # Clean pipx home directory
    if [ -d "$PIPX_HOME" ]; then
        if [ "$DRY_RUN" = true ]; then
            print_dry_run "$PIPX_HOME"
        else
            rm -rf "$PIPX_HOME"
            echo "  Cleaned: pipx home directory"
        fi
    fi
    
    # Clean pipx cache (NEW)
    if [ -d "$PIPX_HOME/.cache" ]; then
        rm -rf "$PIPX_HOME/.cache" 2>/dev/null || true
        log_info "Cleaned pipx cache"
    fi
    
    # Remove symlinks from user's bin
    if [ -d "$PIPX_BIN" ]; then
        for symlink in "$PIPX_BIN"/*; do
            if [ -L "$symlink" ]; then
                local target=$(readlink "$symlink" 2>/dev/null || true)
                if [[ "$target" == *".local/share/pipx"* ]]; then
                    if [ "$DRY_RUN" = true ]; then
                        print_dry_run "$symlink"
                    else
                        rm -f "$symlink"
                        echo "  Removed: $(basename "$symlink") symlink"
                        removed_count=$((removed_count + 1))
                    fi
                fi
            fi
        done
    fi
    
    if [ "$DRY_RUN" = false ] && [ "$removed_count" -gt 0 ]; then
        log_success "Removed $removed_count pipx packages"
    fi
}

remove_git_tools() {
    echo ""
    log_info "Removing Git-based tools from $GIT_TOOLS_DIR..."
    
    # Define tools with possible directory name variations
    declare -A git_tools=(
        ["sqlmap"]="sqlmap"
        ["ParamSpider"]="ParamSpider"
        ["SecretFinder"]="SecretFinder"
        ["wafw00f"]="wafw00f"
        ["nikto"]="nikto"
        ["LinkFinder"]="LinkFinder"
        ["XSStrike"]="XSStrike"
        ["jwt_tool"]="jwt_tool jwt-tool JWT_Secret"
        ["ghauri"]="ghauri"
        ["GitDorker"]="GitDorker"
    )
    
    local removed_count=0
    
    for tool in "${!git_tools[@]}"; do
        local dir_names="${git_tools[$tool]}"
        
        for dir_name in $dir_names; do
            if [ -d "$GIT_TOOLS_DIR/$dir_name" ]; then
                local size=$(du -sh "$GIT_TOOLS_DIR/$dir_name" 2>/dev/null | cut -f1)
                if [ "$DRY_RUN" = true ]; then
                    print_dry_run "$GIT_TOOLS_DIR/$dir_name ($size)"
                else
                    $SUDO_PREFIX rm -rf "$GIT_TOOLS_DIR/$dir_name"
                    echo "  Removed: $dir_name ($size)"
                    removed_count=$((removed_count + 1))
                fi
            fi
        done
    done
    
    # Also remove wrapper scripts from GO_BIN_DIR
    local wrapper_scripts=(
        "sqlmap" "paramspider" "secretfinder" "wafw00f" "nikto"
        "linkfinder" "xsstrike" "jwt-tool" "jwt_tool" "ghauri" "gitdorker"
    )
    
    for script in "${wrapper_scripts[@]}"; do
        if [ -f "$GO_BIN_DIR/$script" ]; then
            # Check if it's a wrapper script (contains paths to /opt/)
            if grep -q "/opt/\|/.local/opt/" "$GO_BIN_DIR/$script" 2>/dev/null; then
                if [ "$DRY_RUN" = true ]; then
                    print_dry_run "$GO_BIN_DIR/$script (wrapper)"
                else
                    $SUDO_PREFIX rm -f "$GO_BIN_DIR/$script"
                    echo "  Removed: $script (wrapper)"
                    removed_count=$((removed_count + 1))
                fi
            fi
        fi
    done
    
    if [ "$removed_count" -eq 0 ]; then
        log_skip "No Git tools found"
    elif [ "$DRY_RUN" = false ]; then
        log_success "Removed $removed_count Git tools"
    fi
}

remove_wordlists() {
    local target="${1:-all}"
    
    echo ""
    log_info "Removing wordlists from $WORDLISTS_DIR..."
    
    if [ ! -d "$WORDLISTS_DIR" ]; then
        log_skip "Wordlists not found"
        return
    fi
    
    local size=$(get_size "$WORDLISTS_DIR")
    
    if [ "$DRY_RUN" = true ]; then
        print_dry_run "$WORDLISTS_DIR ($size)"
        return
    fi
    
    case "$target" in
        seclists)
            if [ -d "$WORDLISTS_DIR/SecLists" ]; then
                $SUDO_PREFIX rm -rf "$WORDLISTS_DIR/SecLists"
                echo "  Removed: SecLists"
            else
                log_skip "SecLists not found"
            fi
            ;;
        payloads)
            if [ -d "$WORDLISTS_DIR/PayloadsAllTheThings" ]; then
                $SUDO_PREFIX rm -rf "$WORDLISTS_DIR/PayloadsAllTheThings"
                echo "  Removed: PayloadsAllTheThings"
            else
                log_skip "PayloadsAllTheThings not found"
            fi
            ;;
        all|"")
            $SUDO_PREFIX rm -rf "$WORDLISTS_DIR"
            log_success "Removed wordlists ($size)"
            ;;
        *)
            log_error "Unknown target: $target (use: all, seclists, or payloads)"
            ;;
    esac
}

remove_go_runtime() {
    echo ""
    log_info "Removing Go runtime from $GO_RUNTIME..."
    
    local removed_count=0
    
    if [ -d "$GO_RUNTIME" ]; then
        if [ "$DRY_RUN" = true ]; then
            print_dry_run "$GO_RUNTIME"
        else
            $SUDO_PREFIX rm -rf "$GO_RUNTIME"
            echo "  Removed: $GO_RUNTIME"
            removed_count=$((removed_count + 1))
        fi
    fi
    
    if [ "$removed_count" -eq 0 ]; then
        log_skip "No Go runtime found"
    elif [ "$DRY_RUN" = false ]; then
        log_success "Removed Go runtime"
    fi
}

remove_config_files() {
    echo ""
    log_info "Removing config files..."
    
    local removed_count=0
    
    # /etc/profile.d/go.sh
    if [ -f "/etc/profile.d/go.sh" ]; then
        if [ "$DRY_RUN" = true ]; then
            print_dry_run "/etc/profile.d/go.sh"
        else
            sudo rm -f "/etc/profile.d/go.sh"
            echo "  Removed: /etc/profile.d/go.sh"
            removed_count=$((removed_count + 1))
        fi
    fi
    
    # Remove ~/.gf patterns if they exist
    if [ -d "$HOME/.gf" ]; then
        if [ "$DRY_RUN" = true ]; then
            print_dry_run "$HOME/.gf"
        else
            rm -rf "$HOME/.gf"
            echo "  Removed: $HOME/.gf"
            removed_count=$((removed_count + 1))
        fi
    fi
    
    if [ "$removed_count" -eq 0 ]; then
        log_skip "No config files found"
    elif [ "$DRY_RUN" = false ]; then
        log_success "Removed config files"
    fi
}

remove_broken_symlinks() {
    echo ""
    log_info "Removing broken symlinks..."
    
    local removed_count=0
    
    # Check multiple bin directories
    for bin_dir in "/usr/local/bin" "$USER_BIN" "$PIPX_BIN"; do
        [ -d "$bin_dir" ] || continue
        
        while IFS= read -r link; do
            local basename_link=$(basename "$link")
            if [ -L "$link" ] && [ ! -e "$link" ]; then
                if [ "$DRY_RUN" = true ]; then
                    print_dry_run "$link (broken)"
                else
                    sudo rm -f "$link"
                    echo "  Removed: $basename_link (broken symlink)"
                    removed_count=$((removed_count + 1))
                fi
            fi
        done < <(find "$bin_dir" -maxdepth 1 -type l 2>/dev/null)
    done
    
    if [ "$removed_count" -eq 0 ]; then
        log_skip "No broken symlinks found"
    elif [ "$DRY_RUN" = false ]; then
        log_success "Removed $removed_count broken symlinks"
    fi
}

remove_user_bin() {
    echo ""
    log_info "Checking for remaining symlinks in $USER_BIN..."
    
    local removed_count=0
    local reconx_symlinks=("arjun" "sqlmap" "nikto" "paramspider" "wafw00f" "secretfinder" "linkfinder" "xsstrike" "jwt-tool" "ghauri" "gitdorker")
    
    for symlink in "${reconx_symlinks[@]}"; do
        if [ -L "$USER_BIN/$symlink" ] || [ -f "$USER_BIN/$symlink" ]; then
            if [ "$DRY_RUN" = true ]; then
                print_dry_run "$USER_BIN/$symlink"
            else
                $SUDO_PREFIX rm -f "$USER_BIN/$symlink"
                echo "  Removed: $symlink"
                removed_count=$((removed_count + 1))
            fi
        fi
    done
    
    if [ "$removed_count" -eq 0 ]; then
        log_skip "No ReconX symlinks found"
    elif [ "$DRY_RUN" = false ]; then
        log_success "Removed $removed_count symlinks"
    fi
}

verify_removal() {
    local path="$1"
    local name="$2"
    
    if [ -e "$path" ]; then
        log_warning "Still exists after removal attempt: $name"
        return 1
    fi
    return 0
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    local mode="${1:-help}"
    
    # Show detection info for list/dry-run modes
    if [ "$mode" = "--list" ] || [ "$mode" = "--dry-run" ]; then
        show_detection_info
    fi
    
    # Check if running without sudo for removal operations
    if [ "$INSTALL_MODE" = "user" ]; then
        case "$mode" in
            --full|--tools|--wordlists|--go|--config)
                echo ""
                echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
                echo -e "${RED}║          ⚠️  SUDO REQUIRED                           ║${NC}"
                echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
                echo ""
                echo "This operation needs sudo to remove installed tools and files."
                echo ""
                echo "Please run with sudo:"
                echo "  sudo $0 $mode"
                echo ""
                exit 1
                ;;
        esac
    fi
    
    case "$mode" in
        --full)
            show_warning
            show_detection_info
            echo ""
            log_info "Starting full uninstall..."
            remove_go_binaries
            remove_pipx_tools
            remove_git_tools
            remove_wordlists
            remove_go_runtime
            remove_config_files
            remove_broken_symlinks
            remove_user_bin
            
            if [ "$VERIFY_MODE" = true ]; then
                echo ""
                log_info "Running post-removal verification..."
                local failures=0
                verify_removal "/usr/local/bin/nuclei" "Go binaries" || failures=$((failures+1))
                verify_removal "$PIPX_HOME" "pipx home" || failures=$((failures+1))
                verify_removal "$GIT_TOOLS_DIR/sqlmap" "git tools" || failures=$((failures+1))
                verify_removal "$WORDLISTS_DIR" "wordlists" || failures=$((failures+1))
                verify_removal "$GO_RUNTIME" "Go runtime" || failures=$((failures+1))
                
                if [ $failures -gt 0 ]; then
                    echo -e "${RED}Verification failed: $failures items still exist${NC}"
                    exit 1
                else
                    echo -e "${GREEN}All removals verified successfully${NC}"
                fi
            fi
            ;;
        --tools)
            show_warning
            show_detection_info
            echo ""
            log_info "Removing tools only..."
            remove_go_binaries
            remove_pipx_tools
            remove_git_tools
            remove_broken_symlinks
            remove_user_bin
            ;;
        --wordlists)
            show_warning
            show_detection_info
            local wl_target="${2:-all}"
            remove_wordlists "$wl_target"
            ;;
        --go)
            show_warning
            show_detection_info
            remove_go_runtime
            ;;
        --config)
            show_warning
            show_detection_info
            remove_config_files
            ;;
        --dry-run)
            DRY_RUN=true
            log_info "Dry run mode - showing what would be removed..."
            echo ""
            echo "Run without --dry-run to actually remove."
            echo ""
            list_installed
            ;;
        --list)
            list_installed
            ;;
        --verify)
            VERIFY_MODE=true
            show_banner
            show_detection_info
            echo ""
            log_info "Running installation verification..."
            echo ""
            
            local issues=0
            
            # Check Go binaries
            echo -e "${BOLD}Checking Go binaries in $GO_BIN_DIR/:${NC}"
            local go_tools=("subfinder" "amass" "assetfinder" "dnsx" "httpx" "katana" "ffuf" "dalfox" "waybackurls" "gau" "gospider" "hakrawler" "nuclei" "gf" "masscan" "feroxbuster" "x8")
            for tool in "${go_tools[@]}"; do
                if [ -f "$GO_BIN_DIR/$tool" ]; then
                    echo "  ✓ $tool"
                else
                    echo -e "  ✗ $tool (not found)"
                    issues=$((issues+1))
                fi
            done
            echo ""
            
            # Check pipx
            echo -e "${BOLD}Checking pipx in $PIPX_HOME/:${NC}"
            if [ -d "$PIPX_HOME" ]; then
                local pipx_count=$(find "$PIPX_HOME" -maxdepth 1 -type d 2>/dev/null | wc -l)
                if [ $pipx_count -gt 1 ]; then
                    echo "  ✓ pipx installed ($pipx_count packages)"
                else
                    echo "  ✓ pipx directory exists (no packages)"
                fi
            else
                echo -e "  ✗ pipx home directory not found"
                issues=$((issues+1))
            fi
            echo ""
            
            # Check git tools
            echo -e "${BOLD}Checking git tools in $GIT_TOOLS_DIR/:${NC}"
            local git_tool_dirs=("sqlmap" "ParamSpider" "SecretFinder" "wafw00f" "nikto" "LinkFinder" "XSStrike" "jwt_tool" "ghauri" "GitDorker")
            for dir in "${git_tool_dirs[@]}"; do
                if [ -d "$GIT_TOOLS_DIR/$dir" ]; then
                    echo "  ✓ $dir"
                else
                    echo -e "  ✗ $dir (not found)"
                    issues=$((issues+1))
                fi
            done
            echo ""
            
            # Check wordlists
            echo -e "${BOLD}Checking wordlists in $WORDLISTS_DIR/:${NC}"
            if [ -d "$WORDLISTS_DIR" ]; then
                local wl_count=$(ls -1 "$WORDLISTS_DIR" 2>/dev/null | wc -l)
                if [ $wl_count -gt 0 ]; then
                    echo "  ✓ wordlists installed ($wl_count directories)"
                    ls "$WORDLISTS_DIR" 2>/dev/null | head -3 | while read wl; do
                        echo "    - $wl"
                    done
                else
                    echo "  ✓ wordlists directory empty"
                fi
            else
                echo -e "  ✗ wordlists directory not found"
                issues=$((issues+1))
            fi
            echo ""
            
            # Check Go runtime
            echo -e "${BOLD}Checking Go runtime in $GO_RUNTIME/:${NC}"
            if [ -d "$GO_RUNTIME" ]; then
                echo "  ✓ Go runtime installed"
            else
                echo -e "  ✗ Go runtime not found"
                issues=$((issues+1))
            fi
            echo ""
            
            # Summary
            echo -e "${BOLD}════════════════════════════════════════════════════════${NC}"
            if [ $issues -eq 0 ]; then
                echo -e "${GREEN}Verification passed: All components installed correctly${NC}"
            else
                echo -e "${RED}Verification failed: $issues issues found${NC}"
                exit 1
            fi
            exit 0
            ;;
        --help|*)
            show_help
            exit 0
            ;;
    esac
    
    echo ""
    if [ "$DRY_RUN" = true ]; then
        echo -e "${CYAN}Dry run complete. Run without --dry-run to actually uninstall.${NC}"
    else
        echo -e "${GREEN}Uninstall complete!${NC}"
    fi
}

main "$@"
