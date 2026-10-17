"""Pipeline diário: extração -> carga -> tratamento.

Execução manual:
    python main.py                       # pipeline completo
    python main.py --lojas kabum amazon  # só algumas lojas
    python main.py --somente-tratamento  # recalcula os indicadores

A execução automática é feita pelo Agendador de Tarefas do Windows
(ver agendar_tarefa.ps1).
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import config
from carga import executar_carga
from catalogo import carregar_catalogo
from extracao import ScriptExtracao, coleta_para_carga, registrar_execucao
from notificacao import notificar
from tratamento import executar_tratamento

log = logging.getLogger("pipeline")

ARQUIVO_TRAVA = config.PASTA_DADOS / ".pipeline.lock"
TRAVA_EXPIRADA = 6 * 60 * 60  # segundos


def configurar_log():
    config.PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    arquivo = config.PASTA_LOGS / f"coleta_{datetime.now():%Y-%m-%d}.log"
    manipuladores = [logging.FileHandler(arquivo, encoding="utf-8")]
    if sys.stdout is not None:  # pythonw.exe não tem console
        manipuladores.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=manipuladores,
    )
    for ruidoso in ("selenium", "urllib3", "WDM"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    return arquivo


def processo_ativo(pid):
    """Indica se o processo com esse número ainda está rodando."""
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        consulta_limitada, ainda_ativo = 0x1000, 259
        alca = kernel32.OpenProcess(consulta_limitada, False, pid)
        if not alca:
            return False
        try:
            codigo = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(alca, ctypes.byref(codigo))
            return bool(ok) and codigo.value == ainda_ativo
        finally:
            kernel32.CloseHandle(alca)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def ler_trava():
    """Devolve (pid, início) da execução que detém a trava, ou None se a
    trava estiver abandonada (processo encerrado ou trava muito antiga)."""
    try:
        pid_texto, inicio = ARQUIVO_TRAVA.read_text().split(";", 1)
        pid = int(pid_texto)
    except (OSError, ValueError):
        pid, inicio = None, ""
    if pid is not None:
        return (pid, inicio) if processo_ativo(pid) else None
    # Trava sem número de processo: só vale enquanto for recente.
    try:
        idade = time.time() - ARQUIVO_TRAVA.stat().st_mtime
    except OSError:
        return None
    return (None, "") if idade < TRAVA_EXPIRADA else None


def adquirir_trava():
    """Impede duas execuções simultâneas (ex.: manual + agendada). Devolve
    None se conseguiu a trava, ou (pid, início) da execução em andamento."""
    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            descritor = os.open(ARQUIVO_TRAVA, os.O_CREAT | os.O_EXCL
                                | os.O_WRONLY)
        except FileExistsError:
            em_andamento = ler_trava()
            if em_andamento is not None:
                return em_andamento
            log.info("Removendo trava abandonada de uma execução "
                     "interrompida.")
            ARQUIVO_TRAVA.unlink(missing_ok=True)
            continue
        with os.fdopen(descritor, "w") as arquivo:
            arquivo.write(f"{os.getpid()};{datetime.now():%d/%m/%Y %H:%M}")
        return None
    return (None, "")


def liberar_trava():
    ARQUIVO_TRAVA.unlink(missing_ok=True)


def executar(lojas=None, somente_tratamento=False):
    inicio = datetime.now().replace(microsecond=0)
    resultados = []
    if not somente_tratamento:
        produtos = carregar_catalogo()
        log.info("Catálogo: %s produtos ativos", len(produtos))
        extracao = ScriptExtracao(produtos, lojas)
        resultados = extracao.extrair_dados_brutos()
        try:
            registrar_execucao(resultados, inicio)
        except Exception:
            log.exception("Falha ao gravar log_execucoes.xlsx")
        executar_carga(coleta_para_carga(resultados))

    resumo = executar_tratamento()
    duracao = datetime.now() - inicio.replace(microsecond=0)
    log.info("Pipeline concluído em %s", str(duracao).split(".")[0])

    if resultados:
        partes = [f"{r.loja}: {len(r.registros)}" + (
            "" if r.status in ("OK", "PARCIAL") else f" ({r.status})")
            for r in resultados]
        notificar("Coleta de preços concluída",
                  " | ".join(partes) +
                  f" | Total no banco: {resumo.get('ofertas', 0)} ofertas")
    return resultados


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lojas", nargs="+",
                        choices=["kabum", "pichau", "terabyte", "amazon"],
                        help="coleta apenas as lojas informadas")
    parser.add_argument("--somente-tratamento", action="store_true",
                        help="não coleta; só recalcula os indicadores")
    args = parser.parse_args()

    os.chdir(Path(__file__).resolve().parent)
    arquivo_log = configurar_log()
    em_andamento = adquirir_trava()
    if em_andamento is not None:
        pid, inicio = em_andamento
        log.warning(
            "Já existe uma coleta em andamento%s (provavelmente a automática,"
            " que roda sozinha quando o computador liga). Aguarde ela "
            "terminar (cerca de 8 minutos) e acompanhe em %s. Não é preciso "
            "rodar de novo: ela coleta as 4 lojas.",
            f" desde {inicio} (processo {pid})" if pid else "", arquivo_log)
        return 1
    try:
        log.info("=" * 70)
        log.info("Início do pipeline (log: %s)", arquivo_log)
        executar(args.lojas, args.somente_tratamento)
        return 0
    except Exception as erro:
        log.exception("Falha no pipeline: %s", erro)
        notificar("Coleta de preços FALHOU",
                  f"{erro}. Veja o log em {arquivo_log}")
        return 2
    finally:
        liberar_trava()


if __name__ == "__main__":
    sys.exit(main())
