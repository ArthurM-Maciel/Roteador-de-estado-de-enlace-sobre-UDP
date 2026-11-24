# Resumo dos experimentos (dados extraídos dos arquivos)

Topologia de teste: `config/teste/t1..t5.conf`, tudo em 127.0.0.1, portas 6001-6005.
Custos: R1-R2=2, R1-R3=5, R2-R3=1, R2-R4=4, R3-R4=2, R4-R5=3, R3-R5=8.
Horários em hora local da máquina, 24-11-2026. Captura: tshark na interface
"Adapter for loopback traffic capture", filtro `udp portrange 6001-6005`.

Fontes:
- Experimento 1 (queda do R3): `capturas/queda_r3.pcapng` e `evidencias/queda_r3/t*.log`
- Experimento 2 (queda do R4): `capturas/queda_r4.pcapng` e `logs/t*.log` (mover para
  `evidencias/queda_r4/` quando encerrar os roteadores)

## Experimento 1 — queda do R3 (`sair` no t3)

| Evento | Horário |
| --- | --- |
| Último HELLO enviado pelo R3 (captura) | 09:56:48.975 |
| `sair` no R3 (`t3.log`, "encerrado") | 09:56:53.365 |
| Primeira detecção (R1 marca R3 INATIVO) | 09:57:09.023 |
| Última detecção (R4) | 09:57:09.695 |
| Tabela final do R1, sem 10.7.3.0/24 | 09:57:09.696 |

- Detecção: 20,05 s após o último HELLO (15,7 s após o `sair`).
- Inundação + recálculo: 0,67 s (primeira detecção até a tabela final do R1).
- Total: 16,3 s após o `sair`; 20,7 s após o último HELLO.
- LSPs na janela 09:57:09.02-09:57:09.70: **18 pacotes**; 4 LSPs novos (R1, R2, R4, R5);
  6 enviados ao R3 já morto; **0 descartados como cópia** (nenhuma linha "descartado" nos
  logs dessa janela). Sobram R1-R2-R4-R5 em linha, sem ciclo, por isso não há cópias.
- Rota nova do R1 até o R5: via R2, custo 9 (antes: via R2, custo 8).
- Reinício do R3 (09:59:21.446): R1 vê o R3 ativo às 09:59:22.449; tabela final do R1
  igual à original às 09:59:24.604 (3,2 s). Tabelas transitórias do R1 no caminho:
  10.7.3.0/24 com custo 17, depois 8, depois 3.

## Experimento 2 — queda do R4 (`sair` no t4)

| Evento | Horário |
| --- | --- |
| Último HELLO enviado pelo R4 (captura) | 10:10:54.765 |
| `sair` no R4 (`t4.log`, "encerrado") | 10:10:55.451 |
| Primeira detecção (R5) | 10:11:14.853 |
| Detecção R3 / R2 (última) | 10:11:15.464 / 10:11:15.756 |
| Tabela final do R1, sem 10.7.4.0/24 | 10:11:15.757 |

- Detecção: 20,09 s após o último HELLO (19,4 s após o `sair`).
- Inundação + recálculo: 0,90 s (primeira detecção até a tabela final do R1).
- Total: 20,3 s após o `sair`; 21,0 s após o último HELLO.
- LSPs na janela 10:11:14.85-10:11:15.76: **18 pacotes**; 3 LSPs novos (R5, R3, R2);
  3 enviados ao R4 morto; 15 entregues = 9 aceitos + **6 descartados como cópia**
  (t1: 3, t2: 2, t3: 1 nos logs). Sobra o triângulo R1-R2-R3 (com ciclo) mais o R5.
- Tabela do R1 depois: 10.7.2.0/24 via 10.7.2.1 custo 2; 10.7.3.0/24 via 10.7.2.1 custo 3;
  10.7.5.0/24 via 10.7.2.1 custo 11 (antes 8). Sem rota para 10.7.4.0/24.
- Tabelas transitórias: R1 para 10.7.4.0/24: custo 5 -> 6 -> sem rota.
  R5 para 10.7.4.0/24: custo 10 -> 13 -> sem rota.
- `ping 10.7.5.1` com TTL 1/2/3 no R1: tempo excedido de 10.7.2.1, tempo excedido de
  10.7.3.1, resposta de eco de 10.7.5.1 (tela do usuário).
- `ping 10.7.4.1`: "destino inalcancavel: sem rota para 10.7.4.0/24" (tela do usuário),
  antes de o LSP do R4 envelhecer da LSDB.
- Envelhecimento: "10.7.4.1 removido da LSDB (sem renovacao ha mais de 90s)" às 10:12:07.932
  (log do R1, tela do usuário).

## Experimento 3 — rede real, 2 máquinas (PC Windows = R3, Mac = R4)

Configs: `config/dois_pcs_r3.conf` e `config/dois_pcs_r4.conf` (PC 192.168.15.10, Mac
192.168.15.4, porta 6000, enlace R3-R4 custo 3). Fonte: `logs/dois_pcs_r3.log` (lado do PC).

- 10:27:58.120 R3 sobe; 10:27:59.031 vê o R4 ATIVO (menos de 1 s depois).
- 10:27:59.032 gera LSP com R4=3; 10:27:59.034 sincroniza; 10:27:59.132 recebe o LSP do R4
  e recalcula: `10.7.4.0/24 -> 10.7.4.1 (3)`.
- Renovação de 30 s do R3 em 10:28:29, 10:28:59, 10:29:29... (seq 1795526880, 881, 882...).
- 10:29:27.630 o R3 responde a um eco vindo do R4 (id 1).
- 10:30:04.216 o R3 envia ping ao R4 (TTL 16, id 1); 10:30:19.983 envia `msg` (DADOS id 2).
- O usuário relatou que `vizinhos`, `tabela`, `ping` e `msg` funcionaram nos dois lados
  (as saídas dos comandos estão só na tela, não no log).
- Observação: o primeiro seq do R4 (1795526968) é ~90 s maior que o do R3 (1795526878),
  ou seja, o relógio do Mac está ~90 s adiantado em relação ao do PC. Não afeta o protocolo.
