#!/usr/bin/env python3
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as config_mod
import dijkstra
import pacotes
from constantes import (INTERVALO_HELLO, INTERVALO_TICK, TAMANHO_BUFFER,
                        TTL_INICIAL)
from encaminhamento import Encaminhador
from log import abrir as abrir_log, log
from lsdb import LSDB
from vizinhos import Vizinhanca

AJUDA = ("comandos: tabela | lsdb | vizinhos | "
         "msg <destino> <texto> | ping <destino> [TTL] | sair")


class Roteador:
    def __init__(self, caminho_config):
        self.cfg = config_mod.ler(caminho_config)
        self.lock = threading.RLock()
        self.rodando = True

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", self.cfg.porta))

        self.origens_validas = {(v.ip, v.porta) for v in self.cfg.vizinhos}

        self.vizinhanca = Vizinhanca(self.cfg, self.enviar, self.ao_mudar_vizinho)
        self.lsdb = LSDB(self.cfg, self.vizinhanca, self.enviar, self.ao_mudar_lsdb)
        self.proximo_hello = 0.0
        self.tabela = {}
        self.encaminhador = Encaminhador(self.cfg, self.vizinhanca,
                                         self.enviar, lambda: self.tabela)

    def ao_mudar_vizinho(self, endereco, ativo):
        self.lsdb.gerar_proprio()
        if ativo:
            self.lsdb.sincronizar_com(endereco)

    def ao_mudar_lsdb(self):
        antiga = self.tabela
        self.tabela = dijkstra.calcular(self.lsdb.grafo(), self.cfg.endereco)
        if self.tabela != antiga:
            rotas = ", ".join(f"{r}->{s} ({c})"
                              for r, (s, c) in sorted(self.tabela.items()))
            log("ROTA", f"tabela recalculada: {len(self.tabela)} rota(s) -- "
                        f"{rotas or 'nenhuma'}")

    def enviar(self, texto, ip, porta):
        try:
            self.sock.sendto(texto.encode("ascii", errors="replace"), (ip, porta))
        except OSError as e:
            log("ERRO", f"falha ao enviar para {ip}:{porta}: {e}")

    def laco_recepcao(self):
        while self.rodando:
            try:
                dados, origem = self.sock.recvfrom(TAMANHO_BUFFER)
            except OSError:
                if not self.rodando:
                    return
                continue
            try:
                if origem not in self.origens_validas:
                    log("ERRO", f"pacote de origem desconhecida "
                                f"{origem[0]}:{origem[1]} -- descartado")
                    continue
                texto = pacotes.decodificar(dados)
                pacote = pacotes.parse(texto)
                if pacote is None:
                    log("ERRO", f"malformado de {origem[0]}:{origem[1]}: "
                                f"{texto!r} -- descartado")
                    continue
                with self.lock:
                    self.despachar(pacote, origem)
            except Exception as e:
                log("ERRO", f"excecao tratando pacote de {origem}: {e!r}")

    def despachar(self, pacote, origem):
        ip, porta = origem
        if isinstance(pacote, pacotes.Hello):
            self.vizinhanca.ao_receber_hello(pacote, ip, porta)
        elif isinstance(pacote, pacotes.LSP):
            self.lsdb.ao_receber_lsp(pacote, ip, porta)
        else:
            self.encaminhador.ao_receber(pacote, ip, porta)

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
                        self.lsdb.gerar_proprio()
                    self.encaminhador.expirar_pings()
            except Exception as e:
                log("ERRO", f"excecao nos temporizadores: {e!r}")

    def laco_cli(self):
        print(AJUDA)
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
            elif cmd == "tabela":
                self.mostrar_tabela()
            elif cmd == "msg":
                self.comando_msg(partes)
            elif cmd == "ping":
                self.comando_ping(partes)
            else:
                print(AJUDA)
        self.parar()

    def comando_msg(self, partes):
        if len(partes) < 3:
            print("uso: msg <destino> <texto>")
            return
        if not pacotes.endereco_valido(partes[1]):
            print(f"destino invalido: {partes[1]!r} (use um endereco virtual, ex. 10.7.4.1)")
            return
        with self.lock:
            self.encaminhador.originar_dados(partes[1], partes[2])

    def comando_ping(self, partes):
        if len(partes) < 2:
            print("uso: ping <destino> [TTL]")
            return
        if not pacotes.endereco_valido(partes[1]):
            print(f"destino invalido: {partes[1]!r} (use um endereco virtual, ex. 10.7.4.1)")
            return
        ttl = TTL_INICIAL
        if len(partes) >= 3:
            if not partes[2].isdigit() or not 1 <= int(partes[2]) <= 255:
                print("TTL deve ser um inteiro de 1 a 255")
                return
            ttl = int(partes[2])
        with self.lock:
            self.encaminhador.originar_ping(partes[1], ttl)

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

    def mostrar_tabela(self):
        with self.lock:
            tabela = dict(self.tabela)
        print(f"{'REDE DESTINO':<16} {'PROXIMO SALTO':<15} CUSTO")
        if not tabela:
            print("(vazia -- nenhum roteador alcancavel)")
            return
        for rede, (salto, custo) in sorted(tabela.items()):
            print(f"{rede:<16} {salto:<15} {custo}")

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

    def executar(self):
        log("INFO", f"roteador {self.cfg.endereco} rede {self.cfg.rede} "
                    f"porta UDP {self.cfg.porta}")
        for v in self.cfg.vizinhos:
            log("INFO", f"vizinho configurado {v.endereco} em {v.ip}:{v.porta} custo {v.custo}")

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
    try:
        roteador = Roteador(caminho)
    except (OSError, ValueError) as e:
        print(f"erro na subida: {e}", file=sys.stderr)
        return 1
    roteador.executar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
