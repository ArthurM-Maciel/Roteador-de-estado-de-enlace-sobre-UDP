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
import pacotes
from constantes import INTERVALO_HELLO, INTERVALO_TICK, TAMANHO_BUFFER
from log import abrir as abrir_log, log
from lsdb import LSDB
from vizinhos import Vizinhanca


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

        self.vizinhanca = Vizinhanca(self.cfg, self.enviar, self.ao_mudar_vizinho)
        self.lsdb = LSDB(self.cfg, self.vizinhanca, self.enviar, self.ao_mudar_lsdb)
        self.proximo_hello = 0.0        # monotonic; 0 = manda no primeiro tick

        # TODO (etapas 7-9): instanciar o Encaminhador.
        self.tabela = {}

    def ao_mudar_vizinho(self, endereco, ativo):
        """Chamado pela Vizinhanca quando um vizinho entra ou sai.

        O enunciado: toda mudanca na lista de ativos gera IMEDIATAMENTE um novo
        LSP proprio. E, na entrada, o roteador ainda envia ao novo vizinho uma
        copia de toda a sua LSDB -- sem isso, quem acabou de entrar na rede so
        conheceria os outros na proxima renovacao, ate 30 s depois.
        """
        self.lsdb.gerar_proprio()
        if ativo:
            self.lsdb.sincronizar_com(endereco)

    def ao_mudar_lsdb(self):
        """A LSDB mudou -> a tabela e recalculada. Sempre."""
        # TODO (etapa 7): self.tabela = dijkstra.calcular(self.lsdb.grafo(),
        #                                                 self.cfg.endereco)
        pass

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
                texto = pacotes.decodificar(dados)
                pacote = pacotes.parse(texto)
                if pacote is None:
                    log("ERRO", f"malformado de {origem[0]}:{origem[1]}: {texto!r} -- descartado")
                    continue
                with self.lock:
                    self.despachar(pacote, origem)

            except Exception as e:                       # noqa: BLE001
                log("ERRO", f"excecao tratando pacote de {origem}: {e!r}")

    def despachar(self, pacote, origem):
        """Chamado com o lock segurado."""
        ip, porta = origem
        if isinstance(pacote, pacotes.Hello):
            self.vizinhanca.ao_receber_hello(pacote, ip, porta)
        elif isinstance(pacote, pacotes.LSP):
            self.lsdb.ao_receber_lsp(pacote, ip, porta)
        else:
            # TODO (etapas 8 e 9): encaminhador.ao_receber(pacote, ip, porta)
            log("FWD", f"{type(pacote).__name__} de {ip}:{porta} "
                       f"-- encaminhamento nao implementado")

    # ------------------------------------------------------------ temporizador
    def laco_temporizadores(self):
        while self.rodando:
            time.sleep(INTERVALO_TICK)
            try:
                with self.lock:
                    agora = time.monotonic()
                    if agora >= self.proximo_hello:
                        self.vizinhanca.enviar_hellos()
                        self.proximo_hello = agora + INTERVALO_HELLO
                    self.vizinhanca.varrer_timeouts()
                    self.lsdb.envelhecer()
                    if agora >= self.lsdb.proxima_renovacao:
                        self.lsdb.gerar_proprio()       # renovacao de 30 s
                    # TODO (etapa 9): expirar pings pendentes
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
            elif cmd == "vizinhos":
                self.mostrar_vizinhos()
            elif cmd == "lsdb":
                self.mostrar_lsdb()
            elif cmd in ("tabela", "msg", "ping"):
                print(f"[{cmd}] ainda nao implementado")
            else:
                print(ajuda)
        self.parar()

    def mostrar_vizinhos(self):
        with self.lock:
            ativos = [e for e in self.vizinhanca.listar() if e.ativo]
            total = len(self.vizinhanca.listar())
        if not ativos:
            print(f"nenhum vizinho ativo (de {total} configurados)")
            return
        print(f"{'ENDERECO':<12} {'IP REAL':<16} {'PORTA':<7} CUSTO")
        for e in ativos:
            print(f"{e.endereco:<12} {e.ip:<16} {e.porta:<7} {e.custo}")

    def mostrar_lsdb(self):
        with self.lock:
            linhas = self.lsdb.linhas()
        if not linhas:
            print("LSDB vazia")
            return
        print(f"{'ORIGEM':<12} {'SEQ':<12} VIZINHOS")
        for origem, seq, vizinhos in linhas:
            marca = " (eu)" if origem == self.cfg.endereco else ""
            print(f"{origem:<12} {seq:<12} {vizinhos}{marca}")

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

        # LSP inicial: sem vizinho ativo ainda, vai com a lista vazia --
        # LSP:10.7.1.1:<unix time>:  -- que e valido pelo enunciado.
        with self.lock:
            self.lsdb.gerar_proprio()

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
