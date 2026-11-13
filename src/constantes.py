"""Constantes do protocolo.

Todos os prazos estao em segundos. As PROPORCOES importam e caem na banca:
  TIMEOUT_VIZINHO = 4 x INTERVALO_HELLO  -> tolera 3 HELLOs perdidos (UDP perde)
  TIMEOUT_LSP     = 3 x INTERVALO_RENOVACAO_LSP -> mesma logica, um nivel acima
"""

INTERVALO_HELLO = 5
TIMEOUT_VIZINHO = 20
INTERVALO_RENOVACAO_LSP = 30
TIMEOUT_LSP = 90
TIMEOUT_PING = 2

TTL_INICIAL = 16
PORTA_PADRAO = 6000
TAMANHO_BUFFER = 4096
INTERVALO_TICK = 1          # varredura de prazos

# Tipos ICMP (tabela do enunciado)
ICMP_RESPOSTA_ECO = 0
ICMP_DESTINO_INALCANCAVEL = 3
ICMP_PEDIDO_ECO = 8
ICMP_TEMPO_EXCEDIDO = 11

# Nunca se gera mensagem de erro em resposta a outra mensagem de erro.
ICMP_TIPOS_ERRO = (ICMP_DESTINO_INALCANCAVEL, ICMP_TEMPO_EXCEDIDO)
