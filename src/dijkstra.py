"""Camada 3 -- Dijkstra e tabela de roteamento.  (criterio 3, 15%)

Unico modulo sem rede: entra um grafo, sai uma tabela. Testavel sozinho, sem
socket, sem thread, sem temporizador.

PROIBIDO biblioteca de grafos (networkx, scipy.sparse.csgraph, JGraphT).
PERMITIDO heapq -- e estrutura de dados da biblioteca padrao, nao algoritmo
de roteamento.

A DIFERENCA PARA O DIJKSTRA DA AULA e o PROXIMO SALTO. A tabela nao precisa do
caminho inteiro, so de para quem entregar agora. Entao, junto da distancia,
carregamos qual foi o primeiro vizinho daquele caminho:

    primeiro_salto[v] = v           se estamos relaxando a partir de nos
    primeiro_salto[v] = primeiro_salto[u]   caso contrario (v herda de u)

POR QUE A DISTANCIA E DEFINITIVA AO SAIR DA FILA: qualquer caminho alternativo
teria que passar por um no ainda nao visitado, que esta a distancia maior ou
igual; como todos os custos sao positivos, o resto do caminho so aumenta. A
garantia depende de custos nao-negativos, e o enunciado exige inteiro positivo.

EMPATE: o enunciado aceita qualquer caminho de custo minimo. Desempatamos pelo
MENOR endereco virtual de proposito -- saida deterministica faz a tabela do
programa bater com a conta feita a mao na questao 1 do relatorio.
"""

import heapq


def calcular(grafo, eu):
    """grafo: {origem: {vizinho: custo}} (ja bidirecional, vindo da LSDB)
    eu:     nosso endereco virtual

    -> {rede de destino: (proximo salto, custo)}
       ex. {"10.7.4.0/24": ("10.7.2.1", 6)}

    Roteadores inalcancaveis simplesmente nao aparecem na tabela -- e e a
    ausencia de rota que gera o ICMP tipo 3 la no encaminhamento.
    """
    dist = {eu: 0}
    primeiro_salto = {eu: None}
    visitados = set()
    fila = [(0, eu)]

    while fila:
        d, u = heapq.heappop(fila)
        if u in visitados:
            continue            # entrada obsoleta: nao fazemos decrease-key,
        visitados.add(u)        # reinserimos e descartamos a velha aqui

        for v, custo in grafo.get(u, {}).items():
            if v in visitados:
                continue
            novo = d + custo
            salto = v if u == eu else primeiro_salto[u]
            atual = dist.get(v)

            melhor = atual is None or novo < atual
            # Empate de custo: fica o menor endereco virtual (decisao C7).
            empate = (atual is not None and novo == atual
                      and salto < primeiro_salto[v])
            if melhor or empate:
                dist[v] = novo
                primeiro_salto[v] = salto
                heapq.heappush(fila, (novo, v))

    return {rede_de(destino): (primeiro_salto[destino], custo)
            for destino, custo in dist.items() if destino != eu}


def rede_de(endereco):
    """10.7.4.1 -> 10.7.4.0/24"""
    a, b, c, _ = endereco.split(".")
    return f"{a}.{b}.{c}.0/24"


def pertence(endereco, rede):
    """O endereco esta na rede /24? Usado na entrega local: nao ha host real,
    10.7.1.1 e 10.7.1.50 sao ambos atendidos pelo roteador 10.7.1.1."""
    return rede_de(endereco) == rede
