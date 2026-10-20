"""
COMPASS Hardware & Environment Detection Utility
Provides dynamic, non-hardcoded hardware and system discovery.
"""

import ctypes
import platform
import subprocess
from typing import Any

import psutil


def get_system_hardware() -> dict[str, Any]:
    """
    Dynamically detect host CPU, RAM, GPU, VRAM, Windows OS version, and display resolution.
    Never assumes or hardcodes development machine specs.
    """
    info: dict[str, Any] = {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count_logical": psutil.cpu_count(logical=True) or 1,
        "cpu_count_physical": psutil.cpu_count(logical=False) or 1,
    }

    # Memory
    try:
        mem = psutil.virtual_memory()
        info["ram_total_mb"] = round(mem.total / (1024 * 1024), 2)
        info["ram_available_mb"] = round(mem.available / (1024 * 1024), 2)
        info["ram_used_percent"] = mem.percent
    except Exception as e:  # noqa: BLE001
        info["ram_error"] = str(e)

    # Display Resolution
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        info["display"] = {"width": screen_w, "height": screen_h}
    except Exception as e:  # noqa: BLE001
        info["display"] = {"error": str(e)}

    # GPU Detection (Dynamic via WMI or dxdiag if available on Windows)
    info["gpus"] = []
    vram_measured = False
    vram_total_mb = 0.0
    try:
        import os
        import shutil

        powershell_exe = (
            shutil.which("pwsh")
            or os.path.join(
                os.environ.get("SystemRoot", r"C:\Windows"),
                "System32",
                "WindowsPowerShell",
                "v1.0",
                "powershell.exe",
            )
        )
        cmd = [
            powershell_exe,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json",
        ]
        out = subprocess.check_output(cmd, timeout=3, shell=False).decode()
        import json

        gpu_data = json.loads(out)
        if isinstance(gpu_data, dict):
            gpu_data = [gpu_data]
        for g in gpu_data:
            name = g.get("Name", "Unknown")
            ram = g.get("AdapterRAM")
            vram_mb = round(ram / (1024 * 1024), 2) if ram else None
            if vram_mb is not None:
                vram_measured = True
                vram_total_mb += vram_mb
            info["gpus"].append({"name": name, "vram_mb": vram_mb})
    except Exception:  # noqa: BLE001, S110
        pass

    info["vram_measured"] = vram_measured
    info["vram_total_mb"] = vram_total_mb if vram_measured else None
    info["vram_used_mb"] = None

    info["execution_tier"] = get_execution_tier(info)
    return info


def get_execution_tier(hardware_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Auto-negotiates execution tier based on dynamic hardware discovery:
    - Tier 1: Dedicated GPU with >= 3000MB VRAM (e.g. RTX 2050 4GB) -> 'qwen2.5:3b-instruct' (Fluid, ~1.9GB VRAM)
    - Tier 2: Low-VRAM GPU (1500-3000MB) or iGPU with >=8GB RAM -> 'qwen2.5-coder:1.5b-instruct' (Sub-second)
    - Tier 3: Pure CPU or <=8GB RAM -> 'qwen2.5:0.5b' / CPU quantized fallback (Zero-GPU Reach)
    """
    if hardware_info is None:
        hardware_info = get_system_hardware()

    max_vram_mb = 0.0
    has_nvidia = False
    gpus = hardware_info.get("gpus", [])
    for g in gpus:
        vram = g.get("vram_mb") or 0.0
        max_vram_mb = max(max_vram_mb, vram)
        name = (g.get("name") or "").lower()
        if "nvidia" in name or "rtx" in name or "geforce" in name:
            has_nvidia = True

    ram_total_mb = hardware_info.get("ram_total_mb") or 8192.0

    if (max_vram_mb >= 3000.0 or (has_nvidia and ram_total_mb >= 10000.0)):
        return {
            "tier": 1,
            "name": "GPU Acceleration (High-Precision)",
            "recommended_model": "local/ollama/qwen2.5:3b-instruct",
            "vram_ceiling_mb": 2500,
            "device": "cuda" if has_nvidia else "gpu",
            "description": "Dedicated discrete GPU with sufficient VRAM for full 3B+ model offloading.",
        }
    elif max_vram_mb >= 1500.0 or ram_total_mb >= 10000.0:
        return {
            "tier": 2,
            "name": "Balanced Performance (Hybrid/iGPU)",
            "recommended_model": "local/ollama/qwen2.5-coder:1.5b-instruct",
            "vram_ceiling_mb": 1500,
            "device": "hybrid",
            "description": "Standard iGPU or budget VRAM configuration. Optimized for 1.5B low-latency execution.",
        }
    else:
        return {
            "tier": 3,
            "name": "Universal Zero-GPU Fallback (CPU Quantized)",
            "recommended_model": "local/ollama/qwen2.5:0.5b",
            "vram_ceiling_mb": 0,
            "device": "cpu",
            "description": "Pure CPU quantized mode. Operates in under 350MB system RAM without requiring a discrete GPU.",
        }

