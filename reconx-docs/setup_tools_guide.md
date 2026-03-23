# reconx Tools Installation Guide

## Quick Start

```bash
# Run the complete setup (requires sudo)
sudo bash setup_tools.sh

# Or install specific categories only
sudo bash setup_tools.sh --go       # Go-based tools only
sudo bash setup_tools.sh --python   # Python tools only
sudo bash setup_tools.sh --git      # Git-based tools only
sudo bash setup_tools.sh --wordlists # Wordlists only
```

## Tools Installed

### Go-Based Tools (via `go install`)

| Tool | Repository | Purpose |
|------|------------|---------|
| subfinder | projectdiscovery/subfinder | Subdomain discovery |
| amass | OWASP/Amass | In-depth subdomain enumeration |
| assetfinder | tomnomnom/assetfinder | Find domains and subdomains |
| dnsx | projectdiscovery/dnsx | DNS toolkit |
| httpx | projectdiscovery/httpx | Fast HTTP prober |
| katana | projectdiscovery/katana | Web crawler |
| ffuf | ffuf/ffuf | Fast web fuzzer |
| dalfox | hahwul/dalfox | XSS scanner |
| gf | tomnomnom/gf | grep on steroids |
| waybackurls | tomnomnom/waybackurls | Wayback Machine URLs |
| gau | lc/gau | GetAllUrls |
| gospider | jaeles-project/gospider | Web spider |
| hakrawler | hakluke/hakrawler | URL discovery |
| nuclei | projectdiscovery/nuclei | Vulnerability scanner |

### Python-Based Tools (via `pip3`)

| Tool | Repository | Purpose |
|------|------------|---------|
| arjun | s0md3v/Arjun | HTTP parameter discovery |
| ghauri | r0oth3x49/ghauri | SQL injection tool |
| trufflehog | trufflesecurity/trufflehog | Secret scanner |

### Git-Based Tools (cloned to `/opt`)

| Tool | Repository | Purpose |
|------|------------|---------|
| sqlmap | sqlmapproject/sqlmap | SQL injection automation |
| paramspider | devanshbatham/ParamSpider | Parameter discovery |
| secretfinder | m4ll0k/SecretFinder | Secret detection in JS |
| wafw00f | EnableSecurity/wafw00f | WAF detection |
| nikto | sullo/nikto | Web vulnerability scanner |
| linkfinder | GerbenJavado/LinkFinder | JS endpoint discovery |
| xsstrike | s0md3v/XSStrike | XSS detection |
| ssrfire | 0xInfection/ssrfire | SSRF exploitation |
| jwt-tool | ticarpi/jwt_tool | JWT manipulation |
| gitdorker | obheda12/GitDorker | GitHub dorking |

### Compiled/Binary Tools

| Tool | Source | Purpose |
|------|--------|---------|
| nmap | apt/yum/pacman | Network scanner |
| masscan | robertdavidgraham/masscan | Fast port scanner |
| feroxbuster | epi052/feroxbuster | Content discovery |
| x8 | Sh1Yo/x8 | Hidden parameter discovery |

### Wordlists

| Collection | Location |
|------------|----------|
| SecLists | `/usr/share/wordlists/SecLists` |
| PayloadsAllTheThings | `/usr/share/wordlists/PayloadsAllTheThings` |

## Installation Details

### Directory Structure After Setup

```
/usr/local/bin/          # All tool binaries
├── subfinder
├── amass
├── dnsx
├── httpx
├── katana
├── ffuf
├── dalfox
├── gf
├── waybackurls
├── gau
├── gospider
├── hakrawler
├── nuclei
├── arjun
├── ghauri
├── trufflehog
├── sqlmap          (wrapper script)
├── paramspider     (wrapper script)
├── secretfinder    (wrapper script)
├── wafw00f         (symlink)
├── nikto           (wrapper script)
├── linkfinder      (wrapper script)
├── xsstrike        (wrapper script)
├── ssrfire         (wrapper script)
├── jwt-tool        (wrapper script)
├── gitdorker       (wrapper script)
├── masscan
├── nmap
├── feroxbuster
└── x8

/opt/                    # Git-cloned tools
├── sqlmap/
├── ParamSpider/
├── SecretFinder/
├── wafw00f/
├── nikto/
├── LinkFinder/
├── XSStrike/
├── ssrfire/
├── jwt_tool/
├── GitDorker/
├── masscan/
└── ...

/usr/share/wordlists/    # Wordlists
├── SecLists/
└── PayloadsAllTheThings/

/usr/local/go/           # Go installation
└── bin/
    └── go

/root/go/bin/            # Go tools before copying
└── [compiled tools]
```

## Verifying Installation

```bash
# Check all tools
which subfinder amass dnsx httpx katana ffuf dalfox gf waybackurls gau gospider hakrawler nuclei arjun ghauri trufflehog sqlmap paramspider secretfinder wafw00f nikto linkfinder xsstrike ssrfire jwt-tool gitdorker masscan nmap feroxbuster x8

# Test individual tools
subfinder -version
nuclei -version
sqlmap --version
nmap --version
```

## Updating Tools

### Update Go Tools
```bash
# Re-run the installer for Go tools
sudo bash setup_tools.sh --go
```

### Update Git Tools
```bash
# Update all git-based tools
cd /opt/sqlmap && git pull
cd /opt/ParamSpider && git pull
cd /opt/SecretFinder && git pull
# ... etc
```

### Update Nuclei Templates
```bash
nuclei -update-templates
```

### Update Wordlists
```bash
cd /usr/share/wordlists/SecLists && git pull
cd /usr/share/wordlists/PayloadsAllTheThings && git pull
```

## Troubleshooting

### "command not found" after installation

```bash
# Reload shell environment
source /etc/profile.d/go.sh
source ~/.bashrc
# Or
source ~/.zshrc

# Or open a new terminal
```

### Go tools not found

```bash
# Check Go installation
go version

# Check Go binary path
ls -la /usr/local/go/bin/

# Check if ~/go/bin exists
ls -la ~/go/bin/

# Add to PATH manually
export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin
```

### Python tools not found

```bash
# Check pip installation
pip3 list | grep -E "arjun|ghauri"

# Reinstall
pip3 install --force-reinstall arjun ghauri
```

### Permission denied

```bash
# Fix permissions
sudo chmod +x /usr/local/bin/*
```

### Missing dependencies

```bash
# Reinstall system dependencies
sudo apt-get update
sudo apt-get install -y build-essential libpcap-dev libssl-dev
```

## Manual Installation (If Script Fails)

### Install Go Manually

```bash
# Download
wget https://go.dev/dl/go1.22.0.linux-amd64.tar.gz

# Extract
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz

# Add to PATH
echo 'export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin' >> ~/.bashrc
# Or
echo 'export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin' >> ~/.zshrc
source ~/.bashrc
# OR
source ~/.zshrc

# Verify
go version
```

### Install Subfinder Manually

```bash
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
sudo cp ~/go/bin/subfinder /usr/local/bin/
```

### Install SQLMap Manually

```bash
sudo git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git /opt/sqlmap
sudo tee /usr/local/bin/sqlmap << 'EOF'
#!/bin/bash
python3 /opt/sqlmap/sqlmap.py "$@"
EOF
sudo chmod +x /usr/local/bin/sqlmap
```

## Uninstalling

```bash
# Remove all tools
sudo rm -f /usr/local/bin/{subfinder,amass,dnsx,httpx,katana,ffuf,dalfox,gf,waybackurls,gau,gospider,hakrawler,nuclei,arjun,ghauri,trufflehog,sqlmap,paramspider,secretfinder,wafw00f,nikto,linkfinder,xsstrike,ssrfire,jwt-tool,gitdorker,masscan,nmap,feroxbuster,x8}

# Remove git tools
sudo rm -rf /opt/{sqlmap,ParamSpider,SecretFinder,wafw00f,nikto,LinkFinder,XSStrike,ssrfire,jwt_tool,GitDorker,masscan}

# Remove wordlists
sudo rm -rf /usr/share/wordlists

# Remove Go (optional)
sudo rm -rf /usr/local/go
sudo rm -f /etc/profile.d/go.sh
```

## System Requirements

- **OS**: Ubuntu 20.04+, Debian 10+, or similar
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 10GB free space (mostly for wordlists)
- **Network**: Internet connection for downloads
- **Privileges**: Root/sudo access required

## Security Notes

- All tools are installed from official repositories
- Go tools are compiled from source
- Python tools use pip with latest versions
- Git tools track the main/master branch
- Wordlists are community-maintained collections
