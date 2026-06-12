"""
Хранилище для документов с обработкой перед загрузкой в Yandex Cloud.
"""

import os
import logging
from .storage_backends import YandexCloudWithProcessingStorage
from PyPDF2 import PdfReader, PdfWriter
import openpyxl
import csv

logger = logging.getLogger(__name__)

class YandexDocumentProcessingStorage(YandexCloudWithProcessingStorage):
    """
    Хранилище для документов с обработкой:
    - PDF: извлечение первых 3 страниц.
    - DOCX: извлечение текста в .txt.
    - XLSX: конвертация в CSV.
    - Остальные: без изменений.
    """

    def _process_file(self, temp_path, name):
        """
        Обрабатывает документ перед загрузкой.
        """
        try:
            # Определяем расширение файла
            ext = os.path.splitext(temp_path)[1].lower()
            base_name = os.path.splitext(temp_path)[0]
            processed_path = temp_path # По умолчанию оставляем как есть
            additional_files = []

            if ext == '.pdf':
                processed_path = self._process_pdf(temp_path, base_name)
            elif ext == '.xlsx':
                processed_path = self._process_xlsx(temp_path, base_name)
                additional_files.append(processed_path) # Добавляем .csv к удалению

            return processed_path, additional_files

        except Exception as e:
            logger.error(f"Ошибка при обработке документа {name}: {e}")
            return temp_path, [] # В случае ошибки возвращаем исходный файл

    def _process_pdf(self, temp_path, base_name):
        """Извлекает первые 3 страницы из PDF."""
        reader = PdfReader(temp_path)
        writer = PdfWriter()

        # Добавляем до 3 страниц
        for page in reader.pages[:3]:
            writer.add_page(page)

        output_path = f"{base_name}_preview.pdf"
        with open(output_path, "wb") as out_file:
            writer.write(out_file)
        return output_path

    def _process_docx(self, temp_path, base_name):
        """Извлекает текст из DOCX и сохраняет в .txt."""
        doc = docx.Document(temp_path)
        text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])
        
        output_path = f"{base_name}.txt"
        with open(output_path, "w", encoding="utf-8") as text_file:
            text_file.write(text)
        return output_path

    def _process_xlsx(self, temp_path, base_name):
        """Конвертирует первый лист XLSX в CSV."""
        wb = openpyxl.load_workbook(temp_path, read_only=True)
        ws = wb.active

        output_path = f"{base_name}.csv"
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for row in ws.iter_rows(values_only=True):
                writer.writerow(row)
        return output_path