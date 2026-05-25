#!/bin/bash
set -e

################################################################################
# CONFIGURATION - Modify these variables to adapt to your program
################################################################################

# Application information
APP_NAME="EiTodo"
APP_DESCRIPTION="Eisenhower TODO matrix"
APP_COMMENT="Eisenhower matrix to-do list (PyQt6 tray app)"
APP_CATEGORIES="Utility;Office;"

# GitHub repository (the whole repo is downloaded as an archive, so every
# tracked file is installed automatically — add a file to the repo and it is
# picked up here without editing this script).
GITHUB_USER="vtflosa"
GITHUB_REPO="EiTodo"
GITHUB_BRANCH="master"

# PRIVATE repo only: a GitHub Personal Access Token with read access. Leave the
# default for a public repo. Pass it without editing this file, e.g.:
#   GITHUB_TOKEN=ghp_xxx ./install_EiTodo.sh
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# Main Python file to execute
MAIN_PYTHON_FILE="main.py"

# Icon file (must be a tracked file in the repo)
ICON_FILE="EiTodo.png"

# Python dependencies
NEEDS_TKINTER=false  # EiTodo uses PyQt6, not Tkinter

# Additional system dependencies, applied on top of the ones handled per-distro
# below (pip, venv, the Qt xcb runtime lib). Leave empty if none.
EXTRA_SYSTEM_DEPS=""

################################################################################
# END OF CONFIGURATION - Do not modify below this line
################################################################################

# Automatic calculation of installation folder based on APP_NAME
APP_NAME_LOWER=$(echo "$APP_NAME" | tr '[:upper:]' '[:lower:]')
INSTALL_SUBDIR=".local/share/${APP_NAME_LOWER}"

# Archive URL: GitHub builds this from the git tree on the fly. A token (private
# repo) uses the authenticated API tarball endpoint; otherwise the public one.
if [ -n "$GITHUB_TOKEN" ]; then
    ARCHIVE_URL="https://api.github.com/repos/${GITHUB_USER}/${GITHUB_REPO}/tarball/${GITHUB_BRANCH}"
else
    ARCHIVE_URL="https://github.com/${GITHUB_USER}/${GITHUB_REPO}/archive/refs/heads/${GITHUB_BRANCH}.tar.gz"
fi

echo "╔══════════════════════════════════════════════════╗"
echo "║     Installing ${APP_NAME}"
echo "║     ${APP_DESCRIPTION}"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Colors for messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to display messages
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Download helper: prefer curl, fall back to wget. Sends the GitHub auth header
# when GITHUB_TOKEN is set (private repo).
download() {
    # $1 = url, $2 = output path
    if command -v curl &> /dev/null; then
        if [ -n "$GITHUB_TOKEN" ]; then
            curl -fL --progress-bar -H "Authorization: Bearer $GITHUB_TOKEN" "$1" -o "$2"
        else
            curl -fL --progress-bar "$1" -o "$2"
        fi
    elif command -v wget &> /dev/null; then
        if [ -n "$GITHUB_TOKEN" ]; then
            wget -q --show-progress --header="Authorization: Bearer $GITHUB_TOKEN" "$1" -O "$2"
        else
            wget -q --show-progress "$1" -O "$2"
        fi
    else
        error "Neither curl nor wget is installed — cannot download the archive."
        exit 1
    fi
}


# #############################################################
# Check that Python 3 is installed
# #############################################################

if ! command -v python3 &> /dev/null; then
    error "Python 3 is not installed!"
    echo "Please install Python 3 first."
    exit 1
fi

info "Python 3 detected: $(python3 --version)"


# #############################################################
# Check / install system dependencies
# #############################################################
#
# EiTodo is a PyQt6 app. We need pip + venv to build the virtual environment,
# and the Qt 'xcb' platform plugin needs libxcb-cursor at runtime (PyQt6 >= 6.5)
# — without it the app fails with "Could not load the Qt platform plugin xcb".

info "Checking system dependencies..."

PIP_OK=false
if python3 -m pip --version &> /dev/null; then PIP_OK=true; fi

VENV_OK=false
if python3 -m venv --help &> /dev/null; then VENV_OK=true; fi

XCB_OK=false
if ldconfig -p 2>/dev/null | grep -q 'libxcb-cursor\.so'; then XCB_OK=true; fi

TKINTER_OK=true  # OK by default if not needed
if [ "$NEEDS_TKINTER" = true ]; then
    TKINTER_OK=false
    if python3 -c "import tkinter" 2>/dev/null; then TKINTER_OK=true; fi
fi

if [ "$PIP_OK" = true ] && [ "$VENV_OK" = true ] && [ "$XCB_OK" = true ] && [ "$TKINTER_OK" = true ]; then
    info "All system dependencies are already installed ✓"
else
    warning "Missing system dependencies:"
    [ "$PIP_OK" = false ]     && echo "  ✗ pip"
    [ "$VENV_OK" = false ]    && echo "  ✗ venv"
    [ "$XCB_OK" = false ]     && echo "  ✗ libxcb-cursor (Qt xcb plugin)"
    [ "$TKINTER_OK" = false ] && echo "  ✗ tkinter"

    info "Detecting your Linux distribution..."

    if command -v apt &> /dev/null; then
        info "Distribution detected: Debian/Ubuntu"
        PKGS=""
        [ "$PIP_OK" = false ]     && PKGS="$PKGS python3-pip"
        [ "$VENV_OK" = false ]    && PKGS="$PKGS python3-venv"
        [ "$XCB_OK" = false ]     && PKGS="$PKGS libxcb-cursor0"
        [ "$TKINTER_OK" = false ] && PKGS="$PKGS python3-tk"
        info "Installing:$PKGS $EXTRA_SYSTEM_DEPS"
        sudo apt update
        sudo apt install -y $PKGS $EXTRA_SYSTEM_DEPS

    elif command -v dnf &> /dev/null; then
        info "Distribution detected: Fedora/RHEL"
        PKGS=""
        [ "$PIP_OK" = false ]     && PKGS="$PKGS python3-pip"
        [ "$XCB_OK" = false ]     && PKGS="$PKGS xcb-util-cursor"
        [ "$TKINTER_OK" = false ] && PKGS="$PKGS python3-tkinter"
        info "Installing:$PKGS $EXTRA_SYSTEM_DEPS"
        sudo dnf install -y $PKGS $EXTRA_SYSTEM_DEPS

    elif command -v pacman &> /dev/null; then
        info "Distribution detected: Arch Linux"
        PKGS="python"
        [ "$PIP_OK" = false ]     && PKGS="$PKGS python-pip"
        [ "$XCB_OK" = false ]     && PKGS="$PKGS xcb-util-cursor"
        [ "$TKINTER_OK" = false ] && PKGS="$PKGS tk"
        info "Installing:$PKGS $EXTRA_SYSTEM_DEPS"
        sudo pacman -S --noconfirm $PKGS $EXTRA_SYSTEM_DEPS

    else
        error "Distribution not recognized."
        error "Please install manually: python3-pip, python3-venv, libxcb-cursor0"
        [ "$NEEDS_TKINTER" = true ] && error "and: python3-tk"
        exit 1
    fi

    # Post-installation check
    info "Post-installation check..."
    INSTALL_SUCCESS=true
    python3 -m pip --version &>/dev/null || { error "✗ pip still missing"; INSTALL_SUCCESS=false; }
    python3 -m venv --help   &>/dev/null || { error "✗ venv still missing"; INSTALL_SUCCESS=false; }
    if [ "$NEEDS_TKINTER" = true ] && ! python3 -c "import tkinter" 2>/dev/null; then
        error "✗ tkinter still missing"; INSTALL_SUCCESS=false
    fi
    if [ "$INSTALL_SUCCESS" = true ]; then
        info "System dependencies installed ✓"
    else
        error "Some dependencies could not be installed"
        exit 1
    fi
fi


# #############################################################
# Download and extract the application from GitHub
# #############################################################

INSTALL_DIR="$HOME/$INSTALL_SUBDIR"
info "Creating installation folder: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

info "Downloading ${APP_NAME} archive from GitHub (${GITHUB_BRANCH} branch)..."
TMP_ARCHIVE="$(mktemp --suffix=.tar.gz)"
trap 'rm -f "$TMP_ARCHIVE"' EXIT

if ! download "$ARCHIVE_URL" "$TMP_ARCHIVE"; then
    error "Failed to download the archive from: $ARCHIVE_URL"
    error "Check the repository name/branch and your internet connection."
    error "(If the repository is private, this URL requires authentication.)"
    exit 1
fi

# The archive expands to a top-level "<repo>-<branch>/" folder; --strip-components=1
# drops it so files land directly in INSTALL_DIR. Existing user data (param.json,
# logs/, save/, config.INI) is not in the archive, so a re-install keeps it.
info "Extracting into $INSTALL_DIR ..."
if ! tar -xzf "$TMP_ARCHIVE" --strip-components=1 -C "$INSTALL_DIR"; then
    error "Failed to extract the archive."
    exit 1
fi

# Sanity check: the entry point and icon must be present after extraction.
if [ ! -f "$INSTALL_DIR/$MAIN_PYTHON_FILE" ]; then
    error "Archive extracted but $MAIN_PYTHON_FILE is missing — aborting."
    exit 1
fi
if [ ! -f "$INSTALL_DIR/$ICON_FILE" ]; then
    warning "Icon $ICON_FILE not found in the archive; the launcher will have no icon."
fi

info "Application files installed ✓"


# #############################################################
# Virtual environment and dependencies
# #############################################################

cd "$INSTALL_DIR"

info "Creating Python virtual environment..."
python3 -m venv venv

info "Installing Python dependencies..."
source venv/bin/activate

if ! pip install --upgrade pip; then
    error "Failed to upgrade pip"
    deactivate
    exit 1
fi

if ! pip install -r requirements.txt; then
    error "Failed to install Python dependencies from requirements.txt"
    error "Check the content of requirements.txt and your internet connection"
    deactivate
    exit 1
fi

deactivate
info "Dependencies installed ✓"


# #############################################################
# Create .desktop launcher
# #############################################################

info "Creating application launcher..."
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

# Path= is required: EiTodo resolves logs/, save/ and param.json relative to the
# working directory, so the launcher must start it inside INSTALL_DIR.
cat > "$DESKTOP_DIR/${APP_NAME}.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=${APP_NAME}
Comment=${APP_COMMENT}
Exec=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/${MAIN_PYTHON_FILE}
Path=$INSTALL_DIR
Icon=$INSTALL_DIR/${ICON_FILE}
Terminal=false
Categories=${APP_CATEGORIES}
StartupNotify=true
EOF

chmod +x "$DESKTOP_DIR/${APP_NAME}.desktop"
info "Launcher created ✓"

# Also create a launcher on the desktop if the folder exists
DESKTOP_FOLDER=""
if [ -d "$HOME/Bureau" ]; then
    DESKTOP_FOLDER="$HOME/Bureau"
elif [ -d "$HOME/Desktop" ]; then
    DESKTOP_FOLDER="$HOME/Desktop"
fi

if [ -n "$DESKTOP_FOLDER" ]; then
    info "Creating desktop shortcut..."
    cp "$DESKTOP_DIR/${APP_NAME}.desktop" "$DESKTOP_FOLDER/"
    chmod +x "$DESKTOP_FOLDER/${APP_NAME}.desktop"

    # For GNOME, mark as trusted
    if [ "$XDG_CURRENT_DESKTOP" = "GNOME" ] || [ "$XDG_CURRENT_DESKTOP" = "ubuntu:GNOME" ]; then
        gio set "$DESKTOP_FOLDER/${APP_NAME}.desktop" metadata::trusted true 2>/dev/null || true
    fi
    info "Desktop shortcut created ✓"
fi


# #############################################################
# Create uninstall script
# #############################################################

cat > "$INSTALL_DIR/uninstall.sh" << EOF
#!/bin/bash
echo "Uninstalling ${APP_NAME}..."
rm -rf "$INSTALL_DIR"
rm -f "$DESKTOP_DIR/${APP_NAME}.desktop"
rm -f ~/Bureau/${APP_NAME}.desktop
rm -f ~/Desktop/${APP_NAME}.desktop
echo "${APP_NAME} has been uninstalled."
EOF

chmod +x "$INSTALL_DIR/uninstall.sh"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         Installation completed successfully! ✓   ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
info "${APP_NAME} has been installed in: $INSTALL_DIR"
info "You can now launch the application from:"
echo "  • The applications menu (search for '${APP_NAME}')"
if [ -n "$DESKTOP_FOLDER" ]; then
    echo "  • The icon on your desktop"
fi
echo ""
info "To uninstall cleanly, execute in console: $INSTALL_DIR/uninstall.sh"
echo ""
echo ""
echo "Thank you!"
