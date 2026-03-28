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
DRY_RUN=false

# ── Paths ──────────────────────────────────────────────────────────────────
USER_BIN="$HOME/.local/bin"
GIT_TOOLS_DIR="$HOME/.local/opt"
WORDLISTS_DIR="$HOME/.local/share/wordlists"
GO_DIR="$HOME/.local/go"

# ── Tool List ────────────────────────────────────────────────────────────────
declare -a TOOLS=(
    "subfinder" "amass" "assetfinder" "dnsx" "httpx" "katana"
    "ffuf" "dalfox" "waybackurls" "gospider" "hakrawler"
    "nuclei" "masscan" "feroxbuster" "x8"
    "sqlmap" "ghauri" "gitdorker" "paramspider" "nikto"
    "wafw00f" "linkfinder" "xsstrike" "jwt-tool" "secretfinder"
)

# ── Logging ──────────────────────────────────────────────────────────────────
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
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
    echo -e "${GREEN}Detected: User installation${NC}"
    echo "  Paths: ~/.local/bin/, ~/.local/opt/, ~/.local/share/"
    echo ""
}
show_help() {
    show_banner
    echo -e "${BOLD}USAGE:${NC}"
    echo "  $0 [OPTIONS]"
    echo ""
    echo -e "${BOLD}OPTIONS:${NC}"
    echo "  --full        Remove everything (tools, wordlists, Go)"
    echo "  --tools       Remove tools only (keep wordlists, Go)"
    echo "  --wordlists   Remove wordlists only [all|seclists|payloads]"
    echo "  --dry-run     Preview only (show what would be removed)"
    echo "  --help        Show this help message"
    echo ""
    echo -e "${BOLD}REMOVES:${NC}"
    echo "  Tools:        ~/.local/bin/ (subfinder, amass, httpx, ffuf, etc.)"
    echo "  Git Tools:    ~/.local/opt/ (sqlmap, nikto, xsstrike, etc.)"
    echo "  Wordlists:    ~/.local/share/wordlists/"
    echo "  Go:           ~/.local/go/"
    echo ""
    echo -e "${BOLD}EXAMPLES:${NC}"
    echo "  $0 --full                     # Remove everything"
    echo "  $0 --tools                    # Remove tools only"
    echo "  $0 --wordlists                # Remove all wordlists"
    echo "  $0 --wordlists seclists       # Remove only SecLists"
    echo "  $0 --dry-run                  # Preview what would be removed"
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
    
    # Tools in ~/.local/bin
    echo -e "${BOLD}Tools in $USER_BIN/:${NC}"
    local tools_found=false
    local tools_size=0
    for tool in "${TOOLS[@]}"; do
        if [ -f "$USER_BIN/$tool" ]; then
            echo "  - $tool"
            tools_found=true
            tools_size=$((tools_size + $(stat -c%s "$USER_BIN/$tool" 2>/dev/null || echo 0)))
        fi
    done
    if [ "$tools_found" = true ]; then
        echo "  Size: $(format_bytes $tools_size)"
        total_size=$((total_size + tools_size))
    else
        echo "  (none found)"
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
    
    # Go Runtime
    echo -e "${BOLD}Go in $GO_DIR/:${NC}"
    if [ -d "$GO_DIR" ]; then
        local go_size=$(get_size "$GO_DIR")
        echo "  - Go ($go_size)"
        total_size=$((total_size + $(get_size_bytes "$GO_DIR")))
    else
        echo "  (not found)"
    fi
    echo ""
    
    # Summary
    echo -e "${BOLD}────────────────────────────────────────${NC}"
    echo -e "Total: ${GREEN}$(format_bytes $total_size)${NC}"
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
    
    echo "  - Tools from $USER_BIN/"
    [ -d "$GIT_TOOLS_DIR" ] && echo "  - Git tools from $GIT_TOOLS_DIR/"
    [ -d "$WORDLISTS_DIR" ] && echo "  - Wordlists ($WORDLISTS_DIR/)"
    [ -d "$GO_DIR" ] && echo "  - Go ($GO_DIR/)"
    
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

remove_tools() {
    echo ""
    log_info "Removing tools from $USER_BIN..."
    
    local removed_count=0
    for tool in "${TOOLS[@]}"; do
        if [ -f "$USER_BIN/$tool" ] || [ -L "$USER_BIN/$tool" ]; then
            if [ "$DRY_RUN" = true ]; then
                print_dry_run "$USER_BIN/$tool"
            else
                rm -f "$USER_BIN/$tool"
                echo "  Removed: $tool"
                removed_count=$((removed_count + 1))
            fi
        fi
    done
    
    if [ "$removed_count" -eq 0 ]; then
        log_skip "No tools found"
    elif [ "$DRY_RUN" = false ]; then
        log_success "Removed $removed_count tools"
    fi
}

remove_git_tools() {
    echo ""
    log_info "Removing Git-based tools from $GIT_TOOLS_DIR..."
    
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
                    rm -rf "$GIT_TOOLS_DIR/$dir_name"
                    echo "  Removed: $dir_name ($size)"
                    removed_count=$((removed_count + 1))
                fi
            fi
        done
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
                rm -rf "$WORDLISTS_DIR/SecLists"
                echo "  Removed: SecLists"
            else
                log_skip "SecLists not found"
            fi
            ;;
        payloads)
            if [ -d "$WORDLISTS_DIR/PayloadsAllTheThings" ]; then
                rm -rf "$WORDLISTS_DIR/PayloadsAllTheThings"
                echo "  Removed: PayloadsAllTheThings"
            else
                log_skip "PayloadsAllTheThings not found"
            fi
            ;;
        all|"")
            rm -rf "$WORDLISTS_DIR"
            log_success "Removed wordlists ($size)"
            ;;
        *)
            log_error "Unknown target: $target (use: all, seclists, or payloads)"
            ;;
    esac
}

remove_go() {
    echo ""
    log_info "Removing Go from $GO_DIR..."
    
    if [ ! -d "$GO_DIR" ]; then
        log_skip "Go not found"
        return
    fi
    
    local size=$(get_size "$GO_DIR")
    
    if [ "$DRY_RUN" = true ]; then
        print_dry_run "$GO_DIR ($size)"
        return
    fi
    
    rm -rf "$GO_DIR"
    log_success "Removed Go ($size)"
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    local mode="${1:-help}"
    
    if [ "$mode" = "--dry-run" ]; then
        show_detection_info
    fi
    
    case "$mode" in
        --full)
            show_warning
            show_detection_info
            echo ""
            log_info "Starting full uninstall..."
            remove_tools
            remove_git_tools
            remove_wordlists
            remove_go
            ;;
        --tools)
            show_warning
            show_detection_info
            echo ""
            log_info "Removing tools only..."
            remove_tools
            remove_git_tools
            ;;
        --wordlists)
            show_warning
            show_detection_info
            local wl_target="${2:-all}"
            remove_wordlists "$wl_target"
            ;;
        --dry-run)
            DRY_RUN=true
            log_info "Dry run mode - showing what would be removed..."
            echo ""
            echo "Run without --dry-run to actually remove."
            echo ""
            list_installed
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
