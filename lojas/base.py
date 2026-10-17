"""Estruturas e utilitários compartilhados pelos coletores das lojas."""

import logging
import random
import re
import time
from dataclasses import dataclass

import requests

import config

log = logging.getLogger(__name__)


@dataclass
class Anuncio:
    """Um produto como aparece na listagem de uma loja."""

    titulo: str
    preco: float | None          # preço à vista (PIX/boleto)
    url: str
    disponivel: bool = True
    preco_prazo: float | None = None   # preço parcelado, quando houver


class LojaBloqueada(Exception):
    """A loja recusou o acesso (desafio anti-bot, CAPTCHA, página de
    bloqueio). O coletor nunca tenta contornar: registra e segue."""


class PaginaIndisponivel(Exception):
    """A página não existe mais (404) ou veio vazia."""


def converter_preco(texto):
    """Converte "R$ 1.404,90" (ou 1404.9) em float. Devolve None se não
    houver número."""
    if texto is None:
        return None
    if isinstance(texto, (int, float)):
        return float(texto)
    limpo = re.sub(r"[^\d,.]", "", str(texto).replace("\xa0", " "))
    if not limpo:
        return None
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", limpo):
        limpo = limpo.replace(".", "")  # "1.404" = mil quatrocentos e quatro
    try:
        return float(limpo)
    except ValueError:
        return None


def pausa_educada(intervalo=config.ESPERA_ENTRE_BUSCAS):
    """Espera um tempo aleatório entre requisições para não sobrecarregar
    o site da loja."""
    time.sleep(random.uniform(*intervalo))


def nova_sessao_http():
    """Sessão HTTP com cabeçalhos de navegador comuns."""
    sessao = requests.Session()
    sessao.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    })
    return sessao


def get_com_tentativas(sessao, url, **kwargs):
    """GET com novas tentativas para falhas temporárias (rede, 5xx).
    Respostas 403/429 indicam bloqueio e não são repetidas."""
    ultimo_erro = None
    for tentativa in range(1, config.TENTATIVAS_HTTP + 1):
        try:
            resposta = sessao.get(url, timeout=config.TIMEOUT_HTTP, **kwargs)
        except requests.RequestException as erro:
            ultimo_erro = erro
            log.warning("Falha de rede (%s/%s) em %s: %s",
                        tentativa, config.TENTATIVAS_HTTP, url, erro)
        else:
            if resposta.status_code in (403, 429):
                raise LojaBloqueada(
                    f"HTTP {resposta.status_code} ao acessar {url}")
            if resposta.status_code < 500:
                return resposta
            ultimo_erro = f"HTTP {resposta.status_code}"
            log.warning("Erro do servidor (%s/%s) em %s: %s",
                        tentativa, config.TENTATIVAS_HTTP, url, ultimo_erro)
        time.sleep(5 * tentativa)
    raise ConnectionError(f"Não foi possível acessar {url}: {ultimo_erro}")
