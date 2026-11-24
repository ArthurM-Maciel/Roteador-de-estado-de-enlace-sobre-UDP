import time
from dataclasses import dataclass

import pacotes
from constantes import TIMEOUT_VIZINHO
from log import log


@dataclass
class EstadoVizinho:
    endereco: str
    ip: str
    porta: int
    custo: int
    ativo: bool = False
    ultimo_hello: float = 0.0


class Vizinhanca:
    def __init__(self, config, enviar, ao_mudar):
        self.cfg = config
        self._enviar = enviar
        self._ao_mudar = ao_mudar
        self.por_endpoint = {
            (v.ip, v.porta): EstadoVizinho(v.endereco, v.ip, v.porta, v.custo)
            for v in config.vizinhos
        }

    def enviar_hellos(self):
        texto = pacotes.monta_hello(self.cfg.endereco)
        for est in self.por_endpoint.values():
            self._enviar(texto, est.ip, est.porta)

    def ao_receber_hello(self, hello, ip, porta):
        est = self.por_endpoint.get((ip, porta))
        if est is None:
            return

        if hello.endereco != est.endereco:
            log("VIZINHO", f"{ip}:{porta} se identifica como {hello.endereco}, "
                           f"config dizia {est.endereco} -- atualizando")
            est.endereco = hello.endereco

        est.ultimo_hello = time.monotonic()
        if not est.ativo:
            est.ativo = True
            log("VIZINHO", f"{est.endereco} ATIVO em {ip}:{porta}, custo {est.custo}")
            self._ao_mudar(est.endereco, True)

    def varrer_timeouts(self):
        agora = time.monotonic()
        for est in self.por_endpoint.values():
            if est.ativo and agora - est.ultimo_hello > TIMEOUT_VIZINHO:
                est.ativo = False
                log("VIZINHO", f"{est.endereco} INATIVO -- sem HELLO ha mais de "
                               f"{TIMEOUT_VIZINHO}s")
                self._ao_mudar(est.endereco, False)

    def ativos(self):
        return {e.endereco: e.custo
                for e in self.por_endpoint.values() if e.ativo}

    def endereco_para_destino(self, endereco):
        for est in self.por_endpoint.values():
            if est.ativo and est.endereco == endereco:
                return (est.ip, est.porta)
        return None

    def listar(self):
        return list(self.por_endpoint.values())
