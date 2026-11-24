import time
from dataclasses import dataclass

import pacotes
from constantes import INTERVALO_RENOVACAO_LSP, TIMEOUT_LSP
from log import log


@dataclass
class Entrada:
    lsp: pacotes.LSP
    visto_em: float


class LSDB:
    def __init__(self, config, vizinhanca, enviar, ao_mudar):
        self.cfg = config
        self.vizinhanca = vizinhanca
        self._enviar = enviar
        self._ao_mudar = ao_mudar

        self.base = {}
        self.seq = None
        self.proxima_renovacao = 0.0

    def gerar_proprio(self):
        if self.seq is None:
            self.seq = int(time.time())
        else:
            self.seq += 1

        ativos = self.vizinhanca.ativos()
        lsp = pacotes.LSP(self.cfg.endereco, self.seq, ativos)
        self.base[self.cfg.endereco] = Entrada(lsp, time.monotonic())
        self.proxima_renovacao = time.monotonic() + INTERVALO_RENOVACAO_LSP

        enviados = self._inundar(lsp)
        log("LSP", f"gerado proprio seq {lsp.seq} vizinhos={self._fmt(ativos)} "
                   f"-- enviado a {enviados} vizinho(s)")
        self._ao_mudar()

    def ao_receber_lsp(self, lsp, ip, porta):
        if lsp.origem == self.cfg.endereco:
            log("LSP", f"descartado: LSP de origem propria vindo de {ip}:{porta}")
            return

        atual = self.base.get(lsp.origem)
        if atual is not None and lsp.seq <= atual.lsp.seq:
            log("LSP", f"descartado: copia/antigo de {lsp.origem} seq {lsp.seq} "
                       f"(ja temos {atual.lsp.seq})")
            return

        novidade = atual is None
        self.base[lsp.origem] = Entrada(lsp, time.monotonic())

        enviados = self._inundar(lsp, excluir=(ip, porta))
        log("LSP", f"{'novo' if novidade else 'atualizado'}: {lsp.origem} "
                   f"seq {lsp.seq} vizinhos={self._fmt(lsp.vizinhos)} "
                   f"-- repassado a {enviados} vizinho(s)")
        self._ao_mudar()

    def sincronizar_com(self, endereco):
        destino = self.vizinhanca.endereco_para_destino(endereco)
        if destino is None:
            return
        ip, porta = destino
        for entrada in list(self.base.values()):
            lsp = entrada.lsp
            self._enviar(pacotes.monta_lsp(lsp.origem, lsp.seq, lsp.vizinhos),
                         ip, porta)
        log("LSP", f"sincronizacao: {len(self.base)} LSP(s) enviados a {endereco}")

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

    def grafo(self):
        bruto = {o: e.lsp.vizinhos for o, e in self.base.items()}
        grafo = {o: {} for o in bruto}
        for origem, vizinhos in bruto.items():
            for vizinho, custo in vizinhos.items():
                if vizinho not in bruto or origem not in bruto[vizinho]:
                    continue
                outro = bruto[vizinho][origem]
                if outro != custo:
                    log("LSP", f"custo divergente {origem}<->{vizinho}: "
                               f"{custo} e {outro} -- usando {max(custo, outro)}")
                grafo[origem][vizinho] = max(custo, outro)
        return grafo

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
        return [(e.lsp.origem, e.lsp.seq, self._fmt(e.lsp.vizinhos))
                for e in sorted(self.base.values(), key=lambda x: x.lsp.origem)]
