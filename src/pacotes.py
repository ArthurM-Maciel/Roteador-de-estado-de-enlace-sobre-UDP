"""Serializacao e parse dos 4 formatos do enunciado.

E o modulo mais curto e o de MAIOR RISCO: e aqui que a interoperabilidade com
o outro grupo quebra.

    HELLO:<endereco>
    LSP:<origem>:<seq>:<vizinho>=<custo>;<vizinho>=<custo>;...
    DADOS:<origem>:<destino>:<TTL>:<id>:<mensagem>
    ICMP:<origem>:<destino>:<TTL>:<id>:<tipo>

CONTRATO DESTE MODULO: parse() NUNCA levanta excecao. Devolver None e a forma
de dizer "pacote malformado, descarta". Quem chama so precisa testar None, e o
roteador nunca cai por causa de um pacote estranho -- que e o que o enunciado
exige e o que a interoperabilidade vai testar.
"""

from dataclasses import dataclass

from constantes import (ICMP_DESTINO_INALCANCAVEL, ICMP_PEDIDO_ECO,
                        ICMP_RESPOSTA_ECO, ICMP_TEMPO_EXCEDIDO)

TIPOS_ICMP_VALIDOS = (ICMP_RESPOSTA_ECO, ICMP_DESTINO_INALCANCAVEL,
                      ICMP_PEDIDO_ECO, ICMP_TEMPO_EXCEDIDO)


# --------------------------------------------------------------- os 4 pacotes

@dataclass
class Hello:
    endereco: str


@dataclass
class LSP:
    origem: str
    seq: int
    vizinhos: dict          # {endereco virtual: custo}; vazio e valido


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


# ------------------------------------------------------------------ validacao

def _endereco_valido(texto):
    """Quatro octetos decimais de 0 a 255. Validamos o formato para nao deixar
    lixo entrar na LSDB, mas sem exigir que seja 10.G.R.1 -- o roteador do
    outro grupo tem outro G, e na interoperabilidade isso tem que passar."""
    partes = texto.split(".")
    if len(partes) != 4:
        return False
    for p in partes:
        # isdigit() ja rejeita vazio, sinal e nao-digito. O texto inteiro ja
        # passou pelo teste de ASCII, entao nao ha digito unicode exotico aqui.
        if not p.isdigit() or int(p) > 255:
            return False
    return True


def _inteiro(texto, minimo=0, maximo=None):
    """-> int ou None. Numero negativo e rejeitado por isdigit(), e nenhum
    campo numerico do protocolo pode ser negativo."""
    if not texto.isdigit():
        return None
    valor = int(texto)
    if valor < minimo or (maximo is not None and valor > maximo):
        return None
    return valor


def mensagem_valida(texto):
    """Regra do enunciado: a mensagem do DADOS nao pode conter ':' nem
    caractere fora do ASCII. Usada tambem pela CLI, para avisar o usuario em
    vez de gerar um pacote que o destino vai descartar."""
    return texto.isascii() and ":" not in texto


# ---------------------------------------------------------------------- parse

def decodificar(dados):
    """bytes -> str, sem nunca levantar excecao.

    errors="replace" troca byte invalido por U+FFFD em vez de estourar
    UnicodeDecodeError. O caractere de substituicao nao e ASCII, entao o teste
    isascii() no parse() derruba o pacote logo em seguida. Sem isto, um acento
    vindo da implementacao do outro grupo mataria a thread de recepcao.
    """
    return dados.decode("ascii", errors="replace")


def parse(texto):
    """str -> Hello | LSP | Dados | Icmp, ou None se malformado."""
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
    return None                                  # tipo desconhecido


def _parse_hello(resto):
    if not _endereco_valido(resto):
        return None
    return Hello(resto)


def _parse_lsp(resto):
    partes = resto.split(":", 2)
    if len(partes) != 3:
        return None
    origem, seq_txt, lista = partes
    if not _endereco_valido(origem):
        return None
    seq = _inteiro(seq_txt)
    if seq is None:
        return None
    vizinhos = _parse_lista_vizinhos(lista)
    if vizinhos is None:
        return None
    return LSP(origem, seq, vizinhos)


def _parse_lista_vizinhos(lista):
    """'10.7.2.1=1;10.7.4.1=3' -> {'10.7.2.1': 1, '10.7.4.1': 3}

    String vazia -> {}. E o LSP de um roteador sem nenhum vizinho ativo, que o
    enunciado exige:  LSP:10.7.1.1:1767712001:
    Em Python, "a:b:".split(":") preserva o campo vazio final -- em Java o
    split descarta, e e ai que os grupos divergem.
    """
    vizinhos = {}
    for par in lista.split(";"):
        if not par:
            continue                    # tolera ';' sobrando no fim
        endereco, sep, custo_txt = par.partition("=")
        if not sep or not _endereco_valido(endereco):
            return None
        custo = _inteiro(custo_txt, minimo=1)      # enunciado: inteiro positivo
        if custo is None:
            return None
        vizinhos[endereco] = custo
    return vizinhos


def _parse_dados(resto):
    # maxsplit=4: a mensagem fica inteira no ultimo campo, mesmo que contenha
    # ':'. Assim o pacote chega completo e nos o rejeitamos explicitamente
    # abaixo, em vez de quebrar na contagem de campos.
    partes = resto.split(":", 4)
    if len(partes) != 5:
        return None
    origem, destino, ttl_txt, id_txt, mensagem = partes
    if not _endereco_valido(origem) or not _endereco_valido(destino):
        return None
    ttl = _inteiro(ttl_txt, maximo=255)
    ident = _inteiro(id_txt)
    if ttl is None or ident is None:
        return None
    if ":" in mensagem:
        return None                     # enunciado: malformado
    return Dados(origem, destino, ttl, ident, mensagem)


def _parse_icmp(resto):
    partes = resto.split(":")
    if len(partes) != 5:
        return None
    origem, destino, ttl_txt, id_txt, tipo_txt = partes
    if not _endereco_valido(origem) or not _endereco_valido(destino):
        return None
    ttl = _inteiro(ttl_txt, maximo=255)
    ident = _inteiro(id_txt)
    tipo = _inteiro(tipo_txt)
    if ttl is None or ident is None or tipo is None:
        return None
    if tipo not in TIPOS_ICMP_VALIDOS:
        return None
    return Icmp(origem, destino, ttl, ident, tipo)


# ------------------------------------------------------------------ montagem

def monta_hello(endereco):
    return f"HELLO:{endereco}"


def monta_lsp(origem, seq, vizinhos):
    """vizinhos: {endereco: custo}. Dict vazio -> lista vazia.

    Ordenado de proposito: saida deterministica faz os logs e as capturas do
    relatorio ficarem comparaveis entre rodadas.
    """
    lista = ";".join(f"{e}={c}" for e, c in sorted(vizinhos.items()))
    return f"LSP:{origem}:{seq}:{lista}"


def monta_dados(origem, destino, ttl, ident, mensagem):
    return f"DADOS:{origem}:{destino}:{ttl}:{ident}:{mensagem}"


def monta_icmp(origem, destino, ttl, ident, tipo):
    return f"ICMP:{origem}:{destino}:{ttl}:{ident}:{tipo}"
