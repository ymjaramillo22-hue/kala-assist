# Guardar el archivo físicamente en Colab y descargarlo
with open("main.py", "w", encoding="utf-8") as f:
    f.write(In[-1])  # Guarda la celda anterior como código

from google.colab import files
files.download("main.py")