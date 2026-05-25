#!/bin/bash
set -e

################################################################################
# CONFIGURATION - Modify these variables to adapt to your program
################################################################################

# Application information
APP_NAME="MyPythonApp"
APP_DESCRIPTION="Short description of your app"
APP_COMMENT="Comment for the launcher"
APP_CATEGORIES="Utility;Graphics;"

# GitHub repository URL (without trailing /)
GITHUB_REPO_URL="https://raw.githubusercontent.com/USER/REPO/main"

# List of files to download from GitHub
# Format: "remote_filename:local_filename" (or just "filename" if identical)
DOWNLOAD_FILES=(
    "main.py"
    "requirements.txt"
    "icon.png"
)

# Main Python file to execute
MAIN_PYTHON_FILE="main.py"

# Icon file
ICON_FILE="icon.png"

# Python dependencies
NEEDS_TKINTER=true  # true if your program uses Tkinter, false otherwise

# Additional system dependencies (in addition to python3-pip, python3-venv and possibly python3-tk)
# Leave empty if no additional dependencies
EXTRA_SYSTEM_DEPS=""

################################################################################
# END OF CONFIGURATION - Do not modify below this line
################################################################################

# Automatic calculation of installation folder based on APP_NAME
APP_NAME_LOWER=$(echo "$APP_NAME" | tr '[:upper:]' '[:lower:]')
INSTALL_SUBDIR=".local/share/${APP_NAME_LOWER}"

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
# Check if tkinter, pip and venv are already installed
# #############################################################

info "Checking Python dependencies..."

TKINTER_OK=true  # OK by default if not needed
PIP_OK=false
VENV_OK=false

# Test tkinter only if needed
if [ "$NEEDS_TKINTER" = true ]; then
    TKINTER_OK=false
    if python3 -c "import tkinter" 2>/dev/null; then
        TKINTER_OK=true
    fi
fi

# Test pip
if python3 -m pip --version &>/dev/null; then
    PIP_OK=true
fi

# Test venv
if python3 -m venv --help &>/dev/null; then
    VENV_OK=true
fi

# Check if everything is present
if [ "$TKINTER_OK" = true ] && [ "$PIP_OK" = true ] && [ "$VENV_OK" = true ]; then
    if [ "$NEEDS_TKINTER" = true ]; then
        info "All dependencies are already installed (tkinter, pip, venv) ✓"
    else
        info "All dependencies are already installed (pip, venv) ✓"
    fi
    ALL_INSTALLED=true
else
    # Display what's missing
    warning "Missing dependencies:"
    [ "$NEEDS_TKINTER" = true ] && [ "$TKINTER_OK" = false ] && echo "  ✗ tkinter"
    [ "$PIP_OK" = false ] && echo "  ✗ pip"
    [ "$VENV_OK" = false ] && echo "  ✗ venv"
    ALL_INSTALLED=false
fi

# Install only if something is missing
if [ "$ALL_INSTALLED" = false ]; then
    info "Detecting your Linux distribution..."
    
    # Build the list of packages to install
    TKINTER_PACKAGE=""
    if [ "$NEEDS_TKINTER" = true ]; then
        TKINTER_PACKAGE="python3-tk"
    fi
    
    if command -v apt &> /dev/null; then
        PKG_MANAGER="apt"
        DISTRO="Debian/Ubuntu"
        info "Distribution detected: $DISTRO"
        info "Installing missing dependencies..."
        sudo apt update
        sudo apt install -y $TKINTER_PACKAGE python3-pip python3-venv $EXTRA_SYSTEM_DEPS
        
    elif command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
        DISTRO="Fedora/RHEL"
        TKINTER_FEDORA=""
        if [ "$NEEDS_TKINTER" = true ]; then
            TKINTER_FEDORA="python3-tkinter"
        fi
        info "Distribution detected: $DISTRO"
        info "Installing missing dependencies..."
        sudo dnf install -y $TKINTER_FEDORA python3-pip $EXTRA_SYSTEM_DEPS
        
    elif command -v pacman &> /dev/null; then
        PKG_MANAGER="pacman"
        DISTRO="Arch Linux"
        TKINTER_ARCH=""
        if [ "$NEEDS_TKINTER" = true ]; then
            TKINTER_ARCH="tk"
        fi
        info "Distribution detected: $DISTRO"
        info "Installing missing dependencies..."
        sudo pacman -S --noconfirm python $TKINTER_ARCH python-pip $EXTRA_SYSTEM_DEPS
        
    else
        error "Distribution not recognized."
        if [ "$NEEDS_TKINTER" = true ]; then
            error "Please install manually: python3-tk, python3-pip, python3-venv"
        else
            error "Please install manually: python3-pip, python3-venv"
        fi
        exit 1
    fi
    
    # Check that everything is now installed
    info "Post-installation check..."
    INSTALL_SUCCESS=true
    
    if [ "$NEEDS_TKINTER" = true ] && ! python3 -c "import tkinter" 2>/dev/null; then
        error "✗ tkinter could not be installed"
        INSTALL_SUCCESS=false
    fi
    
    if ! python3 -m pip --version &>/dev/null; then
        error "✗ pip could not be installed"
        INSTALL_SUCCESS=false
    fi
    
    if ! python3 -m venv --help &>/dev/null; then
        error "✗ venv could not be installed"
        INSTALL_SUCCESS=false
    fi
    
    if [ "$INSTALL_SUCCESS" = true ]; then
        info "All dependencies have been successfully installed ✓"
    else
        error "Some dependencies could not be installed"
        exit 1
    fi
fi


# #############################################################
# Create installation folder
# #############################################################

INSTALL_DIR="$HOME/$INSTALL_SUBDIR"
info "Creating installation folder: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Download files from GitHub
info "Downloading files from GitHub..."

for file_entry in "${DOWNLOAD_FILES[@]}"; do
    # Separate remote name from local name if format "remote:local"
    if [[ "$file_entry" == *":"* ]]; then
        remote_file="${file_entry%%:*}"
        local_file="${file_entry##*:}"
    else
        remote_file="$file_entry"
        local_file="$file_entry"
    fi
    
    info "Downloading $remote_file..."
    if ! wget -q --show-progress "$GITHUB_REPO_URL/$remote_file" -O "$local_file"; then
        error "Failed to download $remote_file"
        exit 1
    fi
done

info "All files have been successfully downloaded ✓"


# #############################################################
# Virtual environment and dependencies
# #############################################################

# Create a virtual environment
info "Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment and install dependencies
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

info "Dependencies installed ✓"


# #############################################################
# Create .desktop launcher
# #############################################################

info "Creating application launcher..."
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/${APP_NAME}.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=${APP_NAME}
Comment=${APP_COMMENT}
Exec=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/${MAIN_PYTHON_FILE}
Icon=$INSTALL_DIR/${ICON_FILE}
Terminal=false
Categories=${APP_CATEGORIES}
StartupNotify=true
EOF

chmod +x "$DESKTOP_DIR/${APP_NAME}.desktop"

info "Launcher created ✓"

# Also create a launcher on desktop if folder exists
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
