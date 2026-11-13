"""Serializacao e parse dos 4 formatos. ESQUELETO -- a implementar.

E o modulo mais curto e o de MAIOR RISCO: e aqui que a interoperabilidade com
o outro grupo quebra. Escrever a quatro maos e validar contra os vetores de
teste compartilhados.

Formatos (texto ASCII, campos separados por ':'):

    HELLO:<endereco>
    LSP:<origem>:<seq>:<vizinho>=<custo>;<vizinho>=<custo>;...
    DADOS:<origem>:<destino>:<TTL>:<id>:<mensagem>
    ICMP:<origem>:<destino>:<TTL>:<id>:<tipo>

Regras do enunciado que moram aqui:
  - LSP sem vizinho ativo vai com a lista vazia:  LSP:10.7.1.1:1767712001:
    Em Python, "a:b:c:".split(":") preserva o campo vazio final -- e o que
    queremos. Ainda assim, VALIDE o numero de campos.
  - A mensagem do DADOS nao pode ter ':' nem caractere fora do ASCII.
  - Pacote malformado (tipo desconhecido, numero errado de campos, valor
    nao-numerico) e DESCARTADO sem derrubar o roteador.

Decodificacao: use errors="replace". O outro grupo pode mandar byte acentuado,
e um UnicodeDecodeError nao tratado mata a thread de recepcao.
"""


def decodificar(dados):
    """bytes -> str, sem nunca levantar excecao."""
    raise NotImplementedError("TODO: dados.decode('ascii', errors='replace')")


def parse(texto):
    """str -> objeto de pacote, ou None se malformado.

    Nunca levanta excecao: devolver None e a forma de dizer 'descarta'.
    """
    raise NotImplementedError("TODO")


def monta_hello(endereco):
    raise NotImplementedError("TODO")


def monta_lsp(origem, seq, vizinhos_com_custo):
    """vizinhos_com_custo: dict {endereco: custo}. Dict vazio -> lista vazia."""
    raise NotImplementedError("TODO")


def monta_dados(origem, destino, ttl, ident, mensagem):
    raise NotImplementedError("TODO")


def monta_icmp(origem, destino, ttl, ident, tipo):
    raise NotImplementedError("TODO")
