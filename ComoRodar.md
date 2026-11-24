# Como rodar

Precisa só de Python 3, sem bibliotecas extras. No Mac/Linux use `python3` no lugar de `python`.

Rode a partir da pasta do projeto:

```
python src/roteador.py <arquivo de configuração>
```

Exemplo: `python src/roteador.py config/r1.conf`

## Arquivo de configuração

```
endereco 10.7.1.1
porta 6000

# vizinho <endereço virtual> <IP real> <porta> <custo>
vizinho 10.7.2.1 192.168.0.11 6000 1
vizinho 10.7.4.1 192.168.0.14 6000 10
```

- `endereco`: endereço virtual do roteador (10.G.R.1).
- `porta`: porta UDP do roteador (padrão 6000).
- `vizinho`: uma linha por vizinho. O custo é um inteiro positivo, igual nos dois lados do enlace.
- Linhas com `#` são comentários.

Nos arquivos `config/r1.conf` a `r4.conf`, troque `PREENCHER` pelo IP real de cada vizinho no dia, depois de todos conectarem na rede. Para ver o próprio IP, use `ipconfig` no Windows ou `ipconfig getifaddr en0` no Mac. A porta UDP precisa estar liberada no firewall.

## Comandos

| Comando | O que faz |
| --- | --- |
| `vizinhos` | vizinhos ativos |
| `lsdb` | LSDB |
| `tabela` | tabela de roteamento |
| `msg <destino> <texto>` | envia uma mensagem |
| `ping <destino> [TTL]` | ping (TTL padrão 16) |
| `sair` | encerra |

Os logs aparecem no terminal e são salvos em `logs/<nome da config>.log`.

## Teste numa máquina só

Abra 5 terminais e rode um em cada:

```
python src/roteador.py config/teste/t1.conf
python src/roteador.py config/teste/t2.conf
python src/roteador.py config/teste/t3.conf
python src/roteador.py config/teste/t4.conf
python src/roteador.py config/teste/t5.conf
```

Testes automáticos: `python -m unittest discover -s tests -b`
