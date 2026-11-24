import socket
from dataclasses import dataclass, field

from constantes import PORTA_PADRAO


@dataclass
class Vizinho:
    endereco: str
    ip: str
    porta: int
    custo: int


@dataclass
class Config:
    endereco: str
    porta: int = PORTA_PADRAO
    vizinhos: list = field(default_factory=list)

    @property
    def rede(self):
        a, b, c, _ = self.endereco.split(".")
        return f"{a}.{b}.{c}.0/24"


def ler(caminho):
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
