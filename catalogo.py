"""Catálogo de produtos monitorados.

O catálogo fica em catalogo_produtos.xlsx, para ser editado no Excel. Se o
arquivo não existir, é criado com a lista inicial abaixo.

Colunas:
    ativo                  SIM/NÃO - se o produto entra na coleta
    categoria_produto      Processador, Placa de Vídeo, Memória RAM, SSD,
                           Placa-mãe ou Fonte (usada no rodízio de páginas
                           da Pichau e da Terabyte)
    nome_produto           nome padronizado gravado na tabela produto
    termo_busca            texto pesquisado na KaBuM! e na Amazon
    palavras_obrigatorias  termos que o título do anúncio deve conter,
                           separados por ";" (alternativas com "|")
    palavras_proibidas     termos que descartam o anúncio, separados por ";"
    preco_minimo           anúncios abaixo deste valor são ignorados
                           (evita acessórios com nome parecido)
"""

import logging

import pandas as pd

import config

log = logging.getLogger(__name__)

COLUNAS = [
    "ativo", "categoria_produto", "nome_produto", "termo_busca",
    "palavras_obrigatorias", "palavras_proibidas", "preco_minimo",
]

CATALOGO_INICIAL = [
    # --- Processadores ---------------------------------------------------
    ("Processador", "Processador AMD Ryzen 5 5600", "processador ryzen 5 5600",
     "ryzen 5 5600", "", 300),
    ("Processador", "Processador AMD Ryzen 7 5700X",
     "processador ryzen 7 5700x", "ryzen 7 5700x", "", 400),
    ("Processador", "Processador AMD Ryzen 5 7600", "processador ryzen 5 7600",
     "ryzen 5 7600", "", 500),
    ("Processador", "Processador AMD Ryzen 7 7800X3D",
     "processador ryzen 7 7800x3d", "ryzen 7 7800x3d", "", 1000),
    ("Processador", "Processador Intel Core i5-12400F",
     "processador intel core i5 12400f", "i5 12400f", "", 300),
    ("Processador", "Processador Intel Core i5-14400F",
     "processador intel core i5 14400f", "i5 14400f", "", 500),
    # --- Placas de vídeo -------------------------------------------------
    # A busca da KaBuM! não retorna nada quando o termo começa com
    # "placa de video"; por isso o termo usa só modelo e memória.
    ("Placa de Vídeo", "Placa de Vídeo GeForce RTX 5060 8GB",
     "rtx 5060 8gb", "rtx 5060", "5060 ti; fonte; placa mae", 1200),
    ("Placa de Vídeo", "Placa de Vídeo GeForce RTX 5070 12GB",
     "rtx 5070 12gb", "rtx 5070", "5070 ti; fonte; placa mae", 2500),
    ("Placa de Vídeo", "Placa de Vídeo GeForce RTX 3060 12GB",
     "rtx 3060 12gb", "rtx 3060; 12gb|12g",
     "3060 ti; 8gb; fonte; placa mae", 900),
    ("Placa de Vídeo", "Placa de Vídeo Radeon RX 7600 8GB",
     "rx 7600 8gb", "rx 7600", "7600 xt; fonte; placa mae", 900),
    # --- Memórias --------------------------------------------------------
    ("Memória RAM", "Memória Kingston Fury Beast 8GB DDR4 3200MHz",
     "memoria kingston fury beast 8gb ddr4 3200",
     "fury beast; 8gb; ddr4; 3200mhz|3200",
     "rgb; kit; 16gb; 2 x 4gb; 2 x 8gb; sodimm", 80),
    ("Memória RAM", "Memória Kingston Fury Beast 16GB DDR4 3200MHz",
     "memoria kingston fury beast 16gb ddr4 3200",
     "fury beast; 16gb; ddr4; 3200mhz|3200",
     "rgb; kit; 2 x 8gb; sodimm", 150),
    ("Memória RAM", "Memória Kingston Fury Beast 16GB DDR5 5600MHz",
     "memoria kingston fury beast 16gb ddr5 5600",
     "fury beast; 16gb; ddr5; 5600mhz|5600",
     "rgb; kit; 2 x 8gb; sodimm", 200),
    # --- SSDs ------------------------------------------------------------
    ("SSD", "SSD Kingston NV3 1TB M.2 NVMe", "ssd kingston nv3 1tb",
     "nv3; 1tb|1000g", "2230; externo; 2tb; 500gb", 200),
    ("SSD", "SSD Samsung 990 Pro 1TB M.2 NVMe", "ssd samsung 990 pro 1tb",
     "990 pro; 1tb", "2tb; 4tb", 400),
    ("SSD", "SSD Kingston A400 480GB SATA", "ssd kingston a400 480gb",
     "a400; 480gb", "", 100),
    # --- Placas-mãe ------------------------------------------------------
    ("Placa-mãe", "Placa-mãe ASUS TUF Gaming B550M-Plus",
     "placa mae asus tuf gaming b550m plus", "tuf gaming; b550m plus",
     "wifi|wi fi; kit", 400),
    ("Placa-mãe", "Placa-mãe MSI PRO B650M-P", "placa mae msi pro b650m-p",
     "msi; b650m p", "wifi|wi fi; kit", 500),
    # --- Fontes ----------------------------------------------------------
    ("Fonte", "Fonte Corsair CX650 650W 80 Plus Bronze",
     "fonte corsair cx650", "corsair; cx650", "placa de video", 200),
    ("Fonte", "Fonte MSI MAG A650BN 650W 80 Plus Bronze",
     "fonte msi mag a650bn", "a650bn", "placa de video", 150),
    ("Fonte", "Fonte XPG Core Reactor II VE 750W 80 Plus Gold",
     "xpg core reactor 750w", "core reactor; 750w",
     "placa de video; 650w; 850w", 300),
]


def garantir_catalogo():
    """Cria o catalogo_produtos.xlsx com a lista inicial, se não existir."""
    if config.ARQUIVO_CATALOGO.exists():
        return
    linhas = [("SIM",) + item for item in CATALOGO_INICIAL]
    tabela = pd.DataFrame(linhas, columns=COLUNAS)
    tabela.to_excel(config.ARQUIVO_CATALOGO, index=False,
                    sheet_name="catalogo")
    log.info("Catálogo inicial criado em %s", config.ARQUIVO_CATALOGO)


def carregar_catalogo():
    """Devolve os produtos ativos do catálogo como lista de dicionários."""
    garantir_catalogo()
    tabela = pd.read_excel(config.ARQUIVO_CATALOGO, dtype=str)
    faltando = [c for c in COLUNAS if c not in tabela.columns]
    if faltando:
        raise ValueError(f"Colunas ausentes no catálogo: {faltando}")

    tabela = tabela.fillna("")
    tabela["preco_minimo"] = pd.to_numeric(
        tabela["preco_minimo"].str.replace(",", "."), errors="coerce"
    ).fillna(0.0)
    ativos = tabela["ativo"].str.strip().str.upper().isin(["SIM", "S", "1"])
    tabela = tabela[ativos & (tabela["nome_produto"].str.strip() != "")]
    produtos = tabela.to_dict("records")
    for produto in produtos:
        produto["nome_produto"] = produto["nome_produto"].strip()
        produto["categoria_produto"] = produto["categoria_produto"].strip()
        if not produto["termo_busca"].strip():
            produto["termo_busca"] = produto["nome_produto"]
    return produtos
