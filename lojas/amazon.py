"""Coletor da Amazon Brasil pela página de busca (permitida no robots.txt).

A busca da Amazon é montada com JavaScript e recusa requisições HTTP
simples, por isso usa o navegador. Se a Amazon exibir CAPTCHA, o coletor
para e registra o bloqueio.
"""

import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from lojas.base import Anuncio, converter_preco

log = logging.getLogger(__name__)

NOME_LOJA = "amazon"
URL_BUSCA = "https://www.amazon.com.br/s?k={termo}"
URL_PRODUTO = "https://www.amazon.com.br/dp/{asin}"
SELETOR_RESULTADO = 'div[data-component-type="s-search-result"]'


def buscar(navegador, termo):
    """Busca o termo na Amazon e devolve a lista de anúncios."""
    html = navegador.abrir(URL_BUSCA.format(termo=quote_plus(termo)),
                           SELETOR_RESULTADO)
    return extrair_anuncios(html)


def extrair_anuncios(html):
    """Lê os resultados de uma página de busca da Amazon."""
    sopa = BeautifulSoup(html, "html.parser")
    anuncios = []
    for bloco in sopa.select(SELETOR_RESULTADO):
        asin = bloco.get("data-asin")
        cabecalho = bloco.select_one("h2")
        if not asin or cabecalho is None:
            continue
        titulo = cabecalho.get("aria-label") or cabecalho.get_text(
            " ", strip=True)
        titulo = re.sub(r"^An[uú]ncio patrocinado\s*[–-]\s*", "", titulo)

        # O preço atual fica em .a-price; o riscado ("De:") em .a-text-price.
        elemento = bloco.select_one(
            "span.a-price:not(.a-text-price) span.a-offscreen")
        preco = converter_preco(elemento.get_text()) if elemento else None
        anuncios.append(Anuncio(
            titulo=titulo,
            preco=preco,
            url=URL_PRODUTO.format(asin=asin),
            disponivel=preco is not None,
        ))
    return anuncios
