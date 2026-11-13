"""Camada 1 -- vizinhanca. ESQUELETO -- a implementar.  (criterio 1, 5%)

Responsabilidades:
  - enviar HELLO a cada 5 s para TODOS os vizinhos configurados (ativos ou nao)
  - marcar vizinho como ativo ao receber o primeiro HELLO dele
  - marcar como inativo apos 20 s de silencio
  - manter o mapa  endereco virtual -> (ip real, porta)

Esse mapa e a peca que costura o trabalho inteiro: a tabela de roteamento fala
em endereco virtual, mas o sendto() precisa de IP real e porta. Quem traduz e o
HELLO que chegou daquele vizinho.

Toda mudanca na lista de ativos (entrada OU saida) gera imediatamente um novo
LSP proprio -- e, na entrada, tambem o envio da LSDB inteira ao novo vizinho.

Use time.monotonic() para os prazos (imune a ajuste de relogio).
"""


class Vizinhanca:
    def __init__(self, config, enviar, ao_mudar):
        """enviar(texto, ip, porta): manda pelo socket unico do roteador.
        ao_mudar(endereco, ativo: bool): avisa a camada de LSDB."""
        raise NotImplementedError("TODO")

    def enviar_hellos(self):
        """Chamada a cada INTERVALO_HELLO."""
        raise NotImplementedError("TODO")

    def ao_receber_hello(self, endereco, ip, porta):
        raise NotImplementedError("TODO")

    def varrer_timeouts(self):
        """Chamada a cada tick. Marca inativo quem passou de TIMEOUT_VIZINHO."""
        raise NotImplementedError("TODO")

    def ativos(self):
        """dict {endereco: custo} -- e exatamente o conteudo do nosso LSP."""
        raise NotImplementedError("TODO")

    def endereco_para_destino(self, endereco):
        """-> (ip, porta) ou None."""
        raise NotImplementedError("TODO")
