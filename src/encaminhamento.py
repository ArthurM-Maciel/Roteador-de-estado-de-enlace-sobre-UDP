"""Camada 4 -- encaminhamento, DADOS e ICMP. ESQUELETO -- a implementar.
(criterios 4 e 5, 25% somados)

AO ORIGINAR (DADOS ou ICMP)
  Sem rota para a rede do destino -> avisa o usuario, NAO envia nada.
  Com rota -> envia com TTL inicial (16, ou o valor do comando ping).

AO RECEBER
  Destino na NOSSA rede (10.G.R.0/24) -> entrega local. Nao ha host real:
  10.7.1.1 e 10.7.1.50 sao ambos atendidos pelo roteador 10.7.1.1.
      DADOS      -> exibe origem, destino e mensagem
      ICMP  8    -> responde tipo 0 para a origem, MESMO id.
                    A origem da resposta e quem foi pingado.
      ICMP 0/11/3-> exibe o resultado ao usuario
  Destino em OUTRA rede:
      decrementa TTL; chegou a 0 -> descarta e manda ICMP 11 para a origem
      sem rota                   -> descarta e manda ICMP 3  para a origem
      caso contrario             -> encaminha ao proximo salto com o novo TTL

ARMADILHA 1: o TTL so e decrementado no caminho de ENCAMINHAMENTO. Pacote cujo
destino e a nossa propria rede e entregue mesmo com TTL 1 -- e por isso que o
ping com TTL crescente revela um roteador a cada incremento.

ARMADILHA 2: NUNCA gerar mensagem de erro (11 ou 3) em resposta a outra
mensagem de erro. Antes de criar, cheque se o pacote que a causou ja e dos
ICMP_TIPOS_ERRO. Evita tempestade, e e a regra do ICMP real.

Erros gerados por nos usam: origem = nosso endereco, TTL = 16, id = o id do
pacote que causou.
"""


class Encaminhador:
    def __init__(self, config, tabela, vizinhanca, enviar):
        raise NotImplementedError("TODO")

    def originar_dados(self, destino, mensagem):
        raise NotImplementedError("TODO")

    def originar_ping(self, destino, ttl):
        """Guarda id -> time.monotonic() para calcular o RTT e dar timeout
        em TIMEOUT_PING (2 s)."""
        raise NotImplementedError("TODO")

    def ao_receber(self, pacote, origem_ip, origem_porta):
        raise NotImplementedError("TODO")
