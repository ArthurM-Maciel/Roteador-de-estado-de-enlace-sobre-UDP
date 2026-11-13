"""Logs em tempo real (criterio 6 da avaliacao, 5%).

Sai no terminal e em arquivo ao mesmo tempo: o terminal e para a apresentacao,
o arquivo e a evidencia do relatorio.

Categorias fixas, para dar para filtrar com grep na hora de montar o relatorio:
  VIZINHO  entrada e saida de vizinho ativo
  LSP      LSP novo recebido, gerado, repassado, descartado, envelhecido
  ROTA     recalculo da tabela
  FWD      pacote encaminhado (com proximo salto e TTL)
  ICMP     mensagem ICMP gerada
  ERRO     pacote malformado, origem desconhecida, excecao
  INFO     ciclo de vida do roteador
"""

import sys
import threading
import time

_lock = threading.Lock()
_arquivo = None


def abrir(caminho):
    """Abre o arquivo de log. Chamado uma vez, na subida do roteador."""
    global _arquivo
    _arquivo = open(caminho, "a", encoding="utf-8", buffering=1)


def log(categoria, mensagem):
    """Escreve uma linha de log com timestamp de milissegundos.

    Os milissegundos importam: a questao 3 do relatorio mede convergencia.
    """
    agora = time.time()
    carimbo = time.strftime("%H:%M:%S", time.localtime(agora))
    linha = f"{carimbo}.{int(agora % 1 * 1000):03d} [{categoria:<7}] {mensagem}"
    with _lock:
        print(linha, flush=True)
        if _arquivo is not None:
            _arquivo.write(linha + "\n")
