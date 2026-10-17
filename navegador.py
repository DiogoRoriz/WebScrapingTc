"""Navegador Chrome automatizado (Selenium) para lojas que montam a página
com JavaScript.

O navegador é o Chrome padrão, sem nenhuma técnica de disfarce: ele se
identifica como automatizado. Se a loja responder com desafio anti-bot,
CAPTCHA ou página de bloqueio, o coletor NÃO interage com ela; apenas
registra o bloqueio (RNF03) e passa para a próxima loja.

A janela é aberta fora da área visível da tela para não atrapalhar o uso do
computador durante a coleta agendada.
"""

import logging
import subprocess
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

import config
from correspondencia import normalizar
from lojas.base import LojaBloqueada, PaginaIndisponivel

log = logging.getLogger(__name__)

# Trechos do título (normalizado) que indicam bloqueio ou desafio.
TITULOS_BLOQUEIO = [
    "just a moment", "um momento", "attention required", "access denied",
    "acesso negado", "site em manutencao", "algo deu errado",
    "robot check", "verificacao de seguranca",
]
# Trechos do HTML que indicam CAPTCHA ou desafio. Só são verificados quando
# o conteúdo esperado não aparece, pois páginas normais podem carregar
# scripts de CAPTCHA em formulários.
HTML_BLOQUEIO = [
    "/errors/validatecaptcha", "captcha-delivery", "cf-turnstile",
    "digite os caracteres que voce ve",
]
TITULOS_404 = ["404", "pagina nao encontrada", "page not found"]


class Navegador:
    """Gerencia uma instância do Chrome durante a coleta.

    Uso:
        with Navegador() as nav:
            html = nav.abrir(url, seletor_conteudo="div.produto")
    """

    def __init__(self):
        self._driver = None

    def __enter__(self):
        self._iniciar()
        return self

    def __exit__(self, *_):
        self._encerrar()

    def reiniciar(self):
        """Fecha e abre o Chrome de novo (ex.: a janela foi fechada)."""
        self._encerrar()
        self._iniciar()

    def _iniciar(self):
        opcoes = Options()
        opcoes.add_argument("--window-size=1366,900")
        opcoes.add_argument("--window-position=-2400,-2400")
        opcoes.add_argument("--lang=pt-BR")
        opcoes.add_argument("--disable-notifications")
        opcoes.add_argument("--no-first-run")
        # Sem janela de console do chromedriver na execução agendada.
        servico = Service()
        servico.creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._driver = webdriver.Chrome(options=opcoes, service=servico)
        self._driver.set_page_load_timeout(config.TIMEOUT_PAGINA)

    def _encerrar(self):
        if self._driver is not None:
            try:
                self._driver.quit()
            except WebDriverException:
                pass
            self._driver = None

    def abrir(self, url, seletor_conteudo, espera_max=25, salvar_como=None):
        """Abre a URL e devolve o HTML quando o conteúdo esperado aparecer.

        Levanta LojaBloqueada se a loja exibir desafio/bloqueio e
        PaginaIndisponivel se a página não existir ou vier sem conteúdo.
        Com salvar_como, guarda uma cópia do HTML em logs/ para diagnóstico.
        """
        try:
            self._driver.get(url)
        except TimeoutException:
            log.warning("Tempo de carregamento excedido em %s", url)

        limite = time.monotonic() + espera_max
        while True:
            self._verificar_titulo(url)
            if self._driver.find_elements(By.CSS_SELECTOR, seletor_conteudo):
                self._aguardar_lista_completa(seletor_conteudo)
                html = self._driver.page_source
                if salvar_como:
                    self._salvar_copia(html, salvar_como)
                return html
            self._verificar_html(url)
            if time.monotonic() > limite:
                titulo = normalizar(self._driver.title)
                if any(t in titulo for t in TITULOS_404):
                    raise PaginaIndisponivel(f"Página não encontrada: {url}")
                raise PaginaIndisponivel(
                    f"Conteúdo esperado ({seletor_conteudo}) não apareceu "
                    f"em {url} (título: {self._driver.title!r})")
            time.sleep(1)

    def carregar_mais(self, seletor_botao, seletor_itens, max_cliques=6,
                      pausa=4, salvar_como=None):
        """Clica no botão "ver mais produtos" da própria página até a lista
        parar de crescer, e devolve o HTML final. Se a loja recusar o
        carregamento extra, fica com o que já foi carregado."""
        for _ in range(max_cliques):
            botoes = [b for b in self._driver.find_elements(
                By.CSS_SELECTOR, seletor_botao) if b.is_displayed()]
            if not botoes:
                break
            antes = len(self._driver.find_elements(By.CSS_SELECTOR,
                                                   seletor_itens))
            time.sleep(pausa)
            try:
                self._driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});"
                    "arguments[0].click();", botoes[0])
            except WebDriverException as erro:
                log.info("Botão de carregar mais indisponível: %s", erro)
                break
            limite = time.monotonic() + 15
            while time.monotonic() < limite:
                time.sleep(1)
                if len(self._driver.find_elements(
                        By.CSS_SELECTOR, seletor_itens)) > antes:
                    break
            else:
                break  # nada novo carregou
            self._aguardar_lista_completa(seletor_itens)
        html = self._driver.page_source
        if salvar_como:
            self._salvar_copia(html, salvar_como)
        return html

    @staticmethod
    def _salvar_copia(html, nome):
        try:
            config.PASTA_LOGS.mkdir(parents=True, exist_ok=True)
            destino = config.PASTA_LOGS / f"ultima_pagina_{nome}.html"
            destino.write_text(html, encoding="utf-8")
        except OSError as erro:
            log.debug("Não foi possível salvar a cópia da página: %s", erro)

    def _aguardar_lista_completa(self, seletor, espera_max=20):
        """A lista de produtos é montada aos poucos; espera até a quantidade
        de itens ficar estável por 3 segundos seguidos."""
        anterior, estavel = -1, 0
        limite = time.monotonic() + espera_max
        while estavel < 3 and time.monotonic() < limite:
            time.sleep(1)
            atual = len(self._driver.find_elements(By.CSS_SELECTOR, seletor))
            estavel = estavel + 1 if atual == anterior else 0
            anterior = atual

    def _verificar_titulo(self, url):
        titulo = normalizar(self._driver.title)
        if any(t in titulo for t in TITULOS_BLOQUEIO):
            raise LojaBloqueada(
                f"Página de bloqueio/desafio em {url} "
                f"(título: {self._driver.title!r})")

    def _verificar_html(self, url):
        html = self._driver.page_source.lower()
        if any(t in html for t in HTML_BLOQUEIO):
            raise LojaBloqueada(f"CAPTCHA/desafio detectado em {url}")
