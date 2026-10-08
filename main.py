import os
import sys
from pathlib import Path
from PIL import Image, ImageOps
from dotenv import load_dotenv

# Обеспечиваем корректный вывод кириллицы в консоли Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Загружаем переменные окружения из файла .env
load_dotenv()


def str_to_bool(val: str, default: bool = False) -> bool:
    """Преобразует строковое значение в булево."""
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "y", "да")


def format_size(bytes_count: int) -> str:
    """Форматирует размер в байтах в человекочитаемый вид."""
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} ТБ"


def convert_image(
    image_path: Path,
    quality: int,
    skip_existing: bool,
    remove_original: bool,
) -> tuple[bool, int, int]:
    """
    Конвертирует отдельный JPG/JPEG файл в WebP.
    Возвращает: (успех, исходный_размер, новый_размер)
    """
    output_path = image_path.with_suffix(".webp")

    if skip_existing and output_path.exists():
        print(f"[ПРОПУСК] Уже существует: {output_path.name}")
        return False, 0, 0

    original_size = image_path.stat().st_size

    try:
        with Image.open(image_path) as img:
            # Корректируем ориентацию по EXIF (актуально для фото со смартфонов/камер)
            img = ImageOps.exif_transpose(img)

            # WebP поддерживает RGB и RGBA. Если режим CMYK, конвертируем в RGB
            if img.mode in ("CMYK", "P", "1"):
                img = img.convert("RGB")

            # Сохраняем в WebP с максимальной степенью сжатия алгоритма (method=6)
            img.save(
                output_path,
                format="WEBP",
                quality=quality,
                method=6,
                optimize=True,
            )

        new_size = output_path.stat().st_size
        saved_bytes = original_size - new_size
        saved_pct = (saved_bytes / original_size * 100) if original_size > 0 else 0

        print(
            f"[OK] {image_path.name} -> {output_path.name} | "
            f"{format_size(original_size)} -> {format_size(new_size)} "
            f"({saved_pct:+.1f}%)"
        )

        if remove_original:
            try:
                image_path.unlink()
                print(f"  └─ Удален оригинал: {image_path.name}")
            except OSError as e:
                print(f"  └─ Ошибка удаления оригинала: {e}")

        return True, original_size, new_size

    except Exception as e:
        print(f"[ОШИБКА] Не удалось сконвертировать {image_path.name}: {e}")
        return False, 0, 0


def main():
    print("=" * 60)
    print("      Конвертер JPG/JPEG в WebP для веб-портфолио      ")
    print("=" * 60)

    # Чтение конфигурации из .env
    raw_dir = os.getenv("PHOTOS_DIR")
    if not raw_dir:
        print("\n[ОШИБКА] Переменная PHOTOS_DIR не задана в файле .env!")
        print("Создайте файл .env (на основе .env.example) и укажите путь к фото.")
        sys.exit(1)

    # Очищаем путь от возможных лишних кавычек
    clean_dir = raw_dir.strip("\"'")
    photos_dir = Path(clean_dir).resolve()

    if not photos_dir.exists():
        print(f"\n[ОШИБКА] Указанная папка не найдена: {photos_dir}")
        sys.exit(1)

    if not photos_dir.is_dir():
        print(f"\n[ОШИБКА] Указанный путь не является папкой: {photos_dir}")
        sys.exit(1)

    # Параметры конвертации
    try:
        quality = int(os.getenv("WEBP_QUALITY", "80"))
        quality = max(1, min(100, quality))
    except ValueError:
        quality = 80

    recursive = str_to_bool(os.getenv("RECURSIVE"), default=True)
    skip_existing = str_to_bool(os.getenv("SKIP_EXISTING"), default=True)
    remove_originals = str_to_bool(os.getenv("REMOVE_ORIGINALS"), default=False)

    print(f"Папка с фото:      {photos_dir}")
    print(f"Качество WebP:     {quality}%")
    print(f"Поиск в подпапках: {'Да' if recursive else 'Нет'}")
    print(f"Пропускать готовые:{'Да' if skip_existing else 'Нет'}")
    print(f"Удалять оригиналы: {'Да' if remove_originals else 'Нет'}")
    print("-" * 60)

    # Поддерживаемые расширения
    target_extensions = {".jpg", ".jpeg"}

    # Поиск файлов
    all_files = photos_dir.rglob("*") if recursive else photos_dir.glob("*")
    images_to_convert = [
        f for f in all_files if f.is_file() and f.suffix.lower() in target_extensions
    ]

    total_found = len(images_to_convert)
    if total_found == 0:
        print("В указанной директории не найдено файлов JPG или JPEG.")
        return

    print(f"Найдено фото для обработки: {total_found}\n")

    converted_count = 0
    total_original_size = 0
    total_new_size = 0

    for idx, img_path in enumerate(images_to_convert, 1):
        prefix = f"[{idx}/{total_found}]"
        print(f"{prefix} ", end="")
        success, orig_sz, new_sz = convert_image(
            image_path=img_path,
            quality=quality,
            skip_existing=skip_existing,
            remove_original=remove_originals,
        )
        if success:
            converted_count += 1
            total_original_size += orig_sz
            total_new_size += new_sz

    # Итоговая статистика
    print("\n" + "=" * 60)
    print("                     ИТОГИ ОБРАБОТКИ                     ")
    print("=" * 60)
    print(f"Обработано файлов:   {converted_count} из {total_found}")

    if converted_count > 0:
        saved_bytes = total_original_size - total_new_size
        saved_pct = (
            (saved_bytes / total_original_size * 100)
            if total_original_size > 0
            else 0
        )
        print(f"Исходный размер:     {format_size(total_original_size)}")
        print(f"Итоговый размер:     {format_size(total_new_size)}")
        print(f"Сэкономлено места:   {format_size(saved_bytes)} ({saved_pct:.1f}%)")
    print("Готово!")


if __name__ == "__main__":
    main()
