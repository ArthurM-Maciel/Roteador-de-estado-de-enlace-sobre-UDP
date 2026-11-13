"""Interface com o usuario. ESQUELETO -- a implementar.

Comandos do enunciado (<destino> e sempre endereco virtual):
    tabela                  rede, proximo salto, custo
    lsdb                    origem, numero de sequencia, vizinhos e custos
    vizinhos                endereco virtual, IP real e porta dos ATIVOS
    msg <destino> <texto>   envia pacote de dados
    ping <destino> [TTL]    pedido de eco; mostra resposta, quem enviou e RTT,
                            ou timeout apos 2 s
    sair                    (nosso, nao e do enunciado)

Validar na origem a mensagem do msg: sem ':' e sem caractere fora do ASCII.
Avisar o usuario e melhor que gerar um pacote que o enunciado define como
malformado.

input() bloqueia so esta thread -- o resto do roteador segue rodando.
"""


def laco(roteador):
    raise NotImplementedError("TODO")
