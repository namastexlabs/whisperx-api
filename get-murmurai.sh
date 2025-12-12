#!/usr/bin/env bash
# 🎙️ MurmurAI API - GPU Transcription in One Command
set -e

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COLOR CODES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REQUIRED_PYTHON="3.12"
CONFIG_DIR="$HOME/.config/murmurai"
CPU_MODE=false

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

command_exists() {
    local cmd="$1"
    local cmd_path=$(command -v "$cmd" 2>/dev/null)

    # In WSL, ignore Windows paths (mounted under /mnt/)
    if [[ -n "$cmd_path" ]] && [[ "$cmd_path" == /mnt/* ]]; then
        return 1
    fi

    [ -n "$cmd_path" ] && [ -x "$cmd_path" ]
}

add_to_profile() {
    local line="$1"
    local comment="$2"

    for profile in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.profile"; do
        if [ -f "$profile" ] && [ -w "$profile" ]; then
            if ! grep -qF "$line" "$profile" 2>/dev/null; then
                {
                    echo ''
                    echo "# $comment"
                    echo "$line"
                } >> "$profile" 2>/dev/null || true
            fi
        fi
    done
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WELCOME MESSAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${CYAN}🎙️  MurmurAI API Installer${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "GPU-powered transcription API in one command"
echo ""
echo "Features:"
echo "  🗣️  Speaker diarization (who said what)"
echo "  ⏱️  Word-level timestamps"
echo "  📄  Export to SRT, VTT, JSON, TXT"
echo "  🚀  GPU-accelerated (or CPU fallback)"
echo ""
echo "This script will:"
echo "  1. Check/install Python 3.12"
echo "  2. Check/install uv (fast Python package manager)"
echo "  3. Check GPU/CUDA availability"
echo "  4. Install murmurai"
echo "  5. Create default configuration"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. DETECT OPERATING SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OS_TYPE="unknown"
DISTRO="unknown"
ARCH=$(uname -m)

if [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
    echo -e "${CYAN}🍎 Detected: macOS (${ARCH})${NC}"
    echo -e "${YELLOW}⚠️  Note: macOS has no CUDA support. CPU mode will be used (slower).${NC}"

elif [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "linux"* ]]; then
    OS_TYPE="linux"

    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        echo -e "${CYAN}🐧 Detected: Linux - $DISTRO (${ARCH})${NC}"
    else
        echo -e "${CYAN}🐧 Detected: Linux - unknown distro (${ARCH})${NC}"
    fi

    # Check if running in WSL
    if grep -qi microsoft /proc/version 2>/dev/null; then
        echo -e "${CYAN}   Running in WSL2${NC}"
    fi

elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    echo -e "${RED}❌ Windows detected. Please use WSL2 for GPU support.${NC}"
    echo ""
    echo "Install WSL2:"
    echo "  wsl --install -d Ubuntu"
    echo ""
    echo "Then run this script inside WSL2."
    exit 1
fi

echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. CHECK/INSTALL UV
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

install_uv() {
    if command_exists uv; then
        local uv_version=$(uv --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        echo -e "${GREEN}✅ uv already installed (v${uv_version})${NC}"
        return 0
    fi

    echo -e "${MAGENTA}📦 Installing uv (fast Python package manager)...${NC}"

    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Add to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"

    # Add to shell profiles
    add_to_profile 'export PATH="$HOME/.local/bin:$PATH"' "uv (added by murmurai installer)"

    if command_exists uv; then
        echo -e "${GREEN}✅ uv installed successfully!${NC}"
    else
        echo -e "${RED}❌ Failed to install uv${NC}"
        exit 1
    fi
    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. CHECK PYTHON 3.12
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

check_python() {
    echo -e "${CYAN}🐍 Checking Python version...${NC}"

    # uv can manage Python versions, so we'll use that
    if command_exists uv; then
        # Check if Python 3.12 is available via uv
        if uv python list 2>/dev/null | grep -q "3.12"; then
            echo -e "${GREEN}✅ Python 3.12 available via uv${NC}"
            return 0
        fi

        echo -e "${MAGENTA}📦 Installing Python 3.12 via uv...${NC}"
        uv python install 3.12
        echo -e "${GREEN}✅ Python 3.12 installed!${NC}"
    fi
    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. CHECK GPU/CUDA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

check_gpu() {
    echo -e "${CYAN}🎮 Checking GPU/CUDA availability...${NC}"

    # Check for NVIDIA driver
    if ! command_exists nvidia-smi; then
        echo -e "${YELLOW}⚠️  nvidia-smi not found${NC}"

        if [[ "$OS_TYPE" == "macos" ]]; then
            echo -e "${YELLOW}   macOS does not support NVIDIA CUDA.${NC}"
            CPU_MODE=true
        else
            echo ""
            echo "To use GPU acceleration, install NVIDIA drivers:"
            echo ""
            if [[ "$DISTRO" == "ubuntu" ]] || [[ "$DISTRO" == "debian" ]]; then
                echo "  sudo apt update"
                echo "  sudo apt install nvidia-driver-550"  # or latest version
                echo "  sudo reboot"
            else
                echo "  Visit: https://www.nvidia.com/drivers"
            fi
            echo ""
            echo -e "${YELLOW}⚠️  No NVIDIA GPU detected. CPU mode will be VERY slow.${NC}"
            echo -e "${YELLOW}   A 1-minute audio file may take 10+ minutes to transcribe.${NC}"
            echo ""
            read -p "Continue with CPU mode anyway? [y/N] " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Installation cancelled. Install NVIDIA drivers and try again."
                exit 1
            fi
            CPU_MODE=true
        fi
    else
        # nvidia-smi exists, check GPU info
        echo -e "${GREEN}✅ NVIDIA driver found${NC}"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | while read line; do
            echo -e "   ${CYAN}GPU: $line${NC}"
        done

        # Check CUDA version
        if command_exists nvcc; then
            local cuda_version=$(nvcc --version | grep -oE 'release [0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+')
            echo -e "${GREEN}✅ CUDA Toolkit: v${cuda_version}${NC}"
        else
            # CUDA toolkit not installed, but driver is - that's usually fine
            echo -e "${YELLOW}⚠️  CUDA Toolkit not found (nvcc), but driver is present${NC}"
            echo -e "   PyTorch bundles CUDA runtime, so this should work.${NC}"
        fi
    fi
    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. INSTALL MURMURAI-API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

install_murmurai_api() {
    echo -e "${CYAN}🎙️ How would you like to use murmurai?${NC}"
    echo ""
    echo -e "  1) ${GREEN}Run now (recommended)${NC} - No installation, runs immediately"
    echo "     Uses: uvx murmurai"
    echo ""
    echo "  2) Install globally - Adds 'murmurai' command to your PATH"
    echo "     Uses: uv tool install murmurai"
    echo ""
    read -p "Choose [1/2] (default: 1): " -n 1 -r
    echo

    case $REPLY in
        2)
            echo -e "${MAGENTA}📦 Installing globally...${NC}"
            if uv tool install murmurai; then
                echo -e "${GREEN}✅ Installed! Run anytime with: murmurai${NC}"
            else
                echo -e "${RED}❌ Installation failed. Try running directly with: uvx murmurai${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "${GREEN}✅ Ready to run!${NC}"
            echo ""
            echo "Starting murmurai..."
            echo ""
            exec uvx murmurai
            ;;
    esac
    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. CREATE DEFAULT CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

create_config() {
    echo -e "${CYAN}⚙️  Setting up configuration...${NC}"

    mkdir -p "$CONFIG_DIR"

    if [ ! -f "$CONFIG_DIR/.env" ]; then
        # Generate a random API key
        API_KEY=$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32)

        cat > "$CONFIG_DIR/.env" << EOF
# MurmurAI API Configuration
# Generated by get-murmurai.sh

# API authentication key (required)
MURMURAI_API_KEY=${API_KEY}

# Server settings
MURMURAI_HOST=0.0.0.0
MURMURAI_PORT=8880

# Model settings
MURMURAI_MODEL=large-v3-turbo
MURMURAI_COMPUTE_TYPE=float16
MURMURAI_BATCH_SIZE=16

# GPU device (for multi-GPU systems)
MURMURAI_DEVICE=0

# HuggingFace token for speaker diarization (optional)
# Get yours at: https://huggingface.co/settings/tokens
# MURMURAI_HF_TOKEN=hf_xxx
EOF

        echo -e "${GREEN}✅ Configuration created at: ${CONFIG_DIR}/.env${NC}"
        echo ""
        echo -e "${CYAN}Your API key is:${NC} ${API_KEY}"
        echo ""
        echo "To enable speaker diarization:"
        echo "  1. Accept license at: https://hf.co/pyannote/speaker-diarization-community-1"
        echo "  2. Get token at: https://huggingface.co/settings/tokens"
        echo "  3. Add to ${CONFIG_DIR}/.env: MURMURAI_HF_TOKEN=hf_xxx"
    else
        echo -e "${GREEN}✅ Configuration already exists at: ${CONFIG_DIR}/.env${NC}"
    fi
    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. SUMMARY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

show_summary() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}✅ INSTALLATION COMPLETE${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    if [[ "$CPU_MODE" == "true" ]]; then
        echo -e "${YELLOW}⚠️  Running in CPU mode (no GPU detected)${NC}"
        echo "   Transcription will be slower than with a GPU."
        echo ""
    fi

    echo "To start the server:"
    echo ""
    echo -e "  ${CYAN}murmurai${NC}"
    echo ""
    echo "Or run directly (ephemeral):"
    echo ""
    echo -e "  ${CYAN}uvx murmurai${NC}"
    echo ""
    echo "API will be available at:"
    echo "  http://localhost:8880"
    echo "  http://localhost:8880/docs (Swagger UI)"
    echo ""
    echo "Configuration file:"
    echo "  ${CONFIG_DIR}/.env"
    echo ""
    echo "Example transcription:"
    echo ""
    echo "  curl -X POST http://localhost:8880/v1/transcript \\"
    echo "    -H \"Authorization: Bearer \$(grep MURMURAI_API_KEY ${CONFIG_DIR}/.env | cut -d= -f2)\" \\"
    echo "    -F \"file=@audio.mp3\""
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "Made with ❤️ by ${CYAN}Namastex Labs${NC}"
    echo "https://github.com/namastexlabs/murmurai"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN INSTALLATION FLOW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

install_uv
check_python
check_gpu
install_murmurai_api
create_config
show_summary
