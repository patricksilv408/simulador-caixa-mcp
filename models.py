from dataclasses import dataclass, field
from typing import Optional

TIPO_IMOVEL_MAP = {
    "Residencial": "1",
    "Comercial": "2",
    "Rural": "5",
}

CATEGORIA_MAP = {
    "Aquisição de Imóvel Novo": "1",
    "Construção": "2",
    "Reforma e/ou Ampliação": "3",
    "Aquisição de Imóvel Usado": "4",
    "Rural": "5",
    "Aquisição de Terreno": "6",
    "Empréstimo Garantido por Imóvel": "7",
    "Imóveis CAIXA": "11",
}

CATEGORIAS_POR_TIPO = {
    "Residencial": [
        "Aquisição de Imóvel Novo",
        "Aquisição de Imóvel Usado",
        "Aquisição de Terreno",
        "Construção",
        "Empréstimo Garantido por Imóvel",
        "Imóveis CAIXA",
        "Reforma e/ou Ampliação",
    ],
    "Comercial": [
        "Aquisição de Imóvel Novo",
        "Aquisição de Imóvel Usado",
        "Aquisição de Terreno",
        "Empréstimo Garantido por Imóvel",
        "Imóveis CAIXA",
    ],
    "Rural": [],
}

UFS = [
    "AC","AL","AM","AP","BA","CE","DF","ES","GO",
    "MA","MG","MS","MT","PA","PB","PE","PI","PR",
    "RJ","RN","RO","RR","RS","SC","SE","SP","TO",
]


@dataclass
class SimulacaoParams:
    tipo_imovel: str          # "Residencial" | "Comercial" | "Rural"
    categoria: str            # ver CATEGORIAS_POR_TIPO
    valor_imovel: float       # valor em R$
    uf: str                   # sigla do estado ex: "SP"
    cidade: str               # nome da cidade ex: "SAO PAULO"
    renda_familiar: float     # renda bruta mensal em R$
    data_nascimento: str      # "DD/MM/AAAA"
    cpf: str                  # CPF formatado "000.000.000-00" ou só dígitos
    telefone: str = ""
    possui_fgts: bool = False
    ja_beneficiado_fgts: bool = False
    data_beneficio_fgts: str = ""
    possui_convenio: bool = False
    cnpj_convenio: str = ""
    fator_social: bool = False
    mais_de_um_comprador: bool = False
    relacionamento_caixa: bool = False
    servidor_publico: bool = False
    conta_salario_caixa: bool = False
    possui_imovel_na_cidade: bool = False
    portabilidade: bool = False
    tipo_pessoa: str = "F"    # "F"=Física, "J"=Jurídica


@dataclass
class Produto:
    modalidade: str
    programa: str = ""
    valor_imovel: float = 0.0
    valor_financiado: float = 0.0
    valor_entrada: float = 0.0
    prazo_meses: int = 0
    taxa_juros_anual: str = ""
    taxa_juros_mensal: str = ""
    cet_anual: str = ""
    parcela_minima: float = 0.0
    parcela_maxima: float = 0.0
    sistema_amortizacao: str = ""
    seguro_mip: float = 0.0
    seguro_dfi: float = 0.0
    comprometimento_renda: str = ""
    linha_credito: str = ""
    detalhes_extras: dict = field(default_factory=dict)


@dataclass
class Cidade:
    id: str
    nome: str
    uf: str
