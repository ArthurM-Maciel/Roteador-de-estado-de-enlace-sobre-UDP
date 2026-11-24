# Como testar o roteador

Passo a passo dos testes que o grupo já rodou. Todos os comandos abaixo foram executados de
verdade (Windows 10 com PowerShell, e macOS no teste de rede real), e os resultados esperados
são os que apareceram nesses testes.

Todos os comandos rodam a partir da pasta do projeto, a que tem `src/`, `config/` e `tests/`.

## 0. O que precisa

- Python 3 (no Windows `python`, no Mac `python3`).
- Para as capturas: Wireshark com Npcap. No Windows ele cria a interface
  "Adapter for loopback traffic capture", que captura o tráfego entre roteadores na mesma máquina.

## 1. Testes automáticos

```powershell
python -m unittest discover -s tests -b
```

Esperado: `Ran 63 tests` e `OK`. Leva uns 10 s, porque um dos testes sobe 3 roteadores de verdade.

## 2. Cinco roteadores na mesma máquina

Topologia: arquivos `config/teste/t1.conf` a `t5.conf`, todos em 127.0.0.1, portas 6001 a 6005.

| Enlace | R1–R2 | R1–R3 | R2–R3 | R2–R4 | R3–R4 | R4–R5 | R3–R5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Custo | 2 | 5 | 1 | 4 | 2 | 3 | 8 |

Abra 5 janelas do PowerShell, entre na pasta do projeto em cada uma, e rode um roteador por janela:

```powershell
python src\roteador.py config\teste\t1.conf
```

```powershell
python src\roteador.py config\teste\t2.conf
```

```powershell
python src\roteador.py config\teste\t3.conf
```

```powershell
python src\roteador.py config\teste\t4.conf
```

```powershell
python src\roteador.py config\teste\t5.conf
```

Se o Windows perguntar sobre o firewall, clique em Permitir.

Espere uns 15 s e digite no R1 (janela do t1):

| Comando | Resultado esperado |
| --- | --- |
| `vizinhos` | 10.7.2.1 (porta 6002, custo 2) e 10.7.3.1 (porta 6003, custo 5) |
| `lsdb` | 5 linhas, uma por roteador, com os vizinhos e custos da tabela acima |
| `tabela` | 10.7.2.0/24 custo 2, 10.7.3.0/24 custo 3, 10.7.4.0/24 custo 5, 10.7.5.0/24 custo 8, todas pelo próximo salto 10.7.2.1 |
| `ping 10.7.5.1 1` | tempo excedido de 10.7.2.1 |
| `ping 10.7.5.1 2` | tempo excedido de 10.7.3.1 |
| `ping 10.7.5.1 3` | tempo excedido de 10.7.4.1 |
| `ping 10.7.5.1 4` | resposta de eco de 10.7.5.1 |
| `msg 10.7.5.1 Oi pessoal` | a mensagem aparece na janela do t5 |
| `ping 10.7.9.1` | destino inalcançável (rede que não existe) |

Para encerrar um roteador, digite `sair`.

## 3. Derrubar um roteador e capturar (questões 2 e 3 do relatório)

Os logs são gravados em `logs/` em modo de **acréscimo**. Antes de cada experimento, arquive os logs
do experimento anterior (com os roteadores fechados, senão o Windows não deixa mover):

```powershell
New-Item -ItemType Directory -Force evidencias\queda_r4
```

```powershell
Move-Item logs\t*.log evidencias\queda_r4\
```

Passos:

1. Suba os 5 roteadores (seção 2) e espere uns 30 s.
2. Descubra o número da interface de loopback (no nosso PC foi a 6, "Adapter for loopback traffic capture"):

   ```powershell
   & "C:\Program Files\Wireshark\tshark.exe" -D
   ```

3. Numa sexta janela, comece a captura, que para sozinha depois de 40 s. Troque o `6` pelo número
   encontrado no passo 2:

   ```powershell
   & "C:\Program Files\Wireshark\tshark.exe" -i 6 -f "udp portrange 6001-6005" -a duration:40 -w capturas\queda_r4.pcapng
   ```

4. Em até 5 s, digite `sair` na janela do roteador que vai cair (o t4 neste exemplo).
5. Não digite nada nos outros roteadores até a captura terminar.
6. Depois, no R1: `tabela`, `ping 10.7.5.1 1`, `2`, `3` e `ping 10.7.4.1`.

Resultado esperado (queda do R4):

- Entre 15 s e 20 s depois do `sair`, os vizinhos do R4 mostram `10.7.4.1 INATIVO -- sem HELLO ha mais de 20s`.
- A tabela do R1 fica: 10.7.2.0/24 custo 2, 10.7.3.0/24 custo 3, 10.7.5.0/24 custo 11, sem rota para 10.7.4.0/24.
- `ping 10.7.5.1` com TTL 1, 2 e 3: tempo excedido de 10.7.2.1, tempo excedido de 10.7.3.1, resposta de eco de 10.7.5.1.
- `ping 10.7.4.1`: destino inalcançável.
- Uns 90 s depois, o log mostra `envelhecido: 10.7.4.1 removido da LSDB`.

Para religar o roteador, rode de novo o mesmo comando na janela dele. O R1 volta a vê-lo em poucos segundos
(foram 3,2 s quando religamos o R3).

## 4. Analisar a captura e os logs

**No Wireshark:** abra o `.pcapng` e aplique o filtro `frame contains "LSP:"`. Para ver a hora do dia na
coluna Time, use no menu **Exibir** a opção de formato de exibição do tempo (*Time Display Format*, no Wireshark
em inglês). Cada roteador é identificado pela
porta: R1 = 6001, R2 = 6002, R3 = 6003, R4 = 6004 e R5 = 6005. Clicando num pacote, o conteúdo aparece na
parte de baixo (por exemplo, `LSP:10.7.5.1:1795525723:10.7.3.1=8`).

**Nos logs** (PowerShell), para achar os momentos da queda:

```powershell
Select-String -Path evidencias\queda_r4\t*.log -Pattern "INATIVO"
```

```powershell
Select-String -Path evidencias\queda_r4\t1.log -Pattern "tabela recalculada"
```

```powershell
Select-String -Path evidencias\queda_r4\t*.log -Pattern "descartado: copia"
```

O último comando lista **todos** os descartes do arquivo, desde que o roteador subiu. Para a questão 2,
conte só os descartes com horário dentro da janela da queda.

Os números que medimos estão em `evidencias/resumo_experimentos.md` e no relatório.

## 5. Rede real com duas máquinas

Testado com um PC Windows (192.168.15.10) como R3 e um MacBook (192.168.15.4) como R4, na mesma rede de casa.
Os IPs mudam a cada conexão (DHCP), então confira os seus antes.

1. **Descobrir os IPs.** No Windows, `ipconfig`. No Mac:

   ```bash
   ipconfig getifaddr en0
   ```

2. **Liberar a porta 6000 no firewall do Windows.** Isso é necessário se a rede estiver como "Pública".
   Rode no PowerShell **como administrador**:

   ```powershell
   New-NetFirewallRule -DisplayName "Roteador UDP 6000" -Direction Inbound -Protocol UDP -LocalPort 6000 -Action Allow
   ```

3. **Copiar a pasta do projeto para a segunda máquina** e entrar nela.

4. **Configurar.** Em cada máquina, troque o IP do vizinho pelo IP real da outra máquina:
   - na máquina do R3, em `config/dois_pcs_r3.conf`, coloque o IP da máquina do R4;
   - na máquina do R4, em `config/dois_pcs_r4.conf`, coloque o IP da máquina do R3.

   Exemplo do arquivo do R4:

   ```
   endereco 10.7.4.1
   porta 6000
   vizinho 10.7.3.1 <IP da máquina do R3> 6000 3
   ```

5. **Subir os dois.** Na máquina do R3 (Windows):

   ```powershell
   python src\roteador.py config\dois_pcs_r3.conf
   ```

   Na máquina do R4 (Mac):

   ```bash
   python3 src/roteador.py config/dois_pcs_r4.conf
   ```

Esperado: em 1 ou 2 s aparece `ATIVO` nos dois lados. `tabela` mostra a rede do outro com custo 3.
`ping 10.7.4.1` (no R3) e `ping 10.7.3.1` (no R4) respondem, e `msg 10.7.4.1 oi` enviada do R3 aparece no R4.

## 6. Rede do grupo com 4 máquinas (ainda não testada)

Arquivos `config/r1.conf` a `r4.conf`: R1 Arthur, R2 Samuel, R3 Lucas e R4 Anthony, em anel com custos
R1–R2 = 1, R2–R3 = 2, R3–R4 = 3 e R4–R1 = 10. Troque cada `PREENCHER` pelo IP real do vizinho.
Com `PREENCHER` no arquivo, o roteador **não sobe**. Ele mostra, por exemplo,
`erro na subida: config/r3.conf:9: IP invalido: 'PREENCHER'` e encerra.
Todos precisam liberar a porta UDP 6000 no firewall.

## Problemas que já encontramos

| Sintoma | Causa |
| --- | --- |
| Logs de testes diferentes misturados | O log é aberto em modo de acréscimo. Arquive `logs\*.log` antes de cada experimento. |
| `Move-Item` falha nos logs | O roteador ainda está aberto. Digite `sair` em todos antes. |
| Filtro do `tshark` com aspas não funciona no PowerShell | O PowerShell 5.1 tira as aspas internas. Use o filtro no Wireshark gráfico. |
| Roteador não sobe com `config/r*.conf` | Ainda tem `PREENCHER` no lugar de um IP. |
