# Simulador Caixa MCP

Servidor MCP (Model Context Protocol) para simulação de financiamento imobiliário na **Caixa Econômica Federal**, usando automação Playwright headless.

Permite que agentes de IA realizem simulações completas no simulador da Caixa sem interação manual — ideal para corretores de imóveis que precisam de simulações rápidas para clientes.

---

## Ferramentas disponíveis

| Ferramenta | Descrição |
|---|---|
| `simular_financiamento` | Simulação completa (produtos, parcelas, taxas, CET) |
| `listar_cidades` | Lista cidades disponíveis por UF |
| `obter_categorias` | Lista categorias de financiamento por tipo de imóvel |

---

## Instalação

### Pré-requisitos

- Python 3.10+ (recomendado: 3.12 via `uv`)
- [uv](https://docs.astral.sh/uv/) (opcional, mas recomendado)

### Passos

```bash
# Clonar o repositório
git clone https://github.com/patricksilv408/simulador-caixa-mcp.git
cd simulador-caixa-mcp

# Criar ambiente virtual com Python 3.12
uv python install 3.12
uv venv --python 3.12 .venv
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Instalar navegador Chromium para o Playwright
playwright install chromium
```

### Configuração

Copie `.env.example` para `.env` e ajuste conforme necessário:

```bash
cp .env.example .env
```

---

## Uso

### Modo stdio (Claude Code desktop)

Adicione ao `~/.claude/mcp.json`:

```json
{
  "simulador-caixa": {
    "command": "/caminho/para/.venv/bin/python",
    "args": ["/caminho/para/server.py"]
  }
}
```

### Modo HTTP (VPS / servidor remoto)

```bash
# SSE (compatível com a maioria dos clientes MCP)
MCP_TRANSPORT=sse MCP_PORT=8000 python server.py

# Streamable HTTP (recomendado para VPS)
MCP_TRANSPORT=streamable-http MCP_PORT=8000 python server.py
```

Endpoints:
- SSE: `http://HOST:8000/sse`
- Streamable HTTP: `http://HOST:8000/mcp`

---

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `stdio`, `sse` ou `streamable-http` |
| `MCP_HOST` | `0.0.0.0` | Host para escutar (modo HTTP) |
| `MCP_PORT` | `8000` | Porta para escutar (modo HTTP) |

---

## Exemplo de simulação

```
Simule um financiamento de imóvel residencial (aquisição de imóvel novo)
no valor de R$260.000 em Camaçari/BA.
CPF: 078.853.455-64, nascimento: 28/06/1999, renda familiar: R$6.000.
```

Retorna lista de produtos disponíveis com: modalidade, programa, parcelas (mín/máx), prazo, taxa de juros, CET e valor financiado.

---

## Estrutura do projeto

```
simulador-caixa-mcp/
├── server.py           # Servidor MCP (FastMCP) com 3 ferramentas
├── simulator.py        # Automação Playwright — core da simulação
├── models.py           # Dataclasses: SimulacaoParams, Produto, Cidade
├── cities_cache.py     # Carrega e busca cidades por UF
├── cities_cache.json   # Cache com 5.571 cidades (27 UFs)
├── populate_cache.py   # Script para regenerar o cache de cidades
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Notas técnicas

- O simulador da Caixa usa ShieldSquare (anti-bot). A automação usa `headless=True` com fingerprinting desativado, o que passa a validação sem Xvfb.
- O campo `valorImovel` tem máscara de moeda que trata os últimos 2 dígitos como centavos — o valor é multiplicado por 100 antes de ser enviado via JS.
- Os produtos são extraídos da etapa 3 (lista de nomes) e depois detalhados um a um via `simuladorInternet.simular()` para obter taxas/parcelas da etapa 4.

---

## Licença

MIT
