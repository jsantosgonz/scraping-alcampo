# scraper_optimizado.py
import time
import json
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re

def limpiar_texto(texto):
    if not texto:
        return ""
    return re.sub(r"\s+", " ", texto).strip()

def iniciar_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Ejecutar en segundo plano
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def obtener_subcategorias(driver, url_categoria):
    driver.get(url_categoria)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "a")))
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
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    enlaces = set()
    SCROLL_PAUSE_TIME = 1
    MAX_SCROLL = 25
    last_height = driver.execute_script("return document.body.scrollHeight")
    attempts = 0

    while attempts < MAX_SCROLL:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
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
                        enlaces.add(item["url"])
        except:
            continue

    if not enlaces:
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("/producto/"):
                enlaces.add("https://www.compraonline.alcampo.es" + a["href"])
    return list(enlaces)

def safe_find(driver, selector, by=By.CSS_SELECTOR, attr="text"):
    try:
        el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((by, selector)))
        return el.text.strip() if attr == "text" else el.get_attribute(attr)
    except:
        return ""

def extraer_datos_producto(driver, enlace):
    driver.get(enlace)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
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

    # Ingredientes y campos extra
    ingredientes, campos = "", {
        "País de origen": "", "Lugar de procedencia": "", "Peso Neto": "",
        "Denominación legal del alimento": "", "Formato": "", "Eco::Etiqueta ecológica de la UE::": ""
    }
    bloques = driver.find_elements(By.CLASS_NAME, "sc-3ycw9o-0")
    for b in bloques:
        texto = b.text
        if "Ingredientes" in texto:
            ingredientes = texto.split("\n", 1)[-1].strip()
        elif "<table" in b.get_attribute("outerHTML"):
            for f in b.find_elements(By.TAG_NAME, "tr"):
                celdas = f.find_elements(By.TAG_NAME, "td")
                if len(celdas) == 2:
                    clave, valor = celdas[0].text.strip(), celdas[1].text.strip()
                    if clave in campos:
                        campos[clave] = limpiar_texto(valor)
    producto["Ingredientes"] = limpiar_texto(ingredientes)
    producto.update(campos)

    # Información nutricional
    nutricionales = {
        "Valor energético (Kj)": "", "Valor energético (Kcal)": "",
        "Grasas": "", "Grasas saturadas": "", "Hidratos de carbono": "",
        "Azúcares": "", "Proteínas": "", "Sal": ""
    }
    try:
        divs = driver.find_elements(By.TAG_NAME, "div")
        for d in divs:
            try:
                if "Datos nutricionales" in d.text:
                    for fila in d.find_elements(By.TAG_NAME, "tr"):
                        celdas = fila.find_elements(By.TAG_NAME, "td")
                        if len(celdas) == 2:
                            clave = celdas[0].text.strip().replace(":", "")
                            valor = celdas[1].text.strip()
                            if clave in nutricionales:
                                nutricionales[clave] = limpiar_texto(valor)
                    break
            except:
                continue
    except:
        pass

    producto.update(nutricionales)
    return producto

def guardar_csv_parcial(productos, path):
    df = pd.DataFrame(productos)
    df.to_csv(path, index=False, sep=";", encoding="utf-8-sig")
    print(f"[Guardado parcial] {len(df)} productos → {path}")