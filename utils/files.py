import os
from aiogram.types import BufferedInputFile
import aiofiles


async def get_photo_for_pay():
    file_path = os.path.join("image", "qr_payment.jpeg")
    try:
        async with aiofiles.open(file_path, mode="rb") as photo:
            result = await photo.read()
        return BufferedInputFile(result, filename="qr_payment.jpeg")
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл {file_path} не найден.")
    except Exception as e:
        raise Exception(f"Ошибка при чтении файла: {e}")
