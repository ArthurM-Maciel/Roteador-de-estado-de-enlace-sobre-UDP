"""Camada 2 -- LSDB e inundacao.  (criterio 2 da avaliacao, 20%)

A parte mais dificil do trabalho e a de maior peso. A ideia: cada roteador
anuncia APENAS o que enxerga (seus enlaces ativos), e esse anuncio e inundado
ate todo mundo ter a mesma base. Com a base igual, cada um calcula sozinho.

Quatro mecanismos, e cada um existe por um motivo especifico:

GERACAO
  LSP proprio quando um vizinho entra ou sai, e a cada 30 s de renovacao.
  O primeiro numero de sequencia e int(time.time()) -- Unix time, NAO 1.
  Motivo: um roteador reiniciado precisa gerar numeros MAIORES que os que os
  outros ja guardam. Comecando do zero, seus LSPs novos seriam descartados
  como antigos e ele ficaria invisivel ate envelhecer (90 s).
  (time.time() aqui; time.monotonic() nos PRAZOS. Sao coisas diferentes.)

RECEBIMENTO (vindo do vizinho V)
  origem == nos          -> descarta
  seq <= a que ja temos  -> descarta: e copia que deu a volta, ou LSP antigo
  senao                  -> guarda, repassa a todos os ativos EXCETO V,
                            e manda recalcular a tabela
  O descarte por sequencia e o FREIO DA INUNDACAO: sem ele, cada LSP circularia
  para sempre. Cada roteador repassa um LSP novo exatamente uma vez.
  Ao repassar LSP alheio o numero de sequencia NAO muda -- ele pertence a quem
  gerou, e mexer nele quebraria a deteccao de copia na rede inteira.

SINCRONIZACAO
  Vizinho que acaba de ficar ativo recebe copia de TODA a nossa LSDB. Sem isso,
  quem entra na rede so conheceria os outros na proxima renovacao, ate 30 s
  depois. E o que faz um roteador reiniciado voltar a rotear em segundos.

ENVELHECIMENTO
  LSP de outro roteador parado ha 90 s sai da base e a tabela e recalculada.
  Sem isso, quem saiu da rede ficaria no mapa para sempre e o Dijkstra
  calcularia rotas por um enlace que nao existe mais.
  90 = 3 x 30: dois LSPs de renovacao podem se perder sem consequencia.
"""

import time
from dataclasses import dataclass

import pacotes
from constantes import INTERVALO_RENOVACAO_LSP, TIMEOUT_LSP
from log import log


@dataclass
class Entrada:
    lsp: pacotes.LSP
    visto_em: float          # time.monotonic(), para o envelhecimento


class LSDB:
    def __init__(self, config, vizinhanca, enviar, ao_mudar):
        """ao_mudar() -- avisa que a base mudou: recalcular a tabela."""
        self.cfg = config
        self.vizinhanca = vizinhanca
        self._enviar = enviar
        self._ao_mudar = ao_mudar

        self.base = {}                      # {origem: Entrada}
        self.seq = None                     # nosso numero de sequencia
        self.proxima_renovacao = 0.0        # monotonic

    # ------------------------------------------------------------- geracao

    def gerar_proprio(self):
        """Gera, guarda na propria base e inunda o nosso LSP."""
        if self.seq is None:
            self.seq = int(time.time())     # Unix time: ver docstring do modulo
        else:
            self.seq += 1

        ativos = self.vizinhanca.ativos()   # SO vizinhos ativos entram no LSP
        lsp = pacotes.LSP(self.cfg.endereco, self.seq, ativos)
        self.base[self.cfg.endereco] = Entrada(lsp, time.monotonic())
        self.proxima_renovacao = time.monotonic() + INTERVALO_RENOVACAO_LSP

        enviados = self._inundar(lsp)
        log("LSP", f"gerado proprio seq {lsp.seq} vizinhos={self._fmt(ativos)} "
                   f"-- enviado a {enviados} vizinho(s)")
        self._ao_mudar()

    # ---------------------------------------------------------- recebimento

    def ao_receber_lsp(self, lsp, ip, porta):
        if lsp.origem == self.cfg.endereco:
            # Nosso proprio LSP voltando pela inundacao.
            log("LSP", f"descartado: LSP de origem propria vindo de {ip}:{porta}")
            return

        atual = self.base.get(lsp.origem)
        if atual is not None and lsp.seq <= atual.lsp.seq:
            log("LSP", f"descartado: copia/antigo de {lsp.origem} seq {lsp.seq} "
                       f"(ja temos {atual.lsp.seq})")
            return

        novidade = atual is None
        self.base[lsp.origem] = Entrada(lsp, time.monotonic())

        # Repassa a todos os ativos EXCETO quem nos mandou. A sequencia nao muda.
        enviados = self._inundar(lsp, excluir=(ip, porta))
        log("LSP", f"{'novo' if novidade else 'atualizado'}: {lsp.origem} "
                   f"seq {lsp.seq} vizinhos={self._fmt(lsp.vizinhos)} "
                   f"-- repassado a {enviados} vizinho(s)")
        self._ao_mudar()

    # -------------------------------------------------------- sincronizacao

    def sincronizar_com(self, endereco):
        """Envia a base inteira a um vizinho que acabou de ficar ativo.

        O nosso proprio LSP acabou de ser enviado por gerar_proprio(); ele vai
        de novo aqui e o vizinho descarta a segunda copia pela regra de
        sequencia. Custa um pacote e mantem a regra simples.
        """
        destino = self.vizinhanca.endereco_para_destino(endereco)
        if destino is None:
            return
        ip, porta = destino
        for entrada in list(self.base.values()):
            lsp = entrada.lsp
            self._enviar(pacotes.monta_lsp(lsp.origem, lsp.seq, lsp.vizinhos),
                         ip, porta)
        log("LSP", f"sincronizacao: {len(self.base)} LSP(s) enviados a {endereco}")

    # -------------------------------------------------------- envelhecimento

    def envelhecer(self):
        agora = time.monotonic()
        vencidos = [o for o, e in self.base.items()
                    if o != self.cfg.endereco and agora - e.visto_em > TIMEOUT_LSP]
        for origem in vencidos:
            del self.base[origem]
            log("LSP", f"envelhecido: {origem} removido da LSDB "
                       f"(sem renovacao ha mais de {TIMEOUT_LSP}s)")
        if vencidos:
            self._ao_mudar()

    # ---------------------------------------------------------------- grafo

    def grafo(self):
        """LSDB -> {origem: {vizinho: custo}} para o Dijkstra.

        Decisao C1: exigir BIDIRECIONALIDADE. So entra a aresta que os dois
        LSPs declaram. Durante a convergencia e normal um lado ja ter
        atualizado e o outro nao; usar a aresta nesse intervalo faria rotear
        por um enlace que o outro lado ja abandonou. E o que o OSPF faz.
        """
        bruto = {o: e.lsp.vizinhos for o, e in self.base.items()}
        grafo = {o: {} for o in bruto}
        for origem, vizinhos in bruto.items():
            for vizinho, custo in vizinhos.items():
                if vizinho not in bruto or origem not in bruto[vizinho]:
                    continue                       # ainda unilateral: ignora
                outro = bruto[vizinho][origem]
                if outro != custo:
                    # Decisao C2: os dois lados deviam ter o mesmo custo.
                    log("LSP", f"custo divergente {origem}<->{vizinho}: "
                               f"{custo} e {outro} -- usando {max(custo, outro)}")
                grafo[origem][vizinho] = max(custo, outro)
        return grafo

    # -------------------------------------------------------------- apoio

    def _inundar(self, lsp, excluir=None):
        texto = pacotes.monta_lsp(lsp.origem, lsp.seq, lsp.vizinhos)
        enviados = 0
        for est in self.vizinhanca.listar():
            if not est.ativo or (est.ip, est.porta) == excluir:
                continue
            self._enviar(texto, est.ip, est.porta)
            enviados += 1
        return enviados

    @staticmethod
    def _fmt(vizinhos):
        return ",".join(f"{e}={c}" for e, c in sorted(vizinhos.items())) or "(nenhum)"

    def linhas(self):
        """Para o comando 'lsdb'."""
        return [(e.lsp.origem, e.lsp.seq, self._fmt(e.lsp.vizinhos))
                for e in sorted(self.base.values(), key=lambda x: x.lsp.origem)]
