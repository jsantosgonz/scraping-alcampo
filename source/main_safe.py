# main_optimizado.py
from scraper import (
    iniciar_driver,
    obtener_subcategorias,
    obtener_enlaces_productos,
    extraer_datos_producto,
    guardar_csv_parcial
)

import pandas as pd
import time
import os
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException

# Configuración de directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "dataset")
os.makedirs(DATA_DIR, exist_ok=True)
error_log_path = os.path.join(DATA_DIR, "errores_scraping.txt")
if os.path.exists(error_log_path):
    os.remove(error_log_path)

URL_HOME = "https://www.compraonline.alcampo.es/categories"

# Iniciar navegador
driver = iniciar_driver()
driver.get(URL_HOME)
time.sleep(3)

# Extraer secciones
soup = BeautifulSoup(driver.page_source, "html.parser")
secciones = []
for link in soup.find_all("a", href=True):
    href = link.get("href")
    texto = link.get_text(strip=True)
    if href and href.startswith("/categories/") and texto:
        url = "https://www.compraonline.alcampo.es" + href
        item = {"nombre": texto, "url": url}
        if item not in secciones:
            secciones.append(item)

print(f"Secciones encontradas: {len(secciones)}")

productos = []

for seccion in secciones:
    nombre_seccion = seccion["nombre"]
    url_seccion = seccion["url"]
    print(f"Sección: {nombre_seccion}")

    try:
        subcategorias = obtener_subcategorias(driver, url_seccion)
    except Exception as e:
        print(f"Error en subcategorías {nombre_seccion}: {e}")
        with open(error_log_path, "a", encoding="utf-8") as log:
            log.write(f"[SECCIÓN] {nombre_seccion} - {e}\n")
        continue

    for sub in subcategorias:
        try:
            enlaces = obtener_enlaces_productos(driver, sub["url"])
            print(f"   Subcategoría: {sub['nombre']} ({len(enlaces)} productos)")
        except Exception as e:
            print(f"Error enlaces {sub['nombre']}: {e}")
            with open(error_log_path, "a", encoding="utf-8") as log:
                log.write(f"[ENLACES] {sub['nombre']} - {e}\n")
            continue

        tiempo_inicio = time.time()
        for i, enlace in enumerate(enlaces):
            try:
                producto = extraer_datos_producto(driver, enlace)
                producto["Sección"] = nombre_seccion
                producto["Subcategoría"] = sub["nombre"]
                productos.append(producto)

                if (i + 1) % 10 == 0 or i + 1 == len(enlaces):
                    t_total = time.time() - tiempo_inicio
                    promedio = t_total / (i + 1)
                    restante = promedio * (len(enlaces) - i - 1)
                    print(f"{i+1}/{len(enlaces)} productos procesados → {restante/60:.1f} min restantes")

                if len(productos) % 100 == 0:
                    guardar_csv_parcial(productos, os.path.join(DATA_DIR, "scraping_parcial.csv"))

            except WebDriverException as e:
                print(f"Reiniciando driver por error: {e}")
                driver.quit()
                driver = iniciar_driver()
                continue
            except Exception as e:
                print(f"Error en producto: {enlace} → {e}")
                with open(error_log_path, "a", encoding="utf-8") as log:
                    log.write(f"[PRODUCTO] {enlace} - {e}\n")

# Cerrar driver y guardar CSV final
driver.quit()
df = pd.DataFrame(productos).drop_duplicates(subset="URL")

orden_columnas = [
    "Sección", "Subcategoría", "Nombre", "Precio total", "Precio €/kg", "Marca", "Ingredientes", "URL",
    "País de origen", "Lugar de procedencia", "Peso Neto", "Denominación legal del alimento",
    "Formato", "Eco::Etiqueta ecológica de la UE::",
    "Valor energético (Kj)", "Valor energético (Kcal)", "Grasas", "Grasas saturadas",
    "Hidratos de carbono", "Azúcares", "Proteínas", "Sal"
]

for col in orden_columnas:
    if col not in df.columns:
        df[col] = ""

output_file = os.path.join(DATA_DIR, "alcampo_products_dataset.csv")
df[orden_columnas].to_csv(output_file, index=False, sep=";", encoding="utf-8-sig")
print(f"Guardado CSV con {len(df)} productos en {output_file}")
