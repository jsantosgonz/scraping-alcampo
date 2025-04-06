
# scraper.py
# Funciones auxiliares para scraping en Alcampo

import time
import json
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


import re


def limpiar_texto(texto):
    if not texto:
        return ""
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()

def iniciar_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def obtener_subcategorias(driver, url_categoria):
    driver.get(url_categoria)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    subcategorias = []
    for link in soup.find_all("a", attrs={"data-test": "root-category-link"}):
        nombre = link.get_text(strip=True)
        href = link.get("href")
        if href:
            subcategorias.append({"nombre": nombre, "url": "https://www.compraonline.alcampo.es" + href})
    return subcategorias

def obtener_enlaces_productos(driver, url_categoria):
    driver.get(url_categoria)
    time.sleep(2)
    enlaces = []
    SCROLL_PAUSE_TIME = 1
    MAX_SCROLL = 25
    last_height = driver.execute_script("return document.body.scrollHeight")
    attempts = 0
    while attempts < MAX_SCROLL:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(SCROLL_PAUSE_TIME)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            attempts += 1
        else:
            attempts = 0
            last_height = new_height
    soup = BeautifulSoup(driver.page_source, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "ItemList":
                for item in data.get("itemListElement", []):
                    if "url" in item:
                        enlaces.append(item["url"])
        except:
            continue
    if not enlaces:
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("/producto/"):
                url = "https://www.compraonline.alcampo.es" + a["href"]
                if url not in enlaces:
                    enlaces.append(url)
    return enlaces

def safe_find(driver, selector, by=By.CSS_SELECTOR, attr="text"):
    try:
        el = driver.find_element(by, selector)
        return el.text.strip() if attr == "text" else el.get_attribute(attr)
    except:
        return ""

def extraer_datos_producto(driver, enlace):
    driver.get(enlace)
    time.sleep(2)
    producto = {
        "Nombre": limpiar_texto(safe_find(driver, "h1", By.TAG_NAME)),
        "Precio total": limpiar_texto(safe_find(driver, '[data-test="price-container"] span')),
        "Precio €/kg": limpiar_texto(safe_find(driver, '[data-test="size-container"] span.salt-vc')),
        "URL": enlace
    }
    try:
        producto["Marca"] = limpiar_texto(driver.find_element(By.CLASS_NAME, "sc-3ycw9o-0").text.split("\n")[0])
    except:
        producto["Marca"] = ""
    ingredientes = ""
    bloques = driver.find_elements(By.CLASS_NAME, "sc-3ycw9o-0")
    for b in bloques:
        if "Ingredientes" in b.text:
            ingredientes = b.text.split("\n", 1)[-1].strip()
            break
    producto["Ingredientes"] = limpiar_texto(ingredientes)
    campos = {
        "País de origen": "", "Lugar de procedencia": "", "Peso Neto": "",
        "Denominación legal del alimento": "", "Formato": "", "Eco::Etiqueta ecológica de la UE::": ""
    }
    for b in bloques:
        if "<table" in b.get_attribute("outerHTML"):
            filas = b.find_elements(By.TAG_NAME, "tr")
            for f in filas:
                celdas = f.find_elements(By.TAG_NAME, "td")
                if len(celdas) == 2:
                    clave = celdas[0].text.strip()
                    valor = celdas[1].text.strip()
                    if clave in campos:
                        campos[clave] = limpiar_texto(valor)
            break
    producto.update(campos)

    # Extraer información nutricional
    nutricionales_dict = {
        "Valor energético (Kj)": "",
        "Valor energético (Kcal)": "",
        "Grasas": "",
        "Grasas saturadas": "",
        "Hidratos de carbono": "",
        "Azúcares": "",
        "Proteínas": "",
        "Sal": ""
    }

    try:
        posibles_bloques = driver.find_elements(By.TAG_NAME, "div")
        for bloque in posibles_bloques:
            try:
                titulo = bloque.find_element(By.TAG_NAME, "h2")
                if "Datos nutricionales" in titulo.text:
                    filas = bloque.find_elements(By.TAG_NAME, "tr")
                    for fila in filas:
                        celdas = fila.find_elements(By.TAG_NAME, "td")
                        if len(celdas) == 2:
                            clave = celdas[0].text.strip().replace(":", "")
                            valor = celdas[1].text.strip()
                            if clave in nutricionales_dict:
                                nutricionales_dict[clave] = limpiar_texto(valor)
                    break
            except:
                continue
    except:
        pass

    producto.update(nutricionales_dict)
    return producto

def reiniciar_driver(driver):
    try:
        driver.quit()
    except:
        pass
    return iniciar_driver()

def guardar_csv_parcial(productos, path):
    df = pd.DataFrame(productos)
    df.to_csv(path, index=False, sep=";", encoding="utf-8-sig")
    print(f"[Guardado parcial] {len(df)} productos → {path}")