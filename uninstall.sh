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

# ── Paths ────────────────────────────────────────────────────────────────────
USER_BIN="$HOME/.local/bin"
GIT_TOOLS_DIR="$HOME/.local/opt"
WORDLISTS_DIR="$HOME/.local/share/wordlists"
GO_DIR="$HOME/.local/go"
GO_CACHE_DIR="$HOME/.local/go_cache"

# ── Tool List ────────────────────────────────────────────────────────────────
declare -a TOOLS=(
    "subfinder" "amass" "assetfinder" "dnsx" "httpx" "katana"
    "ffuf" "dalfox" "waybackurls" "gospider" "hakrawler"
    "nuclei" "masscan" "feroxbuster" "x8" "gf" "gau"
    "sqlmap" "ghauri" "gitdorker" "paramspider" "nikto"
    "wafw00f" "linkfinder" "xsstrike" "jwt-tool" "secretfinder"
    "ncat" "nmap" "nping"
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
    
    if rm -rf "$path" 2>/dev/null; then
        log_success "Removed $description"
        return 0
    else
        log_warning "Failed to remove $description"
        return 1
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

# ── Confirmation ─────────────────────────────────────────────────────────────
show_warning() {
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                        WARNING                         ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "This will remove:"
    echo ""
    echo "  - Tools from $USER_BIN/"
    [[ -d "$GIT_TOOLS_DIR" ]] && echo "  - Git tools from $GIT_TOOLS_DIR/"
    [[ -d "$WORDLISTS_DIR" ]] && echo "  - Wordlists ($WORDLISTS_DIR/)"
    [[ -d "$GO_DIR" ]] && echo "  - Go ($GO_DIR/)"
    [[ -d "$GO_CACHE_DIR" ]] && echo "  - Go cache ($GO_CACHE_DIR/)"
    
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
    
    local removed_count=0
    local skipped_count=0
    
    for tool in "${TOOLS[@]}"; do
        local tool_path="$USER_BIN/$tool"
        
        if [[ -f "$tool_path" || -L "$tool_path" ]]; then
            rm -f "$tool_path"
            echo "  Removed: $tool"
            removed_count=$((removed_count + 1))
        else
            echo "  Skipped: $tool"
            skipped_count=$((skipped_count + 1))
        fi
    done
    
    echo ""
    log_info "Removed: $removed_count | Skipped: $skipped_count"
}

remove_git_tools() {
    echo ""
    log_info "Removing Git-based tools from $GIT_TOOLS_DIR..."
    
    local removed_count=0
    
    for dir in "${GIT_TOOL_DIRS[@]}"; do
        local full_path="$GIT_TOOLS_DIR/$dir"
        
        if [[ -d "$full_path" ]]; then
            local size
            size=$(du -sh "$full_path" 2>/dev/null | cut -f1)
            if safe_remove "$full_path" "$dir"; then
                echo "  Removed: $dir ($size)"
                removed_count=$((removed_count + 1))
            fi
        fi
    done
    
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
    
    if [[ -z "$GO_CACHE_DIR" || "$GO_CACHE_DIR" == "/" ]]; then
        log_warning "Invalid path, refusing to delete"
        return 1
    fi
    
    log_warning "This requires sudo privileges..."
    
    if sudo rm -rf "$GO_CACHE_DIR" 2>/dev/null; then
        log_success "Removed Go cache"
    else
        log_warning "Some files could not be removed (permission denied)"
        return 1
    fi
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
    
    echo ""
    echo -e "${GREEN}Uninstall complete!${NC}"
}

main "$@"
