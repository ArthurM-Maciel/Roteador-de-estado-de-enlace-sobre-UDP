"""Camada 3 -- Dijkstra e tabela de roteamento. ESQUELETO -- a implementar.
(criterio 3, 15%)

Unico modulo sem rede: entra um grafo, sai uma tabela. Testavel sozinho, sem
socket, sem thread, sem temporizador.

PROIBIDO usar biblioteca de grafos (networkx, scipy.sparse.csgraph, JGraphT).
PERMITIDO heapq / PriorityQueue -- sao estrutura de dados da biblioteca padrao.

A diferenca para o Dijkstra da aula e o PROXIMO SALTO: a tabela nao precisa do
caminho inteiro, so de para quem entregar agora. Carregue essa informacao junto
durante a relaxacao:

    dist[eu] = 0 ; primeiro_salto[eu] = None
    fila <- (0, eu)
    enquanto a fila nao esvazia:
        (d, u) <- menor da fila
        se u ja visitado: continua          # entrada obsoleta, sem decrease-key
        marca u visitado
        para cada (v, custo) em grafo[u]:
            se dist[u] + custo < dist[v]:
                dist[v] = dist[u] + custo
                primeiro_salto[v] = v se u == eu senao primeiro_salto[u]
                insere (dist[v], v) na fila

Empate: o enunciado aceita qualquer caminho minimo. Desempatar pelo MENOR
endereco virtual, de proposito -- saida deterministica faz a tabela do programa
bater com a conta feita a mao na questao 1 do relatorio.
"""


def calcular(grafo, eu):
    """grafo: {origem: {vizinho: custo}}, eu: nosso endereco virtual.

    -> {rede_destino: (proximo_salto, custo)}
       ex. {"10.7.4.0/24": ("10.7.2.1", 6)}
    """
    raise NotImplementedError("TODO")


def rede_de(endereco):
    """10.7.4.1 -> 10.7.4.0/24"""
    a, b, c, _ = endereco.split(".")
    return f"{a}.{b}.{c}.0/24"
