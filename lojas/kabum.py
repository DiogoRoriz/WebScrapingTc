"""Coletor da KaBuM! via API pública de catálogo (JSON).

A própria página da KaBuM! consome esta API, então não é preciso abrir o
navegador: uma requisição por produto do catálogo é suficiente.
"""

import logging
import time

from lojas.base import Anuncio, get_com_tentativas

log = logging.getLogger(__name__)

NOME_LOJA = "kabum"
API_BUSCA = (
    "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/search"
)
URL_PRODUTO = "https://www.kabum.com.br/produto/{id}/{slug}"


def buscar(sessao, termo, quantidade=40):
    """Busca o termo na KaBuM! e devolve a lista de anúncios."""
    params = {"query": termo, "page_number": 1, "page_size": quantidade}
    resposta = get_com_tentativas(sessao, API_BUSCA, params=params)
    itens = resposta.json().get("data") or []
    return [a for a in (_converter(item) for item in itens) if a]


def _converter(item):
    atributos = item.get("attributes") or {}
    titulo = atributos.get("title")
    if not titulo:
        return None

    preco_prazo = atributos.get("price") or None
    preco_vista = atributos.get("price_with_discount") or preco_prazo
    # Ofertas relâmpago trazem um preço próprio, normalmente menor; só vale
    # enquanto a oferta estiver no período de vigência.
    oferta = atributos.get("offer") or {}
    preco_oferta = oferta.get("price_with_discount")
    agora = time.time()
    vigente = (oferta.get("starts_at") or 0) <= agora <= (
        oferta.get("ends_at") or float("inf"))
    if preco_oferta and vigente and (not preco_vista
                                     or preco_oferta < preco_vista):
        preco_vista = preco_oferta

    disponivel = bool(atributos.get("available")) and not atributos.get(
        "is_openbox")
    return Anuncio(
        titulo=titulo,
        preco=float(preco_vista) if preco_vista else None,
        preco_prazo=float(preco_prazo) if preco_prazo else None,
        url=URL_PRODUTO.format(id=item.get("id"),
                               slug=atributos.get("product_link", "")),
        disponivel=disponivel,
    )
