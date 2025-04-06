from scraper import (
    iniciar_driver,
    obtener_subcategorias,
    obtener_enlaces_productos,
    extraer_datos_producto,
    reiniciar_driver,
    guardar_csv_parcial
)

import pandas as pd
import time
from bs4 import BeautifulSoup
import os


# URL de Alcampo
URL_HOME = "https://www.compraonline.alcampo.es/categories"

# Carpeta para errores y logs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "dataset")
os.makedirs(DATA_DIR, exist_ok=True)
error_log_path = os.path.join(DATA_DIR, "errores_scraping.txt")
if os.path.exists(error_log_path):
    os.remove(error_log_path)

# Iniciar navegador y acceder a la home
driver = iniciar_driver()
driver.get(URL_HOME)
time.sleep(3)


# Secciones 
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

# Recorremos cada sección y subcategoria
productos = []
driver = reiniciar_driver(driver)

for seccion in secciones:
    nombre_seccion = seccion["nombre"]
    url_seccion = seccion["url"]
    print(f"Sección: {nombre_seccion}")

    try:
        subcategorias = obtener_subcategorias(driver, url_seccion)
    except Exception as e:
        print(f"Subcategorías inaccesibles en {nombre_seccion}: {e}")
        with open(error_log_path, "a", encoding="utf-8") as log:
            log.write(f"[SECCIÓN] {nombre_seccion} - {e}\n")
        continue

    for sub in subcategorias:
        try:
            enlaces = obtener_enlaces_productos(driver, sub["url"])
            print(f"  ↳ Subcategoría: {sub['nombre']} ({len(enlaces)} productos)")
            tiempo_inicio = time.time()
        except Exception as e:
            print(f"Error obteniendo enlaces de {sub['nombre']}: {e}")
            with open(error_log_path, "a", encoding="utf-8") as log:
                log.write(f"[ENLACES] {sub['nombre']} - {e}\n")
            continue

        for i, enlace in enumerate(enlaces):
            try:
                info = extraer_datos_producto(driver, enlace)
                info["Sección"] = nombre_seccion
                info["Subcategoría"] = sub["nombre"]
                productos.append(info)

                if (i + 1) % 10 == 0 or i + 1 == len(enlaces):
                    tiempo_transcurrido = time.time() - tiempo_inicio
                    promedio = tiempo_transcurrido / (i + 1)
                    restante = promedio * (len(enlaces) - i - 1)
                    print(f"⏳ {i+1}/{len(enlaces)} productos → tiempo restante estimado: {restante/60:.1f} min")

                if len(productos) % 100 == 0:
                    guardar_csv_parcial(productos, os.path.join(DATA_DIR, "scraping_parcial.csv"))

            except Exception as e:
                print(f"Error en producto: {enlace} → {e}")
                with open(error_log_path, "a", encoding="utf-8") as log:
                    log.write(f"[PRODUCTO] {enlace} - {e}\n")

        driver = reiniciar_driver(driver)

driver.quit()


# Guardar el dataset 
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

df = df[orden_columnas]

output_file = os.path.join(DATA_DIR, "alcampo_products_dataset.csv")
df.to_csv(output_file, index=False, sep=";", encoding="utf-8-sig")
print(f"Guardado CSV con {len(df)} productos en {output_file}")
