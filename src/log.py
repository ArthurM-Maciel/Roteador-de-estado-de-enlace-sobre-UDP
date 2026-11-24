import threading
import time

_lock = threading.Lock()
_arquivo = None


def abrir(caminho):
    global _arquivo
    _arquivo = open(caminho, "a", encoding="utf-8", buffering=1)


def log(categoria, mensagem):
    agora = time.time()
    carimbo = time.strftime("%H:%M:%S", time.localtime(agora))
    linha = f"{carimbo}.{int(agora % 1 * 1000):03d} [{categoria:<7}] {mensagem}"
    with _lock:
        print(linha, flush=True)
        if _arquivo is not None:
            _arquivo.write(linha + "\n")
