import os

import aiofiles


async def get_photo_for_pay():
    file_path = os.path.join("image", "qr_payment.jpeg")
    try:
        async with aiofiles.open(file_path, mode="rb") as photo:
            return await photo.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл {file_path} не найден.")
    except Exception as e:
        raise Exception(f"Ошибка при чтении файла: {e}")
