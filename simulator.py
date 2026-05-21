"""
Motor de automação Playwright para o simulador da Caixa.
"""

import asyncio
import re
from typing import Optional
from playwright.async_api import async_playwright, Page

from models import SimulacaoParams, Produto, TIPO_IMOVEL_MAP, CATEGORIA_MAP
from cities_cache import find_city_id, get_cities

URL = "https://www8.caixa.gov.br/siopiinternet-web/simulaOperacaoInternet.do?method=inicializarCasoUso"

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-setuid-sandbox",
    "--window-size=1280,900",
]

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# Script de anti-detecção injetado em todas as páginas
STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});
    Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});
    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
    Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});
    Object.defineProperty(screen, 'colorDepth', {get: () => 24});
    window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};
    window.Notification = {permission: 'default'};
    delete window.__playwright;
    delete window.__pw_manual;
"""


async def _set_select(page: Page, select_id: str, value: str):
    await page.evaluate(f"""
        (function() {{
            var s = document.getElementById('{select_id}');
            if (s) {{
                s.value = '{value}';
                s.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        }})()
    """)
    await page.wait_for_timeout(1300)


async def _set_currency(page: Page, field_id: str, value: float):
    """Preenche campo com máscara de moeda brasileira.

    O campo tem máscara que trata os últimos 2 dígitos como centavos,
    então R$ 300.000,00 requer passar 30000000 (= 300000 × 100).
    """
    cents = int(value * 100)
    await page.evaluate(f"""
        (function() {{
            var el = document.getElementById('{field_id}');
            if (el) {{
                el.value = '{cents}';
                el.dispatchEvent(new Event('keyup', {{bubbles: true}}));
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        }})()
    """)
    await page.wait_for_timeout(300)


async def _set_checkbox(page: Page, input_id: str, checked: bool):
    current = await page.evaluate(f"(function(){{var el=document.getElementById('{input_id}');return el?el.checked:null}})()")
    if current is None:
        return
    if current != checked:
        if checked:
            await page.check(f"#{input_id}")
        else:
            await page.uncheck(f"#{input_id}")
    await page.wait_for_timeout(200)


async def _dismiss_modal(page: Page) -> bool:
    """Fecha modal de erro se existir. Retorna True se havia modal."""
    try:
        ok_btn = page.locator("button:has-text('OK'), input[type=button][value='OK']").first
        if await ok_btn.is_visible(timeout=1000):
            await ok_btn.click()
            await page.wait_for_timeout(500)
            return True
    except Exception:
        pass
    return False


def _parse_currency(text: str) -> float:
    """Converte 'R$ 1.234,56' → 1234.56"""
    if not text:
        return 0.0
    text = re.sub(r"[R$\s]", "", text)
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


async def _get_produtos_passo3(page: Page) -> list[dict]:
    """Extrai lista de produtos disponíveis no passo3."""
    return await page.evaluate("""
        (function() {
            var result = [];
            var links = document.querySelectorAll('a.js-form-next[onclick]');
            links.forEach(function(a) {
                var onclick = a.getAttribute('onclick') || '';
                var match = onclick.match(/simular\\s*\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*'([^']+)'/);
                if (match) {
                    var descEl = a.parentElement ? a.parentElement.querySelector('.label-extra-desc') : null;
                    result.push({
                        produto_id: match[1],
                        tipo_simulacao: match[2],
                        nome: match[3],
                        descricao: descEl ? descEl.innerText.trim() : '',
                    });
                }
            });
            return result;
        })()
    """)


def _parse_passo4_text(text: str, nome_produto: str, descricao: str) -> Optional[Produto]:
    """Extrai dados financeiros do texto do passo4."""
    if not text or len(text) < 50:
        return None

    produto = Produto(modalidade=nome_produto, programa=descricao)

    # Valor do imóvel
    m = re.search(r"Valor do im[oó]vel\s*R\$\s*([\d.,]+)", text)
    if m:
        produto.valor_imovel = _parse_currency(m.group(1))

    # Valor do financiamento
    m = re.search(r"Valor do financiamento\s*R\$\s*([\d.,]+)", text)
    if m:
        produto.valor_financiado = _parse_currency(m.group(1))

    # Prazo escolhido
    m = re.search(r"Prazo escolhido\s*(\d+)\s*meses", text)
    if m:
        produto.prazo_meses = int(m.group(1))

    # Sistema de amortização
    if "SAC" in text.upper():
        produto.sistema_amortizacao = "SAC"
    if "PRICE" in text.upper():
        produto.sistema_amortizacao = ("SAC/PRICE" if produto.sistema_amortizacao == "SAC"
                                       else "PRICE")

    # Juros nominais (taxa a.a.)
    m = re.search(r"Juros Nominais\s*([\d,.]+%\s*a\.a\.)", text, re.IGNORECASE)
    if m:
        produto.taxa_juros_anual = m.group(1).strip()

    # Juros efetivos (taxa a.a. — usamos como fallback se nominal não encontrado)
    m_ef = re.search(r"Juros Efetivos\s*([\d,.]+%\s*a\.a\.)", text, re.IGNORECASE)
    if m_ef and not produto.taxa_juros_anual:
        produto.taxa_juros_anual = m_ef.group(1).strip()

    # Primeira prestação
    m = re.search(r"1ª Prestação\s*R\$\s*([\d.,]+)", text, re.IGNORECASE)
    primeira = _parse_currency(m.group(1)) if m else 0.0

    # Última prestação (mínima no SAC)
    m = re.search(r"[UÚ]ltima Prestação\s*R\$\s*([\d.,]+)", text, re.IGNORECASE)
    ultima = _parse_currency(m.group(1)) if m else 0.0

    # "Demais prestações" — múltiplas colunas por tipo de seguro, pegar a maior
    demais = re.findall(r"Demais prestações\s*R\$\s*([\d.,]+)", text, re.IGNORECASE)
    demais_max = max((_parse_currency(v) for v in demais if _parse_currency(v) > 0), default=0.0)

    all_vals = [v for v in [primeira, ultima, demais_max] if v > 0]
    if all_vals:
        produto.parcela_minima = min(all_vals)  # última prestação no SAC
        produto.parcela_maxima = max(all_vals)  # demais/primeira no SAC

    return produto


async def _extract_produto_details(page: Page, produto_id: str, tipo: str,
                                   nome: str, descricao: str) -> Optional[Produto]:
    """Chama simular() para o produto e extrai dados do passo4."""
    nome_escaped = nome.replace("'", "\\'")
    await page.evaluate(f"simuladorInternet.simular({produto_id}, {tipo}, '{nome_escaped}')")
    await page.wait_for_timeout(4000)

    passo4_data = await page.evaluate("""
        (function() {
            var p4 = document.getElementById('passo4');
            if (!p4) return {erro: 'passo4 nao existe'};
            var style = window.getComputedStyle(p4);
            if (style.display === 'none') return {erro: 'passo4 oculto'};
            return {texto: p4.innerText.substring(0, 6000)};
        })()
    """)

    if passo4_data.get("erro"):
        return None

    return _parse_passo4_text(passo4_data["texto"], nome, descricao)


async def simular(params: SimulacaoParams) -> dict:
    """
    Executa a simulação completa no simulador da Caixa.
    Retorna dict com 'produtos' (list) e 'erro' (str|None).
    """
    cidade_id = find_city_id(params.uf, params.cidade)
    if not cidade_id:
        return {"produtos": [], "erro": f"Cidade '{params.cidade}' não encontrada na UF '{params.uf}'"}

    tipo_value = TIPO_IMOVEL_MAP.get(params.tipo_imovel, "1")
    categoria_value = CATEGORIA_MAP.get(params.categoria, "1")

    cpf = re.sub(r"\D", "", params.cpf)
    if len(cpf) == 11:
        cpf_fmt = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    else:
        cpf_fmt = params.cpf

    # Roteia pelo proxy SOCKS5 do Android (via Tailscale) para evitar bloqueio de IP de datacenter.
    # O Android (IP móvel/residencial) é aceito pela Caixa; IPs de VPS recebem 403.
    # Se o proxy não estiver disponível (ambiente local), roda sem proxy.
    import socket as _socket
    import os as _os

    _proxy_host = _os.getenv("SOCKS5_PROXY_HOST", "100.82.36.81")
    _proxy_port = int(_os.getenv("SOCKS5_PROXY_PORT", "1080"))
    _proxy_available = False
    try:
        _s = _socket.create_connection((_proxy_host, _proxy_port), timeout=3)
        _s.close()
        _proxy_available = True
    except Exception:
        pass

    _proxy = {"server": f"socks5://{_proxy_host}:{_proxy_port}"} if _proxy_available else None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=BROWSER_ARGS,
            proxy=_proxy,
        )
        context = await browser.new_context(
            user_agent=UA,
            viewport={"width": 1280, "height": 900},
            locale="pt-BR",
        )
        page = await context.new_page()
        await page.add_init_script(STEALTH_SCRIPT)

        try:
            await page.goto(URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # ── Etapa 1 ────────────────────────────────────────────────
            radio_id = "pessoaF" if params.tipo_pessoa == "F" else "pessoaJ"
            await page.evaluate(f"(function(){{var el=document.getElementById('{radio_id}');if(el)el.checked=true;}})()")

            await _set_select(page, "tipoImovel", tipo_value)
            await page.wait_for_timeout(1500)  # aguarda AJAX da categoria carregar
            await _set_select(page, "categoriaImovel", categoria_value)

            # valorImovel tem máscara de moeda: valor × 100 para acertar os decimais
            await _set_currency(page, "valorImovel", params.valor_imovel)

            if params.categoria == "Reforma e/ou Ampliação" and hasattr(params, "valor_reforma"):
                await _set_currency(page, "valorReforma", params.valor_imovel)

            await _set_select(page, "uf", params.uf.upper())
            await page.wait_for_timeout(2000)  # aguarda AJAX das cidades
            await _set_select(page, "cidade", cidade_id)
            await page.wait_for_timeout(500)

            if params.possui_imovel_na_cidade:
                await page.evaluate("(function(){var el=document.getElementById('imovelCidade');if(el)el.checked=true;})()")
            if params.portabilidade:
                await page.evaluate("(function(){var el=document.getElementById('icPortabilidadeCreditoImobiliario');if(el)el.checked=true;})()")

            # Clica via JS para evitar timeout em VPS headless (div, não button)
            await page.evaluate("(function(){var el=document.getElementById('btn_next1');if(el)el.click();})()")

            # Espera ativa: aguarda o campo CPF aparecer (confirma que o passo2 carregou)
            try:
                await page.wait_for_selector("#nuCpfCnpjInteressado", state="visible", timeout=15000)
            except Exception:
                await page.wait_for_timeout(4000)

            # ── Etapa 2 ────────────────────────────────────────────────
            if cpf_fmt:
                await page.evaluate(f"""
                    (function() {{
                        var el = document.getElementById('nuCpfCnpjInteressado');
                        if (el) {{ el.value = '{cpf_fmt}'; el.dispatchEvent(new Event('input', {{bubbles: true}})); }}
                    }})()
                """)

            if params.telefone:
                await page.evaluate(f"""
                    (function() {{
                        var el = document.getElementById('nuTelefoneCelular');
                        if (el) {{ el.value = '{params.telefone}'; el.dispatchEvent(new Event('input', {{bubbles: true}})); }}
                    }})()
                """)

            await page.evaluate(f"""
                (function() {{
                    var el = document.getElementById('rendaFamiliarBruta');
                    if (el) {{ el.value = '{int(params.renda_familiar)}'; el.dispatchEvent(new Event('input', {{bubbles: true}})); }}
                }})()
            """)

            await page.evaluate(f"""
                (function() {{
                    var el = document.getElementById('dataNascimento');
                    if (el) {{ el.value = '{params.data_nascimento}'; el.dispatchEvent(new Event('input', {{bubbles: true}})); }}
                }})()
            """)

            if params.possui_fgts:
                await _set_checkbox(page, "vaContaFgtsS", True)
            if params.ja_beneficiado_fgts:
                await _set_checkbox(page, "beneficiadoFGTS", True)
                if params.data_beneficio_fgts:
                    await page.evaluate(f"(function(){{var el=document.getElementById('dataBeneficioFGTS');if(el)el.value='{params.data_beneficio_fgts}';}})() ")
            if params.possui_convenio and params.cnpj_convenio:
                await _set_checkbox(page, "possuiConvenio", True)
                await page.wait_for_timeout(500)
                await page.evaluate(f"(function(){{var el=document.getElementById('cnpjConvenio');if(el)el.value='{params.cnpj_convenio}';}})() ")
            if params.fator_social:
                await _set_checkbox(page, "icFatorSocial", True)
            if params.mais_de_um_comprador:
                await _set_checkbox(page, "icPerguntaFatorSocial", True)
            if params.relacionamento_caixa:
                await _set_checkbox(page, "icPossuiRelacionamentoCAIXA", True)
            if params.servidor_publico:
                await _set_checkbox(page, "icServidorPublico", True)
            if params.conta_salario_caixa:
                await _set_checkbox(page, "icContaSalarioCAIXA", True)

            # Clica via JS para evitar timeout em VPS headless (div, não button)
            await page.evaluate("(function(){var el=document.getElementById('btn_next2');if(el)el.click();})()")

            # Espera ativa: aguarda o passo3 ficar visível (confirma envio do formulário)
            try:
                await page.wait_for_function(
                    """() => {
                        var p3 = document.getElementById('passo3');
                        if (!p3) return false;
                        var style = window.getComputedStyle(p3);
                        return style.display !== 'none' && p3.innerText.trim().length > 10;
                    }""",
                    timeout=20000,
                )
            except Exception:
                await page.wait_for_timeout(6000)

            await _dismiss_modal(page)

            # ── Passo 3: extrair lista de produtos disponíveis ─────────
            lista_produtos = await _get_produtos_passo3(page)

            passo3_text = await page.evaluate("""
                (function() {
                    var el = document.getElementById('passo3');
                    return el ? el.innerText.substring(0, 8000) : '';
                })()
            """)

            if not lista_produtos:
                # Salva screenshot de debug para diagnosticar o que a Caixa retornou
                import os, time as _time
                debug_path = f"/tmp/caixa_debug_{int(_time.time())}.png"
                try:
                    await page.screenshot(path=debug_path, full_page=True)
                except Exception:
                    debug_path = ""
                return {
                    "produtos": [],
                    "texto_completo": passo3_text,
                    "debug_screenshot": debug_path,
                    "erro": None,
                }

            # ── Passo 4: navegar por cada produto e extrair detalhes ───
            produtos_detalhados = []
            for prod in lista_produtos:
                produto = await _extract_produto_details(
                    page,
                    prod["produto_id"],
                    prod["tipo_simulacao"],
                    prod["nome"],
                    prod["descricao"],
                )
                if produto:
                    produtos_detalhados.append(vars(produto))

            return {
                "produtos": produtos_detalhados,
                "texto_completo": passo3_text,
                "erro": None,
            }

        except Exception as e:
            return {"produtos": [], "erro": str(e), "texto_completo": ""}
        finally:
            await browser.close()


async def listar_cidades_uf(uf: str) -> list[dict]:
    """Retorna lista de cidades de uma UF a partir do cache."""
    cidades = get_cities(uf.upper())
    return [{"id": c.id, "nome": c.nome, "uf": c.uf} for c in cidades]
