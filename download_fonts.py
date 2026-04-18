import requests

# URLs для скачивания шрифтов
fonts = {
    "DejaVuSans.ttf": "https://sourceforge.net/projects/dejavu/files/dejavu/2.37/dejavu-fonts-ttf-2.37.zip/download",
    "DejaVuSans-Bold.ttf": "https://sourceforge.net/projects/dejavu/files/dejavu/2.37/dejavu-fonts-ttf-2.37.zip/download",
}

# Скачиваем шрифты
for font_name in fonts:
    url = fonts[font_name]
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(font_name, "wb") as f:
            f.write(response.content)
        print(f"Шрифт {font_name} успешно загружен.")
    else:
        print(f"Не удалось загрузить шрифт {font_name}")
