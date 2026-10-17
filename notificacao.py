"""Notificação na central de avisos do Windows ao fim de cada execução
(RNF03). Falhas aqui nunca interrompem o pipeline."""

import logging
import os
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

log = logging.getLogger(__name__)

SCRIPT = Path(__file__).resolve().parent / "notificar.ps1"


def notificar(titulo, texto):
    """Exibe um aviso do Windows com o resumo da coleta."""
    if os.name != "nt" or not SCRIPT.exists():
        return
    ambiente = dict(os.environ,
                    AVISO_TITULO=escape(titulo)[:120],
                    AVISO_TEXTO=escape(texto)[:500])
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT)],
            env=ambiente, timeout=30, capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False)
    except (OSError, subprocess.SubprocessError) as erro:
        log.debug("Não foi possível exibir a notificação: %s", erro)
