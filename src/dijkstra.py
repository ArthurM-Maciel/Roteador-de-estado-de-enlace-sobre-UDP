import heapq


def calcular(grafo, eu):
    dist = {eu: 0}
    primeiro_salto = {eu: None}
    visitados = set()
    fila = [(0, eu)]

    while fila:
        d, u = heapq.heappop(fila)
        if u in visitados:
            continue
        visitados.add(u)

        for v, custo in grafo.get(u, {}).items():
            if v in visitados:
                continue
            novo = d + custo
            salto = v if u == eu else primeiro_salto[u]
            atual = dist.get(v)

            melhor = atual is None or novo < atual
            empate = atual is not None and novo == atual and salto < primeiro_salto[v]
            if melhor or empate:
                dist[v] = novo
                primeiro_salto[v] = salto
                heapq.heappush(fila, (novo, v))

    return {rede_de(destino): (primeiro_salto[destino], custo)
            for destino, custo in dist.items() if destino != eu}


def rede_de(endereco):
    a, b, c, _ = endereco.split(".")
    return f"{a}.{b}.{c}.0/24"


def pertence(endereco, rede):
    return rede_de(endereco) == rede
