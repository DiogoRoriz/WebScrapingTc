"""Correspondência entre anúncios das lojas e produtos do catálogo.

Cada loja escreve o mesmo produto de um jeito diferente, por exemplo
"Processador AMD Ryzen 5 5600, 3.5GHz" ou "AMD Ryzen 5 5600 6-Core". Para
comparar preços entre lojas, cada anúncio é associado a um produto do
catálogo por palavras obrigatórias e proibidas.

Regras dos termos:
* a comparação ignora maiúsculas, acentos e pontuação;
* um termo só casa com palavras inteiras: "ryzen 5 5600" NÃO casa com
  "ryzen 5 5600x";
* entre número e unidade o espaço é opcional: "16gb" casa com "16 GB";
* alternativas são separadas por "|": "3200mhz|3200".
"""

import re
import unicodedata
from functools import lru_cache


def normalizar(texto):
    """Converte o texto para minúsculas, sem acentos e sem pontuação."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    # "2x8GB" -> "2 x 8gb", para que kits não pareçam "8gb" isolado. Só
    # quando seguido de unidade, para não quebrar modelos como "7600X3D".
    texto = re.sub(r"(\d)\s*x\s*(\d+\s*(?:gb|tb|mb|g)(?![a-z0-9]))",
                   r"\1 x \2", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


def _regex_termo(termo):
    """Monta a expressão regular de um termo (sem alternativas).

    Entre letras e dígitos o espaço é opcional ("16gb" ~ "16 GB",
    "rtx 3060" ~ "RTX3060"); entre dois números ou duas palavras o espaço é
    obrigatório ("ryzen 5 5600" não casa com "ryzen 55600").
    """
    pedacos = re.findall(r"[0-9]+|[a-z]+", normalizar(termo))
    if not pedacos:
        return None
    regex = re.escape(pedacos[0])
    for anterior, atual in zip(pedacos, pedacos[1:]):
        mesmo_tipo = anterior[-1].isdigit() == atual[0].isdigit()
        regex += (r"\s+" if mesmo_tipo else r"\s*") + re.escape(atual)
    return r"(?<![a-z0-9])" + regex + r"(?![a-z0-9])"


@lru_cache(maxsize=4096)
def _compilar(termo):
    alternativas = [_regex_termo(t) for t in str(termo).split("|")]
    alternativas = [a for a in alternativas if a]
    if not alternativas:
        return None
    return re.compile("|".join(f"(?:{a})" for a in alternativas))


def contem(titulo_normalizado, termo):
    """Indica se o termo (com possíveis alternativas) aparece no título."""
    regex = _compilar(termo)
    return bool(regex and regex.search(titulo_normalizado))


def separar_termos(valor):
    """Converte "a; b; c" em ["a", "b", "c"], ignorando vazios."""
    if valor is None:
        return []
    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        return []
    return [t.strip() for t in texto.split(";") if t.strip()]


def anuncio_corresponde(titulo, obrigatorias, proibidas):
    """Verifica se o título tem todos os termos obrigatórios e nenhum
    termo proibido."""
    alvo = normalizar(titulo)
    if not all(contem(alvo, t) for t in obrigatorias):
        return False
    return not any(contem(alvo, t) for t in proibidas)


def escolher_melhor_oferta(candidatos, produto, proibidas_globais):
    """Entre os anúncios de uma loja, devolve o mais barato que corresponda
    ao produto do catálogo e esteja disponível; ou None."""
    obrigatorias = separar_termos(produto.get("palavras_obrigatorias"))
    proibidas = separar_termos(produto.get("palavras_proibidas"))
    proibidas = proibidas + list(proibidas_globais)
    try:
        preco_minimo = float(produto.get("preco_minimo") or 0)
    except (TypeError, ValueError):
        preco_minimo = 0.0
    if preco_minimo != preco_minimo:  # NaN vindo de célula vazia
        preco_minimo = 0.0

    validos = [
        c for c in candidatos
        if c.disponivel
        and c.preco is not None
        and c.preco > 0
        and c.preco >= preco_minimo
        and anuncio_corresponde(c.titulo, obrigatorias, proibidas)
    ]
    if not validos:
        return None
    return min(validos, key=lambda c: c.preco)
