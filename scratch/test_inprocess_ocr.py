import asyncio
from pathlib import Path

import winrt.windows.globalization as glob
from PIL import Image, ImageDraw
from winrt.windows import storage
from winrt.windows.graphics import imaging
from winrt.windows.media import ocr


async def main():
    # 1. Create a test image
    img_path = Path("scratch/ocr_test_img.png").resolve()
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 35), "COMPASS IN-PROCESS OCR", fill=(0, 0, 0))
    img.save(img_path)

    # 2. Open via WinRT StorageFile & BitmapDecoder
    file = await storage.StorageFile.get_file_from_path_async(str(img_path))
    stream = await file.open_async(storage.FileAccessMode.READ)
    decoder = await imaging.BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    # 3. Recognize via in-process OcrEngine
    engine = ocr.OcrEngine.try_create_from_user_profile_languages()
    if not engine:
        engine = ocr.OcrEngine.try_create_from_language(glob.Language("en-US"))

    result = await engine.recognize_async(bitmap)
    print("Recognized Text:", result.text)
    for line in result.lines:
        for word in line.words:
            print(
                f"Word: '{word.text}' Bounds: (x={word.bounding_rect.x}, y={word.bounding_rect.y}, w={word.bounding_rect.width}, h={word.bounding_rect.height})"
            )


asyncio.run(main())
