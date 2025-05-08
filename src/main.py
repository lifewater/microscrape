from flask import Flask, Response
from threading import Thread
from bs4 import BeautifulSoup
import requests
import re
import datetime
import time
import sys


# How often promtheus metrics are pushed
sleep_interval = 1 # In minutes

# Flask Port 
flask_port = 10123

# Prometheus metrics route
metrics_route="/metrics"

GPUs = {}
nvidia_url = "https://www.microcenter.com/search/search_results.aspx?Ntk=all&sortby=match&N=4294802166&myStore=false&storeid=155&rpp=96"
radeon_url = "https://www.microcenter.com/search/search_results.aspx?Ntk=all&sortby=match&N=4294802072&myStore=false&storeid=155&rpp=96"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'}
brands = ["ASRock", "ASUS", "Gigabyte", "MSI", "PNY", "PowerColor", "Sapphire", "XFX", "Zotac"]
types = ["RTX 5090", "RTX 5080", "RTX 5070 Ti", "RTX 5060 Ti", "RTX 5070","RTX 5060"]

def get_html(url: str):
    page = requests.get(url, headers=headers)
    print (f"Response: {page.status_code}")
    return BeautifulSoup(page.text, "html.parser")

def get_titles(html: BeautifulSoup):
    titles = []
    elements = html.find_all(class_='detail_wrapper')
    for element in elements:
        tmp=element.find("a").string
        title = re.sub(r"NVIDIA |AMD |GeForce |Radeon |GDDR7|GDDR6|PCIe 4.0|PCIe 5.0|Graphics Card", "", tmp.text).strip()
        titles.append(title)
    print (f"titles: {titles}")
    return titles

def get_sku(html: BeautifulSoup):
    skus = []
    elements = html.find_all(class_='sku')
    for element in elements:
        #print (f"B {element}")
        sku = element.text.replace("SKU: ", "")
        #print (f"A {sku}")
        if len(sku) > 0:
            skus.append(sku)
        else:
            skus.append("unknown")
    return skus

def get_stock(html: BeautifulSoup):
    stock = []
    unwanted_text = ["IN STOCK", "SOLD OUT", "at Houston Store", "+", "Buy In Store", "-"]
    elements = html.find_all(class_ = "stock")
    for element in elements:
        #print {f"working on {element}"}
        text = re.sub(r"SOLD OUT|IN STOCK|at Houston Store|\+|Buy In Store|-", "", element.text).strip()
        if len(text) > 0:
            stock.append(int(text))
        else:
            stock.append(int(0))
    return stock

def get_prices(html: BeautifulSoup):
    prices = []
    elements = html.find_all(class_="price")
    for element in elements:
        price_span = element.find('span', itemprop='price')
        #print(f"Span {price_span}")
        if price_span is not None:
            price_text = price_span.get_text()
            #print(f"Text {price_text}")
            match = re.search(r'[\d,.]+', price_text)
            if match:
                price = match.group().replace(',', '')
                #print (f"Match {price}")
                prices.append(float(price))
    return prices

def sleep_until(interval):
    now = datetime.datetime.now()
    next_minute = ((now.minute // interval) + 1) * interval
    if next_minute >= 60:
        next_time = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    else:
        next_time = now.replace(minute=next_minute, second=0, microsecond=0)
    sleep_seconds = (next_time - now).total_seconds()
    print(f"Sleeping for {sleep_seconds:.0f} seconds until {next_time.strftime('%H:%M')}")
    time.sleep(sleep_seconds)

def update_metrics():
    global GPUs
    while True:
        try:
            sleep_until(sleep_interval)

            print(f"Started: {datetime.datetime.now()}")
            nvidia_html = get_html(nvidia_url)
            titles = get_titles(nvidia_html)
            skus = get_sku(nvidia_html)
            stocks = get_stock(nvidia_html)
            prices = get_prices(nvidia_html)
            time.sleep(5)
            radeon_html = get_html(radeon_url)
            titles.extend(get_titles(radeon_html))
            skus.extend(get_sku(radeon_html))
            stocks.extend(get_stock(radeon_html))
            prices.extend(get_prices(radeon_html))
            print(F"{len(titles)} titles found")

            for idx, title in enumerate(titles):
                sku = skus[idx]
                
                brand = next((b for b in brands if title.startswith(b)), None)
                type_ = next((t for t in types if t in title), None)

                remaining_title = title
                if brand:
                    remaining_title = remaining_title[len(brand):].strip()
                if type_:
                    remaining_title = remaining_title[len(type_):].strip()
                
                parts = remaining_title.rsplit(' ', 1)
                model = parts[0]
                ram = parts[1]
                stock = stocks[idx]
                price = prices[idx]
                GPUs[sku] = {
                    "brand": brand,
                    "type": type_,
                    "model": model,
                    "stock": stock,
                    "ram": ram,
                    "price": price
                    }
            print(f"Ended: {datetime.datetime.now()}")
            #for idx, title in enumerate(titles):
            #    print (f"Title: {title}")
            #    print (f"After: {GPUs[skus[idx]]['brand']} {GPUs[skus[idx]]['type']} {GPUs[skus[idx]]['model']} {GPUs[skus[idx]]['ram']}, Stock: {GPUs[skus[idx]]['stock']}, Price: {GPUs[skus[idx]]['price']}")
        except Exception as e:
            print(f"Error updating metrics: {e}")

def prometheus_metrics():
    lines = []
    for sku, data in GPUs.items():
        labels = f'brand="{data["brand"]}",type="{data["type"]}",model="{data["model"]}",ram="{data["ram"]}",sku="{sku}"'
        lines.append(f'gpu_stock{{{labels}}} {data["stock"]}')
        lines.append(f'gpu_price{{{labels}}} {data["price"]}')
    return "\n".join(lines) + "\n"

# --- Flask App ---
app = Flask(__name__)

@app.route(metrics_route)
def metrics():
    return Response(prometheus_metrics(), mimetype="text/plain")


def main():
    print(f"Initialized: {datetime.datetime.now()}")
    t = Thread(target=update_metrics, daemon=True)
    t.start()
    #t.join()
    app.run(host="0.0.0.0", port=flask_port)

if __name__ == "__main__":
    main()


