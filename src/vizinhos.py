"""Camada 1 -- vizinhanca.  (criterio 1 da avaliacao, 5%)

O arquivo de configuracao diz quem PODERIA ser vizinho. Nao diz quem esta
ligado. Como UDP nao tem conexao, nao existe "cair a conexao": a unica
evidencia de que alguem esta vivo e ele continuar falando.

Tres funcoes do HELLO, segundo o enunciado:
  1. dizer que o vizinho configurado esta de fato em funcionamento (ativo)
  2. detectar a falha pela AUSENCIA de HELLO
  3. informar o endereco virtual, associando-o ao par (IP real, porta)

A funcao 3 e a que costura o trabalho inteiro: a tabela de roteamento fala em
endereco virtual ("mande para 10.7.2.1"), mas o sendto() precisa de IP real e
porta. Quem traduz e o HELLO que chegou daquele vizinho.

TEMPORIZADORES: 20 s = 4 x 5 s. Tolera a perda de ate 3 HELLOs seguidos antes
de declarar queda. Derrubar um vizinho por um unico pacote perdido causaria
oscilacao de rotas (flapping) -- e UDP perde pacote.

CONCORRENCIA: esta classe NAO se sincroniza sozinha. Quem chama (as threads de
recepcao e de temporizadores do Roteador) segura o lock global. Um lock so,
porque a rede e minuscula e corrida e o bug mais caro numa apresentacao.
"""

import time
from dataclasses import dataclass

import pacotes
from constantes import TIMEOUT_VIZINHO
from log import log


@dataclass
class EstadoVizinho:
    endereco: str           # endereco virtual (do config, corrigido pelo HELLO)
    ip: str
    porta: int
    custo: int
    ativo: bool = False
    ultimo_hello: float = 0.0        # time.monotonic()


class Vizinhanca:
    def __init__(self, config, enviar, ao_mudar):
        """enviar(texto, ip, porta) -- manda pelo socket unico do roteador.
        ao_mudar(endereco, ativo)  -- avisa a camada de LSDB. Toda mudanca na
        lista de ativos gera imediatamente um novo LSP proprio."""
        self.cfg = config
        self._enviar = enviar
        self._ao_mudar = ao_mudar

        # Indexado pelo par (ip, porta): e o que o socket entrega no recvfrom
        # e e o que o filtro de origem do enunciado usa.
        self.por_endpoint = {
            (v.ip, v.porta): EstadoVizinho(v.endereco, v.ip, v.porta, v.custo)
            for v in config.vizinhos
        }

    def enviar_hellos(self):
        """A cada 5 s, para TODOS os vizinhos configurados -- inclusive os
        inativos. E assim que um vizinho que voltou e redescoberto."""
        texto = pacotes.monta_hello(self.cfg.endereco)
        for est in self.por_endpoint.values():
            self._enviar(texto, est.ip, est.porta)

    def ao_receber_hello(self, hello, ip, porta):
        est = self.por_endpoint.get((ip, porta))
        if est is None:
            return                       # ja barrado pelo filtro de origem

        # Decisao C3: aceitar e atualizar. O vizinho pode ter sido
        # reconfigurado; recusar deixaria o enlace morto sem explicacao.
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
        """Chamada a cada tick. monotonic() nao e afetado por ajuste do relogio
        da maquina -- usar time.time() aqui daria falso positivo de queda."""
        agora = time.monotonic()
        for est in self.por_endpoint.values():
            if est.ativo and agora - est.ultimo_hello > TIMEOUT_VIZINHO:
                est.ativo = False
                log("VIZINHO", f"{est.endereco} INATIVO -- sem HELLO ha mais de "
                               f"{TIMEOUT_VIZINHO}s")
                self._ao_mudar(est.endereco, False)

    def ativos(self):
        """{endereco: custo} dos vizinhos ativos.

        E exatamente o conteudo do nosso LSP: so vizinho ATIVO entra, nunca o
        que esta apenas configurado.
        """
        return {e.endereco: e.custo
                for e in self.por_endpoint.values() if e.ativo}

    def endereco_para_destino(self, endereco):
        """endereco virtual -> (ip real, porta), ou None.

        A traducao que a camada de encaminhamento usa no proximo salto.
        """
        for est in self.por_endpoint.values():
            if est.ativo and est.endereco == endereco:
                return (est.ip, est.porta)
        return None

    def listar(self):
        return list(self.por_endpoint.values())
