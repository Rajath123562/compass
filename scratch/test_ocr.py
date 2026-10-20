import asyncio
import os

import winrt.windows.globalization as glob
from PIL import Image, ImageDraw
from winrt.windows import storage
from winrt.windows.graphics import imaging
from winrt.windows.media import ocr


async def main():
    img = Image.new("RGBA", (200, 50), color="white")
    d = ImageDraw.Draw(img)
    d.text((10, 10), "Hello World", fill=(0, 0, 0))

    # Save to a temporary file
    temp_path = os.path.abspath("temp_ocr.png")
    img.save(temp_path)

    # Load using winrt
    file = await storage.StorageFile.get_file_from_path_async(temp_path)
    stream = await file.open_async(storage.FileAccessMode.READ)
    decoder = await imaging.BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    lang = glob.Language("en-US")
    engine = ocr.OcrEngine.try_create_from_language(lang)

    result = await engine.recognize_async(bitmap)
    print("Found text:", result.text)

    for line in result.lines:
        for word in line.words:
            rect = word.bounding_rect
            print(f"Word '{word.text}' at {rect.x},{rect.y} {rect.width}x{rect.height}")

    os.remove(temp_path)


if __name__ == "__main__":
    asyncio.run(main())
