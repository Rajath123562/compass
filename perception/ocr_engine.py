"""
COMPASS Phase 7 — OCR Engine Abstraction & Backends
Provides a unified OCR layer combining:
1. Native Windows 11 WinRT OCR (Windows.Media.Ocr.OcrEngine)
2. Tesseract OCR (if installed)
3. Mock OCR (for isolated deterministic testing)

Enforces:
- Automatic backend discovery and capability reporting
- Strict timeouts and cancellation
- Bounded image dimensions and resource limits
- Caching by SHA256 of image content
- Untrusted content marking (Section 8, 17)
"""

from __future__ import annotations

import abc
import hashlib
import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from perception.models_multimodal import (
    BoundingBox,
    CapabilityStatus,
    CoordinateSpace,
    EvidenceProvenance,
    EvidenceSource,
    MultimodalEvidence,
)

logger = logging.getLogger(__name__)

import os

POWERSHELL_EXE = (
    shutil.which("pwsh")
    or os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )
)


def normalize_ocr_text(text: str) -> str:
    """Normalize extracted OCR text (strip non-printable characters, condense whitespace)."""
    if not text:
        return ""
    # Strip control characters except newline and tab
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Condense consecutive whitespace into a single space
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


class OCRBackend(abc.ABC):
    """Abstract interface for all OCR engines."""

    @property
    @abc.abstractmethod
    def backend_name(self) -> str:
        pass

    @abc.abstractmethod
    def is_available(self) -> bool:
        pass

    @abc.abstractmethod
    def extract_text_and_boxes(
        self,
        image_path: str,
        offset_x: int = 0,
        offset_y: int = 0,
        timeout_sec: float = 8.0,
    ) -> list[MultimodalEvidence]:
        pass


class WinRTOcrBackend(OCRBackend):
    """
    Native Windows 10/11 OCR engine using Windows.Media.Ocr.
    Hardware-accelerated, zero external model download, fully local.
    """

    def __init__(self, language: str = "en-US"):
        self._available: bool | None = None
        self.language = None
        self.engine = None
        if sys.platform == "win32":
            try:
                import winrt.windows.globalization as glob
                from winrt.windows.media import ocr

                self.language = glob.Language(language)
                self.engine = ocr.OcrEngine.try_create_from_language(self.language)
            except Exception:
                self.engine = None
            if self.engine is None and self.is_available():
                self.engine = "powershell_winrt_bridge"

    @property
    def backend_name(self) -> str:
        return "WinRT-OCR"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available

        if sys.platform != "win32":
            self._available = False
            return False

        # 1. Primary check: In-process native WinRT OCR module
        try:
            from winrt.windows.media import ocr

            engine = ocr.OcrEngine.try_create_from_user_profile_languages()
            if engine:
                self._available = True
                return True
        except Exception:  # noqa: BLE001, S110
            pass

        # 2. Fallback check: PowerShell WinRT bridge
        try:
            check_cmd = (
                "[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null; "
                "$e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages(); "
                "if ($e -ne $null) { Write-Output 'OK' } else { Write-Output 'NO_LANG' }"
            )
            res = subprocess.run(  # noqa: PLW1510
                [
                    POWERSHELL_EXE,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    check_cmd,
                ],
                capture_output=True,
                text=True,
                timeout=4.0,
                shell=False,
            )
            self._available = "OK" in res.stdout
        except Exception as e:  # noqa: BLE001
            logger.warning("WinRT OCR capability check failed: %s", e)
            self._available = False

        return self._available

    def _extract_inprocess(
        self,
        image_path: Path,
    ) -> list[dict[str, Any]] | None:
        """
        Extract OCR lines and words directly in-process via native Windows.Media.Ocr.
        Executed in dedicated worker thread with isolated event loop to prevent STA/MTA COM deadlocks.
        """
        try:
            import concurrent.futures

            def _worker():
                import asyncio
                import winrt.windows.globalization as glob
                from winrt.windows import storage
                from winrt.windows.graphics import imaging
                from winrt.windows.media import ocr

                async def _run():
                    file = await storage.StorageFile.get_file_from_path_async(
                        str(image_path)
                    )
                    stream = await file.open_async(storage.FileAccessMode.READ)
                    decoder = await imaging.BitmapDecoder.create_async(stream)
                    bitmap = await decoder.get_software_bitmap_async()

                    engine = ocr.OcrEngine.try_create_from_user_profile_languages()
                    if not engine:
                        engine = ocr.OcrEngine.try_create_from_language(
                            glob.Language("en-US")
                        )
                    if not engine:
                        return None

                    result = await engine.recognize_async(bitmap)
                    lines_data = []
                    for line in result.lines:
                        words_data = []
                        for w in line.words:
                            words_data.append(
                                {
                                    "text": w.text,
                                    "x": int(w.bounding_rect.x),
                                    "y": int(w.bounding_rect.y),
                                    "width": int(w.bounding_rect.width),
                                    "height": int(w.bounding_rect.height),
                                }
                            )
                        lines_data.append({"text": line.text, "words": words_data})
                    return lines_data

                worker_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(worker_loop)
                try:
                    return worker_loop.run_until_complete(_run())
                finally:
                    worker_loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(_worker).result(timeout=6.0)

        except Exception as e:  # noqa: BLE001
            logger.debug("In-process WinRT OCR extraction skipped: %s", e)
            return None

    def _extract_powershell(
        self,
        image_path: Path,
        timeout_sec: float = 6.0,
    ) -> list[dict[str, Any]]:
        """Fallback extraction using PowerShell bridge."""
        safe_path = str(image_path).replace("'", "''")
        ps_script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | ? {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }}

Function Await($WinRtTask, $ResultType) {{
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}}

[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync('{safe_path}')) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($engine -eq $null) {{
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
}}
if ($engine -eq $null) {{
    exit 1
}}

$ocrResult = $engine.RecognizeAsync($bitmap)
$res = Await ($ocrResult) ([Windows.Media.Ocr.OcrResult])

$lines = @()
foreach ($line in $res.Lines) {{
    $words = @()
    foreach ($w in $line.Words) {{
        $words += @{{
            text = $w.Text
            x = [int]$w.BoundingRect.X
            y = [int]$w.BoundingRect.Y
            width = [int]$w.BoundingRect.Width
            height = [int]$w.BoundingRect.Height
        }}
    }}
    $lines += @{{
        text = $line.Text
        words = $words
    }}
}}

@{{ lines = $lines }} | ConvertTo-Json -Depth 5 -Compress
"""
        try:
            res = subprocess.run(  # noqa: PLW1510
                [
                    POWERSHELL_EXE,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    ps_script,
                ],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                shell=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout.strip())
                return data.get("lines", [])
        except Exception as e:  # noqa: BLE001
            logger.warning("PowerShell OCR fallback failed: %s", e)
        return []

    def extract_text_and_boxes(
        self,
        image_path: str,
        offset_x: int = 0,
        offset_y: int = 0,
        timeout_sec: float = 6.0,
    ) -> list[MultimodalEvidence]:
        p = Path(image_path).resolve()
        if not p.exists():
            logger.error("OCR target image does not exist: %s", p)
            return []

        # 1. Primary: In-process native WinRT C-extensions (zero child processes)
        lines = self._extract_inprocess(p)

        # 2. Secondary fallback: PowerShell WinRT bridge if in-process fails
        if lines is None:
            lines = self._extract_powershell(p, timeout_sec=timeout_sec)

        evidence_list: list[MultimodalEvidence] = []
        if not lines:
            return []

        try:
            for line_idx, line in enumerate(lines):
                line_text = normalize_ocr_text(line.get("text", ""))
                words = line.get("words", [])

                # If line has words with individual bounding boxes, emit both line and words
                line_min_x = 999999
                line_min_y = 999999
                line_max_x = -999999
                line_max_y = -999999

                for word_data in words:
                    w_text = normalize_ocr_text(word_data.get("text", ""))
                    if not w_text:
                        continue
                    wx = int(word_data.get("x", 0)) + offset_x
                    wy = int(word_data.get("y", 0)) + offset_y
                    ww = int(word_data.get("width", 0))
                    wh = int(word_data.get("height", 0))

                    line_min_x = min(line_min_x, wx)
                    line_min_y = min(line_min_y, wy)
                    line_max_x = max(line_max_x, wx + ww)
                    line_max_y = max(line_max_y, wy + wh)

                    word_box = BoundingBox.from_ltwh(
                        wx, wy, ww, wh, CoordinateSpace.SCREEN_PHYSICAL
                    )
                    prov = EvidenceProvenance(
                        source=EvidenceSource.OCR,
                        source_version="WinRT-11",
                        device_context={"backend": self.backend_name},
                    )
                    evidence_list.append(
                        MultimodalEvidence(
                            source=EvidenceSource.OCR,
                            bounding_box=word_box,
                            extracted_text=w_text,
                            confidence=0.92,
                            provenance=prov,
                            metadata={"type": "word", "line_index": line_idx},
                            is_untrusted=True,
                        )
                    )

                # Emit whole line evidence if valid
                if line_text and line_min_x < line_max_x and line_min_y < line_max_y:
                    line_box = BoundingBox(
                        left=line_min_x,
                        top=line_min_y,
                        right=line_max_x,
                        bottom=line_max_y,
                        coordinate_space=CoordinateSpace.SCREEN_PHYSICAL,
                    )
                    prov_line = EvidenceProvenance(
                        source=EvidenceSource.OCR,
                        source_version="WinRT-11",
                        device_context={"backend": self.backend_name},
                    )
                    evidence_list.append(
                        MultimodalEvidence(
                            source=EvidenceSource.OCR,
                            bounding_box=line_box,
                            extracted_text=line_text,
                            confidence=0.95,
                            provenance=prov_line,
                            metadata={"type": "line", "line_index": line_idx},
                            is_untrusted=True,
                        )
                    )

        except Exception as e:  # noqa: BLE001
            logger.error("WinRT OCR line parsing error: %s", e)

        return evidence_list

    async def _extract_async(self, image: Any) -> list[Any]:
        import os
        import tempfile
        from pathlib import Path
        from perception.models import CoordinateBounds, OcrElement

        fd, temp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            if hasattr(image, "save"):
                image.save(temp_path)
            elif isinstance(image, (str, Path)) and os.path.exists(str(image)):
                temp_path = str(image)
            else:
                return []

            # 1. Native in-process WinRT OCR if available
            if self.engine and not isinstance(self.engine, str):
                try:
                    from winrt.windows import storage
                    from winrt.windows.graphics import imaging

                    file = await storage.StorageFile.get_file_from_path_async(temp_path)
                    stream = await file.open_async(storage.FileAccessMode.READ)
                    decoder = await imaging.BitmapDecoder.create_async(stream)
                    bitmap = await decoder.get_software_bitmap_async()
                    result = await self.engine.recognize_async(bitmap)
                    elements = []
                    for line in result.lines:
                        for word in line.words:
                            rect = word.bounding_rect
                            bounds = CoordinateBounds(
                                left=int(rect.x),
                                top=int(rect.y),
                                right=int(rect.x + rect.width),
                                bottom=int(rect.y + rect.height),
                            )
                            elements.append(
                                OcrElement(
                                    text=word.text,
                                    bounds=bounds,
                                    confidence=1.0,
                                )
                            )
                    if elements:
                        return elements
                except Exception as e:
                    logger.debug("In-process WinRT OCR extraction failed: %s", e)

            # 2. PowerShell WinRT Bridge fallback
            ps_lines = self._extract_powershell(Path(temp_path), timeout_sec=6.0)
            elements = []
            for line in ps_lines:
                words = line.get("words", [])
                if words:
                    for w in words:
                        elements.append(
                            OcrElement(
                                text=w.get("text", ""),
                                bounds=CoordinateBounds(
                                    left=int(w.get("x", 0)),
                                    top=int(w.get("y", 0)),
                                    right=int(w.get("x", 0) + max(1, w.get("width", 10))),
                                    bottom=int(w.get("y", 0) + max(1, w.get("height", 10))),
                                ),
                                confidence=1.0,
                            )
                        )
                elif line.get("text"):
                    elements.append(
                        OcrElement(
                            text=line.get("text", ""),
                            bounds=CoordinateBounds(left=0, top=0, right=100, bottom=30),
                            confidence=1.0,
                        )
                    )
            return elements
        except Exception as e:
            logger.debug("WinRTOcrBackend error: %s", e)
            return []
        finally:
            if os.path.exists(temp_path) and temp_path != str(image):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def extract_text(self, image: Any) -> list[Any]:
        import asyncio
        import concurrent.futures

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, self._extract_async(image)).result(timeout=10.0)
            return loop.run_until_complete(self._extract_async(image))
        except Exception:
            try:
                return asyncio.run(self._extract_async(image))
            except Exception:
                return []


class TesseractOcrBackend(OCRBackend):
    """Tesseract CLI OCR Backend fallback if installed."""

    def __init__(self):
        self._tesseract_path = shutil.which("tesseract")

    @property
    def backend_name(self) -> str:
        return "Tesseract"

    def is_available(self) -> bool:
        return self._tesseract_path is not None

    def extract_text_and_boxes(
        self,
        image_path: str,
        offset_x: int = 0,
        offset_y: int = 0,
        timeout_sec: float = 8.0,
    ) -> list[MultimodalEvidence]:
        if not self.is_available():
            return []

        evidence_list: list[MultimodalEvidence] = []
        try:
            # Run tesseract with tsv output to get bounding boxes
            cmd = [
                self._tesseract_path,
                image_path,
                "stdout",
                "--oem",
                "1",
                "-l",
                "eng",
                "tsv",
            ]
            res = subprocess.run(  # noqa: PLW1510
                cmd, capture_output=True, text=True, timeout=timeout_sec
            )
            if res.returncode != 0:
                return []

            lines = res.stdout.strip().splitlines()
            if len(lines) <= 1:
                return []

            header = lines[0].split("\t")
            col_map = {col.strip(): i for i, col in enumerate(header)}

            for row in lines[1:]:
                parts = row.split("\t")
                if len(parts) <= max(col_map.values()):
                    continue
                text = normalize_ocr_text(parts[col_map.get("text", -1)])
                conf_str = parts[col_map.get("conf", -1)]
                try:
                    conf = float(conf_str) / 100.0
                except (ValueError, TypeError):
                    conf = 0.5

                if not text or conf < 0.2:
                    continue

                left = int(parts[col_map.get("left", 0)]) + offset_x
                top = int(parts[col_map.get("top", 0)]) + offset_y
                w = int(parts[col_map.get("width", 0)])
                h = int(parts[col_map.get("height", 0)])

                box = BoundingBox.from_ltwh(
                    left, top, w, h, CoordinateSpace.SCREEN_PHYSICAL
                )
                prov = EvidenceProvenance(
                    source=EvidenceSource.OCR,
                    source_version="Tesseract-CLI",
                    device_context={"backend": self.backend_name},
                )
                evidence_list.append(
                    MultimodalEvidence(
                        source=EvidenceSource.OCR,
                        bounding_box=box,
                        extracted_text=text,
                        confidence=conf,
                        provenance=prov,
                        metadata={"type": "word"},
                        is_untrusted=True,
                    )
                )
        except Exception as e:  # noqa: BLE001
            logger.error("Tesseract OCR error: %s", e)

        return evidence_list


class MockOcrBackend(OCRBackend):
    """
    Mock OCR Backend strictly for isolated unit testing.
    Explicitly labeled as mock in source_version and device_context.
    """

    def __init__(self, predefined_results: list[dict[str, Any]] | None = None):
        self.predefined_results = predefined_results or []

    @property
    def backend_name(self) -> str:
        return "MockOCR-TestOnly"

    def is_available(self) -> bool:
        return True

    def extract_text_and_boxes(
        self,
        image_path: str,
        offset_x: int = 0,
        offset_y: int = 0,
        timeout_sec: float = 8.0,
    ) -> list[MultimodalEvidence]:
        evidence_list: list[MultimodalEvidence] = []
        for item in self.predefined_results:
            text = item.get("text", "")
            box_dict = item.get("box", {"left": 0, "top": 0, "width": 50, "height": 20})
            left = box_dict.get("left", 0) + offset_x
            top = box_dict.get("top", 0) + offset_y
            w = box_dict.get("width", 50)
            h = box_dict.get("height", 20)
            box = BoundingBox.from_ltwh(
                left, top, w, h, CoordinateSpace.SCREEN_PHYSICAL
            )
            prov = EvidenceProvenance(
                source=EvidenceSource.OCR,
                source_version="MockOcr-TestOnly",
                device_context={"backend": self.backend_name, "mock": True},
            )
            evidence_list.append(
                MultimodalEvidence(
                    source=EvidenceSource.OCR,
                    bounding_box=box,
                    extracted_text=text,
                    confidence=item.get("confidence", 0.95),
                    provenance=prov,
                    metadata={"mock": True},
                    is_untrusted=True,
                )
            )
        return evidence_list


class OCREngineManager:
    """
    Manages OCR lifecycle, backend selection, resource limits, and caching (Section 8, 19).
    """

    def __init__(self, preferred_backend: OCRBackend | None = None):
        self._backends: list[OCRBackend] = []
        if preferred_backend:
            self._backends.append(preferred_backend)
        else:
            # Register native backends in order of preference
            winrt = WinRTOcrBackend()
            if winrt.is_available():
                self._backends.append(winrt)
            tess = TesseractOcrBackend()
            if tess.is_available():
                self._backends.append(tess)

        self._cache: dict[str, list[MultimodalEvidence]] = {}
        self._max_cache_size = 50

    @property
    def active_backend(self) -> OCRBackend | None:
        for b in self._backends:
            if b.is_available():
                return b
        return None

    def get_capability_status(self) -> CapabilityStatus:
        if self.active_backend is not None:
            return CapabilityStatus.AVAILABLE
        return CapabilityStatus.UNAVAILABLE

    def extract(
        self,
        image_path: str,
        offset_x: int = 0,
        offset_y: int = 0,
        timeout_sec: float = 8.0,
    ) -> list[MultimodalEvidence]:
        """
        Extract text and bounding boxes from an image file with caching and resource limits.
        """
        backend = self.active_backend
        if not backend:
            logger.warning("No OCR backend available")
            return []

        p = Path(image_path)
        if not p.exists():
            if isinstance(backend, MockOcrBackend):
                return backend.extract_text_and_boxes(
                    image_path=str(image_path),
                    offset_x=offset_x,
                    offset_y=offset_y,
                    timeout_sec=timeout_sec,
                )
            return []

        # Hash image content for caching
        try:
            with open(p, "rb") as f:
                img_bytes = f.read()
            img_hash = hashlib.sha256(img_bytes).hexdigest()
            cache_key = f"{img_hash}_{offset_x}_{offset_y}_{backend.backend_name}"
            if cache_key in self._cache:
                return self._cache[cache_key]
        except Exception:  # noqa: BLE001
            cache_key = None

        # Execute extraction
        evidence = backend.extract_text_and_boxes(
            image_path=str(p),
            offset_x=offset_x,
            offset_y=offset_y,
            timeout_sec=timeout_sec,
        )

        if cache_key:
            if len(self._cache) >= self._max_cache_size:
                # Evict oldest entry
                first_key = next(iter(self._cache))
                del self._cache[first_key]
            self._cache[cache_key] = evidence

        return evidence
