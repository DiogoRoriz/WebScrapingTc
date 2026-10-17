"""Extração diária de preços (UC01 / RF01).

Percorre as lojas, associa cada anúncio a um produto do catálogo e grava a
planilha bruta do dia em dados/coletas/coleta_AAAA-MM-DD.xlsx.

Estratégia por loja:
* KaBuM!   - API pública de catálogo (uma busca por produto);
* Amazon   - página de busca no navegador (uma busca por produto);
* Pichau   - uma página de categoria por execução (rodízio diário);
* Terabyte - uma página de categoria por execução (rodízio diário).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
from selenium.common.exceptions import WebDriverException

import config
import planilhas
from correspondencia import escolher_melhor_oferta
from lojas import amazon, kabum, pichau, terabyte
from lojas.base import (LojaBloqueada, PaginaIndisponivel, nova_sessao_http,
                        pausa_educada)
from navegador import Navegador

log = logging.getLogger(__name__)

COLUNAS_COLETA = [
    "data_coleta", "loja", "categoria_produto", "nome_produto",
    "titulo_anuncio", "preco", "preco_prazo", "url_oferta",
]
COLUNAS_LOG = [
    "data_execucao", "loja", "categoria", "status", "ofertas_coletadas",
    "produtos_nao_encontrados", "mensagem",
]


@dataclass
class ResultadoLoja:
    """Resumo da coleta de uma loja, gravado em log_execucoes.xlsx."""

    loja: str
    categoria: str = "todas"
    status: str = "OK"
    registros: list = field(default_factory=list)
    nao_encontrados: list = field(default_factory=list)
    mensagem: str = ""

    def como_linha(self, inicio):
        return [
            inicio, self.loja, self.categoria, self.status,
            len(self.registros), "; ".join(self.nao_encontrados),
            self.mensagem,
        ]


class ScriptExtracao:
    """Coleta os preços dos produtos do catálogo em todas as lojas."""

    def __init__(self, produtos, lojas=None):
        self.produtos = produtos
        self.lojas = [loja.lower() for loja in (
            lojas or ["kabum", "pichau", "terabyte", "amazon"])]

    # ------------------------------------------------------------------
    def extrair_dados_brutos(self):
        """Executa a coleta e devolve a lista de ResultadoLoja.

        Cada loja é gravada na planilha bruta do dia assim que termina, para
        que uma execução interrompida não perca o que já foi coletado.
        """
        resultados = []

        def concluir(resultado):
            resultados.append(resultado)
            try:
                self.salvar_tabela_unica([resultado])
            except Exception:
                log.exception("Falha ao gravar a planilha bruta do dia; os "
                              "registros seguem em memória para a carga")

        if "kabum" in self.lojas:
            concluir(self._coletar_kabum())

        no_navegador = [loja for loja in ("pichau", "terabyte", "amazon")
                        if loja in self.lojas]
        if no_navegador:
            try:
                with Navegador() as nav:
                    if "pichau" in no_navegador:
                        concluir(self._coletar_categoria(
                            nav, "Pichau", pichau, config.CATEGORIAS_PICHAU))
                    if "terabyte" in no_navegador:
                        concluir(self._coletar_categoria(
                            nav, "Terabyte", terabyte,
                            config.CATEGORIAS_TERABYTE))
                    if "amazon" in no_navegador:
                        concluir(self._coletar_amazon(nav))
            except WebDriverException as erro:
                log.error("Não foi possível iniciar o Chrome: %s", erro)
                ja_feitas = {r.loja.lower() for r in resultados}
                for loja in no_navegador:
                    if loja not in ja_feitas:
                        resultados.append(ResultadoLoja(
                            loja=loja.capitalize(), status="ERRO",
                            mensagem=f"Falha ao iniciar o Chrome: {erro}"))
        return resultados

    # ------------------------------------------------------------------
    def _coletar_kabum(self):
        resultado = ResultadoLoja(loja="KaBuM!")
        sessao = nova_sessao_http()
        log.info("KaBuM!: buscando %s produtos pela API", len(self.produtos))
        for produto in self.produtos:
            try:
                anuncios = kabum.buscar(sessao, produto["termo_busca"])
            except LojaBloqueada as erro:
                return self._bloqueio(resultado, erro)
            except Exception as erro:  # erro isolado de um produto
                log.warning("KaBuM!: falha ao buscar %s: %s",
                            produto["nome_produto"], erro)
                resultado.nao_encontrados.append(produto["nome_produto"])
                continue
            self._registrar(resultado, kabum.NOME_LOJA, produto, anuncios)
            pausa_educada((1.5, 3))
        return self._finalizar(resultado)

    def _coletar_amazon(self, nav):
        resultado = ResultadoLoja(loja="Amazon")
        log.info("Amazon: buscando %s produtos", len(self.produtos))
        reaberto = False
        for produto in self.produtos:
            anuncios = []
            for _ in range(2):  # 2ª tentativa só se o Chrome for reaberto
                try:
                    anuncios = amazon.buscar(nav, produto["termo_busca"])
                except LojaBloqueada as erro:
                    return self._bloqueio(resultado, erro)
                except PaginaIndisponivel as erro:
                    log.warning("Amazon: sem resultados para %s (%s)",
                                produto["nome_produto"], erro)
                except WebDriverException as erro:
                    if not navegador_fechado(erro):
                        log.warning("Amazon: falha ao buscar %s: %s",
                                    produto["nome_produto"], erro.msg)
                    elif not reaberto and self._reabrir(nav):
                        reaberto = True
                        continue
                    else:
                        return self._interromper(
                            resultado, "O Chrome foi fechado durante a "
                            "coleta da Amazon e não pôde ser reaberto.")
                except Exception as erro:
                    log.warning("Amazon: falha ao buscar %s: %s",
                                produto["nome_produto"], erro)
                break
            self._registrar(resultado, amazon.NOME_LOJA, produto, anuncios)
            pausa_educada()
        return self._finalizar(resultado)

    @staticmethod
    def _reabrir(nav):
        log.warning("O Chrome foi fechado durante a coleta; reabrindo. "
                    "(Não feche a janela do Chrome enquanto a coleta roda.)")
        try:
            nav.reiniciar()
            return True
        except WebDriverException as erro:
            log.error("Não foi possível reabrir o Chrome: %s", erro)
            return False

    def _interromper(self, resultado, mensagem):
        self._finalizar(resultado)
        resultado.status = "ERRO"
        resultado.mensagem = mensagem
        log.error("%s: %s", resultado.loja, mensagem)
        return resultado

    def _coletar_categoria(self, nav, nome_loja, modulo, categorias):
        """Visita uma única página de categoria (rodízio) da loja."""
        categoria = escolher_categoria_do_dia(nome_loja, categorias,
                                              self.produtos)
        resultado = ResultadoLoja(loja=nome_loja, categoria=categoria or "-")
        if categoria is None:
            resultado.status = "SEM_DADOS"
            resultado.mensagem = "Nenhuma categoria do catálogo configurada."
            return resultado

        url = categorias[categoria]
        log.info("%s: lendo a categoria %s (%s)", nome_loja, categoria, url)
        try:
            anuncios = modulo.coletar_categoria(nav, url)
        except LojaBloqueada as erro:
            return self._bloqueio(resultado, erro)
        except Exception as erro:
            log.error("%s: falha ao ler %s: %s", nome_loja, url, erro)
            resultado.status = "ERRO"
            resultado.mensagem = str(erro)
            return resultado

        log.info("%s: %s anúncios na página (%s disponíveis)", nome_loja,
                 len(anuncios), sum(a.disponivel for a in anuncios))
        for produto in self.produtos:
            if produto["categoria_produto"] == categoria:
                self._registrar(resultado, modulo.NOME_LOJA, produto,
                                anuncios)
        return self._finalizar(resultado)

    # ------------------------------------------------------------------
    @staticmethod
    def _registrar(resultado, nome_loja, produto, anuncios):
        melhor = escolher_melhor_oferta(anuncios, produto,
                                        config.PALAVRAS_PROIBIDAS_GLOBAIS)
        if melhor is None:
            resultado.nao_encontrados.append(produto["nome_produto"])
            log.info("  %-10s %-48s não encontrado/sem estoque",
                     resultado.loja, produto["nome_produto"][:48])
            return
        resultado.registros.append({
            "data_coleta": datetime.now().replace(microsecond=0),
            "loja": nome_loja,
            "categoria_produto": produto["categoria_produto"],
            "nome_produto": produto["nome_produto"],
            "titulo_anuncio": melhor.titulo,
            "preco": round(melhor.preco, 2),
            "preco_prazo": melhor.preco_prazo,
            "url_oferta": melhor.url,
        })
        log.info("  %-10s %-48s R$ %10.2f", resultado.loja,
                 produto["nome_produto"][:48], melhor.preco)

    @staticmethod
    def _bloqueio(resultado, erro):
        resultado.status = "BLOQUEADO"
        resultado.mensagem = str(erro)
        log.error("%s bloqueou o acesso automatizado: %s. A coleta desta "
                  "loja foi interrompida (nenhuma tentativa de contorno).",
                  resultado.loja, erro)
        return resultado

    @staticmethod
    def _finalizar(resultado):
        if not resultado.registros:
            resultado.status = "SEM_DADOS"
            resultado.mensagem = (resultado.mensagem or
                                  "Nenhum produto do catálogo encontrado.")
        elif resultado.nao_encontrados:
            resultado.status = "PARCIAL"
        log.info("%s: %s ofertas coletadas, %s não encontradas",
                 resultado.loja, len(resultado.registros),
                 len(resultado.nao_encontrados))
        return resultado

    # ------------------------------------------------------------------
    @staticmethod
    def registros_como_tabela(resultados):
        """Junta os registros de todas as lojas em um DataFrame."""
        registros = [r for res in resultados for r in res.registros]
        return pd.DataFrame(registros, columns=COLUNAS_COLETA)

    @staticmethod
    def salvar_tabela_unica(resultados, dia=None):
        """Acrescenta os registros à planilha bruta do dia e devolve o
        DataFrame com esses registros."""
        tabela = ScriptExtracao.registros_como_tabela(resultados)
        registros = tabela.to_dict("records")
        arquivo = arquivo_coleta(dia)
        if registros:
            planilhas.anexar_linhas(arquivo, "coleta", registros,
                                    COLUNAS_COLETA)
            log.info("Planilha bruta do dia: %s (%s registros novos)",
                     arquivo.name, len(registros))
        return tabela


def arquivo_coleta(dia=None):
    """Caminho da planilha bruta do dia (UC01)."""
    dia = dia or datetime.now().date()
    return config.PASTA_COLETAS / f"coleta_{dia.isoformat()}.xlsx"


def coleta_para_carga(resultados, dia=None):
    """Registros a carregar: a planilha bruta do dia inteira (inclui o que
    uma execução interrompida mais cedo deixou gravado) somada aos registros
    desta execução. A carga ignora o que já estiver no banco."""
    desta_execucao = ScriptExtracao.registros_como_tabela(resultados)
    try:
        do_dia = planilhas.ler_aba(arquivo_coleta(dia), "coleta",
                                   COLUNAS_COLETA)
    except Exception:
        log.exception("Não foi possível ler a planilha bruta do dia")
        return desta_execucao
    partes = [t for t in (do_dia, desta_execucao) if not t.empty]
    if not partes:
        log.warning("Nenhum dado coletado nesta execução (UC01-E01).")
        return desta_execucao
    combinado = pd.concat(partes, ignore_index=True)
    combinado["data_coleta"] = pd.to_datetime(combinado["data_coleta"])
    return combinado.drop_duplicates(
        subset=["data_coleta", "loja", "nome_produto"], ignore_index=True)


def navegador_fechado(erro):
    """Indica se o erro do Selenium significa que o Chrome não existe mais
    (janela fechada, processo encerrado)."""
    texto = str(erro).lower()
    return any(t in texto for t in (
        "invalid session id", "no such window", "browser has closed",
        "chrome not reachable", "target window already closed",
        "disconnected"))


def escolher_categoria_do_dia(nome_loja, categorias, produtos):
    """Escolhe a categoria visitada há mais tempo nesta loja, entre as que
    têm produtos ativos no catálogo e endereço configurado."""
    usadas = {p["categoria_produto"] for p in produtos}
    candidatas = [c for c in categorias if c in usadas]
    if not candidatas:
        return None

    historico = planilhas.ler_aba(config.ARQUIVO_LOG_EXECUCOES, "execucoes",
                                  COLUNAS_LOG)
    historico = historico[historico["loja"] == nome_loja].copy()
    historico["data_execucao"] = pd.to_datetime(historico["data_execucao"])
    ultima_visita = historico.groupby("categoria")["data_execucao"].max()
    ultima_visita = ultima_visita.to_dict()
    nunca = pd.Timestamp.min
    return min(candidatas, key=lambda c: (ultima_visita.get(c, nunca),
                                          candidatas.index(c)))


def registrar_execucao(resultados, inicio):
    """Grava uma linha por loja em log_execucoes.xlsx (RNF03)."""
    linhas = [r.como_linha(inicio) for r in resultados]
    if linhas:
        planilhas.anexar_linhas(config.ARQUIVO_LOG_EXECUCOES, "execucoes",
                                linhas, COLUNAS_LOG)
