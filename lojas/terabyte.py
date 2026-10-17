"""Coletor da Terabyte pela página de categoria.

A Terabyte bloqueia navegação automatizada depois da primeira página de
cada visita; por isso cada execução lê apenas uma página de categoria (que
lista todos os produtos da categoria, inclusive esgotados).
"""

import logging
import re

from bs4 import BeautifulSoup

from lojas.base import Anuncio, converter_preco

log = logging.getLogger(__name__)

NOME_LOJA = "terabyte"
SELETOR_PRODUTO = "a.product-item__name"
SELETOR_VER_MAIS = "a.btn-pdmore"


def coletar_categoria(navegador, url):
    """Abre a página de categoria, usa o botão "ver mais produtos" da
    própria página e devolve todos os anúncios carregados."""
    navegador.abrir(url, SELETOR_PRODUTO)
    html = navegador.carregar_mais(SELETOR_VER_MAIS, SELETOR_PRODUTO,
                                   salvar_como=NOME_LOJA)
    return extrair_anuncios(html)


def extrair_anuncios(html):
    """Lê os cards de produto de uma página de categoria da Terabyte."""
    sopa = BeautifulSoup(html, "html.parser")
    anuncios = []
    for card in sopa.select("div.product-item__box"):
        link = card.select_one(SELETOR_PRODUTO)
        if link is None:
            continue
        titulo = link.get("title") or link.get_text(" ", strip=True)

        preco_el = card.select_one(".product-item__new-price span")
        preco = converter_preco(preco_el.get_text()) if preco_el else None

        preco_prazo = None
        juros = card.select_one(".product-item__juros")
        if juros is not None:
            # "12x de R$ 92,16 sem juros" -> 12 * 92,16
            texto = juros.get_text(" ", strip=True)
            parcelas = re.search(r"(\d+)\s*x", texto)
            valor = re.search(r"R\$\s*([\d.,]+)", texto)
            if parcelas and valor:
                preco_prazo = round(
                    int(parcelas.group(1)) * converter_preco(valor.group(1)),
                    2)

        esgotado = card.select_one(".tbt_esgotado") is not None
        anuncios.append(Anuncio(
            titulo=titulo,
            preco=preco,
            preco_prazo=preco_prazo,
            url=link.get("href"),
            disponivel=not esgotado and preco is not None,
        ))
    return anuncios
