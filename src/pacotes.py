from dataclasses import dataclass

from constantes import (ICMP_DESTINO_INALCANCAVEL, ICMP_PEDIDO_ECO,
                        ICMP_RESPOSTA_ECO, ICMP_TEMPO_EXCEDIDO)

TIPOS_ICMP_VALIDOS = (ICMP_RESPOSTA_ECO, ICMP_DESTINO_INALCANCAVEL,
                      ICMP_PEDIDO_ECO, ICMP_TEMPO_EXCEDIDO)


@dataclass
class Hello:
    endereco: str


@dataclass
class LSP:
    origem: str
    seq: int
    vizinhos: dict


@dataclass
class Dados:
    origem: str
    destino: str
    ttl: int
    ident: int
    mensagem: str


@dataclass
class Icmp:
    origem: str
    destino: str
    ttl: int
    ident: int
    tipo: int


def endereco_valido(texto):
    partes = texto.split(".")
    if len(partes) != 4:
        return False
    for p in partes:
        if not p.isdigit() or int(p) > 255:
            return False
    return True


def _inteiro(texto, minimo=0, maximo=None):
    if not texto.isdigit():
        return None
    valor = int(texto)
    if valor < minimo or (maximo is not None and valor > maximo):
        return None
    return valor


def mensagem_valida(texto):
    return texto.isascii() and ":" not in texto


def decodificar(dados):
    return dados.decode("ascii", errors="replace")


def parse(texto):
    if not texto.isascii():
        return None
    tipo, _, resto = texto.partition(":")
    if tipo == "HELLO":
        return _parse_hello(resto)
    if tipo == "LSP":
        return _parse_lsp(resto)
    if tipo == "DADOS":
        return _parse_dados(resto)
    if tipo == "ICMP":
        return _parse_icmp(resto)
    return None


def _parse_hello(resto):
    if not endereco_valido(resto):
        return None
    return Hello(resto)


def _parse_lsp(resto):
    partes = resto.split(":", 2)
    if len(partes) != 3:
        return None
    origem, seq_txt, lista = partes
    if not endereco_valido(origem):
        return None
    seq = _inteiro(seq_txt)
    if seq is None:
        return None
    vizinhos = _parse_lista_vizinhos(lista)
    if vizinhos is None:
        return None
    return LSP(origem, seq, vizinhos)


def _parse_lista_vizinhos(lista):
    vizinhos = {}
    for par in lista.split(";"):
        if not par:
            continue
        endereco, sep, custo_txt = par.partition("=")
        if not sep or not endereco_valido(endereco):
            return None
        custo = _inteiro(custo_txt, minimo=1)
        if custo is None:
            return None
        vizinhos[endereco] = custo
    return vizinhos


def _parse_dados(resto):
    partes = resto.split(":", 4)
    if len(partes) != 5:
        return None
    origem, destino, ttl_txt, id_txt, mensagem = partes
    if not endereco_valido(origem) or not endereco_valido(destino):
        return None
    ttl = _inteiro(ttl_txt, maximo=255)
    ident = _inteiro(id_txt)
    if ttl is None or ident is None:
        return None
    if ":" in mensagem:
        return None
    return Dados(origem, destino, ttl, ident, mensagem)


def _parse_icmp(resto):
    partes = resto.split(":")
    if len(partes) != 5:
        return None
    origem, destino, ttl_txt, id_txt, tipo_txt = partes
    if not endereco_valido(origem) or not endereco_valido(destino):
        return None
    ttl = _inteiro(ttl_txt, maximo=255)
    ident = _inteiro(id_txt)
    tipo = _inteiro(tipo_txt)
    if ttl is None or ident is None or tipo is None:
        return None
    if tipo not in TIPOS_ICMP_VALIDOS:
        return None
    return Icmp(origem, destino, ttl, ident, tipo)


def monta_hello(endereco):
    return f"HELLO:{endereco}"


def monta_lsp(origem, seq, vizinhos):
    lista = ";".join(f"{e}={c}" for e, c in sorted(vizinhos.items()))
    return f"LSP:{origem}:{seq}:{lista}"


def monta_dados(origem, destino, ttl, ident, mensagem):
    return f"DADOS:{origem}:{destino}:{ttl}:{ident}:{mensagem}"


def monta_icmp(origem, destino, ttl, ident, tipo):
    return f"ICMP:{origem}:{destino}:{ttl}:{ident}:{tipo}"
