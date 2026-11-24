"""Teste ponta a ponta: 3 roteadores reais (processos + UDP em 127.0.0.1),
em linha A -1- B -2- C. Leva ~5 s por causa do HELLO de 1 s de tick.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROTEADOR = os.path.join(RAIZ, "src", "roteador.py")


def porta_livre():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestTresRoteadores(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        pa, pb, pc = porta_livre(), porta_livre(), porta_livre()
        confs = {
            "a": f"endereco 10.99.1.1\nporta {pa}\nvizinho 10.99.2.1 127.0.0.1 {pb} 1\n",
            "b": (f"endereco 10.99.2.1\nporta {pb}\nvizinho 10.99.1.1 127.0.0.1 {pa} 1\n"
                  f"vizinho 10.99.3.1 127.0.0.1 {pc} 2\n"),
            "c": f"endereco 10.99.3.1\nporta {pc}\nvizinho 10.99.2.1 127.0.0.1 {pb} 2\n",
        }
        self.procs = {}
        for nome, texto in confs.items():
            caminho = os.path.join(self.dir.name, f"teste_{nome}.conf")
            with open(caminho, "w") as f:
                f.write(texto)
            self.procs[nome] = subprocess.Popen(
                [sys.executable, ROTEADOR, caminho], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for p in self.procs.values():
            self.addCleanup(p.kill)

    def tearDown(self):
        log = os.path.join(RAIZ, "logs")
        for nome in "abc":
            arq = os.path.join(log, f"teste_{nome}.log")
            if os.path.exists(arq):
                os.unlink(arq)

    def test_convergencia_ping_ttl_msg_e_entrada_invalida(self):
        time.sleep(4)                                 # HELLO + inundacao
        a = self.procs["a"]
        a.stdin.write("tabela\nmsg foo oi\nping 10.99.3.1\nping 10.99.3.1 1\n"
                      "ping 10.99.9.1\nmsg 10.99.3.7 oi pessoal\n")
        a.stdin.flush()
        time.sleep(1)
        saidas = {n: p.communicate("sair\n", timeout=10)[0] for n, p in self.procs.items()}
        sa = saidas["a"]

        self.assertIn("10.99.3.0/24     10.99.2.1       3", sa)          # A->C via B, custo 3
        self.assertIn("destino invalido: 'foo'", sa)                     # nao derruba
        self.assertIn("resposta de 10.99.3.1: resposta de eco", sa)
        self.assertIn("resposta de 10.99.2.1: tempo excedido", sa)       # TTL 1 morre em B
        self.assertIn("destino inalcancavel: sem rota para 10.99.9.0/24", sa)
        self.assertIn("[DADOS] de 10.99.1.1 para 10.99.3.7: oi pessoal", saidas["c"])
        for nome, p in self.procs.items():
            self.assertEqual(p.returncode, 0, saidas[nome])
            self.assertNotIn("Traceback", saidas[nome])


if __name__ == "__main__":
    unittest.main()
