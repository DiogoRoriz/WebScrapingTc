"""Dicionário de dados do modelo estrela (produto, loja, oferta).

Fonte única das colunas, tipos, descrições e chaves de cada tabela. É usado
pela carga e pelo tratamento (ordem das colunas) e pela gravação das
planilhas (aba "dicionario" e formatação das abas de dados).
"""

from collections import namedtuple

Coluna = namedtuple("Coluna", "nome tipo descricao chave")

TABELAS = {
    "produto": {
        "titulo": "PRODUTO",
        "cor": "85B7EB",
        "colunas": [
            Coluna("id_produto", "INT64",
                   "Identificação numérica única do produto", "pk"),
            Coluna("nome_produto", "STRING",
                   "Nome comercial do produto", ""),
            Coluna("categoria_produto", "STRING",
                   "Categoria para filtragem (ex: placa de vídeo)", ""),
            Coluna("marca", "STRING",
                   "Fabricante do produto (ex: NVIDIA, AMD, Intel)", ""),
        ],
    },
    "loja": {
        "titulo": "LOJA",
        "cor": "5DCAA5",
        "colunas": [
            Coluna("id_loja", "INT64",
                   "Identificação numérica única da loja", "pk"),
            Coluna("nome_loja", "STRING", "Nome padronizado da loja", ""),
            Coluna("url_base", "STRING",
                   "URL principal da loja, usada como referência", ""),
        ],
    },
    "oferta": {
        "titulo": "OFERTA",
        "cor": "AFA9EC",
        "colunas": [
            Coluna("id_oferta", "INT64",
                   "Identificação única da oferta coletada", "pk"),
            Coluna("id_produto", "INT64", "Referência ao produto", "fk"),
            Coluna("id_loja", "INT64", "Referência à loja", "fk"),
            Coluna("preco", "FLOAT64", "Preço do produto nessa oferta", ""),
            Coluna("preco_medio_historico", "FLOAT64",
                   "Média histórica do produto na coleta (RF04)", ""),
            Coluna("outlier", "BOOL",
                   "TRUE se identificada como anomalia (UC02 / RF06)", ""),
            Coluna("situacao_compra", "STRING",
                   "Boa compra, preço médio ou evitar (UC03 / RF07)", ""),
            Coluna("url_oferta", "STRING",
                   "Link direto para a oferta na loja (RF11)", ""),
            Coluna("data_coleta", "TIMESTAMP",
                   "Momento em que a oferta foi extraída (UC01)", ""),
        ],
    },
}


def colunas(tabela):
    """Nomes das colunas da tabela, na ordem do dicionário."""
    return [c.nome for c in TABELAS[tabela]["colunas"]]
