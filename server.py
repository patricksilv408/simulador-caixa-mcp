"""
Servidor MCP – Simulador de Financiamento Imobiliário da Caixa Econômica Federal.

Ferramentas disponíveis:
  - simular_financiamento   : Realiza simulação completa
  - listar_cidades          : Lista cidades disponíveis por UF
  - obter_categorias        : Lista categorias de financiamento por tipo de imóvel
"""

import json
import asyncio
import os
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

from models import SimulacaoParams, CATEGORIAS_POR_TIPO, UFS
from simulator import simular, listar_cidades_uf

mcp = FastMCP(
    "simulador-caixa",
    instructions=(
        "Servidor MCP para simulação de financiamento imobiliário na Caixa Econômica Federal. "
        "Use simular_financiamento para obter parcelas, taxas e condições de financiamento. "
        "Use listar_cidades para descobrir o nome exato da cidade. "
        "Use obter_categorias para ver as opções disponíveis por tipo de imóvel."
    )
)


@mcp.tool()
async def simular_financiamento(
    tipo_imovel: str,
    categoria: str,
    valor_imovel: float,
    uf: str,
    cidade: str,
    renda_familiar: float,
    data_nascimento: str,
    cpf: str,
    telefone: str = "",
    tipo_pessoa: str = "F",
    possui_fgts: bool = False,
    ja_beneficiado_fgts: bool = False,
    data_beneficio_fgts: str = "",
    possui_convenio: bool = False,
    cnpj_convenio: str = "",
    fator_social: bool = False,
    mais_de_um_comprador: bool = False,
    relacionamento_caixa: bool = False,
    servidor_publico: bool = False,
    conta_salario_caixa: bool = False,
    possui_imovel_na_cidade: bool = False,
    portabilidade: bool = False,
) -> str:
    """
    Realiza uma simulação completa de financiamento imobiliário no simulador da Caixa.

    Parâmetros obrigatórios:
    - tipo_imovel: "Residencial", "Comercial" ou "Rural"
    - categoria: ex "Aquisição de Imóvel Novo", "Aquisição de Imóvel Usado", "Construção", etc.
                 Use obter_categorias para ver todas as opções por tipo.
    - valor_imovel: valor do imóvel em R$ (ex: 350000)
    - uf: sigla do estado em maiúsculas (ex: "SP", "RJ", "MG")
    - cidade: nome da cidade em maiúsculas sem acentos (ex: "SAO PAULO", "RIO DE JANEIRO")
              Use listar_cidades se não souber o nome exato.
    - renda_familiar: renda bruta mensal do núcleo familiar em R$ (ex: 6000)
    - data_nascimento: data de nascimento do proponente no formato "DD/MM/AAAA"
    - cpf: CPF do proponente (formato "000.000.000-00" ou só dígitos)

    Parâmetros opcionais que influenciam as modalidades disponíveis:
    - tipo_pessoa: "F" (Física, padrão) ou "J" (Jurídica)
    - possui_fgts: tem 3 anos de trabalho sob regime FGTS (true/false)
    - ja_beneficiado_fgts: já foi beneficiado com subsídio FGTS/União (true/false)
    - relacionamento_caixa: tem ou deseja conta corrente/poupança na Caixa
    - servidor_publico: é servidor público federal/estadual/municipal
    - conta_salario_caixa: tem crédito salário ou previdência na Caixa
    - mais_de_um_comprador: há mais de um comprador ou dependente na proposta

    Retorna:
    JSON com lista de produtos (modalidades) disponíveis, cada um contendo:
    modalidade, programa, parcela_minima, parcela_maxima, prazo_meses,
    taxa_juros_anual, taxa_juros_mensal, cet_anual, sistema_amortizacao, valor_financiado.
    """
    # Validações básicas
    uf = uf.upper().strip()
    if uf not in UFS:
        return json.dumps({"erro": f"UF inválida: {uf}. Use uma das: {', '.join(UFS)}"}, ensure_ascii=False)

    if tipo_imovel not in CATEGORIAS_POR_TIPO:
        return json.dumps({
            "erro": f"Tipo de imóvel inválido: '{tipo_imovel}'. Use: {', '.join(CATEGORIAS_POR_TIPO.keys())}"
        }, ensure_ascii=False)

    categorias_validas = CATEGORIAS_POR_TIPO[tipo_imovel]
    if categorias_validas and categoria not in categorias_validas:
        return json.dumps({
            "erro": f"Categoria inválida para {tipo_imovel}: '{categoria}'. "
                    f"Opções: {', '.join(categorias_validas)}"
        }, ensure_ascii=False)

    params = SimulacaoParams(
        tipo_imovel=tipo_imovel,
        categoria=categoria,
        valor_imovel=valor_imovel,
        uf=uf,
        cidade=cidade.upper().strip(),
        renda_familiar=renda_familiar,
        data_nascimento=data_nascimento,
        cpf=cpf,
        telefone=telefone,
        tipo_pessoa=tipo_pessoa,
        possui_fgts=possui_fgts,
        ja_beneficiado_fgts=ja_beneficiado_fgts,
        data_beneficio_fgts=data_beneficio_fgts,
        possui_convenio=possui_convenio,
        cnpj_convenio=cnpj_convenio,
        fator_social=fator_social,
        mais_de_um_comprador=mais_de_um_comprador,
        relacionamento_caixa=relacionamento_caixa,
        servidor_publico=servidor_publico,
        conta_salario_caixa=conta_salario_caixa,
        possui_imovel_na_cidade=possui_imovel_na_cidade,
        portabilidade=portabilidade,
    )

    resultado = await simular(params)

    # Formatar resposta limpa para o agente
    if resultado.get("erro"):
        return json.dumps({
            "sucesso": False,
            "erro": resultado["erro"],
        }, ensure_ascii=False, indent=2)

    produtos = resultado.get("produtos", [])
    texto = resultado.get("texto_completo", "")

    if not produtos:
        return json.dumps({
            "sucesso": False,
            "mensagem": "Nenhum produto encontrado para os dados informados.",
            "dica": (
                "Verifique: renda compatível com o valor do imóvel, "
                "CPF válido, cidade correta para a UF informada. "
                "Para Minha Casa Minha Vida, a renda deve ser até R$8.000 "
                "e o imóvel até R$350.000."
            ),
            "texto_bruto": texto[:3000] if texto else "",
        }, ensure_ascii=False, indent=2)

    return json.dumps({
        "sucesso": True,
        "total_produtos": len(produtos),
        "produtos": produtos,
        "texto_completo": texto[:4000] if texto else "",
        "observacao": (
            "Os valores são estimativas. Condições definitivas sujeitas a análise de crédito. "
            "Para contratar, visite uma agência Caixa ou Correspondente Caixa Aqui."
        ),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def listar_cidades(uf: str) -> str:
    """
    Lista todas as cidades disponíveis no simulador da Caixa para uma UF.

    Parâmetros:
    - uf: sigla do estado em maiúsculas (ex: "SP", "RJ", "MG")

    Retorna lista de cidades com id e nome.
    Use o campo 'nome' exatamente como retornado ao chamar simular_financiamento.
    """
    uf = uf.upper().strip()
    if uf not in UFS:
        return json.dumps({
            "erro": f"UF inválida: '{uf}'. UFs disponíveis: {', '.join(UFS)}"
        }, ensure_ascii=False)

    cidades = await listar_cidades_uf(uf)
    return json.dumps({
        "uf": uf,
        "total": len(cidades),
        "cidades": cidades,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def obter_categorias(tipo_imovel: str) -> str:
    """
    Lista as categorias de financiamento disponíveis para um tipo de imóvel.

    Parâmetros:
    - tipo_imovel: "Residencial", "Comercial" ou "Rural"

    Retorna lista de categorias válidas para usar em simular_financiamento.
    """
    if tipo_imovel not in CATEGORIAS_POR_TIPO:
        return json.dumps({
            "erro": f"Tipo inválido: '{tipo_imovel}'. Use: Residencial, Comercial ou Rural"
        }, ensure_ascii=False)

    categorias = CATEGORIAS_POR_TIPO[tipo_imovel]
    return json.dumps({
        "tipo_imovel": tipo_imovel,
        "categorias": categorias,
        "total": len(categorias),
        "nota": "Categoria 'Rural' não possui subcategorias disponíveis no simulador.",
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")  # "stdio" | "sse" | "streamable-http"
    host      = os.getenv("MCP_HOST", "0.0.0.0")
    port      = int(os.getenv("MCP_PORT", "8000"))

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "sse":
        import uvicorn
        print(f"Iniciando servidor SSE em http://{host}:{port}/sse")
        uvicorn.run(mcp.sse_app(), host=host, port=port)
    else:  # streamable-http (padrão para VPS)
        import uvicorn
        print(f"Iniciando servidor HTTP em http://{host}:{port}/mcp")
        uvicorn.run(mcp.streamable_http_app(), host=host, port=port)
