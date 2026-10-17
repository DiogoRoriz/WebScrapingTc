"""Carga estrutural no modelo estrela (RF03).

Insere os registros coletados nas dimensões produto e loja e na tabela fato
oferta da planilha banco_dados.xlsx. As colunas analíticas
(preco_medio_historico, outlier, situacao_compra) ficam nulas aqui e são
preenchidas pelo tratamento (padrão ELT).

A carga é idempotente: uma oferta do mesmo produto, na mesma loja e no
mesmo dia não é inserida duas vezes, então o pipeline pode ser executado
de novo após uma falha sem duplicar dados.
"""

import logging

import pandas as pd

import config
import planilhas
from tratamento import (COLUNAS_LOJA, COLUNAS_OFERTA, COLUNAS_PRODUTO,
                        padronizar_loja)

log = logging.getLogger(__name__)


def _proximo_id(tabela, coluna):
    valores = pd.to_numeric(tabela[coluna], errors="coerce").dropna()
    return int(valores.max()) + 1 if not valores.empty else 1


def executar_carga(coleta):
    """Carrega o DataFrame da coleta nas tabelas do banco."""
    if coleta.empty:
        log.info("Carga: nenhum registro novo.")
        return {"produtos": 0, "lojas": 0, "ofertas": 0, "ignoradas": 0}

    arquivo = config.ARQUIVO_BANCO
    produto = planilhas.ler_aba(arquivo, "produto", COLUNAS_PRODUTO)
    loja = planilhas.ler_aba(arquivo, "loja", COLUNAS_LOJA)
    oferta = planilhas.ler_aba(arquivo, "oferta", COLUNAS_OFERTA)

    ids_produto = {str(n).strip().lower(): int(i) for i, n in
                   zip(produto["id_produto"], produto["nome_produto"])}
    ids_loja = {padronizar_loja(n): int(i) for i, n in
                zip(loja["id_loja"], loja["nome_loja"])}
    ja_carregadas = {
        (int(p), int(l), pd.Timestamp(d).date())
        for p, l, d in zip(oferta["id_produto"], oferta["id_loja"],
                           oferta["data_coleta"])
    }

    novos_produtos, novas_lojas, novas_ofertas = [], [], []
    proximo_produto = _proximo_id(produto, "id_produto")
    proxima_loja = _proximo_id(loja, "id_loja")
    proxima_oferta = _proximo_id(oferta, "id_oferta")
    ignoradas = 0

    for registro in coleta.to_dict("records"):
        nome_loja = padronizar_loja(registro["loja"])
        if nome_loja not in ids_loja:
            ids_loja[nome_loja] = proxima_loja
            novas_lojas.append({
                "id_loja": proxima_loja, "nome_loja": nome_loja,
                "url_base": config.LOJAS.get(nome_loja, ""),
            })
            proxima_loja += 1

        chave_produto = registro["nome_produto"].strip().lower()
        if chave_produto not in ids_produto:
            ids_produto[chave_produto] = proximo_produto
            novos_produtos.append({
                "id_produto": proximo_produto,
                "nome_produto": registro["nome_produto"].strip(),
                "categoria_produto": registro["categoria_produto"],
                "marca": None,  # preenchida no tratamento
            })
            proximo_produto += 1

        id_produto = ids_produto[chave_produto]
        id_loja = ids_loja[nome_loja]
        data_coleta = pd.Timestamp(registro["data_coleta"])
        chave_oferta = (id_produto, id_loja, data_coleta.date())
        if chave_oferta in ja_carregadas:
            ignoradas += 1
            continue
        ja_carregadas.add(chave_oferta)
        novas_ofertas.append({
            "id_oferta": proxima_oferta,
            "id_produto": id_produto,
            "id_loja": id_loja,
            "preco": float(registro["preco"]),
            "preco_medio_historico": None,
            "outlier": None,
            "situacao_compra": None,
            "url_oferta": registro["url_oferta"],
            "data_coleta": data_coleta,
        })
        proxima_oferta += 1

    planilhas.salvar_abas(arquivo, {
        "produto": _juntar(produto, novos_produtos, COLUNAS_PRODUTO),
        "loja": _juntar(loja, novas_lojas, COLUNAS_LOJA),
        "oferta": _juntar(oferta, novas_ofertas, COLUNAS_OFERTA),
    })
    resumo = {"produtos": len(novos_produtos), "lojas": len(novas_lojas),
              "ofertas": len(novas_ofertas), "ignoradas": ignoradas}
    log.info("Carga: %(ofertas)s ofertas, %(produtos)s produtos e "
             "%(lojas)s lojas novas; %(ignoradas)s já existiam no dia",
             resumo)
    return resumo


def _juntar(atual, novas, colunas):
    if not novas:
        return atual[colunas]
    novas = pd.DataFrame(novas, columns=colunas)
    if atual.empty:
        return novas
    return pd.concat([atual[colunas], novas], ignore_index=True)
