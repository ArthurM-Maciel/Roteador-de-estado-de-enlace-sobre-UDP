"""Camada 4 -- encaminhamento, DADOS e ICMP.  (criterios 4 e 5, 25% somados)

Com a tabela pronta, encaminhar e mecanico. O que nao e mecanico sao tres
regras finas, e e nelas que a banca bate:

ARMADILHA 1 -- o TTL so e decrementado no caminho de ENCAMINHAMENTO.
  Pacote cujo destino e a NOSSA rede e entregue mesmo com TTL 1. E por isso que
  o ping com TTL crescente revela um roteador a cada incremento: o TTL zera no
  roteador seguinte do caminho, nunca em quem deveria responder.

ARMADILHA 2 -- nunca gerar erro (tipo 11 ou 3) em resposta a outra mensagem de
  erro. Evita tempestade: um ICMP 11 que se perde geraria outro ICMP 11, e
  assim por diante. Regra identica a do ICMP real.

ARMADILHA 3 -- na resposta de eco, a origem e QUEM FOI PINGADO, isto e, o
  endereco de DESTINO do pedido -- nao o nosso endereco. Se alguem pingar
  10.7.1.50, a resposta sai de 10.7.1.50, porque o roteador representa toda a
  sua /24.

Mensagens de erro geradas por nos usam: origem = nosso endereco, TTL = 16, e o
id do pacote que as provocou.
"""

import time

import dijkstra
import pacotes
from constantes import (ICMP_DESTINO_INALCANCAVEL, ICMP_PEDIDO_ECO,
                        ICMP_RESPOSTA_ECO, ICMP_TEMPO_EXCEDIDO,
                        ICMP_TIPOS_ERRO, TIMEOUT_PING, TTL_INICIAL)
from log import log

NOME_ICMP = {
    ICMP_RESPOSTA_ECO: "resposta de eco",
    ICMP_DESTINO_INALCANCAVEL: "destino inalcancavel",
    ICMP_PEDIDO_ECO: "pedido de eco",
    ICMP_TEMPO_EXCEDIDO: "tempo excedido",
}


class Encaminhador:
    def __init__(self, config, vizinhanca, enviar, obter_tabela):
        self.cfg = config
        self.vizinhanca = vizinhanca
        self._enviar = enviar
        self._obter_tabela = obter_tabela
        self._proximo_id = 1
        self.pings = {}          # {id: (destino, instante monotonic)}

    # ----------------------------------------------------------- originacao

    def originar_dados(self, destino, mensagem):
        if not pacotes.mensagem_valida(mensagem):
            print("mensagem invalida: nao pode conter ':' nem acento "
                  "(o enunciado define isso como malformado)")
            return
        if self._e_para_mim(destino):
            print(f"[DADOS] de {self.cfg.endereco} para {destino}: {mensagem}")
            return
        ident = self._novo_id()
        texto = pacotes.monta_dados(self.cfg.endereco, destino,
                                    TTL_INICIAL, ident, mensagem)
        self._originar(texto, destino, f"DADOS id {ident}")

    def originar_ping(self, destino, ttl):
        if self._e_para_mim(destino):
            print(f"resposta de {destino}: eco local, rtt 0.0 ms")
            return
        ident = self._novo_id()
        texto = pacotes.monta_icmp(self.cfg.endereco, destino,
                                   ttl, ident, ICMP_PEDIDO_ECO)
        if self._originar(texto, destino, f"ICMP pedido de eco id {ident} ttl {ttl}"):
            self.pings[ident] = (destino, time.monotonic())

    def _originar(self, texto, destino, descricao):
        """Consulta a tabela. Sem rota: avisa o usuario e NAO envia nada --
        e a regra do enunciado para pacote originado aqui."""
        rota = self._rota(destino)
        if rota is None:
            print(f"destino inalcancavel: sem rota para {dijkstra.rede_de(destino)}")
            return False
        salto, _ = rota
        if not self._entregar_ao_salto(texto, salto):
            return False
        log("FWD", f"originado {descricao} para {destino} "
                   f"-- proximo salto {salto}")
        return True

    # ----------------------------------------------------------- recepcao

    def ao_receber(self, pacote, ip, porta):
        if self._e_para_mim(pacote.destino):
            self._entregar_local(pacote)
            return

        # Destino em outra rede: AGORA sim o TTL e decrementado.
        ttl = pacote.ttl - 1
        if ttl <= 0:
            log("FWD", f"descartado: TTL zerou em {type(pacote).__name__} "
                       f"{pacote.origem}->{pacote.destino}")
            self._erro(ICMP_TEMPO_EXCEDIDO, pacote)
            return

        rota = self._rota(pacote.destino)
        if rota is None:
            log("FWD", f"descartado: sem rota para {pacote.destino}")
            self._erro(ICMP_DESTINO_INALCANCAVEL, pacote)
            return

        salto, _ = rota
        pacote.ttl = ttl
        if self._entregar_ao_salto(self._serializar(pacote), salto):
            log("FWD", f"{type(pacote).__name__} {pacote.origem}->{pacote.destino} "
                       f"encaminhado ao proximo salto {salto} com TTL {ttl}")

    def _entregar_local(self, pacote):
        if isinstance(pacote, pacotes.Dados):
            print(f"[DADOS] de {pacote.origem} para {pacote.destino}: {pacote.mensagem}")
            log("FWD", f"DADOS entregue localmente, origem {pacote.origem}")
            return

        if pacote.tipo == ICMP_PEDIDO_ECO:
            # Armadilha 3: a origem da resposta e quem foi pingado.
            texto = pacotes.monta_icmp(pacote.destino, pacote.origem,
                                       TTL_INICIAL, pacote.ident,
                                       ICMP_RESPOSTA_ECO)
            log("ICMP", f"gerada resposta de eco id {pacote.ident} "
                        f"de {pacote.destino} para {pacote.origem}")
            self._originar(texto, pacote.origem, f"ICMP resposta de eco id {pacote.ident}")
            return

        # Tipos 0, 11 e 3: resultado para o usuario.
        pendente = self.pings.pop(pacote.ident, None)
        if pendente is not None:
            rtt = (time.monotonic() - pendente[1]) * 1000
            print(f"resposta de {pacote.origem}: {NOME_ICMP[pacote.tipo]}, "
                  f"id {pacote.ident}, rtt {rtt:.1f} ms")
        else:
            print(f"ICMP de {pacote.origem}: {NOME_ICMP[pacote.tipo]} "
                  f"(id {pacote.ident}, sem pedido pendente)")

    # -------------------------------------------------------------- erros

    def _erro(self, tipo, causador):
        """Armadilha 2: nunca erro em resposta a erro."""
        if isinstance(causador, pacotes.Icmp) and causador.tipo in ICMP_TIPOS_ERRO:
            log("ICMP", f"suprimido: nao se gera {NOME_ICMP[tipo]} em resposta a "
                        f"{NOME_ICMP[causador.tipo]}")
            return
        texto = pacotes.monta_icmp(self.cfg.endereco, causador.origem,
                                   TTL_INICIAL, causador.ident, tipo)
        log("ICMP", f"gerada {NOME_ICMP[tipo]} id {causador.ident} "
                    f"para {causador.origem}")
        rota = self._rota(causador.origem)
        if rota is None:
            log("ICMP", f"sem rota de volta para {causador.origem} -- "
                        f"mensagem de erro descartada")
            return
        self._entregar_ao_salto(texto, rota[0])

    # ------------------------------------------------------------- pings

    def expirar_pings(self):
        agora = time.monotonic()
        for ident in [i for i, (_, t) in self.pings.items()
                      if agora - t > TIMEOUT_PING]:
            destino, _ = self.pings.pop(ident)
            print(f"timeout: sem resposta de {destino} em {TIMEOUT_PING}s "
                  f"(id {ident})")

    # -------------------------------------------------------------- apoio

    def _e_para_mim(self, destino):
        return dijkstra.rede_de(destino) == self.cfg.rede

    def _rota(self, destino):
        return self._obter_tabela().get(dijkstra.rede_de(destino))

    def _entregar_ao_salto(self, texto, salto):
        endpoint = self.vizinhanca.endereco_para_destino(salto)
        if endpoint is None:
            log("ERRO", f"proximo salto {salto} nao esta ativo -- pacote descartado")
            return False
        self._enviar(texto, endpoint[0], endpoint[1])
        return True

    def _novo_id(self):
        ident = self._proximo_id
        self._proximo_id += 1
        return ident

    @staticmethod
    def _serializar(p):
        if isinstance(p, pacotes.Dados):
            return pacotes.monta_dados(p.origem, p.destino, p.ttl, p.ident, p.mensagem)
        return pacotes.monta_icmp(p.origem, p.destino, p.ttl, p.ident, p.tipo)
