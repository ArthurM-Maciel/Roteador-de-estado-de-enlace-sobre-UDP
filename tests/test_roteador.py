"""Testes de unidade do roteador. So biblioteca padrao, sem socket.

    python3 -m unittest discover -s tests -b      (na raiz do projeto)

-b esconde os logs dos testes que passam.
"""

import io
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import config as config_mod  # noqa: E402
import dijkstra  # noqa: E402
import pacotes  # noqa: E402
from constantes import TIMEOUT_LSP, TIMEOUT_PING, TIMEOUT_VIZINHO  # noqa: E402
from encaminhamento import Encaminhador  # noqa: E402
from lsdb import LSDB  # noqa: E402
from vizinhos import Vizinhanca  # noqa: E402


def cfg(endereco="10.7.1.1", vizinhos=()):
    return config_mod.Config(endereco=endereco, porta=6001,
                             vizinhos=[config_mod.Vizinho(*v) for v in vizinhos])


class Rede:
    """Captura tudo que seria mandado pelo socket."""
    def __init__(self):
        self.enviados = []

    def __call__(self, texto, ip, porta):
        self.enviados.append((texto, ip, porta))

    def textos(self):
        return [t for t, _, _ in self.enviados]


# ============================================================== pacotes

class TestParse(unittest.TestCase):
    def test_hello(self):
        self.assertEqual(pacotes.parse("HELLO:10.3.1.1"), pacotes.Hello("10.3.1.1"))
        for ruim in ("HELLO:10.3.1", "HELLO:256.1.1.1", "HELLO:", "HELLO:10.3.1.1:x",
                     "HELLO:10.3.1.-1", "HELLO:10.3..1"):
            self.assertIsNone(pacotes.parse(ruim), ruim)

    def test_lsp_exemplo_do_enunciado(self):
        p = pacotes.parse("LSP:10.3.1.1:1767712000:10.3.2.1=1;10.3.4.1=3")
        self.assertEqual(p, pacotes.LSP("10.3.1.1", 1767712000,
                                        {"10.3.2.1": 1, "10.3.4.1": 3}))

    def test_lsp_lista_vazia_e_ponto_e_virgula_sobrando(self):
        self.assertEqual(pacotes.parse("LSP:10.3.1.1:5:"), pacotes.LSP("10.3.1.1", 5, {}))
        self.assertEqual(pacotes.parse("LSP:10.3.1.1:5:10.3.2.1=2;").vizinhos,
                         {"10.3.2.1": 2})
        self.assertEqual(pacotes.parse("LSP:10.3.1.1:5:10.3.2.1=2;;10.3.3.1=1").vizinhos,
                         {"10.3.2.1": 2, "10.3.3.1": 1})

    def test_lsp_malformado(self):
        for ruim in ("LSP:10.3.1.1:5",               # campos a menos
                     "LSP:10.3.1:5:",                 # origem invalida
                     "LSP:10.3.1.1:x:",               # seq nao numerica
                     "LSP:10.3.1.1:-5:",              # seq negativa
                     "LSP:10.3.1.1:5:10.3.2.1=0",     # custo nao positivo
                     "LSP:10.3.1.1:5:10.3.2.1",       # sem '='
                     "LSP:10.3.1.1:5:10.3.2=1",       # vizinho invalido
                     "LSP:10.3.1.1:5:10.3.2.1=a",     # custo nao numerico
                     "LSP:10.3.1.1:5:10.3.2.1=1:x"):  # campo a mais
            self.assertIsNone(pacotes.parse(ruim), ruim)

    def test_dados(self):
        self.assertEqual(pacotes.parse("DADOS:10.3.1.1:10.3.4.1:16:0:Oi pessoal!"),
                         pacotes.Dados("10.3.1.1", "10.3.4.1", 16, 0, "Oi pessoal!"))
        self.assertEqual(pacotes.parse("DADOS:10.3.1.1:10.3.4.1:255:7:").ttl, 255)

    def test_dados_malformado(self):
        for ruim in ("DADOS:10.3.1.1:10.3.4.1:16:0:a:b",     # ':' na mensagem
                     "DADOS:10.3.1.1:10.3.4.1:16:0:olá",  # nao ASCII
                     "DADOS:10.3.1.1:10.3.4.1:256:0:a",      # TTL fora da faixa
                     "DADOS:10.3.1.1:10.3.4.1:x:0:a",
                     "DADOS:10.3.1.1:10.3.4.1:16:x:a",
                     "DADOS:10.3.1:10.3.4.1:16:0:a",
                     "DADOS:10.3.1.1:10.3.4:16:0:a",
                     "DADOS:10.3.1.1:10.3.4.1:16:0"):
            self.assertIsNone(pacotes.parse(ruim), ruim)

    def test_icmp(self):
        self.assertEqual(pacotes.parse("ICMP:10.3.1.1:10.3.4.1:16:42:8"),
                         pacotes.Icmp("10.3.1.1", "10.3.4.1", 16, 42, 8))
        for tipo in (0, 3, 8, 11):
            self.assertEqual(pacotes.parse(f"ICMP:1.1.1.1:2.2.2.2:1:1:{tipo}").tipo, tipo)

    def test_icmp_malformado(self):
        for ruim in ("ICMP:10.3.1.1:10.3.4.1:16:42:5",       # tipo desconhecido
                     "ICMP:10.3.1.1:10.3.4.1:16:42:8:x",
                     "ICMP:10.3.1.1:10.3.4.1:16:42",
                     "ICMP:10.3.1.1:10.3.4.1:256:42:8",
                     "ICMP:10.3.1.1:10.3.4.1:16:a:8",
                     "ICMP:10.3.1.1:10.3.4.1:16:42:a",
                     "ICMP:10.3.1.1:10.3.4.1:a:42:8",
                     "ICMP:x:10.3.4.1:16:42:8",
                     "ICMP:10.3.1.1:x:16:42:8"):
            self.assertIsNone(pacotes.parse(ruim), ruim)

    def test_tipo_desconhecido_e_lixo(self):
        for ruim in ("", "OLA:1", "hello:10.3.1.1", "é", "HELLO10.3.1.1"):
            self.assertIsNone(pacotes.parse(ruim), ruim)

    def test_decodificar_nunca_levanta(self):
        self.assertIsNone(pacotes.parse(pacotes.decodificar(b"HELLO:10.3.1.1\xff")))
        self.assertEqual(pacotes.decodificar(b"HELLO:1.1.1.1"), "HELLO:1.1.1.1")

    def test_endereco_valido_limites(self):
        self.assertTrue(pacotes.endereco_valido("0.0.0.0"))
        self.assertTrue(pacotes.endereco_valido("255.255.255.255"))
        self.assertFalse(pacotes.endereco_valido("255.255.255.256"))
        self.assertFalse(pacotes.endereco_valido("1.1.1"))
        self.assertFalse(pacotes.endereco_valido("1.1.1.1.1"))

    def test_mensagem_valida(self):
        self.assertTrue(pacotes.mensagem_valida("Oi pessoal!"))
        self.assertFalse(pacotes.mensagem_valida("a:b"))
        self.assertFalse(pacotes.mensagem_valida("olá"))


class TestMontagem(unittest.TestCase):
    def test_formatos_exatos(self):
        self.assertEqual(pacotes.monta_hello("10.3.1.1"), "HELLO:10.3.1.1")
        self.assertEqual(pacotes.monta_lsp("10.3.1.1", 9, {"10.3.4.1": 3, "10.3.2.1": 1}),
                         "LSP:10.3.1.1:9:10.3.2.1=1;10.3.4.1=3")
        self.assertEqual(pacotes.monta_lsp("10.3.1.1", 9, {}), "LSP:10.3.1.1:9:")
        self.assertEqual(pacotes.monta_dados("1.1.1.1", "2.2.2.2", 16, 0, "oi"),
                         "DADOS:1.1.1.1:2.2.2.2:16:0:oi")
        self.assertEqual(pacotes.monta_icmp("1.1.1.1", "2.2.2.2", 16, 42, 8),
                         "ICMP:1.1.1.1:2.2.2.2:16:42:8")

    def test_ida_e_volta(self):
        lsp = pacotes.LSP("10.3.1.1", 1, {"10.3.2.1": 4})
        self.assertEqual(pacotes.parse(pacotes.monta_lsp(lsp.origem, lsp.seq, lsp.vizinhos)), lsp)


# ============================================================= dijkstra

def grafo_teste():
    """Topologia de config/teste: R1-R2=2 R1-R3=5 R2-R3=1 R2-R4=4 R3-R4=2 R4-R5=3 R3-R5=8"""
    arestas = [(1, 2, 2), (1, 3, 5), (2, 3, 1), (2, 4, 4), (3, 4, 2), (4, 5, 3), (3, 5, 8)]
    g = {f"10.7.{n}.1": {} for n in range(1, 6)}
    for a, b, c in arestas:
        g[f"10.7.{a}.1"][f"10.7.{b}.1"] = c
        g[f"10.7.{b}.1"][f"10.7.{a}.1"] = c
    return g


class TestDijkstra(unittest.TestCase):
    def test_topologia_do_relatorio(self):
        self.assertEqual(dijkstra.calcular(grafo_teste(), "10.7.1.1"), {
            "10.7.2.0/24": ("10.7.2.1", 2),
            "10.7.3.0/24": ("10.7.2.1", 3),
            "10.7.4.0/24": ("10.7.2.1", 5),
            "10.7.5.0/24": ("10.7.2.1", 8),
        })
        self.assertEqual(dijkstra.calcular(grafo_teste(), "10.7.5.1"), {
            "10.7.4.0/24": ("10.7.4.1", 3),
            "10.7.3.0/24": ("10.7.4.1", 5),
            "10.7.2.0/24": ("10.7.4.1", 6),
            "10.7.1.0/24": ("10.7.4.1", 8),
        })

    def test_empate_descoberto_depois_troca_para_menor_endereco(self):
        # O caminho via 3 chega ao 4 primeiro (3 sai da fila antes do 2);
        # o via 2 empata depois e deve vencer pelo menor endereco.
        g = {"10.0.1.1": {"10.0.3.1": 1, "10.0.2.1": 2},
             "10.0.3.1": {"10.0.1.1": 1, "10.0.4.1": 2},
             "10.0.2.1": {"10.0.1.1": 2, "10.0.4.1": 1},
             "10.0.4.1": {"10.0.3.1": 2, "10.0.2.1": 1}}
        self.assertEqual(dijkstra.calcular(g, "10.0.1.1")["10.0.4.0/24"], ("10.0.2.1", 3))

    def test_empate_fica_com_menor_endereco(self):
        # 1 -> {2, 3} -> 4, tudo custo 1. Ordem de insercao poe o 3 primeiro.
        g = {"10.0.1.1": {"10.0.3.1": 1, "10.0.2.1": 1},
             "10.0.3.1": {"10.0.1.1": 1, "10.0.4.1": 1},
             "10.0.2.1": {"10.0.1.1": 1, "10.0.4.1": 1},
             "10.0.4.1": {"10.0.3.1": 1, "10.0.2.1": 1}}
        self.assertEqual(dijkstra.calcular(g, "10.0.1.1")["10.0.4.0/24"], ("10.0.2.1", 2))

    def test_caminho_longo_mais_barato_vence_salto_direto(self):
        g = {"a.0.0.1": {}, "1.0.0.1": {"2.0.0.1": 10, "3.0.0.1": 1},
             "2.0.0.1": {"1.0.0.1": 10, "3.0.0.1": 1},
             "3.0.0.1": {"1.0.0.1": 1, "2.0.0.1": 1}}
        self.assertEqual(dijkstra.calcular(g, "1.0.0.1")["2.0.0.0/24"], ("3.0.0.1", 2))

    def test_inalcancavel_nao_aparece_e_eu_tambem_nao(self):
        g = {"10.0.1.1": {"10.0.2.1": 1}, "10.0.2.1": {"10.0.1.1": 1}, "10.0.9.1": {}}
        self.assertEqual(dijkstra.calcular(g, "10.0.1.1"), {"10.0.2.0/24": ("10.0.2.1", 1)})
        self.assertEqual(dijkstra.calcular({}, "10.0.1.1"), {})

    def test_rede_de_e_pertence(self):
        self.assertEqual(dijkstra.rede_de("10.7.4.1"), "10.7.4.0/24")
        self.assertTrue(dijkstra.pertence("10.7.4.50", "10.7.4.0/24"))
        self.assertFalse(dijkstra.pertence("10.7.5.1", "10.7.4.0/24"))


# ================================================================= LSDB

class VizFalsa:
    def __init__(self, ativos):
        """ativos: {endereco: (ip, porta, custo)}"""
        self.estados = [SimpleNamespace(endereco=e, ip=ip, porta=p, custo=c, ativo=True)
                        for e, (ip, p, c) in ativos.items()]

    def ativos(self):
        return {e.endereco: e.custo for e in self.estados if e.ativo}

    def listar(self):
        return self.estados

    def endereco_para_destino(self, endereco):
        for e in self.estados:
            if e.ativo and e.endereco == endereco:
                return (e.ip, e.porta)
        return None


class TestLSDB(unittest.TestCase):
    def setUp(self):
        self.rede = Rede()
        self.mudou = 0
        self.viz = VizFalsa({"10.7.2.1": ("h", 6002, 2), "10.7.3.1": ("h", 6003, 5)})
        self.viz.estados.append(SimpleNamespace(endereco="10.7.9.1", ip="h", porta=6009,
                                                custo=1, ativo=False))
        self.db = LSDB(cfg(), self.viz, self.rede, self._mudou)

    def _mudou(self):
        self.mudou += 1

    def test_gerar_proprio_sequencia_unix_e_incremento(self):
        antes = int(time.time())
        self.db.gerar_proprio()
        seq = self.db.seq
        self.assertGreaterEqual(seq, antes)
        self.assertLessEqual(seq, int(time.time()))
        self.db.gerar_proprio()
        self.assertEqual(self.db.seq, seq + 1)
        self.assertEqual(self.mudou, 2)

    def test_gerar_proprio_so_vizinhos_ativos_e_so_para_ativos(self):
        self.db.gerar_proprio()
        lsp = self.db.base["10.7.1.1"].lsp
        self.assertEqual(lsp.vizinhos, {"10.7.2.1": 2, "10.7.3.1": 5})
        self.assertEqual(sorted(p for _, _, p in self.rede.enviados), [6002, 6003])
        self.assertTrue(all(t == f"LSP:10.7.1.1:{lsp.seq}:10.7.2.1=2;10.7.3.1=5"
                            for t in self.rede.textos()))
        self.assertGreater(self.db.proxima_renovacao, time.monotonic() + 25)

    def test_recebe_novo_repassa_exceto_remetente(self):
        lsp = pacotes.LSP("10.7.5.1", 100, {"10.7.3.1": 8})
        self.db.ao_receber_lsp(lsp, "h", 6003)
        self.assertIs(self.db.base["10.7.5.1"].lsp, lsp)
        self.assertEqual(self.rede.enviados, [("LSP:10.7.5.1:100:10.7.3.1=8", "h", 6002)])
        self.assertEqual(self.mudou, 1)

    def test_inundacao_continua_depois_do_remetente(self):
        # Remetente e o PRIMEIRO da lista: os seguintes ainda devem receber.
        self.db.ao_receber_lsp(pacotes.LSP("10.7.5.1", 100, {}), "h", 6002)
        self.assertEqual([p for _, _, p in self.rede.enviados], [6003])

    def test_descarta_copia_antigo_e_proprio(self):
        self.db.ao_receber_lsp(pacotes.LSP("10.7.5.1", 100, {}), "h", 6003)
        self.rede.enviados.clear()
        self.db.ao_receber_lsp(pacotes.LSP("10.7.5.1", 100, {"x.x.x.x": 1}), "h", 6002)
        self.db.ao_receber_lsp(pacotes.LSP("10.7.5.1", 99, {"x.x.x.x": 1}), "h", 6002)
        self.db.ao_receber_lsp(pacotes.LSP("10.7.1.1", 10**12, {}), "h", 6002)
        self.assertEqual(self.rede.enviados, [])
        self.assertEqual(self.db.base["10.7.5.1"].lsp.vizinhos, {})
        self.assertNotIn("10.7.1.1", self.db.base)
        self.assertEqual(self.mudou, 1)

    def test_seq_maior_substitui(self):
        self.db.ao_receber_lsp(pacotes.LSP("10.7.5.1", 100, {}), "h", 6003)
        self.db.ao_receber_lsp(pacotes.LSP("10.7.5.1", 101, {"10.7.4.1": 3}), "h", 6003)
        self.assertEqual(self.db.base["10.7.5.1"].lsp.seq, 101)
        self.assertEqual(self.mudou, 2)

    def test_sincronizar_envia_base_inteira_ao_novo_vizinho(self):
        self.db.gerar_proprio()
        self.db.ao_receber_lsp(pacotes.LSP("10.7.5.1", 100, {}), "h", 6003)
        self.rede.enviados.clear()
        self.db.sincronizar_com("10.7.2.1")
        self.assertEqual(len(self.rede.enviados), 2)
        self.assertTrue(all(p == 6002 for _, _, p in self.rede.enviados))
        self.db.sincronizar_com("10.7.9.1")      # inativo: nada sai
        self.assertEqual(len(self.rede.enviados), 2)

    def test_envelhecimento(self):
        self.db.gerar_proprio()
        self.db.ao_receber_lsp(pacotes.LSP("10.7.5.1", 100, {}), "h", 6003)
        self.db.ao_receber_lsp(pacotes.LSP("10.7.6.1", 100, {}), "h", 6003)
        self.mudou = 0
        self.db.envelhecer()
        self.assertEqual(self.mudou, 0)               # nada venceu
        velho = time.monotonic() - TIMEOUT_LSP - 1
        self.db.base["10.7.5.1"].visto_em = velho
        self.db.base["10.7.1.1"].visto_em = velho     # o proprio nunca envelhece
        self.db.envelhecer()
        self.assertEqual(sorted(self.db.base), ["10.7.1.1", "10.7.6.1"])
        self.assertEqual(self.mudou, 1)

    def test_envelhecimento_respeita_o_prazo(self):
        self.db.ao_receber_lsp(pacotes.LSP("10.7.5.1", 100, {}), "h", 6003)
        self.db.base["10.7.5.1"].visto_em = time.monotonic() - TIMEOUT_LSP + 5
        self.db.envelhecer()
        self.assertIn("10.7.5.1", self.db.base)

    def test_grafo_exige_bidirecional_e_usa_maior_custo(self):
        self.db.gerar_proprio()                       # 1: 2=2, 3=5
        self.db.ao_receber_lsp(pacotes.LSP("10.7.2.1", 1, {"10.7.1.1": 2}), "h", 6002)
        self.db.ao_receber_lsp(pacotes.LSP("10.7.3.1", 1, {"10.7.1.1": 7, "10.7.8.1": 1}),
                               "h", 6003)
        g = self.db.grafo()
        self.assertEqual(g["10.7.1.1"], {"10.7.2.1": 2, "10.7.3.1": 7})
        self.assertEqual(g["10.7.3.1"], {"10.7.1.1": 7})   # 8.1 nao tem LSP
        self.assertNotIn("10.7.8.1", g)

    def test_grafo_aresta_unilateral_nao_esconde_as_seguintes(self):
        self.db.gerar_proprio()
        self.db.ao_receber_lsp(pacotes.LSP("10.7.2.1", 1, {"10.7.0.1": 1, "10.7.1.1": 2}),
                               "h", 6002)
        self.assertEqual(self.db.grafo()["10.7.2.1"], {"10.7.1.1": 2})

    def test_grafo_ignora_enlace_que_o_outro_lado_nao_declara(self):
        self.db.gerar_proprio()
        self.db.ao_receber_lsp(pacotes.LSP("10.7.2.1", 1, {}), "h", 6002)
        self.assertEqual(self.db.grafo()["10.7.1.1"], {})

    def test_linhas(self):
        self.db.ao_receber_lsp(pacotes.LSP("10.7.5.1", 9, {"10.7.4.1": 3}), "h", 6003)
        self.db.ao_receber_lsp(pacotes.LSP("10.7.0.1", 8, {}), "h", 6003)
        self.assertEqual(self.db.linhas(), [("10.7.0.1", 8, "(nenhum)"),
                                            ("10.7.5.1", 9, "10.7.4.1=3")])


# ============================================================ vizinhanca

class TestVizinhanca(unittest.TestCase):
    def setUp(self):
        self.rede = Rede()
        self.mudancas = []
        self.viz = Vizinhanca(cfg(vizinhos=[("10.7.2.1", "h", 6002, 2),
                                            ("10.7.3.1", "h", 6003, 5)]),
                              self.rede, lambda e, a: self.mudancas.append((e, a)))

    def test_hello_para_todos_os_configurados(self):
        self.viz.enviar_hellos()
        self.assertEqual(sorted(self.rede.enviados),
                         [("HELLO:10.7.1.1", "h", 6002), ("HELLO:10.7.1.1", "h", 6003)])

    def test_primeiro_hello_ativa_uma_vez(self):
        self.assertEqual(self.viz.ativos(), {})
        self.viz.ao_receber_hello(pacotes.Hello("10.7.2.1"), "h", 6002)
        self.viz.ao_receber_hello(pacotes.Hello("10.7.2.1"), "h", 6002)
        self.assertEqual(self.mudancas, [("10.7.2.1", True)])
        self.assertEqual(self.viz.ativos(), {"10.7.2.1": 2})
        self.assertEqual(self.viz.endereco_para_destino("10.7.2.1"), ("h", 6002))
        self.assertIsNone(self.viz.endereco_para_destino("10.7.3.1"))   # so configurado

    def test_endpoint_desconhecido_ignorado(self):
        self.viz.ao_receber_hello(pacotes.Hello("10.7.2.1"), "h", 7777)
        self.assertEqual(self.mudancas, [])

    def test_hello_com_outro_endereco_atualiza(self):
        self.viz.ao_receber_hello(pacotes.Hello("10.7.20.1"), "h", 6002)
        self.assertEqual(self.viz.ativos(), {"10.7.20.1": 2})

    def test_hello_renova_o_prazo(self):
        self.viz.ao_receber_hello(pacotes.Hello("10.7.2.1"), "h", 6002)
        self.viz.varrer_timeouts()
        self.assertEqual(self.viz.ativos(), {"10.7.2.1": 2})

    def test_timeout(self):
        self.viz.ao_receber_hello(pacotes.Hello("10.7.2.1"), "h", 6002)
        est = self.viz.por_endpoint[("h", 6002)]
        est.ultimo_hello = time.monotonic() - TIMEOUT_VIZINHO + 2
        self.viz.varrer_timeouts()
        self.assertTrue(est.ativo)
        est.ultimo_hello = time.monotonic() - TIMEOUT_VIZINHO - 1
        self.viz.varrer_timeouts()
        self.viz.varrer_timeouts()
        self.assertFalse(est.ativo)
        self.assertEqual(self.mudancas, [("10.7.2.1", True), ("10.7.2.1", False)])
        self.assertEqual(self.viz.ativos(), {})
        self.assertEqual(len(self.viz.listar()), 2)


# ========================================================= encaminhamento

class TestEncaminhamento(unittest.TestCase):
    """Somos 10.7.1.1. Vizinho ativo 10.7.2.1 em h:6002; rota para 10.7.4.0/24."""
    def setUp(self):
        self.rede = Rede()
        self.viz = VizFalsa({"10.7.2.1": ("h", 6002, 2)})
        self.tabela = {"10.7.2.0/24": ("10.7.2.1", 2), "10.7.4.0/24": ("10.7.2.1", 5)}
        self.enc = Encaminhador(cfg(), self.viz, self.rede, lambda: self.tabela)

    def receber(self, texto):
        saida = io.StringIO()
        with redirect_stdout(saida):
            self.enc.ao_receber(pacotes.parse(texto), "h", 6002)
        return saida.getvalue()

    def test_encaminha_decrementando_ttl(self):
        self.receber("DADOS:10.7.2.1:10.7.4.9:5:0:oi")
        self.assertEqual(self.rede.enviados, [("DADOS:10.7.2.1:10.7.4.9:4:0:oi", "h", 6002)])
        self.receber("ICMP:10.7.2.1:10.7.4.1:2:3:8")
        self.assertEqual(self.rede.textos()[-1], "ICMP:10.7.2.1:10.7.4.1:1:3:8")

    def test_entrega_local_mesmo_com_ttl_1_e_qualquer_host_da_rede(self):
        saida = self.receber("DADOS:10.7.2.1:10.7.1.50:1:0:Oi pessoal!")
        self.assertIn("de 10.7.2.1 para 10.7.1.50: Oi pessoal!", saida)
        self.assertEqual(self.rede.enviados, [])

    def test_ttl_zera_gera_tempo_excedido(self):
        self.receber("ICMP:10.7.2.1:10.7.4.1:1:42:8")
        self.assertEqual(self.rede.enviados, [("ICMP:10.7.1.1:10.7.2.1:16:42:11", "h", 6002)])

    def test_ttl_zero_recebido_tambem_expira(self):
        self.receber("DADOS:10.7.2.1:10.7.4.1:0:9:x")
        self.assertEqual(self.rede.textos(), ["ICMP:10.7.1.1:10.7.2.1:16:9:11"])

    def test_sem_rota_gera_inalcancavel(self):
        self.receber("DADOS:10.7.2.1:10.7.9.1:16:7:x")
        self.assertEqual(self.rede.textos(), ["ICMP:10.7.1.1:10.7.2.1:16:7:3"])

    def test_nunca_erro_em_resposta_a_erro(self):
        self.receber("ICMP:10.7.2.1:10.7.4.1:1:1:11")
        self.receber("ICMP:10.7.2.1:10.7.9.1:16:1:3")
        self.assertEqual(self.rede.enviados, [])

    def test_erro_em_resposta_a_eco_e_permitido(self):
        self.receber("ICMP:10.7.2.1:10.7.4.1:1:1:0")
        self.assertEqual(self.rede.textos(), ["ICMP:10.7.1.1:10.7.2.1:16:1:11"])

    def test_erro_sem_rota_de_volta_e_descartado(self):
        self.receber("DADOS:10.7.8.1:10.7.9.1:16:7:x")
        self.assertEqual(self.rede.enviados, [])

    def test_resposta_de_eco_sai_de_quem_foi_pingado(self):
        self.receber("ICMP:10.7.2.1:10.7.1.50:3:77:8")
        self.assertEqual(self.rede.enviados, [("ICMP:10.7.1.50:10.7.2.1:16:77:0", "h", 6002)])

    def test_proximo_salto_inativo_descarta(self):
        self.viz.estados[0].ativo = False
        self.receber("DADOS:10.7.2.1:10.7.4.1:16:0:x")
        self.assertEqual(self.rede.enviados, [])

    def test_ping_completo_com_rtt(self):
        with redirect_stdout(io.StringIO()):
            self.enc.originar_ping("10.7.4.1", 3)
        self.assertEqual(self.rede.textos(), ["ICMP:10.7.1.1:10.7.4.1:3:1:8"])
        self.assertIn(1, self.enc.pings)
        saida = self.receber("ICMP:10.7.4.1:10.7.1.1:14:1:0")
        self.assertIn("resposta de 10.7.4.1: resposta de eco, id 1", saida)
        self.assertEqual(self.enc.pings, {})

    def test_rtt_em_milissegundos(self):
        self.enc.pings[5] = ("10.7.4.1", time.monotonic() - 0.5)
        saida = self.receber("ICMP:10.7.4.1:10.7.1.1:14:5:0")
        rtt = float(saida.split("rtt ")[1].split(" ms")[0])
        self.assertTrue(499.9 < rtt < 500.4, rtt)

    def test_ping_com_proximo_salto_inativo_nao_fica_pendente(self):
        self.viz.estados[0].ativo = False
        with redirect_stdout(io.StringIO()):
            self.enc.originar_ping("10.7.4.1", 16)
        self.assertEqual(self.enc.pings, {})

    def test_icmp_sem_pedido_pendente(self):
        self.assertIn("sem pedido pendente", self.receber("ICMP:10.7.4.1:10.7.1.1:14:99:3"))

    def test_ping_sem_rota_nao_envia(self):
        saida = io.StringIO()
        with redirect_stdout(saida):
            self.enc.originar_ping("10.7.9.1", 16)
        self.assertIn("destino inalcancavel", saida.getvalue())
        self.assertEqual(self.rede.enviados, [])
        self.assertEqual(self.enc.pings, {})

    def test_ping_e_msg_para_mim_nao_saem(self):
        saida = io.StringIO()
        with redirect_stdout(saida):
            self.enc.originar_ping("10.7.1.1", 16)
            self.enc.originar_dados("10.7.1.9", "oi")
        self.assertEqual(self.rede.enviados, [])
        self.assertIn("eco local", saida.getvalue())
        self.assertIn("para 10.7.1.9: oi", saida.getvalue())

    def test_ping_timeout(self):
        with redirect_stdout(io.StringIO()):
            self.enc.originar_ping("10.7.4.1", 16)
        self.enc.pings[1] = ("10.7.4.1", time.monotonic() - TIMEOUT_PING + 1)
        self.enc.expirar_pings()
        self.assertIn(1, self.enc.pings)
        self.enc.pings[1] = ("10.7.4.1", time.monotonic() - TIMEOUT_PING - 0.1)
        saida = io.StringIO()
        with redirect_stdout(saida):
            self.enc.expirar_pings()
        self.assertIn("timeout", saida.getvalue())
        self.assertEqual(self.enc.pings, {})

    def test_msg_ids_crescentes_e_ttl_16(self):
        with redirect_stdout(io.StringIO()):
            self.enc.originar_dados("10.7.4.1", "a")
            self.enc.originar_dados("10.7.4.1", "b")
        self.assertEqual(self.rede.textos(), ["DADOS:10.7.1.1:10.7.4.1:16:1:a",
                                              "DADOS:10.7.1.1:10.7.4.1:16:2:b"])

    def test_msg_invalida_nao_sai(self):
        saida = io.StringIO()
        with redirect_stdout(saida):
            self.enc.originar_dados("10.7.4.1", "a:b")
            self.enc.originar_dados("10.7.4.1", "olá")
        self.assertEqual(self.rede.enviados, [])
        self.assertIn("mensagem invalida", saida.getvalue())


# ================================================================ config

class TestConfig(unittest.TestCase):
    def ler(self, texto):
        with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as f:
            f.write(texto)
        self.addCleanup(os.unlink, f.name)
        return config_mod.ler(f.name)

    def test_arquivo_valido(self):
        c = self.ler("# x\nendereco 10.7.1.1  # eu\nporta 6001\n\n"
                     "vizinho 10.7.2.1 localhost 6002 3\n"
                     "vizinho 10.7.3.1 127.0.0.1 6003 1\n")
        self.assertEqual((c.endereco, c.porta, c.rede), ("10.7.1.1", 6001, "10.7.1.0/24"))
        self.assertEqual(c.vizinhos, [config_mod.Vizinho("10.7.2.1", "127.0.0.1", 6002, 3),
                                      config_mod.Vizinho("10.7.3.1", "127.0.0.1", 6003, 1)])

    def test_porta_padrao(self):
        self.assertEqual(self.ler("endereco 10.7.1.1\n").porta, 6000)

    def test_erros(self):
        for ruim in ("porta 6000\n",                                   # sem endereco
                     "endereco 10.7.1.1\nvizinho 10.7.2.1 PREENCHER 6000 1\n",
                     "endereco 10.7.1.1\nvizinho 10.7.2.1 127.0.0.1 6000 0\n",
                     "endereco 10.7.1.1\nvizinho 10.7.2.1 127.0.0.1 6000\n",
                     "endereco 10.7.1.1\nporta 6000 7000\n",
                     "endereco 10.7.1.1\nfoo bar\n"):
            with self.assertRaises(ValueError, msg=ruim):
                self.ler(ruim)

    def test_erro_aponta_linha_e_valor(self):
        with self.assertRaisesRegex(ValueError, r":2: IP invalido: 'PREENCHER'"):
            self.ler("endereco 10.7.1.1\nvizinho 10.7.2.1 PREENCHER 6000 1\n")


if __name__ == "__main__":
    unittest.main()
