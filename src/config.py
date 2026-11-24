"""Leitura do arquivo de configuracao.

O formato e livre pelo enunciado. Escolhemos texto simples, uma diretiva por
linha, porque vai ser editado as pressas num notebook estranho minutos antes de
apresentar -- sem indentacao significativa, sem aspas, sem virgula faltando.

    # comentarios comecam com #
    endereco 10.7.1.1
    porta 6000
    vizinho <endereco virtual> <ip real> <porta> <custo>
"""

import socket
from dataclasses import dataclass, field

from constantes import PORTA_PADRAO


@dataclass
class Vizinho:
    """Um vizinho CONFIGURADO. Estar aqui nao significa estar ativo --
    quem diz isso e o HELLO."""
    endereco: str       # endereco virtual, ex. 10.7.2.1
    ip: str             # IP real na rede local
    porta: int
    custo: int


@dataclass
class Config:
    endereco: str                           # nosso endereco virtual, 10.G.R.1
    porta: int = PORTA_PADRAO
    vizinhos: list = field(default_factory=list)

    @property
    def rede(self):
        """Nossa rede /24. Todo pacote para ela e entregue a nos."""
        a, b, c, _ = self.endereco.split(".")
        return f"{a}.{b}.{c}.0/24"


def ler(caminho):
    """Le o arquivo e devolve um Config. Erro de formato aborta a subida --
    melhor nao subir do que subir torto."""
    endereco = None
    porta = PORTA_PADRAO
    vizinhos = []

    with open(caminho, encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            linha = linha.split("#", 1)[0].strip()
            if not linha:
                continue
            campos = linha.split()
            chave = campos[0].lower()

            if chave == "endereco" and len(campos) == 2:
                endereco = campos[1]
            elif chave == "porta" and len(campos) == 2:
                porta = int(campos[1])
            elif chave == "vizinho" and len(campos) == 5:
                # Resolve para IP numerico: e o que o recvfrom devolve, e o filtro
                # de origem compara por igualdade ("localhost" != "127.0.0.1").
                # Tambem aborta a subida se o IP ficou "PREENCHER".
                try:
                    ip = socket.gethostbyname(campos[2])
                except OSError:
                    raise ValueError(f"{caminho}:{n}: IP invalido: {campos[2]!r}")
                custo = int(campos[4])
                if custo < 1:
                    raise ValueError(f"{caminho}:{n}: custo deve ser inteiro positivo")
                vizinhos.append(Vizinho(campos[1], ip, int(campos[3]), custo))
            else:
                raise ValueError(f"{caminho}:{n}: linha invalida: {linha!r}")

    if endereco is None:
        raise ValueError(f"{caminho}: falta a diretiva 'endereco'")
    return Config(endereco=endereco, porta=porta, vizinhos=vizinhos)
