"""Coletor da Pichau pela página de categoria.

A página da Pichau traz, embutidos no HTML, os dados do catálogo (nome,
preço à vista no PIX, preço a prazo, estoque). Como a Pichau também
bloqueia navegação automatizada depois da primeira página de cada visita,
cada execução lê apenas uma página de categoria.
"""

import json
import logging
import re

from lojas.base import Anuncio

log = logging.getLogger(__name__)

NOME_LOJA = "pichau"
URL_BASE = "https://www.pichau.com.br/"
SELETOR_PRODUTO = 'a[data-cy="list-product"]'

_PRODUTO = re.compile(r'"url_key":"([a-z0-9-]+)","name":"([^"]+)"')
_AVISTA = re.compile(r'"pichau_prices":\{"avista":([0-9.]+)')
_FINAL = re.compile(r'"final_price":([0-9.]+)')
_ESTOQUE = re.compile(r'"stock_status":"([A-Z_]+)"')
_OPENBOX = re.compile(r'"is_openbox":(\d)')


def coletar_categoria(navegador, url):
    """Abre a página de categoria e devolve todos os anúncios dela."""
    html = navegador.abrir(url, SELETOR_PRODUTO, salvar_como=NOME_LOJA)
    return extrair_anuncios(html)


def extrair_anuncios(html):
    """Extrai os produtos dos dados embutidos na página da Pichau."""
    dados = html.replace('\\"', '"')
    encontrados = list(_PRODUTO.finditer(dados))
    anuncios = {}
    for i, achado in enumerate(encontrados):
        fim = (encontrados[i + 1].start() if i + 1 < len(encontrados)
               else achado.end() + 20000)
        trecho = dados[achado.end():fim]
        avista = _AVISTA.search(trecho)
        if avista is None:
            continue  # objeto sem preço (ex.: produto relacionado)
        final = _FINAL.search(trecho)
        estoque = _ESTOQUE.search(trecho)
        openbox = _OPENBOX.search(trecho)

        url_key = achado.group(1)
        if url_key in anuncios:
            continue
        anuncios[url_key] = Anuncio(
            titulo=_decodificar(achado.group(2)),
            preco=float(avista.group(1)),
            preco_prazo=float(final.group(1)) if final else None,
            url=URL_BASE + url_key,
            disponivel=(estoque is None or estoque.group(1) == "IN_STOCK")
            and not (openbox and openbox.group(1) == "1"),
        )
    return list(anuncios.values())


def _decodificar(texto):
    """Converte sequências como \\u00e9 em caracteres normais."""
    try:
        return json.loads(f'"{texto}"')
    except ValueError:
        return texto
