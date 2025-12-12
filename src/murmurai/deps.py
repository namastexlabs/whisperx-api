"""Startup dependency validation for MurmurAI."""

import ctypes
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DependencyStatus:
    """Status of a single dependency check."""

    name: str
    available: bool
    version: str | None = None
    required: bool = True
    error: str | None = None
    install_hint: str | None = None
    details: str | None = None


# Platform-specific installation hints
INSTALL_HINTS: dict[str, dict[str, str]] = {
    "cuda": {
        "Linux": """\
CUDA toolkit required. Install from:
  https://developer.nvidia.com/cuda-downloads

Or via package manager (Ubuntu/Debian):
  sudo apt install nvidia-cuda-toolkit

For WSL2, CUDA comes from the Windows driver automatically.""",
        "Darwin": """\
CUDA not available on macOS. MurmurAI requires NVIDIA GPU.
Consider using a Linux machine or cloud GPU instance (AWS, GCP, Lambda Labs).""",
        "Windows": """\
CUDA toolkit required. Install from:
  https://developer.nvidia.com/cuda-downloads""",
    },
    "cudnn": {
        "Linux": """\
cuDNN 8 required for speaker diarization.
Install via NVIDIA repository:
  wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
  sudo dpkg -i cuda-keyring_1.1-1_all.deb
  sudo apt update && sudo apt install -y libcudnn8

Or download manually from: https://developer.nvidia.com/cudnn""",
        "Darwin": """\
cuDNN not available on macOS. Speaker diarization requires NVIDIA GPU.
Transcription will work, but speaker_labels=true will fail.""",
        "Windows": """\
cuDNN 8 required for speaker diarization.
1. Download from: https://developer.nvidia.com/cudnn
2. Extract and copy files to CUDA installation directory
3. Ensure cudnn64_8.dll is in PATH""",
    },
    "ffmpeg": {
        "Linux": "sudo apt install ffmpeg  # or: dnf install ffmpeg",
        "Darwin": "brew install ffmpeg",
        "Windows": "choco install ffmpeg  # or download from https://ffmpeg.org",
    },
}


def get_platform() -> str:
    """Get normalized platform name."""
    return platform.system()  # "Linux", "Darwin", "Windows"


def get_install_hint(dep: str) -> str:
    """Get platform-specific install hint for a dependency."""
    plat = get_platform()
    return INSTALL_HINTS.get(dep, {}).get(plat, f"Please install {dep} for your platform.")


def check_cuda() -> DependencyStatus:
    """Check CUDA availability via PyTorch."""
    try:
        import torch

        if torch.cuda.is_available():
            cuda_version = torch.version.cuda or "unknown"
            device_count = torch.cuda.device_count()
            return DependencyStatus(
                name="CUDA",
                available=True,
                version=cuda_version,
                details=f"{device_count} GPU(s) available",
            )
        else:
            return DependencyStatus(
                name="CUDA",
                available=False,
                error="PyTorch cannot detect CUDA",
                install_hint=get_install_hint("cuda"),
            )
    except ImportError:
        return DependencyStatus(
            name="CUDA",
            available=False,
            error="PyTorch not installed",
            install_hint="pip install torch (with CUDA support)",
        )
    except Exception as e:
        return DependencyStatus(
            name="CUDA",
            available=False,
            error=str(e),
            install_hint=get_install_hint("cuda"),
        )


def check_gpu() -> DependencyStatus:
    """Check GPU availability and memory."""
    try:
        import torch

        if not torch.cuda.is_available():
            return DependencyStatus(
                name="GPU",
                available=False,
                error="No GPU detected",
                install_hint="MurmurAI requires an NVIDIA GPU with CUDA support.",
            )

        device_count = torch.cuda.device_count()
        gpus = []
        total_memory = 0.0

        for i in range(device_count):
            props = torch.cuda.get_device_properties(i)
            mem_gb = props.total_memory / (1024**3)
            total_memory += mem_gb
            gpus.append(f"{props.name} ({mem_gb:.1f}GB)")

        # Warn if low memory (< 4GB)
        min_memory_gb = 4.0
        if total_memory < min_memory_gb:
            return DependencyStatus(
                name="GPU",
                available=True,
                version=gpus[0] if gpus else "unknown",
                details=f"{device_count} GPU(s): {', '.join(gpus)}",
                error=f"Low GPU memory ({total_memory:.1f}GB). Recommend >= {min_memory_gb}GB.",
            )

        return DependencyStatus(
            name="GPU",
            available=True,
            version=gpus[0] if gpus else "unknown",
            details=f"{device_count} GPU(s): {', '.join(gpus)}",
        )

    except Exception as e:
        return DependencyStatus(
            name="GPU",
            available=False,
            error=str(e),
        )


def check_cudnn() -> DependencyStatus:
    """Check cuDNN availability by attempting to load the library."""
    system = get_platform()

    # macOS doesn't have cuDNN
    if system == "Darwin":
        return DependencyStatus(
            name="cuDNN",
            available=False,
            required=False,
            error="cuDNN not available on macOS",
            install_hint=get_install_hint("cudnn"),
        )

    # Try to detect cuDNN version via torch
    try:
        import torch.backends.cudnn as cudnn

        if cudnn.is_available():
            version = str(cudnn.version()) if hasattr(cudnn, "version") else "available"
            return DependencyStatus(
                name="cuDNN",
                available=True,
                version=version,
                required=False,
            )
    except Exception:
        pass

    # Fallback: try loading the library directly
    if system == "Linux":
        lib_names = [
            "libcudnn.so.8",
            "libcudnn.so.9",
            "libcudnn.so",
            "libcudnn_ops_infer.so.8",
        ]
    elif system == "Windows":
        lib_names = ["cudnn64_8.dll", "cudnn64_9.dll", "cudnn.dll"]
    else:
        lib_names = []

    for lib in lib_names:
        try:
            ctypes.CDLL(lib)
            # Extract version from lib name if possible
            version = "8" if "8" in lib else ("9" if "9" in lib else "unknown")
            return DependencyStatus(
                name="cuDNN",
                available=True,
                version=version,
                required=False,
            )
        except OSError:
            continue

    return DependencyStatus(
        name="cuDNN",
        available=False,
        required=False,  # Only required for diarization
        error="cuDNN library not found",
        install_hint=get_install_hint("cudnn"),
    )


def check_ffmpeg() -> DependencyStatus:
    """Check ffmpeg availability (system or bundled)."""
    # Check system ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        try:
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Parse version from first line
            version_line = result.stdout.split("\n")[0]
            version = version_line.split()[2] if len(version_line.split()) > 2 else "unknown"
            return DependencyStatus(
                name="ffmpeg",
                available=True,
                version=version,
                details="system",
            )
        except Exception:
            pass

    # Check bundled ffmpeg via imageio-ffmpeg
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        ffmpeg_path = get_ffmpeg_exe()
        if ffmpeg_path and Path(ffmpeg_path).exists():
            try:
                result = subprocess.run(
                    [ffmpeg_path, "-version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                version_line = result.stdout.split("\n")[0]
                version = version_line.split()[2] if len(version_line.split()) > 2 else "unknown"
                return DependencyStatus(
                    name="ffmpeg",
                    available=True,
                    version=version,
                    details="bundled",
                )
            except Exception:
                return DependencyStatus(
                    name="ffmpeg",
                    available=True,
                    version="unknown",
                    details="bundled",
                )
    except ImportError:
        pass

    return DependencyStatus(
        name="ffmpeg",
        available=False,
        error="ffmpeg not found (system or bundled)",
        install_hint=get_install_hint("ffmpeg"),
    )


def validate_dependencies(require_diarization: bool = False) -> list[DependencyStatus]:
    """Run all dependency checks.

    Args:
        require_diarization: If True, cuDNN becomes required.

    Returns:
        List of DependencyStatus objects.
    """
    statuses = [
        check_cuda(),
        check_gpu(),
        check_cudnn(),
        check_ffmpeg(),
    ]

    # Mark cuDNN as required if diarization is needed
    if require_diarization:
        for status in statuses:
            if status.name == "cuDNN":
                status.required = True

    return statuses


def print_dependency_report(statuses: list[DependencyStatus]) -> bool:
    """Print formatted dependency report.

    Args:
        statuses: List of dependency check results.

    Returns:
        True if all required dependencies are available.
    """
    width = 64
    all_ok = True
    missing_hints: list[str] = []

    # Header
    print()
    print("=" * width)
    print("  MurmurAI - Dependency Check".center(width))
    print("=" * width)

    # Status rows
    for status in statuses:
        icon = "\u2713" if status.available else "\u2717"  # checkmark or X
        version = status.version or "missing"
        req_text = "(required)" if status.required else "(optional)"

        if status.available:
            detail = f"  {status.details}" if status.details else ""
            print(f"  {icon} {status.name:<12} {version:<12} {req_text}{detail}")
        else:
            print(f"  {icon} {status.name:<12} {version:<12} {req_text}")
            if status.required:
                all_ok = False
            if status.install_hint and (status.required or not status.available):
                missing_hints.append(f"[{status.name}] {status.install_hint}")

    print("-" * width)

    # Show install hints for missing dependencies
    if missing_hints:
        print()
        for hint in missing_hints:
            for line in hint.strip().split("\n"):
                print(f"  {line}")
            print()

    if all_ok:
        print("  All required dependencies are available.")
    else:
        print("  [ERROR] Required dependencies missing!")
        print()
        print("  Run the install script to fix:")
        print(
            "    curl -fsSL https://raw.githubusercontent.com/namastexlabs/murmurai/main/get-murmurai.sh | bash"
        )
        print()
        print("  Or continue anyway with: murmurai --force")

    print("=" * width)
    print()

    return all_ok


def startup_check(force: bool = False) -> bool:
    """Run startup dependency check.

    Args:
        force: If True, continue even if dependencies are missing.

    Returns:
        True if startup should proceed, False otherwise.
    """
    import sys

    statuses = validate_dependencies()
    all_ok = print_dependency_report(statuses)

    if not all_ok and not force:
        print("Startup aborted. Use --force to continue anyway.")
        sys.exit(1)

    if not all_ok and force:
        print("WARNING: Running with missing dependencies. Some features may not work.")
        print()

    return True
