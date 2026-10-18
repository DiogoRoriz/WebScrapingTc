"""Configurações centrais do pipeline de coleta de preços.

Todos os caminhos, lojas monitoradas, endereços de categoria e tempos de
espera ficam aqui, para que o restante do código não tenha valores fixos.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------
PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_DADOS = PASTA_PROJETO / "dados"
PASTA_COLETAS = PASTA_DADOS / "coletas"
PASTA_LOGS = PASTA_PROJETO / "logs"

# Planilha que simula o Data Warehouse (abas: produto, loja, oferta).
ARQUIVO_BANCO = PASTA_DADOS / "banco_dados.xlsx"
# Histórico de execuções (sucesso, bloqueio ou erro por loja) - RNF03.
ARQUIVO_LOG_EXECUCOES = PASTA_DADOS / "log_execucoes.xlsx"
# Catálogo editável com os produtos monitorados.
ARQUIVO_CATALOGO = PASTA_PROJETO / "catalogo_produtos.xlsx"

# --------------------------------------------------------------------------
# Lojas monitoradas
# --------------------------------------------------------------------------
LOJAS = {
    "KaBuM!": "https://www.kabum.com.br",
    "Pichau": "https://www.pichau.com.br",
    "Terabyte": "https://www.terabyteshop.com.br",
    "Amazon": "https://www.amazon.com.br",
}

# Pichau e Terabyte bloqueiam navegação automatizada depois da primeira
# página de cada visita. Para respeitar esse limite, cada execução diária
# visita UMA página de categoria por loja, alternando a categoria a cada
# dia (a que foi visitada há mais tempo é escolhida primeiro).
# Categorias sem endereço confirmado ficam de fora do rodízio da loja.
CATEGORIAS_PICHAU = {
    "Processador": "https://www.pichau.com.br/hardware/processadores",
    "Placa de Vídeo": "https://www.pichau.com.br/hardware/placa-de-video",
    "Memória RAM": "https://www.pichau.com.br/hardware/memorias",
    "SSD": "https://www.pichau.com.br/hardware/ssd",
}
_TERABYTE = "https://www.terabyteshop.com.br"
CATEGORIAS_TERABYTE = {
    "Processador": f"{_TERABYTE}/hardware/processadores",
    "Placa de Vídeo": f"{_TERABYTE}/hardware/placas-de-video",
    "Memória RAM": f"{_TERABYTE}/hardware/memorias",
    "SSD": f"{_TERABYTE}/hardware/hard-disk/ssd",
    "Placa-mãe": f"{_TERABYTE}/hardware/placas-mae",
    "Fonte": f"{_TERABYTE}/fontes",
}

# --------------------------------------------------------------------------
# Comportamento da coleta
# --------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
)
TIMEOUT_HTTP = 30            # segundos por requisição HTTP
TIMEOUT_PAGINA = 60          # segundos para carregar uma página no navegador
ESPERA_ENTRE_BUSCAS = (6, 12)  # intervalo aleatório entre buscas (segundos)
TENTATIVAS_HTTP = 3

# Termos que, se presentes no título, descartam o anúncio para qualquer
# produto (computadores montados, kits, usados etc.). Na dúvida, é melhor
# perder um anúncio do que gravar o produto errado.
PALAVRAS_PROIBIDAS_GLOBAIS = [
    "pc gamer", "pc home", "pc office", "pc completo", "mini pc",
    "all in one", "computador", "notebook", "laptop", "windows 10",
    "windows 11", "kit", "combo", "usado", "seminovo",
    "recondicionado", "open box", "openbox", "vitrine", "mostruario",
    "cooler para", "suporte para",
]

# --------------------------------------------------------------------------
# Regras do tratamento (Documentação Tratamento e banco)
# --------------------------------------------------------------------------
LIMITE_OUTLIER = 0.30        # variação > 30% da média histórica = outlier
MARGEM_SITUACAO = 0.10       # faixa de ±10% em torno da média

SITUACAO_BOA = "Boa compra"
SITUACAO_MEDIA = "Preço médio"
SITUACAO_EVITAR = "Evitar"
SITUACAO_SEM_HISTORICO = "Sem histórico"

# Correspondências usadas na padronização do nome das lojas.
MAPA_LOJAS = {
    "kabum": "KaBuM!",
    "kabum!": "KaBuM!",
    "pichau": "Pichau",
    "terabyte": "Terabyte",
    "terabyteshop": "Terabyte",
    "terabyte shop": "Terabyte",
    "amazon": "Amazon",
    "amazon.com.br": "Amazon",
    "amazon brasil": "Amazon",
}

# Marcas reconhecidas no nome do produto. A ordem importa: fabricantes de
# placas (ASUS, MSI, Gigabyte...) são verificados antes dos fabricantes de
# chips (AMD, Intel, NVIDIA).
MARCAS = [
    "ASUS", "MSI", "Gigabyte", "ASRock", "Galax", "Zotac", "PNY", "Sapphire",
    "PowerColor", "XFX", "Corsair", "Kingston", "XPG", "Redragon",
    "Samsung", "Crucial", "Western Digital", "Lexar", "Husky", "Rise Mode",
    "Cooler Master", "Seasonic", "Mancer", "AMD", "Intel", "NVIDIA",
]
APELIDOS_MARCA = {
    "WD": "Western Digital",
    "GeForce": "NVIDIA",
    "Radeon": "AMD",
    "Ryzen": "AMD",
}
