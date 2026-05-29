#!/usr/bin/env bash
#
# PR Fairy One-Command Installer
# https://prfairy.dev
#
# Usage:
#   curl -fsSL https://get.prfairy.dev | bash
#
# This script installs the CLI and immediately launches the interactive wizard.

set -euo pipefail

# Colors
BOLD='\033[1m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

echo -e "${MAGENTA}"
cat <<'EOF'
    ✨  PR FAIRY  ✨
    Ночная фея, которая чинит твой репозиторий пока ты спишь
EOF
echo -e "${RESET}"

info()  { echo -e "${CYAN}➜${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()  { echo -e "${YELLOW}⚠${RESET} $*"; }
error() { echo -e "${RED}✗${RESET} $*"; }

# Detect OS
OS="$(uname -s)"
case "$OS" in
    Darwin)   PLATFORM="macos" ;;
    Linux)    PLATFORM="linux" ;;
    MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
    *)        PLATFORM="unknown" ;;
esac

info "Platform: $PLATFORM"

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
    error "Python 3 is not installed."
    echo "Please install Python 3.10+ from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
info "Python $PYTHON_VERSION"

# Very rough version check
python3 - <<'PY' || {
import sys
v = sys.version_info
if (v.major, v.minor) < (3, 10):
    sys.exit(1)
PY
    error "Python 3.10 or newer is required. You have $PYTHON_VERSION"
    exit 1
}

# Ensure pipx
ensure_pipx() {
    if command -v pipx >/dev/null 2>&1; then
        success "pipx is already installed"
        return 0
    fi

    info "Installing pipx (recommended way to install Python CLIs)..."

    if [[ "$PLATFORM" == "macos" ]]; then
        if command -v brew >/dev/null 2>&1; then
            brew install pipx
        else
            python3 -m pip install --user pipx
        fi
    elif [[ "$PLATFORM" == "linux" ]]; then
        python3 -m pip install --user pipx
        python3 -m pipx ensurepath
    else
        python3 -m pip install --user pipx
    fi

    export PATH="$HOME/.local/bin:$PATH"

    if command -v pipx >/dev/null 2>&1; then
        success "pipx installed"
    else
        warn "pipx may not be in PATH yet. Restart your terminal after installation."
    fi
}

ensure_pipx

# Install pr-fairy
info "Installing / upgrading PR Fairy..."

# For now we install from git. Later this will become a normal PyPI package.
if pipx list 2>/dev/null | grep -q "pr-fairy"; then
    info "Upgrading existing installation..."
    pipx upgrade pr-fairy 2>/dev/null || pipx install --force git+https://github.com/lunvex-code/pr-fairy.git
else
    pipx install git+https://github.com/lunvex-code/pr-fairy.git --force
fi

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v fairy >/dev/null 2>&1; then
    for p in "$HOME/.local/bin/fairy" "/opt/homebrew/bin/fairy" "/usr/local/bin/fairy"; do
        if [ -x "$p" ]; then
            export PATH="$(dirname "$p"):$PATH"
            break
        fi
    done
fi

if ! command -v fairy >/dev/null 2>&1; then
    error "Could not find the 'fairy' command after installation."
    echo "Try restarting your terminal and running:"
    echo "    fairy install"
    exit 1
fi

success "PR Fairy CLI installed!"

# Launch the wizard only if we're in an interactive terminal.
# When the script is piped (curl | bash), we must not try to run interactive prompts.
if [ -t 0 ]; then
    echo
    echo -e "${BOLD}${MAGENTA}Starting the interactive setup wizard...${RESET}"
    echo
    exec fairy install "$@"
else
    echo
    echo -e "${BOLD}${GREEN}Installation complete!${RESET}"
    echo
    echo "To finish setting up PR Fairy (choose language, model, etc.), run:"
    echo
    echo "    ${BOLD}fairy install${RESET}"
    echo
    echo "You can also start using it right away with:"
    echo "    fairy watch --help"
    echo
fi
