"""Tratamento analítico das ofertas (UC02/UC03 - RF02, RF04, RF05, RF06).

Lê as tabelas produto, loja e oferta, recalcula em memória as colunas
analíticas e regrava as tabelas (equivalente ao WRITE_TRUNCATE do BigQuery):

* padroniza o nome das lojas ("kabum", " KaBuM! " -> "KaBuM!");
* identifica a marca a partir do nome do produto;
* preco_medio_historico: média dos preços VÁLIDOS do mesmo produto, em
  todas as lojas, coletados nos dias ANTERIORES à oferta (nunca a própria
  oferta, nem outras lojas do mesmo dia, nem coletas futuras);
* outlier: variação |preço - média| / média acima de 30%. Outliers não
  entram no histórico das comparações seguintes e nunca são apagados
  (RNF04);
* situacao_compra: "Boa compra" (mais de 10% abaixo da média), "Preço
  médio" (até 10% acima ou abaixo), "Evitar" (mais de 10% acima) ou
  "Sem histórico" (primeira coleta do produto).
"""

import logging
import re

import pandas as pd

import config
import esquema
import planilhas
from correspondencia import normalizar

log = logging.getLogger(__name__)

COLUNAS_PRODUTO = esquema.colunas("produto")
COLUNAS_LOJA = esquema.colunas("loja")
COLUNAS_OFERTA = esquema.colunas("oferta")


# ----------------------------------------------------------------------
# Padronização
# ----------------------------------------------------------------------
def padronizar_loja(nome):
    """Devolve o nome padronizado da loja."""
    bruto = " ".join(str(nome).split())
    chave = bruto.lower()
    if chave in config.MAPA_LOJAS:
        return config.MAPA_LOJAS[chave]
    chave_sem_simbolos = normalizar(bruto)
    if chave_sem_simbolos in config.MAPA_LOJAS:
        return config.MAPA_LOJAS[chave_sem_simbolos]
    return bruto.title()  # padronização básica para lojas desconhecidas


def identificar_marca(nome_produto):
    """Procura no nome do produto uma das marcas reconhecidas."""
    alvo = normalizar(nome_produto)
    for marca in config.MARCAS:
        if re.search(rf"(?<![a-z0-9]){re.escape(normalizar(marca))}"
                     rf"(?![a-z0-9])", alvo):
            return marca
    for apelido, marca in config.APELIDOS_MARCA.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(normalizar(apelido))}"
                     rf"(?![a-z0-9])", alvo):
            return marca
    return None


# ----------------------------------------------------------------------
# Indicadores
# ----------------------------------------------------------------------
def classificar(preco, media):
    """Situação de compra a partir do preço e da média histórica."""
    if media is None or pd.isna(media) or media <= 0:
        return config.SITUACAO_SEM_HISTORICO
    if preco < media * (1 - config.MARGEM_SITUACAO):
        return config.SITUACAO_BOA
    if preco > media * (1 + config.MARGEM_SITUACAO):
        return config.SITUACAO_EVITAR
    return config.SITUACAO_MEDIA


def calcular_indicadores(oferta):
    """Recalcula preco_medio_historico, outlier e situacao_compra.

    As ofertas de cada produto são percorridas em ordem de data_coleta. As
    ofertas do mesmo dia (a mesma coleta diária, em lojas diferentes) são
    avaliadas juntas, apenas contra os dias anteriores: a ordem em que as
    lojas foram visitadas não interfere no resultado e a primeira coleta
    de cada produto fica como "Sem histórico".
    """
    tabela = oferta.copy()
    tabela["data_coleta"] = pd.to_datetime(tabela["data_coleta"])
    tabela["preco"] = pd.to_numeric(tabela["preco"], errors="coerce")
    tabela["_dia"] = tabela["data_coleta"].dt.normalize()
    tabela = tabela.sort_values(["id_produto", "data_coleta", "id_oferta"])

    medias, outliers, situacoes = {}, {}, {}
    for _, do_produto in tabela.groupby("id_produto", sort=False):
        historico = []
        for _, mesmo_dia in do_produto.groupby("_dia", sort=True):
            media = (sum(historico) / len(historico)) if historico else None
            validos = []
            for indice, preco in mesmo_dia["preco"].items():
                if pd.isna(preco):
                    medias[indice], outliers[indice] = None, False
                    situacoes[indice] = config.SITUACAO_SEM_HISTORICO
                    continue
                if media is None:
                    medias[indice], outliers[indice] = None, False
                    situacoes[indice] = config.SITUACAO_SEM_HISTORICO
                    validos.append(preco)
                    continue
                variacao = abs(preco - media) / media
                e_outlier = variacao > config.LIMITE_OUTLIER
                medias[indice] = round(media, 2)
                outliers[indice] = bool(e_outlier)
                situacoes[indice] = classificar(preco, media)
                if not e_outlier:
                    validos.append(preco)
            historico.extend(validos)

    tabela["preco_medio_historico"] = pd.Series(medias, dtype="float64")
    tabela["outlier"] = pd.Series(outliers, dtype="bool")
    tabela["situacao_compra"] = pd.Series(situacoes, dtype="object")
    return tabela.sort_values("id_oferta")[COLUNAS_OFERTA].reset_index(
        drop=True)


# ----------------------------------------------------------------------
# Execução
# ----------------------------------------------------------------------
def executar_tratamento():
    """Lê as tabelas, aplica o tratamento, regrava e devolve um resumo."""
    arquivo = config.ARQUIVO_BANCO
    produto = planilhas.ler_aba(arquivo, "produto", COLUNAS_PRODUTO)
    loja = planilhas.ler_aba(arquivo, "loja", COLUNAS_LOJA)
    oferta = planilhas.ler_aba(arquivo, "oferta", COLUNAS_OFERTA)
    if oferta.empty:
        log.warning("Tabela oferta vazia: nada a tratar.")
        return {}

    loja, oferta = _padronizar_lojas(loja, oferta)
    produto["marca"] = produto["nome_produto"].map(identificar_marca)
    oferta = calcular_indicadores(oferta)

    planilhas.salvar_abas(arquivo, {
        "produto": produto[COLUNAS_PRODUTO],
        "loja": loja[COLUNAS_LOJA],
        "oferta": oferta,
    })

    resumo = {
        "ofertas": len(oferta),
        "outliers": int(oferta["outlier"].sum()),
        "situacoes": oferta["situacao_compra"].value_counts().to_dict(),
    }
    log.info("Tratamento concluído: %s ofertas, %s outliers",
             resumo["ofertas"], resumo["outliers"])
    for situacao, quantidade in resumo["situacoes"].items():
        log.info("  %-14s %s", situacao, quantidade)
    return resumo


def _padronizar_lojas(loja, oferta):
    """Padroniza os nomes e funde lojas que viraram o mesmo nome."""
    loja = loja.copy()
    oferta = oferta.copy()
    loja["nome_loja"] = loja["nome_loja"].map(padronizar_loja)
    principal = loja.groupby("nome_loja")["id_loja"].transform("min")
    remapear = dict(zip(loja["id_loja"], principal))
    oferta["id_loja"] = oferta["id_loja"].map(lambda i: remapear.get(i, i))
    loja = loja[loja["id_loja"] == principal].copy()
    loja["url_base"] = loja.apply(
        lambda linha: config.LOJAS.get(linha["nome_loja"], linha["url_base"]),
        axis=1)
    return loja, oferta


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    executar_tratamento()
