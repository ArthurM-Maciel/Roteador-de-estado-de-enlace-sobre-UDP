#!/usr/bin/env python3
"""Ponto de entrada do roteador.

    python3 src/roteador.py config/teste/t1.conf

ESTADO: esqueleto. O que ja funciona:
  - le o arquivo de configuracao
  - sobe o socket UDP unico (envia E recebe pela mesma porta)
  - thread de recepcao, que LOGA todo pacote recebido em bruto
  - thread de temporizadores (tick de 1 s)
  - CLI com os comandos do enunciado

O que ainda nao funciona: todo o protocolo. Os modulos vizinhos/lsdb/
dijkstra/encaminhamento sao stubs com a especificacao escrita dentro.

Util desde ja: rodando isto em dois notebooks e mandando qualquer texto de um
para o outro, da para verificar se o access point deixa os clientes se falarem
-- que e o risco numero 1 do trabalho, e precisa ser testado antes de existir
qualquer linha de protocolo.

ARQUITETURA (ver README):
    thread RECEPCAO  -> recvfrom, filtra origem, despacha por tipo
    thread TIMERS    -> HELLO 5 s | varredura de timeouts | renovacao 30 s
    thread CLI       -> os comandos (esta, a principal)
    Estado compartilhado protegido por UM lock global: a rede e minuscula e
    corrida e o bug mais caro possivel numa apresentacao.
"""

import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as config_mod
from constantes import INTERVALO_TICK, TAMANHO_BUFFER
from log import abrir as abrir_log, log


class Roteador:
    def __init__(self, caminho_config):
        self.cfg = config_mod.ler(caminho_config)
        self.lock = threading.RLock()
        self.rodando = True

        # Um socket so, ligado a porta configurada: assim a porta de origem dos
        # pacotes que saem e a nossa propria, e o vizinho nos reconhece pelo
        # par (IP, porta). Socket efemero para enviar quebra isso.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", self.cfg.porta))

        # Pares (ip, porta) de quem podemos aceitar pacote. Pacote de origem
        # fora desta lista e descartado (regra do enunciado).
        self.origens_validas = {(v.ip, v.porta) for v in self.cfg.vizinhos}

        # TODO: instanciar Vizinhanca, LSDB, Encaminhador e a tabela.
        self.tabela = {}

    # ------------------------------------------------------------------ envio
    def enviar(self, texto, ip, porta):
        self.sock.sendto(texto.encode("ascii", errors="replace"), (ip, porta))

    # -------------------------------------------------------------- recepcao
    def laco_recepcao(self):
        """NUNCA pode morrer: um except em volta do corpo inteiro. Excecao nao
        tratada mataria so esta thread, e o roteador ficaria de pe e mudo."""
        while self.rodando:
            try:
                dados, origem = self.sock.recvfrom(TAMANHO_BUFFER)
            except OSError:
                return
            try:
                if origem not in self.origens_validas:
                    log("ERRO", f"pacote de origem desconhecida {origem[0]}:{origem[1]} -- descartado")
                    continue
                texto = dados.decode("ascii", errors="replace")

                # TODO: pacotes.parse(texto) e despacho por tipo:
                #   HELLO -> vizinhanca.ao_receber_hello
                #   LSP   -> lsdb.ao_receber_lsp
                #   DADOS / ICMP -> encaminhador.ao_receber
                log("INFO", f"recebido de {origem[0]}:{origem[1]}: {texto!r} (tratamento nao implementado)")

            except Exception as e:                       # noqa: BLE001
                log("ERRO", f"excecao tratando pacote de {origem}: {e!r}")

    # ------------------------------------------------------------ temporizador
    def laco_temporizadores(self):
        while self.rodando:
            time.sleep(INTERVALO_TICK)
            try:
                with self.lock:
                    pass
                    # TODO: a cada INTERVALO_HELLO        -> vizinhanca.enviar_hellos()
                    # TODO: a cada tick                   -> vizinhanca.varrer_timeouts()
                    # TODO: a cada tick                   -> lsdb.envelhecer()
                    # TODO: a cada INTERVALO_RENOVACAO_LSP-> lsdb.gerar_proprio()
                    # TODO: a cada tick                   -> expirar pings pendentes
            except Exception as e:                       # noqa: BLE001
                log("ERRO", f"excecao nos temporizadores: {e!r}")

    # --------------------------------------------------------------------- cli
    def laco_cli(self):
        """Provisorio -- migrar para cli.py quando os modulos existirem."""
        ajuda = ("comandos: tabela | lsdb | vizinhos | "
                 "msg <destino> <texto> | ping <destino> [TTL] | sair")
        print(ajuda)
        while self.rodando:
            try:
                linha = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not linha:
                continue
            partes = linha.split(None, 2)
            cmd = partes[0].lower()

            if cmd == "sair":
                break
            elif cmd in ("tabela", "lsdb", "vizinhos", "msg", "ping"):
                print(f"[{cmd}] ainda nao implementado")
            else:
                print(ajuda)
        self.parar()

    def parar(self):
        self.rodando = False
        try:
            self.sock.close()
        except OSError:
            pass

    # -------------------------------------------------------------------- run
    def executar(self):
        log("INFO", f"roteador {self.cfg.endereco} rede {self.cfg.rede} "
                    f"porta UDP {self.cfg.porta}")
        for v in self.cfg.vizinhos:
            log("INFO", f"vizinho configurado {v.endereco} em {v.ip}:{v.porta} custo {v.custo}")

        for alvo in (self.laco_recepcao, self.laco_temporizadores):
            threading.Thread(target=alvo, daemon=True).start()
        self.laco_cli()
        log("INFO", "encerrado")


def main():
    if len(sys.argv) != 2:
        print(f"uso: {sys.argv[0]} <arquivo de configuracao>", file=sys.stderr)
        return 1
    caminho = sys.argv[1]
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(os.path.join(raiz, "logs"), exist_ok=True)
    nome = os.path.splitext(os.path.basename(caminho))[0]
    abrir_log(os.path.join(raiz, "logs", f"{nome}.log"))
    Roteador(caminho).executar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
