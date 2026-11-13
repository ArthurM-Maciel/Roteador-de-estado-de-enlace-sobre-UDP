"""Camada 2 -- LSDB e inundacao. ESQUELETO -- a implementar.  (criterio 2, 20%)

E a parte mais dificil do trabalho e a de maior peso. Quatro mecanismos:

GERACAO
  LSP proprio quando um vizinho entra/sai, e a cada 30 s de renovacao.
  Primeiro numero de sequencia = int(time.time()) -- Unix time, NAO 1.
  Motivo: um roteador reiniciado precisa gerar numeros maiores que os que os
  outros ja conhecem, senao seus LSPs novos sao descartados como antigos.
  (Atencao: time.time() aqui; time.monotonic() nos PRAZOS. Nao trocar.)

RECEBIMENTO (do vizinho V)
  origem == nos                  -> descarta
  seq <= a que ja temos          -> descarta (copia ou LSP antigo)
  caso contrario                 -> guarda, repassa a todos os ativos EXCETO V,
                                    e recalcula a tabela
  Ao repassar LSP alheio, o numero de sequencia NAO muda: ele pertence a quem
  gerou. O descarte por seq e o que faz a inundacao terminar.

SINCRONIZACAO
  Vizinho que acaba de ficar ativo recebe uma copia de TODA a nossa LSDB.
  Sem isso, quem entra na rede so conheceria os outros na proxima renovacao.

ENVELHECIMENTO
  LSP de outro roteador parado ha 90 s sai da LSDB e a tabela e recalculada.
  Remove da base quem saiu da rede.
"""


class LSDB:
    def __init__(self, config, vizinhanca, enviar, ao_mudar):
        """ao_mudar(): avisa que a base mudou -> recalcular a tabela."""
        raise NotImplementedError("TODO")

    def gerar_proprio(self):
        raise NotImplementedError("TODO")

    def ao_receber_lsp(self, lsp, origem_ip, origem_porta):
        raise NotImplementedError("TODO")

    def sincronizar_com(self, endereco):
        """Envia a LSDB inteira a um vizinho que acabou de ficar ativo."""
        raise NotImplementedError("TODO")

    def envelhecer(self):
        raise NotImplementedError("TODO")

    def grafo(self):
        """-> {origem: {vizinho: custo}} para o Dijkstra.

        Exigir bidirecionalidade: so considerar a aresta se os DOIS LSPs a
        declararem (ver decisao C1 no README).
        """
        raise NotImplementedError("TODO")
