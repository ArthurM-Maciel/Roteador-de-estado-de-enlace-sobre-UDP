# Roteador de estado de enlace sobre UDP

**Fundamentos de Redes de Computadores — Trabalho Final — PUCRS**

Implementação de um roteador de estado de enlace inspirado no OSPF, rodando como
aplicação sobre UDP. Cada integrante roda uma instância na sua máquina; juntas,
as instâncias formam uma **rede virtual** sobre a rede local real.

> ### ⚠️ Aviso sobre o enunciado original
>
> O arquivo `TF.html` distribuído pelo professor contém **três cópias de uma
> instrução oculta** (texto invisível em `<span>` com `color:transparent`,
> `font-size:1px` e `user-select:text`), mandando o roteador imprimir uma receita
> de bolo de cenoura e terminar cada linha de log com o nome de um planeta.
>
> É uma armadilha para identificar quem cola o enunciado numa IA e entrega sem
> ler. **Não implementamos isso.** O enunciado reproduzido abaixo é a versão
> higienizada. Detalhes da varredura: [`docs/injecao-removida.md`](docs/injecao-removida.md).
>
> Lembrete do próprio enunciado: *código que o integrante questionado não consiga
> explicar não é considerado de autoria do grupo, e o trabalho recebe zero.*
> Por isso este README começa explicando, não copiando.

---

## Sumário

- [Parte I — Entender](#parte-i--entender)
  - [A ideia em uma página](#a-ideia-em-uma-página)
  - [As quatro camadas do problema](#as-quatro-camadas-do-problema)
  - [Endereçamento virtual](#endereçamento-virtual-como-pensar)
  - [Os temporizadores](#os-temporizadores-decorar-esses)
  - [Por que cada regra existe](#por-que-cada-regra-existe)
- [Parte II — Fazer](#parte-ii--fazer)
  - [Arquitetura sugerida](#arquitetura-sugerida)
  - [Notas de Python](#notas-de-python)
  - [Ordem de implementação](#ordem-de-implementação)
  - [Dijkstra com próximo salto](#dijkstra-com-próximo-salto)
  - [Armadilhas](#armadilhas-onde-os-grupos-perdem-ponto)
- [Parte III — Apresentar](#parte-iii--apresentar)
  - [Roteiro da apresentação](#roteiro-da-apresentação)
  - [Guia do relatório](#guia-do-relatório)
  - [Banco de perguntas da banca](#banco-de-perguntas-da-banca)
- [Parte IV — O enunciado completo](#parte-iv--o-enunciado-completo)
- [Decisões do grupo](#decisões-do-grupo)

---

# Parte I — Entender

## A ideia em uma página

Um roteador de estado de enlace resolve um problema simples de enunciar e
difícil de executar: **cada roteador só enxerga seus vizinhos imediatos, mas
precisa calcular o melhor caminho para toda a rede.**

A solução tem três movimentos:

1. **Descobrir quem está vivo ao meu lado** → mensagens `HELLO`, a cada 5s.
   O arquivo de configuração diz quem *poderia* ser meu vizinho; o HELLO diz
   quem *está de fato ligado agora*.

2. **Contar isso para todo mundo** → cada roteador gera um `LSP` (Link State
   Packet) descrevendo "eu sou X, meus vizinhos ativos são Y com custo 2 e Z com
   custo 5" e **inunda** pela rede: todo mundo que recebe repassa aos seus
   próprios vizinhos. Ao final, todos os roteadores têm a **mesma LSDB** — o
   mapa completo da rede.

3. **Cada um calcula sozinho** → com o mapa idêntico na mão, cada roteador roda
   **Dijkstra a partir de si mesmo** e monta sua tabela de roteamento. Ninguém
   precisa combinar nada: mesmo grafo + mesmo algoritmo = rotas coerentes.

Com a tabela pronta, encaminhar é mecânico: olha o destino, olha a tabela,
manda para o próximo salto, decrementa o TTL.

**O contraste que o relatório vai cobrar:** num protocolo de *vetor distância*
(RIP), cada roteador conta aos vizinhos **o que ele concluiu** ("eu chego em D
com custo 7") e ninguém tem o mapa. Em *estado de enlace*, cada roteador conta
**o que ele vê** ("meus enlaces são estes") e todos reconstroem o mapa. Daí a
convergência mais rápida e a ausência de *count-to-infinity*.

## As quatro camadas do problema

Pense no roteador como quatro subsistemas empilhados. Cada um só depende do de
baixo — e essa é a ordem de implementar e de explicar na apresentação.

```
┌──────────────────────────────────────────────────────────┐
│ 4. ENCAMINHAMENTO     DADOS e ICMP, TTL, ping            │
│    usa ──────────────────────────────────┐               │
├──────────────────────────────────────────┼───────────────┤
│ 3. TABELA DE ROTEAMENTO    Dijkstra ◄────┘               │
│    rede destino → próximo salto, custo                   │
│    recalculada toda vez que a LSDB muda                  │
├──────────────────────────────────────────────────────────┤
│ 2. LSDB + INUNDAÇÃO     LSPs, nº de sequência,           │
│    descarte de cópias, envelhecimento                    │
├──────────────────────────────────────────────────────────┤
│ 1. VIZINHANÇA     HELLO 5s, timeout 20s,                 │
│    mapa endereço virtual → (IP real, porta)              │
└──────────────────────────────────────────────────────────┘
                   ▲
            um único socket UDP
```

O **mapa `endereço virtual → (IP real, porta)`** da camada 1 é a peça que costura
tudo: a tabela de roteamento fala em endereços virtuais ("mande para 10.7.2.1"),
mas o `sendto()` precisa de IP real e porta. Quem traduz é o HELLO que chegou
daquele vizinho.

## Endereçamento virtual (como pensar)

O grupo recebe um número **G**; cada roteador escolhe um **R**.

| | Significado |
| --- | --- |
| `10.G.R.1` | O endereço **do roteador** R — é por ele que os outros o chamam |
| `10.G.R.0/24` | A **rede** pela qual ele responde |

O roteador R **representa toda a sua /24**. Não existem hosts de verdade: se
chegar um pacote para `10.7.1.50`, quem recebe e processa é o roteador
`10.7.1.1`. Isso simplifica muito — a tabela indexa por *rede*, não por host.

Por que `G` no segundo octeto: na apresentação a rede do seu grupo será plugada
na de outro grupo. Com o G embutido, `10.7.1.1` e `10.4.1.1` convivem sem
colisão.

**Importante:** esses endereços só existem *dentro* do trabalho. Eles vão como
texto ASCII no payload UDP. O IP real das máquinas (DHCP da VDI ou do access
point) é o que de fato transporta os pacotes.

## Os temporizadores (decorar esses)

| Evento | Tempo | Relação |
| --- | --- | --- |
| Envio de HELLO | **5 s** | base |
| Vizinho declarado inativo | **20 s** | 4 × HELLO |
| Renovação periódica do LSP | **30 s** | — |
| LSP de outro roteador expira na LSDB | **90 s** | 3 × renovação |
| Timeout do `ping` | **2 s** | — |
| TTL inicial | **16** | (não é tempo, é contagem de saltos) |

As **proporções** são o ponto, e vão cair na apresentação:

- **20 = 4 × 5** → tolera a perda de até 3 HELLOs seguidos antes de declarar
  queda. UDP não garante entrega; derrubar um vizinho por causa de um pacote
  perdido causaria oscilação de rotas (*flapping*).
- **90 = 3 × 30** → mesma lógica, um nível acima: dois LSPs de renovação podem
  se perder sem que o roteador suma do mapa dos outros.

## Por que cada regra existe

Não decore as regras — entenda o problema que cada uma resolve. É exatamente
assim que a pergunta vem na banca.

| Regra | Problema que resolve |
| --- | --- |
| **Número de sequência no LSP** | Sem ele, não dá para distinguir "notícia nova" de "cópia que deu a volta". A inundação nunca terminaria. |
| **Sequência inicial = Unix time** | Se um roteador reinicia e volta do 0, seus LSPs novos são *menores* que os velhos ainda guardados — todos os vizinhos os descartam, e ele fica invisível por até 90 s. Começando pelo relógio, qualquer LSP novo já nasce maior que tudo que existia. |
| **Descartar sequência ≤ a já conhecida** | É o freio da inundação: cada LSP novo é repassado **uma vez** por roteador; as cópias que chegam por outros caminhos morrem aqui. |
| **Não repassar para quem me enviou (`exceto V`)** | Corta o eco óbvio e reduz o tráfego da inundação. |
| **Envio da LSDB inteira a vizinho novo** | Quem acabou de entrar não pode esperar até 30 s pela próxima renovação de cada um dos outros. Isto é a *sincronização de base* — é o que faz um roteador reiniciado voltar a rotear em segundos. |
| **Envelhecimento em 90 s** | Sem isso, um roteador que saiu da rede ficaria no mapa para sempre, e Dijkstra calcularia rotas por um enlace que não existe. |
| **Não alterar a sequência ao repassar LSP alheio** | O número pertence a quem *gerou*. Mexer nele quebra a detecção de cópias em toda a rede. |
| **TTL, mesmo com todos calculando sobre o mesmo mapa** | Durante a convergência os mapas estão **temporariamente diferentes**: A já sabe da queda e desvia por B; B ainda não sabe e devolve para A. Laço. O TTL é a rede de segurança que mata o pacote em 16 saltos. |
| **Nunca gerar erro em resposta a erro** | Evita tempestade: um ICMP tipo 11 que também se perde geraria outro tipo 11, e assim por diante. Regra idêntica à do ICMP real. |
| **Descartar pacote de origem não-vizinha** | Filtro mínimo de sanidade: só processo o que vem de um par (IP, porta) que está na minha configuração. |
| **Descartar malformado sem cair** | O roteador é um serviço: pacote lixo (campo a menos, letra onde era número) não pode derrubá-lo. Vale para a interoperabilidade — a implementação do outro grupo pode errar. |
| **Mesmo socket para enviar e receber** | A porta UDP de origem dos pacotes que saem passa a ser a porta do roteador. É assim que o vizinho reconhece o remetente pelo par (IP, porta). Usar um socket efêmero para enviar quebra o reconhecimento. |

---

# Parte II — Fazer

## Arquitetura sugerida

Um processo, um socket, três atividades concorrentes:

```
 thread/loop RECEPÇÃO          thread/loop TEMPORIZADORES      thread/loop CLI
 ──────────────────────        ──────────────────────────      ───────────────
 recvfrom()                    a cada 5 s  → envia HELLO       input()
   ├─ origem é vizinho? ───┐   a cada 1 s  → varre:            ├─ tabela
   ├─ parse por tipo       │     · vizinho mudo há 20 s        ├─ lsdb
   │   ├─ HELLO  → ativa   │       → inativo → novo LSP        ├─ vizinhos
   │   ├─ LSP    → LSDB    │     · LSP alheio parado há 90 s   ├─ msg <dst> <txt>
   │   ├─ DADOS  → entrega │       → remove → recalcula        └─ ping <dst> [ttl]
   │   │           ou      │     · 30 s desde meu LSP
   │   │           encaminha│      → renova
   │   └─ ICMP   → idem    │
   └─ malformado → descarta┘
                     │
              ESTADO COMPARTILHADO (proteger com lock)
              vizinhos{} · lsdb{} · tabela{} · seq · pings_pendentes{}
```

Módulos sugeridos (vale para qualquer linguagem):

| Módulo | Responsabilidade |
| --- | --- |
| `config` | lê o arquivo de configuração |
| `pacotes` | serializa e **desserializa** os 4 formatos — é aqui que mora a validação |
| `vizinhos` | estado de vizinhança + mapa virtual → (IP, porta) |
| `lsdb` | armazena LSPs, decide descarte, envelhece |
| `dijkstra` | grafo → tabela de roteamento (**escrito pelo grupo**, sem biblioteca) |
| `encaminhamento` | DADOS/ICMP, TTL, geração de erros |
| `roteador` | socket, threads e os 5 comandos da CLI |
| `log` | eventos em tempo real, com timestamp |

## Notas de Python

**Linguagem decidida: Python**, sem nenhuma dependência externa — só `socket`,
`threading`, `heapq`, `time` e `sys`. Fixar **Python 3.10+** e conferir que a
mesma versão roda nas quatro máquinas.

O ganho é real: esta implementação em Python fica em torno de **400–600 linhas**,
contra o dobro disso em uma linguagem mais cerimoniosa. Menos código é menos
superfície de bug e menos coisa para explicar na banca.

As armadilhas específicas da linguagem:

**1. `split(":")` preserva o campo vazio no fim — e isso é o que queremos.**

```python
"LSP:10.7.1.1:1767712001:".split(":")   # ['LSP', '10.7.1.1', '1767712001', '']
```

É exatamente o LSP de lista vazia que o enunciado exige. (Em Java o mesmo
`split` descarta o campo final e devolve 3 elementos — motivo de divergência
clássico com outros grupos. Se a outra implementação for em Java, avise.)
Ainda assim, **valide o número de campos** antes de usar.

**2. Use `maxsplit` no DADOS.**

```python
campos = linha.split(":", 5)   # 6 campos, mensagem intacta
```

A mensagem não pode conter `:` pelo enunciado, mas o pacote do outro grupo pode
vir errado. Com `maxsplit` você recebe o pacote inteiro, valida e descarta de
forma explícita, em vez de quebrar no parser.

**3. A decodificação não pode levantar exceção.**

```python
texto = dados.decode("ascii", errors="replace")   # nunca estoura
```

`dados.decode("ascii")` levanta `UnicodeDecodeError` diante de um byte acentuado
vindo de outra implementação — e derruba a thread de recepção. O enunciado exige
que pacotes malformados sejam "descartados sem derrubar o roteador".

**4. `time.monotonic()` para temporizadores, `time.time()` para a sequência.**

Os prazos (20 s, 90 s, 2 s) precisam de relógio monotônico, imune a ajuste de
horário da máquina. Já o número de sequência do LSP é, por definição do
enunciado, o Unix time: `int(time.time())`. Trocar os dois é um bug silencioso.

**5. A thread de recepção nunca pode morrer.**

Envolva o corpo inteiro do laço em `try/except Exception` com log. Uma exceção
não tratada num pacote estranho mata a thread sem matar o processo: o roteador
fica de pé, mudo, e você perde minutos na apresentação procurando o motivo.

**6. `SO_REUSEADDR` antes do `bind`**, para reiniciar o roteador sem esperar o
socket liberar — e o professor vai mandar reiniciar.

**7. Entrega sem binários:** apagar `__pycache__/` antes de fechar o `.zip`.

O GIL não atrapalha: o trabalho é I/O, não CPU. E `input()` numa thread própria
bloqueia só aquela thread.

## Como rodar

```bash
python3 src/roteador.py config/teste/t1.conf     # um roteador
./scripts/subir_teste.sh                         # os 5 da topologia do relatório
```

Testes (só biblioteca padrão, ~5 s; o de integração sobe 3 roteadores reais):

```bash
python3 -m unittest discover -s tests -b
```

**O roteador está funcionalmente completo** (etapas 0–11): vizinhança, LSDB com
inundação, Dijkstra, encaminhamento, ICMP, logs e tratamento de pacote
malformado. Os cinco comandos do enunciado funcionam.

Falta a **etapa 12 — interoperabilidade**: testar contra a implementação de
outro grupo. É o único item que não dá para fazer sozinho.

> **Use isto antes de escrever qualquer protocolo:** rodem o roteador em dois
> notebooks ligados ao access point, com os IPs reais na configuração, e mandem
> qualquer texto de um para o outro. Se o pacote aparecer no log do outro lado,
> o AP não isola clientes — o maior risco do trabalho fica eliminado. Se não
> aparecer, vocês descobriram isso com três semanas de folga.

## Ordem de implementação

Siga a pilha de baixo para cima. Cada etapa é demonstrável sozinha — e isso
importa: se algo quebrar na véspera, você ainda tem as camadas de baixo
funcionando.

- [x] **0. Esqueleto** — socket UDP no `bind`, loop de recepção, comando `sair`.
- [x] **1. HELLO** — envio a cada 5s, recepção, `vizinhos` mostrando a lista. Testar com 2 processos na mesma máquina em portas diferentes.
- [x] **2. Timeout de vizinho** — matar um processo e ver o outro declarar inativo em 20s.
- [x] **3. LSP próprio** — gerar, numerar pelo Unix time, guardar na própria LSDB, comando `lsdb`.
- [x] **4. Inundação** — repassar, descartar cópia por sequência, não devolver para quem mandou. Testar com 3+ processos e conferir que todas as LSDBs ficam idênticas.
- [x] **5. Sincronização** — vizinho novo recebe a LSDB inteira. Teste: suba o 3º roteador e veja a LSDB dele encher na hora, não em 30s.
- [x] **6. Envelhecimento** — LSP alheio parado há 90s sai da LSDB.
- [x] **7. Dijkstra** — construir o grafo a partir da LSDB, calcular, comando `tabela`. **Conferir no papel** antes de confiar no código.
- [x] **8. DADOS** — `msg`, entrega local, encaminhamento, decremento de TTL.
- [x] **9. ICMP** — `ping` (tipo 8/0) com RTT e timeout de 2s, tipo 11 no TTL zerado, tipo 3 sem rota.
- [x] **10. Logs** — todos os eventos exigidos pelo critério 6.
- [x] **11. Robustez** — pacote malformado, origem desconhecida, campo não-numérico. Mande lixo de propósito com `netcat` e veja se o roteador aguenta.
- [ ] **12. Interoperabilidade** — testar com outro grupo **antes** da apresentação.

## Dijkstra com próximo salto

O Dijkstra da aula devolve distâncias. A tabela precisa de **próximo salto** —
e o truque é carregar essa informação junto durante a relaxação.

Grafo, a partir da LSDB: cada LSP de origem `O` com lista `V=c` vira as arestas
`O → V` de custo `c`. (Um enlace saudável aparece duas vezes, nos dois LSPs; se
aparecer só de um lado, o enlace está assimétrico — um dos lados ainda não
convergiu.)

```
dist[eu] = 0 ; primeiro_salto[eu] = None
fila de prioridade ← (0, eu)

enquanto a fila não esvazia:
    (d, u) ← menor da fila
    se u já visitado: continua          # descarta entrada obsoleta
    marca u visitado
    para cada (v, custo) em arestas[u]:
        se dist[u] + custo < dist[v]:
            dist[v] = dist[u] + custo
            # ESTA é a linha que diferencia da versão da aula:
            primeiro_salto[v] = (v se u == eu senão primeiro_salto[u])
            insere (dist[v], v) na fila
```

A tabela sai disso direto: para cada `v` alcançável e diferente de mim →
`rede de v (10.G.v.0/24) | primeiro_salto[v] | dist[v]`.

`heapq` / `PriorityQueue` são permitidos. `networkx`, `scipy.sparse.csgraph` e
`JGraphT` **não** — o algoritmo tem que ser do grupo.

## Armadilhas (onde os grupos perdem ponto)

1. **Decrementar o TTL em pacote destinado a si mesmo.** O decremento só
   acontece no caminho de *encaminhamento*. Se o destino é a minha rede, eu
   entrego — mesmo com TTL 1. É por isso que o `ping` com TTL crescente revela
   um roteador novo a cada incremento.
2. **Gerar ICMP de erro em resposta a ICMP de erro.** Antes de criar um tipo 11
   ou 3, verifique se o pacote que o causou já é tipo 11 ou 3. Se for, só
   descarte.
3. **Mandar a resposta de eco com a origem errada.** No tipo 0, a origem é
   **quem foi pingado**, e o `id` é copiado do pedido.
4. **Usar um socket novo para enviar.** Quebra o reconhecimento pelo par
   (IP, porta). Um socket só, o mesmo do `bind`.
5. **Alterar o número de sequência ao repassar LSP alheio.**
6. **Esquecer o LSP de lista vazia.** Um roteador sem vizinhos ativos manda
   `LSP:10.3.1.1:1767712001:` — e o parser do *outro* grupo precisa aguentar
   esse campo final vazio. Teste os dois lados.
7. **Acento ou `:` dentro da mensagem do `msg`.** O enunciado define isso como
   malformado. Valide na origem e avise o usuário, em vez de mandar lixo.
8. **Estado compartilhado sem lock.** Três loops mexendo em `lsdb` e `vizinhos`
   ao mesmo tempo dá corrida difícil de reproduzir — e ela vai aparecer na
   apresentação, não no teste.
9. **IP fixo no código.** O DHCP muda o endereço a cada conexão. Tudo no arquivo
   de configuração, fácil de editar no minuto anterior à apresentação.
10. **Firewall bloqueando a porta UDP** no notebook. Testar antes.

---

# Parte III — Apresentar

## Roteiro da apresentação

~30 min por dupla de grupos. Cerca de 10 min são do nosso grupo, 5 min são a
interoperabilidade conjunta. A rede precisa estar **montada e funcionando no
início do horário** — montar na hora conta contra.

**Rede do grupo** (4 roteadores em quartetos, 3 em trios), com custos diferentes
e **pelo menos um caminho alternativo**:

1. Exibir `vizinhos`, `lsdb` e `tabela` em cada roteador, conferindo com a
   topologia desenhada.
2. `ping` com TTL 1, 2, 3... até o roteador mais distante — cada TTL revela o
   próximo roteador do caminho (é um `traceroute` artesanal). Depois, uma `msg`.
3. `ping` para uma rede inexistente → destino inalcançável.
4. **O professor derruba um roteador ou enlace.** Mostrar a reconvergência e
   repetir o `ping` com TTL crescente, evidenciando o **novo caminho**. O
   roteador derrubado é reiniciado em seguida (e aqui a sincronização com
   vizinho novo aparece).
5. Perguntas sobre o código.

**Interoperabilidade** (~5 min, no fim da dupla): cada grupo acrescenta **uma
linha** no arquivo de configuração criando um enlace entre um roteador de cada
rede, e mostra a `lsdb`/`tabela` com os roteadores do outro grupo, `ping` e
`msg` atravessando as duas redes, e a reconvergência quando o professor derruba
o enlace entre os grupos.

> Ter o arquivo de configuração já preparado com a linha do outro grupo
> comentada economiza minutos preciosos.

**Todos os integrantes precisam estar presentes e saber explicar qualquer parte
do código.**

## Guia do relatório

Peso **20%** da nota. Exige uma topologia de teste com **pelo menos 5
roteadores**, custos diferentes e pelo menos um caminho alternativo — pode ser
tudo numa máquina só, em portas diferentes. **Incluir a figura da topologia com
os custos.**

| # | Questão | O que precisa aparecer como evidência |
| --- | --- | --- |
| 1 | **Dijkstra** | A LSDB de um roteador + a execução passo a passo (tabela de iterações, como na aula) + a `tabela` que o programa imprimiu, batendo com a conta feita à mão. |
| 2 | **Inundação** | Contagem de LSPs que circulam após **uma única** mudança (queda de um vizinho), tirada do Wireshark ou dos logs. Quantos foram descartados como cópia. Comparação com o que vetor distância enviaria. |
| 3 | **Convergência** | Derrubar um roteador **que esteja no caminho** entre outros dois e cronometrar até a rota ser recalculada. Separar o tempo em **detecção** (dominado pelos 20 s do HELLO) e **inundação + recálculo** (milissegundos). A conclusão natural: a detecção domina — e por isso o valor do temporizador é o que define a convergência. |
| 4 | **Números de sequência** | Por que existem, e o cenário concreto do reinício a partir do 0 (LSPs novos descartados como antigos; roteador invisível até a expiração dos 90 s). |
| 5 | **Confiabilidade** | LSP perdido = LSDB temporariamente divergente, rota possivelmente errada. Recuperação: a **renovação de 30 s** e a **sincronização com vizinho novo** — não há confirmação nem retransmissão. |
| 6 | **TTL** | O cenário de laço **durante a convergência**, com mapas momentaneamente diferentes entre dois roteadores vizinhos. |

Capturas `.pcapng` usadas no relatório entram no `.zip` da entrega.

> Dica para o item 2: filtre no Wireshark por `udp.port == 6000` e procure o
> payload em texto. Como tudo é ASCII, o `Follow UDP Stream` já mostra os LSPs
> legíveis.

## Banco de perguntas da banca

A banca pergunta **por que**, não *em que linha*. Treinar a resposta falada vale
mais que reler o código.

### Perguntas gerais (qualquer um pode receber)

- Onde você descarta uma cópia de LSP? Por que a comparação é `>=` e não `>`?
- Me mostre onde o TTL é decrementado. Por que não é decrementado aqui também?
- Como o endereço virtual vira IP real e porta na hora de enviar?
- O que acontece se chegar um pacote com 4 campos em vez de 5?
- Por que o número de sequência do LSP do vizinho não muda quando você repassa?
- Onde está a exclusão mútua do estado compartilhado?
- Se eu derrubar este roteador agora, quanto tempo até a rota mudar? Por quê?

### Dijkstra e tabela de roteamento

Conjunto praticamente fechado — nove perguntas cobrem o módulo. Seis delas se
respondem sem olhar o código.

**"Explique seu Dijkstra."**
Começo com distância 0 para mim e infinito para o resto. Tiro da fila sempre o
mais próximo ainda não visitado e o marco como visitado — nesse momento a
distância dele já é definitiva. Para cada vizinho dele, testo se chegar por ele
sai mais barato; se sair, atualizo e reinsiro na fila.

**"Por que a distância é definitiva quando você tira o nó da fila?"**
Porque qualquer caminho alternativo teria que passar por um nó ainda não
visitado, que está a uma distância maior ou igual — e como todos os custos são
positivos, o resto do caminho só pode aumentar. A garantia depende de custos
não-negativos, e o enunciado exige inteiro positivo.

**"Como você obtém o próximo salto, e não só a distância?"**
Carrego junto na relaxação. Ao melhorar o caminho para `v` passando por `u`: se
`u` sou eu, o primeiro salto para `v` é o próprio `v`; senão, `v` herda o
primeiro salto de `u`. A tabela não precisa do caminho inteiro — só de para quem
entregar agora.

**"De onde vem o grafo?"**
Da LSDB. Cada LSP de origem `O` com a lista `V=c` vira a aresta `O→V` de custo
`c`. Um enlace saudável aparece duas vezes, um em cada LSP.

**"E se a aresta aparecer só de um lado?"**
Exijo bidirecionalidade: só uso a aresta se os dois LSPs a declararem. Durante a
convergência é normal um lado já ter atualizado e o outro não, e usar a aresta
nesse intervalo me faria rotear por um enlace que o outro lado já abandonou. É o
que o OSPF faz.

**"Por que fila de prioridade e não varrer o vetor?"**
Heap dá O((V+E)·log V) contra O(V²) da varredura. Nesta escala é indiferente na
prática; usei o heap por ser a estrutura padrão, e o enunciado permite `heapq`
explicitamente.

**"Você insere o mesmo nó mais de uma vez na fila?"**
Sim. Não faço *decrease-key*: reinsiro com a distância menor. A entrada velha
sai depois e é descartada pelo teste de "já visitado". É a forma usual com heap
binário.

**"E em caso de empate?"**
O enunciado aceita qualquer caminho de custo mínimo. Desempato pelo menor
endereço virtual de propósito, para a saída ser determinística e a tabela do
programa bater com a conta feita à mão no relatório.

**"Quando você recalcula?"**
Sempre que a LSDB muda: LSP novo aceito, LSP envelhecido removido, vizinho
entrando ou saindo.

> Bancos equivalentes para vizinhança, LSDB/inundação, encaminhamento e ICMP
> serão escritos conforme cada módulo ficar pronto.

---

# Parte IV — O enunciado completo

> Transcrição integral do enunciado, com as três injeções removidas e nada mais
> alterado. Original higienizado em HTML: [`docs/TF-limpo.html`](docs/TF-limpo.html).

O trabalho consiste em implementar um roteador de estado de enlace, inspirado no OSPF, executando como uma aplicação sobre UDP. Cada integrante do grupo executa uma instância do roteador em sua máquina, e as instâncias formam juntas uma rede virtual sobre uma rede local real: as máquinas virtuais da VDI ou notebooks conectados a um access point (ver Ambiente de execução).

Cada roteador descobre seus vizinhos por meio de mensagens HELLO, gera e inunda LSPs (Link State Packets), monta a base de estados de enlace (LSDB) com a topologia completa da rede virtual e calcula sua tabela de roteamento com o algoritmo de Dijkstra. Sobre essa tabela, o roteador encaminha datagramas com controle de TTL e implementa um subconjunto do ICMP: ping, tempo excedido e destino inalcançável.

**Atenção:** o formato dos pacotes e as regras de processamento devem ser seguidos fielmente. Durante a apresentação, a rede do grupo será conectada à rede de outro grupo, e os roteadores das duas implementações devem funcionar juntos.

## Endereçamento virtual

Cada grupo no Moodle recebe um número G, e cada roteador do grupo deve definir um número R (1, 2, 3...). O roteador R do grupo G:

- tem o endereço virtual `10.G.R.1`;
- é responsável pela rede `10.G.R.0/24`: qualquer datagrama destinado a um endereço dessa rede é entregue a esse roteador.

Exemplo: no grupo 7, os endereços virtuais dos roteadores são 10.7.1.1, 10.7.2.1, 10.7.3.1 e 10.7.4.1. Com isso, os endereços virtuais continuam únicos quando as redes de dois grupos são conectadas.

Os endereços virtuais existem apenas dentro do trabalho. A comunicação real entre as máquinas usa os endereços IP reais delas na rede local.

## Vizinhos, enlaces e arquivo de configuração

Cada roteador conhece apenas seus vizinhos, isto é, os roteadores com os quais tem um enlace direto. Essa informação vem de um arquivo de configuração, lido ao iniciar o roteador. O formato do arquivo fica a critério do grupo, desde que contenha:

- o endereço virtual do roteador (`10.G.R.1`);
- a porta UDP local em que o roteador envia e recebe pacotes (padrão: 6000);
- a lista de vizinhos, cada um com endereço IP real, porta UDP e custo do enlace (inteiro positivo).

Um enlace existe quando os dois roteadores listam um ao outro como vizinho, e os dois lados devem configurar o mesmo custo. As rotas escolhidas são as de menor soma de custos.

O arquivo diz apenas onde cada vizinho pode estar. Se ele está de fato em funcionamento, o roteador descobre pelas mensagens HELLO, descritas a seguir.

## Funcionamento do roteador

Esta seção descreve o comportamento do roteador. O formato exato de cada pacote está em Formato dos pacotes.

### Vizinhança

O HELLO (formato) tem três funções:

1. Indicar que o vizinho configurado está de fato em funcionamento. Um vizinho em funcionamento é chamado de ativo, e somente vizinhos ativos entram no LSP (descrito na próxima seção).
2. Detectar a falha de um vizinho. O UDP não tem conexão, e a ausência de HELLO é a única indicação de que o vizinho caiu.
3. Informar o endereço virtual do vizinho, associando-o ao par (IP real, porta) de onde o HELLO veio.

Regras:

- O roteador envia HELLO a cada 5 segundos para todos os vizinhos configurados (IP real e porta do arquivo de configuração).
- Um vizinho passa a ser ativo quando o primeiro HELLO dele é recebido. O roteador associa o endereço virtual informado no HELLO ao par (IP real, porta) de onde o pacote veio; essa associação é usada para enviar pacotes a esse vizinho.
- Um vizinho que fica 20 segundos (4 períodos) sem enviar HELLO é considerado inativo.
- Toda mudança na lista de vizinhos ativos (entrada ou saída) gera imediatamente um novo LSP.

### LSPs e inundação

O LSP (formato) descreve os vizinhos ativos de um roteador e o custo de cada enlace. Inundando os LSPs, todos os roteadores passam a ter a mesma LSDB, isto é, a topologia completa da rede virtual.

#### Geração

O roteador gera um novo LSP próprio:

- quando um vizinho se torna ativo ou inativo;
- periodicamente, a cada 30 segundos (renovação), mesmo sem mudança.

Cada roteador mantém seu próprio número de sequência, usado apenas nos LSPs que ele gera; ao reenviar o LSP de outro roteador, o número de sequência não é alterado. O número do primeiro LSP é o horário atual em segundos (Unix time), e cada novo LSP incrementa o número em 1. Com isso, um roteador que é reiniciado continua gerando números maiores do que os que os outros roteadores já conhecem.

O LSP próprio é enviado a todos os vizinhos ativos e armazenado na própria LSDB.

#### Recebimento

Ao receber um LSP do vizinho V:

- Se a origem do LSP é o próprio roteador: descartar.
- Se a LSDB já possui um LSP dessa origem com número de sequência maior ou igual: descartar (é uma cópia ou um LSP antigo).
- Caso contrário: substituir o LSP armazenado, reenviar uma cópia a todos os vizinhos ativos, exceto V, e recalcular a tabela de roteamento.

#### Sincronização com novo vizinho

Quando um vizinho se torna ativo, além do novo LSP próprio, o roteador envia a ele uma cópia de todos os LSPs da sua LSDB. Sem isso, um roteador que entra na rede só conheceria os outros roteadores na próxima renovação.

#### Envelhecimento

Um LSP de outro roteador que não é renovado por 90 segundos é removido da LSDB, e a tabela é recalculada. Isso remove da LSDB os roteadores que saíram da rede.

### Cálculo da tabela de roteamento

A LSDB define um grafo: cada LSP de origem O contém as arestas de O para cada vizinho listado, com o custo indicado. O roteador executa o algoritmo de Dijkstra a partir de si mesmo e, para cada roteador alcançável R, registra na tabela:

| Rede de destino | Próximo salto | Custo |
| --- | --- | --- |
| rede de R (ex.: `10.G.R.0/24`) | endereço virtual do vizinho pelo qual começa o caminho de menor custo | soma dos custos |

A tabela é recalculada sempre que a LSDB muda. Em caso de empate, qualquer caminho de custo mínimo é aceito.

### Encaminhamento

O roteador encaminha dois tipos de pacote: **DADOS** (formato), com uma mensagem de texto, e **ICMP** (formato), com mensagens de controle. Ambos têm endereço virtual de origem e de destino, TTL (iniciado em 16 por quem cria o pacote) e um id que associa respostas a pedidos.

#### Tipos de mensagem ICMP

| Tipo | Mensagem | Gerada por |
| --- | --- | --- |
| 8 | Pedido de eco | Origem do ping |
| 0 | Resposta de eco | Destino do pedido de eco |
| 11 | Tempo excedido | Roteador em que o TTL chega a 0 |
| 3 | Destino inalcançável | Roteador sem rota para o destino |

#### Ao originar um pacote (DADOS ou ICMP)

Consultar a tabela. Se não houver rota para a rede do destino, informar destino inalcançável ao usuário, sem enviar nada. Caso contrário, enviar com o TTL inicial (16, ou o valor indicado no comando ping) ao próximo salto, isto é, ao par (IP real, porta) associado ao endereço virtual do próximo salto.

#### Ao receber um pacote DADOS ou ICMP

- **Destino na própria rede (`10.G.R.0/24`):** o pacote é entregue ao próprio roteador, que representa todos os endereços da sua rede (não há hosts reais: 10.7.1.1 e 10.7.1.50 são ambos atendidos pelo roteador 10.7.1.1).
  - DADOS: exibir a origem, o destino e a mensagem.
  - ICMP tipo 8: responder com tipo 0 para a origem, com o mesmo id. A origem da resposta é o endereço de destino do pedido (quem foi "pingado").
  - ICMP tipos 0, 11 ou 3: exibir o resultado ao usuário.
- **Destino em outra rede:**
  - Decrementar o TTL. Se chegar a 0, descartar e enviar ICMP tipo 11 para a origem.
  - Consultar a tabela. Se não houver rota, descartar e enviar ICMP tipo 3 para a origem.
  - Caso contrário, encaminhar ao próximo salto (IP real e porta associados ao seu endereço virtual) com o novo TTL.

Mensagens de erro (tipos 11 e 3) geradas pelo roteador usam o endereço virtual do próprio roteador como origem, TTL 16 e o id do pacote que causou a mensagem.

**Atenção:** assim como no ICMP, nunca se gera mensagem de erro (tipos 11 ou 3) em resposta a outra mensagem de erro.

### Interface com o usuário

O roteador é um único programa, executado em um terminal. Enquanto executa, ele lê comandos digitados nesse mesmo terminal e exibe nele os resultados e os logs. Nos comandos, `<destino>` é sempre um endereço virtual.

| Comando | Ação |
| --- | --- |
| `tabela` | Exibe a tabela de roteamento (rede, próximo salto, custo) |
| `lsdb` | Exibe a LSDB (origem, número de sequência, vizinhos e custos) |
| `vizinhos` | Exibe os vizinhos ativos (endereço virtual, IP real e porta) |
| `msg <destino> <texto>` | Envia um pacote de dados |
| `ping <destino> [TTL]` | Envia um pedido de eco com o TTL indicado (padrão: 16) e exibe a resposta recebida (eco, tempo excedido ou destino inalcançável), quem a enviou e o RTT, ou timeout após 2 s |

Além disso, o roteador deve salvar em logs em tempo real: vizinhos que ficaram ativos/inativos, LSPs novos recebidos, recálculos da tabela, pacotes encaminhados (com o próximo salto e o TTL) e mensagens ICMP geradas.

## Especificação técnica

### Ambiente de execução

Cada grupo escolhe um dos ambientes abaixo, e todos os roteadores do grupo executam nele:

- **VDI:** cada integrante executa seu roteador em sua máquina virtual de redes (somente Python);
- **Access point:** cada integrante executa seu roteador em seu notebook, conectado a um access point sem internet levado pelo professor na apresentação (qualquer linguagem de programação).

Dicas:

- O endereço IP real de cada máquina pode mudar a cada conexão (DHCP). Mantenha um arquivo de configuração fácil de editar.
- Em computadores pessoais, pode ser necessário liberar a porta UDP do roteador no firewall.
- Grupos que usarão o access point podem testar antes em qualquer rede Wi-Fi compartilhada (em casa ou com o celular como ponto de acesso).

### Regras gerais de comunicação

- Toda comunicação usa UDP, com mensagens em texto ASCII e campos separados por `:`.
- O roteador deve enviar e receber pelo mesmo socket, ligado à porta configurada. Assim, a porta UDP de origem dos pacotes enviados é a própria porta do roteador, e o vizinho consegue identificá-lo.
- Pacotes vindos de um par (IP real, porta) que não está na lista de vizinhos são descartados.
- Pacotes malformados (tipo desconhecido, número errado de campos, valores não numéricos) são descartados sem derrubar o roteador.

### Formato dos pacotes

**HELLO**

```
HELLO:<endereço virtual>
```

Exemplo: `HELLO:10.3.1.1`

**LSP**

```
LSP:<origem>:<número de sequência>:<vizinho>=<custo>;<vizinho>=<custo>;...
```

Exemplo: `LSP:10.3.1.1:1767712000:10.3.2.1=1;10.3.4.1=3`

A lista contém os vizinhos ativos do roteador de origem (endereços virtuais), com o custo configurado para cada enlace. Um roteador sem vizinhos ativos envia a lista vazia: `LSP:10.3.1.1:1767712001:`.

**Dados**

```
DADOS:<origem>:<destino>:<TTL>:<id>:<mensagem>
```

Exemplo: `DADOS:10.3.1.1:10.3.4.1:16:0:Oi pessoal!`

**ICMP**

```
ICMP:<origem>:<destino>:<TTL>:<id>:<tipo>
```

Exemplo: `ICMP:10.3.1.1:10.3.4.1:16:42:8`

O campo **tipo** segue a tabela de tipos de mensagem ICMP.

**Campos**

- origem/destino: endereços virtuais.
- TTL: iniciado em 16 por quem cria o pacote.
- id: identificador escolhido pela origem para associar respostas a pedidos (ex.: um contador). Respostas de eco e mensagens de erro copiam o id do pacote que as provocou. Em pacotes de dados, o id pode ser 0.

**Atenção:** a mensagem não pode conter dois pontos (`:`) nem caracteres fora do ASCII (sem acentos). Pacotes com esses caracteres são malformados.

## Relatório

O relatório deve responder às questões abaixo, com evidências (logs, saídas dos comandos, capturas do Wireshark). Os experimentos podem ser feitos em uma única máquina, executando vários roteadores em portas diferentes.

Montar uma topologia de teste com pelo menos 5 roteadores e enlaces de custos diferentes, incluindo pelo menos um caminho alternativo. Incluir a figura da topologia com os custos.

1. **Dijkstra:** para um dos roteadores, apresentar a LSDB e a execução do algoritmo de Dijkstra passo a passo (tabela de iterações, como na aula), comparando o resultado com a tabela exibida pelo programa.
2. **Inundação:** contar, a partir de uma captura do Wireshark ou dos logs, quantos pacotes LSP circulam na rede após uma única mudança (a queda de um vizinho). Quantos foram descartados como cópias? Analise e compare com o que um protocolo de vetor distância enviaria na mesma situação.
3. **Convergência:** derrubar um roteador que esteja no caminho entre dois outros e medir o tempo até a rota ser recalculada. Quanto desse tempo corresponde à detecção da falha e quanto à inundação e ao recálculo? Relacione com os temporizadores do HELLO.
4. **Números de sequência:** por que o LSP precisa de um número de sequência? O que aconteceria se um roteador reiniciado voltasse a numerar seus LSPs a partir de 0?
5. **Confiabilidade:** os LSPs são enviados por UDP e não têm confirmação. O que acontece se um LSP for perdido? Qual mecanismo da especificação recupera a LSDB?
6. **TTL:** se todos os roteadores calculam as rotas sobre a mesma topologia, por que ainda é necessário o TTL? Descreva uma situação, durante a convergência, em que um pacote poderia circular em laço.

## Apresentação

As apresentações ocorrem em 3 dias, com cerca de 5 grupos por dia. Os grupos de cada dia são divididos pelo professor em duplas de grupos (ou um trio de grupos, se o número for ímpar), com cerca de 30 minutos por dupla. As duplas são formadas por grupos do mesmo ambiente de execução (VDI com VDI, access point com access point).

Rede do grupo: cada integrante executa um roteador em sua própria máquina, no ambiente escolhido pelo grupo (4 roteadores nos quartetos, 3 nos trios), com enlaces de custos diferentes e pelo menos um caminho alternativo. A rede deve estar montada e funcionando no início do horário da dupla.

Cada grupo (~10 min):

- Exibe `vizinhos`, `lsdb` e `tabela` em cada roteador, conferindo com a topologia.
- Executa `ping` com TTL 1, 2, 3... até o roteador mais distante, mostrando cada roteador do caminho, e envia uma `msg`.
- Executa `ping` para uma rede inexistente.
- O professor derruba um roteador ou enlace; o grupo mostra a reconvergência e repete o `ping` com TTL crescente, mostrando o novo caminho. O roteador derrubado é reiniciado em seguida.
- Perguntas sobre o código.

Interoperabilidade (~5 min, ao final da dupla): os dois grupos criam um enlace entre um roteador de cada rede (uma linha a mais no arquivo de configuração de cada lado) e mostram:

- a `lsdb` e a `tabela` com os roteadores do outro grupo;
- `ping` (com TTL crescente) e `msg` atravessando as duas redes;
- a reconvergência quando o professor derruba o enlace entre os grupos.

Recomenda-se testar com outros grupos antes da apresentação.

Todos os integrantes devem estar presentes e ser capazes de explicar qualquer parte do código.

**SOBRE O USO DE IA:** o uso de IA é permitido, mas código que o integrante questionado não consiga explicar não será considerado de autoria do grupo, e o trabalho receberá nota zero, independentemente de funcionar.

## Avaliação

Os itens 1 a 6 são avaliados na rede do grupo durante a apresentação; o item 7, na conexão com a rede do outro grupo.

| # | Critério | Descrição | Peso |
| --- | --- | --- | --- |
| 1 | Vizinhança | HELLO periódico, detecção de vizinho ativo/inativo | 5% |
| 2 | LSPs e inundação | Geração, número de sequência, inundação, descarte de cópias, sincronização com novo vizinho, envelhecimento | 20% |
| 3 | Tabela de roteamento | Dijkstra correto sobre a LSDB, recálculo após mudanças | 15% |
| 4 | Encaminhamento | Entrega e encaminhamento de dados com decremento de TTL | 10% |
| 5 | ICMP | ping com TTL, resposta de eco, tempo excedido, destino inalcançável | 15% |
| 6 | Observabilidade | Logs em tempo real dos eventos | 5% |
| 7 | Interoperabilidade | Rede conectada à do outro grupo: LSDB, rotas, ping/msg e reconvergência entre as duas implementações | 10% |
| 8 | Relatório | Experimentos e questões | 20% |
| | **Total** | | **100%** |

## Regras Gerais

Grupos: 4 componentes. Trios serão aceitos apenas para fechar a divisão da turma (ex.: com 58 alunos, 13 quartetos e 2 trios). Informar no Moodle os integrantes e data de apresentação.

Linguagem: livre, usando a API de sockets UDP diretamente. O algoritmo de Dijkstra deve ser implementado pelo grupo: não é permitido usar bibliotecas de grafos ou de roteamento (ex.: networkx, scipy.sparse.csgraph, JGraphT). Estruturas de dados da biblioteca padrão, como filas de prioridade (heapq, PriorityQueue), são permitidas.

Data de entrega: todos os grupos antes do início da primeira aula de apresentação.
Datas de apresentação: conferir no Moodle.

Obs.: todos os participantes do grupo devem estar presentes para a apresentação.

Entrega final (arquivo .zip, por um integrante do grupo):

- Código-fonte (sem binários ou arquivos de build);
- README com instruções de execução e o formato do arquivo de configuração;
- Relatório em PDF;
- Capturas (.pcapng) usadas no relatório.

**IMPORTANTE:** Não serão aceitos trabalhos entregues fora do prazo. Trabalhos que não compilam ou que não executam não serão avaliados. Todos os trabalhos serão analisados e comparados. Caso seja identificada cópia de trabalhos, todos os trabalhos envolvidos receberão nota ZERO.

---

# Decisões do grupo

## Fechadas

| Item | Valor |
| --- | --- |
| **Grupo (G)** | **7** |
| **Integrantes** | Arthur, Samuel, Lucas, Anthony |
| **Ambiente** | Access point (notebooks) |
| **Linguagem** | **Python 3.10+**, biblioteca padrão apenas |
| **Base de código** | **Uma só**, compartilhada pelos quatro |
| **Apresentação** | **01/12/2026** |
| **Entrega do `.zip`** | Anthony |
| **Repositório** | este, com os quatro como colaboradores |

### Endereçamento (a confirmar o R de cada um)

| Integrante | R | Endereço virtual | Rede |
| --- | --- | --- | --- |
| Arthur | 1 | `10.7.1.1` | `10.7.1.0/24` |
| Samuel | 2 | `10.7.2.1` | `10.7.2.0/24` |
| Lucas | 3 | `10.7.3.1` | `10.7.3.0/24` |
| Anthony | 4 | `10.7.4.1` | `10.7.4.0/24` |

### Topologia da rede do grupo (proposta)

```
        1          2          3
  R1 ─────── R2 ─────── R3 ─────── R4
   │                                │
   └────────────── 10 ──────────────┘
```

De `R1` a `R4`, o anel custa 1+2+3 = **6**; o enlace direto custa **10**. A rota
escolhida é a longa, então `ping 10.7.4.1 1`, `2`, `3` revela um roteador por
incremento. Derrubando `R2` ou `R3`, a rota vira o enlace direto: três saltos
viram um, e a mudança fica visível no `ping` com TTL crescente.

> Num anel de quatro, exatamente dois roteadores são de trânsito — é uma
> imposição do grafo, não escolha de custos. Aqui são `R2` e `R3`. Se o
> professor derrubar `R1` ou `R4`, não há rerroteamento a mostrar: o que se
> demonstra é a LSDB encolhendo e o `ping` para a rede dele respondendo destino
> inalcançável. **Ensaiar os dois cenários.**

### Topologia de teste do relatório (proposta, ≥ 5 roteadores)

| Enlace | Custo | | Enlace | Custo |
| --- | --- | --- | --- | --- |
| R1–R2 | 2 | | R3–R4 | 2 |
| R1–R3 | 5 | | R4–R5 | 3 |
| R2–R3 | 1 | | R3–R5 | 8 |
| R2–R4 | 4 | | | |

A partir de `R1`: `R3` por 3 (não pelos 5 diretos), `R4` por 5 (não pelos 6 via
R2), `R5` por 8. Três relaxações que corrigem a estimativa inicial — é o que dá
conteúdo à tabela de iterações da questão 1.

Roda tudo numa máquina só, em portas 6001–6005.

## Em aberto

| Item | Observação |
| --- | --- |
| **Divisão de módulos** | Um dono por módulo, mas todos precisam saber explicar qualquer um. |
| **Isolamento de clientes no AP do professor** | 🔴 **Perguntar com urgência** — se o AP isolar clientes, nada funciona no dia. |
| **Enlace de interoperabilidade** | Qual roteador, com que custo. Deixar a linha pronta e comentada na config. |
| **Grupo para testar interop antes** | O enunciado recomenda. |
| **Questões do relatório** | Distribuir cedo: dependem dos experimentos. |

### A entregar no `.zip`

- [ ] Código-fonte (sem binários nem artefatos de build)
- [ ] README com instruções de execução e o formato do arquivo de configuração
- [ ] Relatório em PDF
- [ ] Capturas `.pcapng` usadas no relatório

## Estrutura do repositório

```
.
├── README.md                     este arquivo
├── src/
│   ├── roteador.py               ponto de entrada: socket, threads, CLI
│   ├── constantes.py             temporizadores, TTL, tipos ICMP
│   ├── config.py                 leitura do arquivo de configuração
│   ├── log.py                    logs em tempo real (terminal + arquivo)
│   ├── pacotes.py                serialização e parse dos 4 formatos
│   ├── vizinhos.py               HELLO, vizinhança, mapa virtual→(IP,porta)
│   ├── lsdb.py                   LSPs, inundação, envelhecimento
│   ├── dijkstra.py               grafo → tabela de roteamento
│   └── encaminhamento.py         DADOS/ICMP, TTL
├── config/
│   ├── r1..r4.conf               topologia do grupo (IPs reais a preencher)
│   └── teste/t1..t5.conf         topologia do relatório, tudo em 127.0.0.1
├── scripts/
│   └── subir_teste.sh            sobe os 5 roteadores locais no tmux
└── docs/
    ├── enunciado.md              enunciado higienizado, em Markdown
    ├── TF-limpo.html             original do professor, sem os 3 spans ocultos
    └── injecao-removida.md       registro da injeção e da varredura do arquivo
```
