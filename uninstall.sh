#!/bin/bash
#
# ReconX Uninstall Script
# Removes all installed tools, wordlists, and dependencies
#
clear
set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Paths ────────────────────────────────────────────────────────────────────
USER_BIN="$HOME/.local/bin"
GIT_TOOLS_DIR="$HOME/.local/opt"
WORDLISTS_DIR="$HOME/.local/share/wordlists"
GO_DIR="$HOME/.local/go"
GO_CACHE_DIR="$HOME/.local/go_cache"
ARJUN_PIPX_DIR="$HOME/.local/share/pipx/arjun"

# ── Tool List ────────────────────────────────────────────────────────────────
declare -a TOOLS=(
    "subfinder" "amass" "assetfinder" "dnsx" "httpx" "katana"
    "ffuf" "dalfox" "waybackurls" "gospider" "hakrawler"
    "nuclei" "masscan" "feroxbuster" "x8" "gf" "gau"
    "sqlmap" "ghauri" "gitdorker" "paramspider" "nikto"
    "wafw00f" "linkfinder" "xsstrike" "jwt-tool" "secretfinder"
    "ncat" "nmap" "nping" "arjun" "trufflehog"
)

# ── Git Tools List ──────────────────────────────────────────────────────────
declare -a GIT_TOOL_DIRS=(
    "sqlmap" "paramspider" "secretfinder" "wafw00f" "nikto"
    "linkfinder" "xsstrike" "jwt-tool" "ghauri" "gitdorker"
)

# ── Logging ──────────────────────────────────────────────────────────────────
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_skip() { echo -e "${CYAN}[SKIP]${NC} $1"; }

# ── Safe Remove Helper ───────────────────────────────────────────────────────
safe_remove() {
    local path="$1"
    local description="${2:-item}"
    
    if [[ -z "$path" ]]; then
        log_warning "Path is empty, skipping $description"
        return 1
    fi
    
    if [[ "$path" == "/" ]]; then
        log_warning "Refusing to delete root directory!"
        return 1
    fi
    
    if [[ ! -e "$path" ]]; then
        log_skip "$description not found"
        return 0
    fi
    
    # Try normal removal first
    if rm -rf "$path" 2>/dev/null; then
        log_success "Removed $description"
        return 0
    fi
    
    # Try with sudo as fallback
    log_warning "Permission denied, trying with sudo..."
    if sudo rm -rf "$path" 2>/dev/null; then
        log_success "Removed $description with sudo"
        return 0
    fi
    
    log_warning "Failed to remove $description"
    return 1
}

# ── Banner ───────────────────────────────────────────────────────────────────
show_banner() {
    printf "${GREEN}"
    cat << 'BANNER'
 $$$$$$$\   $$$$$$\             $$$$$$\            $$\   $$\ 
 $$  __$$\ $$ ___$$\           $$$ __$$\           $$ |  $$ |
 $$ |  $$ |\_/   $$ | $$$$$$$\ $$$$\ $$ |$$$$$$$\  \$$\ $$  |
 $$$$$$$  |  $$$$$ / $$  _____|$$\$$\$$ |$$  __$$\  \$$$$  / 
 $$  __$$<   \___$$\ $$ /      $$ \$$$$ |$$ |  $$ | $$  $$< 
 $$ |  $$ |$$\   $$ |$$ |      $$ |\$$$ |$$ |  $$ |$$  /\$$\
 $$ |  $$ |\$$$$$$  |\$$$$$$$\ \$$$$$$  /$$ |  $$ |$$ /  $$ |
 \__|  \__| \______/  \_______| \______/ \__|  \__|\__|  \__|
BANNER
    printf "${NC}\n"
    echo -e "${BOLD}Uninstall Script${NC} - Remove all ReconX tools"
    echo ""
}

# ── Confirmation ─────────────────────────────────────────────────────────────
show_warning() {
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                        WARNING                         ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "This will remove:"
    echo ""
    [[ -d "$USER_BIN" ]] && echo "  - Tools from $USER_BIN/"
    [[ -d "$GIT_TOOLS_DIR" ]] && echo "  - Git tools from $GIT_TOOLS_DIR/"
    [[ -d "$WORDLISTS_DIR" ]] && echo "  - Wordlists ($WORDLISTS_DIR/)"
    [[ -d "$GO_DIR" ]] && echo "  - Go ($GO_DIR/)"
    [[ -d "$GO_CACHE_DIR" ]] && echo "  - Go cache ($GO_CACHE_DIR/)"
    [[ -d "$ARJUN_PIPX_DIR" ]] && echo "  - Arjun pipx ($ARJUN_PIPX_DIR/)"
    
    echo ""
    echo -e "${YELLOW}Are you sure you want to continue?${NC}"
    echo ""
    read -p "Type 'yes' to confirm: " confirm
    
    if [[ "$confirm" != "yes" ]]; then
        echo "Cancelled."
        exit 0
    fi
}

# ── Removal Functions ────────────────────────────────────────────────────────

remove_tools() {
    echo ""
    log_info "Removing tools from $USER_BIN..."
    
    if [[ ! -d "$USER_BIN" ]]; then
        log_skip "Tools directory not found: $USER_BIN"
        return 0
    fi
    
    local removed_count=0
    local failed_count=0
    local not_found_count=0
    
    for tool in "${TOOLS[@]}"; do
        local tool_path="$USER_BIN/$tool"

        if [[ -f "$tool_path" || -L "$tool_path" ]]; then
            # Remove capabilities before deleting masscan/nmap
            if [[ "$tool" == "masscan" || "$tool" == "nmap" ]] && command -v setcap &>/dev/null; then
                setcap -r "$tool_path" 2>/dev/null || true
            fi

            if rm -f "$tool_path" 2>/dev/null; then
                echo "  Removed: $tool"
                removed_count=$((removed_count + 1))
            else
                # Try with sudo
                if sudo rm -f "$tool_path" 2>/dev/null; then
                    echo "  Removed: $tool (with sudo)"
                    removed_count=$((removed_count + 1))
                else
                    echo "  Failed: $tool"
                    failed_count=$((failed_count + 1))
                fi
            fi
        else
            not_found_count=$((not_found_count + 1))
        fi
    done
    
    echo ""
    log_info "Removed: $removed_count | Failed: $failed_count | Not Found: $not_found_count"
}

remove_git_tools() {
    echo ""
    log_info "Removing Git-based tools from $GIT_TOOLS_DIR..."
    
    if [[ ! -d "$GIT_TOOLS_DIR" ]]; then
        log_skip "Git tools directory not found"
        return 0
    fi
    
    local removed_count=0
    
    for dir in "${GIT_TOOL_DIRS[@]}"; do
        local full_path="$GIT_TOOLS_DIR/$dir"
        safe_remove "$full_path" "$dir" && removed_count=$((removed_count + 1))
    done
    
    # Remove the opt directory itself if empty
    if [[ -d "$GIT_TOOLS_DIR" && -z "$(ls -A "$GIT_TOOLS_DIR" 2>/dev/null)" ]]; then
        safe_remove "$GIT_TOOLS_DIR" "empty opt directory"
    fi
    
    if [[ $removed_count -eq 0 ]]; then
        log_skip "No Git tools found"
    else
        log_info "Removed $removed_count Git tools"
    fi
}

remove_wordlists() {
    echo ""
    log_info "Removing wordlists from $WORDLISTS_DIR..."
    safe_remove "$WORDLISTS_DIR" "wordlists"
}

remove_go() {
    echo ""
    log_info "Removing Go from $GO_DIR..."
    safe_remove "$GO_DIR" "Go"
}

remove_go_cache() {
    echo ""
    log_info "Removing Go cache from $GO_CACHE_DIR..."
    
    if [[ ! -e "$GO_CACHE_DIR" ]]; then
        log_skip "Go cache not found"
        return 0
    fi
    
    safe_remove "$GO_CACHE_DIR" "Go cache"
}

remove_arjun_pipx() {
    echo ""
    log_info "Removing Arjun pipx package..."
    safe_remove "$ARJUN_PIPX_DIR" "Arjun (pipx)"
}

# ── Main ────────────────────────────────────────────────────────────────────
main() {
    show_banner
    show_warning
    
    echo ""
    log_info "Starting uninstall..."
    
    remove_tools
    remove_git_tools
    remove_wordlists
    remove_go
    remove_go_cache
    remove_arjun_pipx
    
    echo ""
    log_success "Uninstall complete!"
}

main "$@"
