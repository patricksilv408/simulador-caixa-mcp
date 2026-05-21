"""
Script one-time para popular o cache de cidades por UF.
Executa o browser e acessa o simulador para cada UF, coletando as cidades.
Salva em cities_cache.json.
"""

import asyncio
import json
from playwright.async_api import async_playwright

URL = "https://www8.caixa.gov.br/siopiinternet-web/simulaOperacaoInternet.do?method=inicializarCasoUso"

UFS = [
    "AC","AL","AM","AP","BA","CE","DF","ES","GO",
    "MA","MG","MS","MT","PA","PB","PE","PI","PR",
    "RJ","RN","RO","RR","RS","SC","SE","SP","TO",
]


async def main():
    cities = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1280,900",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="pt-BR"
        )
        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR','pt','en-US','en']});
            window.chrome = {runtime: {}};
        """)

        print("Acessando simulador...")
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Selecionar Residencial para garantir que a UF funciona
        await page.evaluate("""
            (function() {
                var s = document.getElementById('tipoImovel');
                s.value = '1';
                s.dispatchEvent(new Event('change', {bubbles: true}));
            })()
        """)
        await page.wait_for_timeout(1500)

        for uf in UFS:
            print(f"Coletando cidades de {uf}...")
            await page.evaluate(f"""
                (function() {{
                    var s = document.getElementById('uf');
                    s.value = '{uf}';
                    s.dispatchEvent(new Event('change', {{bubbles: true}}));
                }})()
            """)
            await page.wait_for_timeout(1500)

            opts = await page.evaluate("""
                (function() {
                    return Array.from(document.getElementById('cidade').options)
                        .filter(function(o) { return o.value !== ''; })
                        .map(function(o) { return {id: o.value, nome: o.text.trim()}; });
                })()
            """)
            cities[uf] = opts
            print(f"  {len(opts)} cidades encontradas")

        await browser.close()

    output_path = "cities_cache.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cities, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in cities.values())
    print(f"\nCache salvo em {output_path} ({total} cidades em {len(cities)} UFs)")


if __name__ == "__main__":
    asyncio.run(main())
