# Notas de sessão — Voron Trident (MMX / Happy Hare)

> Documento de contexto para futuras sessões. Resume o que foi diagnosticado e corrigido,
> o que ficou pendente, e armadilhas conhecidas desse setup específico.
> Última atualização: sessão de 2026-08-02.
>
> Ver também [`CLAUDE.md`](../CLAUDE.md) na raiz do repositório: idioma padrão
> (sempre português) e cuidados gerais válidos pra qualquer impressora deste Pi
> multi-instância (nomes de serviço, backup automático, symlinks, etc.).

## Visão geral do hardware

- **Impressora:** Voron Trident, cinemática CoreXY, mesa 300x300 (bed 285x285 útil).
- **Placa principal:** referenciada como `Fly-D7` no config, conectada via CANbus.
- **Host:** BTT Pi v1.2, rodando Armbian (CB1, `sun50i-h616`), sistema atualizado durante
  esta sessão para Armbian 26.5.1 Bookworm.
- **Cabeçote:** A4T-AFC com cortador de filamento embutido (corte por movimento X/Y numa
  alavanca física, **não** é um servo) e hotend Bambu Lab.
- **Toolboard do cabeçote:** BTT EBB36 (extrusora, fans, endstop X), conectada via CANbus.
- **Nivelamento:** BTT Eddy (sonda de corrente parasita, `probe_eddy_current`), via CANbus.
  3 motores de Z independentes (`z_tilt`, não quad_gantry_level).
- **Motores X/Y:** SIBOOR-42STH48-2404 (nominal **2.4A** por fase, confirmado em
  docs.siboor.com).
- **MMU:** MMX de 4 gates (Happy Hare, `mmu_vendor: MMX`), seletor por servo, **sem
  encoder**, **sem sensor de tensão/compressão (sync-feedback)**, **sem buffer físico de
  filamento** (alimentação direta do carretel).
- **Fatiador:** OrcaSlicer, integração oficial Happy Hare (`MMU_START_SETUP` /
  `_MMU_PRE_T_CODE` + `Tn` + `_MMU_POST_T_CODE` / `MMU_END`).

## ⚠️ Este Pi tem 4 impressoras (importante!)

O BTT Pi hospeda **4 instâncias Klipper** que compartilham **um único** `~/klipper` e
**um único** `~/Happy-Hare`:

- `printer_data` (instância padrão)
- `printer_Ender3_data`
- `printer_outra_data`
- `printer_Trident_data` ← esta é a Trident

**Só a Trident usa Happy Hare/MMU.** Qualquer mudança no `~/klipper` (ex: reverter uma
versão) afeta as 4 impressoras — nunca mexer nisso sem considerar as outras 3.

Os nomes reais dos serviços systemd (confirmados via `systemctl list-units`):

- `klipper-Trident.service` (⚠️ **não** existe `klipper.service` sozinho nesse Pi)
- `moonraker-Trident.service`

O `moonraker.conf` da Trident tinha `managed_services: klipper` (nome errado) em duas
seções — já corrigido para `klipper-Trident`.

## Estrutura do repositório (pasta `trident/`)

Reorganizado numa sessão anterior (v3). **Atualizado no item 16 (2026-09-06) pra
migração Happy Hare v4** — estrutura atual:

```
trident/
├── printer.cfg          # Includes, [mcu] (só a placa principal agora), [printer], SAVE_CONFIG
├── toolhead.cfg          # EBB36 (extrusora/fans/tmc) + Eddy (sonda) — fundidos aqui
├── steppers.cfg          # stepper_x/y/z/z1/z2 + tmc2209 + adxl345/resonance_tester
├── bed_leveling.cfg      # safe_z_home, z_tilt, bed_mesh
├── heaters_fans.cfg      # sensores de temperatura, heater_bed, controller_fan
├── misc.cfg              # idle_timeout, virtual_sdcard, exclude_object
├── macros.cfg            # PRINT_START, PRINT_END, LIMPAR_BICO, CORTE_FILAMENTO, _MMU_PURGE_CUSTOM
├── mainsail.cfg           # symlink real no Pi (aqui aparece só como texto do caminho)
├── moonraker.conf
├── mmu.V3/                # BACKUP da config v3 inteira (criado automaticamente pelo install.sh
│                            na migração pra v4) — histórico, NÃO editar/usar.
└── mmu/                   # Config v4, gerada pelo assistente interativo (menuconfig)
    ├── .mmu_config        # Estado salvo do menuconfig (não editar manualmente)
    ├── base/              # mmu.cfg, mmu_hardware_unit0.cfg, mmu_parameters_unit0.cfg,
    │                        mmu_macro_vars.cfg — arquivos REAIS e editáveis. O sufixo
    │                        "_unit0" é novo na v4 (suporte a múltiplas unidades MMU).
    ├── macros/            # NOVO na v4 — mmu_cut_tip.cfg, mmu_form_tip.cfg, mmu_purge.cfg,
    │                        mmu_sequence.cfg, mmu_software.cfg, mmu_state.cfg, mmu_misc.cfg,
    │                        mmu_heater_vent.cfg, mmu_servo_cutter.cfg, mmu_fan_control.cfg,
    │                        blobifier.cfg (não usado) — todos SYMLINKS reais no Pi (aqui
    │                        aparecem só como texto do caminho). NÃO adianta editar esses
    │                        no repo, o conteúdo real está no Pi.
    └── optional/
```

**Não usados / desativados de propósito** (comentados no `printer.cfg`):
- `mmu/addons/blobifier.cfg` — usuário não tem a bandeja/balde físico do Blobifier.
- `mmu/addons/mmu_erec_cutter.cfg` — não usado, corte é feito no cabeçote (X/Y), não na MMU.

Existe uma branch de backup pré-sessão no remoto: `backup/trident-antes-ajustes-2026-08-02`
(snapshot do estado antes de qualquer mudança desta sessão).

O repositório tem um **cron de backup automático rodando no Pi** que commita e dá push
periodicamente (commits "Backup automático: DATA"). **Sempre rodar `git pull --rebase`
antes de editar**, pois o remoto pode estar um pouco à frente.

## O que foi corrigido nesta sessão (cronológico)

### 1. Geometria do toolhead MMX (bico empurrando filamento sem a extrusora girar)
Medido fisicamente pelo usuário. Corrigido em `mmu/base/mmu_parameters.cfg`:
- `toolhead_sensor_to_nozzle`: 101 → **83** (estava 18mm longo demais — causava
  sobre-inserção, travando a extrusora enquanto o gear da MMX continuava empurrando)
- `toolhead_extruder_to_nozzle`: 92 → **93**
- `toolhead_entry_to_extruder`: 8 (já estava certo)

### 2. Purga fazendo bola de filamento na mesa
Causa: `purge_macro` apontava pra `_MMU_PURGE` padrão do Happy Hare, que purga onde o
bico já estiver parado (não move sozinho). Corrigido:
- `mmu_parameters.cfg`: `purge_macro: _MMU_PURGE` → **`_MMU_PURGE_CUSTOM`**
- `macros.cfg`: `_MMU_PURGE_CUSTOM` agora move pro balde (X10,Y310) e chama `_MMU_PURGE`
  **diretamente** (não `MMU_PURGE`, que causaria recursão infinita se fosse a purge_macro
  configurada).

### 3. Crash total após atualizar Klipper + Happy Hare + KlipperScreen + Armbian (grande)
Sintoma: nenhuma placa conectava (principal, EBB36, MMX), todas via CAN.

- **Não era hardware/CAN** — barramento estava saudável (`ip -s -d link show can0` com
  tráfego real, zero erros).
- **Causa raiz #1:** `moonraker.conf` não tinha `install_script:` na seção
  `[update_manager happy-hare]` → atualização só deu `git pull`, nunca rodou
  `~/Happy-Hare/install.sh` → módulos Python do Happy Hare dentro do Klipper ficaram
  desatualizados/incompatíveis com o Klipper novo → crash (`AttributeError` no
  `reactor.py`).
  - **Correção:** rodado manualmente
    `cd ~/Happy-Hare && ./install.sh -c ~/printer_Trident_data/config`
    (flag `-c` necessária por ser Pi multi-instância).
- **Causa raiz #2:** `managed_services: klipper` (nome de serviço errado, ver seção
  acima) em `[update_manager happy-hare]` e `[update_manager mainsail-config]`.
  - **Correção:** trocado pra `klipper-Trident` nas duas seções, e adicionado
    `install_script: install.sh` na seção happy-hare pra não repetir a causa raiz #1.
- **Causa raiz #3 (a de verdade, mais recente):** incompatibilidade real Klipper × Happy
  Hare. O Klipper passou a proibir pausar o reactor (`assert_no_pause`) durante o
  callback de "ready" — mas o Happy Hare (`mmu.py`, `handle_ready()`) chama
  `_load_persisted_state()` de forma síncrona bem nesse momento, o que dispara um
  `SAVE_VARIABLE` bloqueante → `reactor.ReactorError: Internal error - reactor pause
  disabled`.
  - **Correção aplicada (PATCH LOCAL):** em
    `/home/biqu/klipper/klippy/extras/mmu/mmu.py`, linha ~949, trocado:
    ```python
    self._load_persisted_state()
    ```
    por:
    ```python
    self.printer.get_reactor().register_callback(lambda et: self._load_persisted_state())
    ```
    (adia a chamada pra depois do "ready" terminar — é exatamente o padrão que o próprio
    time do Klipper recomenda pra quem escreve extensões, confirmado no Klipper
    Discourse "Prevention of reactor pause").
  - Backup do arquivo original salvo como `mmu.py.bak-prepatch` na mesma pasta.
  - **⚠️ PENDENTE / ARMADILHA:** esse patch é local, direto no arquivo instalado. Da
    próxima vez que `~/Happy-Hare/install.sh` rodar (próxima atualização do Happy Hare),
    esse arquivo é sobrescrito e o crash pode voltar — **até o Happy Hare lançar uma
    correção oficial pra essa mudança do Klipper**. Vale conferir o changelog/GitHub do
    Happy Hare antes da próxima atualização, ou reaplicar o mesmo patch.

- **Efeito colateral do `install.sh`:** ele regravou `mmu_macro_vars.cfg` e removeu uma
  macro customizada (`_MMU_PURGE_EXTENSION`, que chamava `LIMPAR_BICO` após a purga) —
  não preservada porque não é uma `variable_` reconhecida pelo merge do instalador.
  - **Correção:** a chamada de `LIMPAR_BICO` foi movida pra dentro de
    `_MMU_PURGE_CUSTOM` em `macros.cfg` (arquivo do usuário, nunca tocado pelo
    instalador — sobrevive a futuras atualizações).

### 4. Corte de filamento não funcionava (alavanca não se movia / batia e perdia passo)
Diagnosticado em `mmu/base/mmu_macro_vars.cfg` (`_MMU_CUT_TIP_VARS`):
- `variable_pin_loc_xy`: Y 284 → **286** (posição física remedida pelo usuário)
- `variable_pin_park_dist`: **5.0 → -5.0** — o próprio comentário do arquivo diz que
  cabeçotes A4T-A4C (corte no eixo Y em direção a Ymax) precisam de valor **negativo**;
  estava positivo, fazendo a cabeça iniciar o movimento de corte já em cima da alavanca
  em vez de ganhar distância de segurança antes.
- `variable_cut_fast_move_fraction`: **1.0 → 0.85** — estava fazendo 100% do movimento
  de corte na velocidade rápida, sem parte lenta controlada pro toque final na alavanca.
- **Resultado confirmado pelo usuário: corte funcionando perfeitamente.**

### 5. Ramming do OrcaSlicer deformando a ponta do filamento antes da MMU cortar
Sintoma: no meio de impressão, MMX puxava muito filamento sem cortar, ponta deformada
travava no hotend. **Causa não era do Happy Hare** — era o próprio OrcaSlicer fazendo
ramming automático (~94mm de retração crua via `G1 E-`) antes do `_MMU_PRE_T_CODE`,
por causa do modo "Multimaterial com Extrusora Única".

**Correção no OrcaSlicer** (fora deste repositório, feita pelo usuário):
- Impressora → Multimaterial: `Posição/Comprimento do tubo de resfriamento`,
  `Posição de estacionamento`, `Distância de carregamento extra` → todos zerados.
- Filamento → Multimaterial: volume de ramming (ainda em 10, não crítico — já gera só um
  recuo normal de ~2mm, não os 94mm de antes. Pode zerar totalmente se quiser alinhar
  100% com a recomendação oficial do Happy Hare, mas não é urgente).
- Verificado no gcode gerado (`Montagem_PLA_5m10s.gcode`): bloco de ramming sumiu.

### 6. Fim de impressão não desligava motores e bico reaquecia
- `macros.cfg` → `PRINT_END`: reativado `M84` no final (tinha sido removido com um
  comentário "para não perder home", mas o `PRINT_START` já faz `G28` completo no
  início de toda impressão, então isso nunca foi um problema real).
- **⚠️ PENDENTE (ação do usuário, fora deste repo):** recomendado trocar a ordem do
  "End G-code" no OrcaSlicer de `PRINT_END` → `MMU_END` para **`MMU_END` → `PRINT_END`**,
  porque o unload de ferramenta do `MMU_END` precisa de calor e reaquecia o bico logo
  depois do `PRINT_END` já ter desligado. **Não confirmado se o usuário já aplicou essa
  troca no perfil do fatiador.**

### 7. Revisão geral + melhorias aplicadas
- Removido include morto `mmu/addons/mmu_erec_cutter.cfg` (declarava um servo fantasma
  no pino `mmu:PA7` pra um cortador na MMU que não é usado — o corte é no cabeçote).
- Removida do git a pasta `mmu-20260802_152413/` (backup criado pelo `install.sh` do
  Happy Hare, versionada por engano pelo cron de backup). Criado `.gitignore` na raiz do
  repo com `**/mmu-????????_??????/` pra não repetir.
- `has_filament_buffer: 1 → 0` (confirmado: sem buffer físico, alimentação direta do
  carretel) — usa perfil de velocidade/aceleração mais conservador no carregamento.
- `bed_mesh probe_count: 12,12 → 20,20` (modo scan do Eddy é rápido o bastante).
- Motores X/Y: `run_current 0.9A → 1.2A` (motor SIBOOR-42STH48-2404, nominal 2.4A —
  antes rodava só a 37% do nominal, pouca margem de torque pro `max_accel: 6500`
  configurado), `hold_current 0.75A → 0.5A` (menos aquecimento parado).

**Sinalizado mas não alterado** (decisão do usuário, não urgente):
- `moonraker.conf`: `[update_manager] channel: dev` — dado todo o histórico desta sessão
  (Klipper de ponta quebrando compatibilidade), vale considerar um canal mais estável ou
  pelo menos cautela ao clicar "update all" sem checar compatibilidade primeiro.
- Vários parâmetros MMU "inertes" por falta de hardware correspondente (sync-feedback
  tension/compression, flowguard por encoder) — inofensivos, só não fazem nada até o
  usuário instalar esse sensor/encoder.

### 8. Reorganização do `printer.cfg` monolítico
Ver seção "Estrutura do repositório" acima. Nenhum valor foi alterado nessa
reorganização — só reagrupamento por assunto. Conferido que as 47 seções de config do
Klipper aparecem exatamente uma vez cada (sem perda/duplicação).

### 9. Exclude Object / Cancelar objeto pela web (sem tela física)
- `[exclude_object]` já estava presente (agora em `misc.cfg`), não precisa de parâmetro.
- OrcaSlicer: habilitado "Label objects" em Configurações de Impressão → Avançado →
  Outros → G-code output.
- Existe um aviso na documentação do OrcaSlicer de incompatibilidade entre "Label
  objects" e modo Single Extruder Multi-Material — **mas foi verificado no gcode real
  gerado (`Montagem_PLA_35m39s.gcode`) que os marcadores `EXCLUDE_OBJECT_DEFINE/
  START/END` são gerados corretamente nesse setup** (provavelmente porque a purga é
  feita num balde fixo pelo Happy Hare, não por "wipe into object/infill"). **Funciona,
  confirmado.** Uso: painel "Exclude Objects" no Mainsail durante a impressão.

### 10. MMU reativada + "Extruder Sensor"/"Toolhead Sensor" parando a impressão (2026-09-04)
Usuário reativou o MMU e reportou que o "Extruder Sensor" (`extruder_switch_pin` em
`mmu_hardware.cfg`) fica desconectando momentaneamente durante o movimento do filamento
(provável causa física: contato ruim/vibração no microswitch ou ruído elétrico no cabo da
EBB36, pinos PB5/PB6) — isso interrompe a troca de ferramenta e pausa a impressão inteira.

- **Não quis desativar o sensor** (continua sendo útil), só não queria que um soluço dele
  parasse a impressão.
- **Descoberta**: com a config atual (`extruder_force_homing: 0`), o "Extruder Sensor" já
  nem é usado pra homing (só o "Toolhead Sensor" é usado) — ele serve mais pra
  status/checagem. Mesmo assim, uma falha de leitura durante o `Tx` pode disparar
  `pause_macro: PAUSE` e parar tudo.
- **Correção aplicada** em `mmu/base/mmu_parameters.cfg`:
  `retry_tool_change_on_error: 0` → **`1`** — quando uma troca de ferramenta falha (por
  esse tipo de soluço em qualquer um dos dois sensores), o Happy Hare agora tenta
  recuperar automaticamente (equivalente a `MMU_RECOVER` + `Tx` de novo) em vez de pausar.
- **⚠️ Trade-off avisado ao usuário** (texto do próprio comentário do Happy Hare):
  "enabling this can mask problems with your MMU" — isso não resolve a causa raiz (contato
  ruim do sensor), só faz a impressora insistir sozinha. Se o problema for elétrico e
  piorar com o tempo, pode não ser percebido até causar um erro mais sério (grinding,
  troca malfeita).
- **⚠️ PENDENTE (ação física do usuário, fora deste repo):** verificar a fiação/conector
  do "Extruder Sensor" e "Toolhead Sensor" na EBB36 (pinos PB6 e PB5) — reapertar conector,
  checar se o cabo está longe de fontes de ruído (motor/CANbus), e verificar o microswitch
  físico por folga/desgaste. A causa raiz provável é mecânica/elétrica, não de software.

### 11. Instalação do encoder Binky (resolve a causa raiz do item 10, 2026-09-04)
MMX veio com placa **ERCF Binky v1.0.4** (kit Seleadlab, junto com rolamentos 685 e U623) mas
sem carcaça própria — usuário adaptou uma carcaça de terceiros compatível
([Blinky Encoder V623ZZ with dual ECAS](https://www.printables.com/model/1618366-blinky-encoder-v623zz-with-dual-ecas))
e instalou fisicamente no caminho do filamento entre a MMX e a extrusora, com roda de
**12 dentes**.

- **Fiação:** sinal do encoder ligado direto na **FLY-D7 (placa principal, `[mcu]` padrão)**,
  pino **PB4** — usando o conector "3D TOUCH" da placa (`PB4 / 5V / G`), que estava livre
  porque essa Trident usa sonda Eddy, não BLTouch. Confirmado que o Klipper não exige pino
  "interrupt-capable" (não usa hardware interrupt pra isso), então qualquer GPIO livre
  serviria — PB4 foi escolhido por já ter um conector de 3 vias pronto no lugar certo.
- **Correção em `mmu/base/mmu_hardware.cfg`:** descomentada a seção `[mmu_encoder mmu_encoder]`,
  trocado `encoder_pin: ^mmu:MMU_ENCODER` (placa da MMU) por **`encoder_pin: ^PB4`** (placa
  principal, sem prefixo de mcu). `encoder_resolution: 1.0` mantido como valor de partida
  (fórmula do comentário do arquivo, pra roda de 12 dentes) — será sobrescrito pela
  calibração real.
- **Correção em `mmu/base/mmu_parameters.cfg`:** `flowguard_enabled: 0 → 1` — agora que existe
  um encoder de verdade, o método de detecção de clog/tangle por encoder do FlowGuard passa a
  funcionar (documentação do Happy Hare confirma que esse método não depende dos sensores
  Toolhead/Extruder Sensor problemáticos do item 10 — só compara movimento do encoder com o
  da extrusora). Reativado a pedido do usuário, que queria a proteção de clog de volta agora
  que não depende mais dos switches instáveis.
- **⚠️ PENDENTE (ação do usuário):** depois do `RESTART`, rodar `MMU_CALIBRATE_ENCODER` pra
  medir a resolução real (substitui o `1.0` de partida). Testar impressão pra confirmar que
  o FlowGuard não pausa mais por falso positivo.

### 12. MMU Gate Sensor movido da EBB42 para a FLY-D7 (2026-09-05)
Usuário rewireou o "MMU Gate Sensor" (sensor compartilhado que detecta filamento passando
pela gate da MMX) da placa própria da MMU (EBB42, pino `MMU_GATE_SENSOR=PB4` em `mmu.cfg`)
direto pra placa principal (FLY-D7), pino **PB3**.

- **Correção em `mmu/base/mmu_hardware.cfg`:** `gate_switch_pin: ^mmu:MMU_GATE_SENSOR` →
  **`gate_switch_pin: ^PB3`** (sem prefixo de mcu, resolve na FLY-D7). Confirmado que PB3
  não é usado em nenhum outro lugar da config da Trident.
- O alias `MMU_GATE_SENSOR=PB4` continua declarado em `mmu.cfg` (pino da EBB42) mas ficou
  órfão/sem uso — inofensivo, só não referencia mais nada.
- Precisa de `RESTART` pra a mudança valer (config só é lida de novo nesse momento).

### 13. Falso clog/tangle no FlowGuard - causa raiz e correção (2026-09-05)
Depois de instalar o encoder (item 11), o FlowGuard (item 10/11) começou a pausar a
impressão com "A clog/tangle has been detected" com frequência, mesmo sem clog real.
Usuário mandou o `klippy.log` pra investigar.

- **Causa raiz encontrada no log:** o campo "Tool Change G-code" do perfil do OrcaSlicer
  dessa impressora ainda usava macros **obsoletas**:
  ```
  _MMU_PRE_T_CODE P={layer_num}
  T[next_extruder]
  _MMU_POST_T_CODE
  ```
  `_MMU_PRE_T_CODE` e `_MMU_POST_T_CODE` não existem mais nas versões atuais do Happy Hare
  (confirmado na wiki oficial) — toda troca de ferramenta gerava `Unknown command` no log
  pra essas duas linhas, pulando silenciosamente o que quer que elas deveriam fazer. Isso
  provavelmente causava a dessincronia que o FlowGuard interpretava como clog.
- **Correção (feita no OrcaSlicer, fora deste repo):** Tool Change G-code trocado para
  só `T[next_extruder]` — é o valor recomendado pela wiki atual do Happy Hare, o comando
  `Tn` já cuida de tudo internamente agora.
- **Achado secundário (mesmo perfil, Start G-code):** comentários usando `#` em vez de `;`
  (`# 1. Inicializa...` etc.) também geravam `Unknown command` — inofensivo (as macros de
  verdade rodavam certo), mas sujava o log. Corrigido pra `;` também.
- **Ajuste adicional em `mmu/base/mmu_parameters.cfg`:** `flowguard_max_relief: 40 → 70` —
  mantido como margem de segurança extra mesmo depois da correção do gcode, já que o
  encoder tem uma imprecisão natural (zona cega + folga do bowden, ver item 11). Usuário
  optou por manter os dois ajustes juntos em vez de isolar a variável.
- **⚠️ PENDENTE (ação do usuário):** confirmar com uma impressão de teste (com troca de
  cor) que o `Unknown command` sumiu do log e que o FlowGuard não dispara mais falso
  positivo.

### 14. Aviso "Excess slippage" no carregamento do bowden - zona cega do encoder (2026-09-05)
Depois de corrigir o gcode (item 13), o clog/tangle parou, mas apareceu um aviso novo e
consistente a cada carregamento de bowden:
```
Warning: Excess slippage was detected in bowden tube load but 'bowden_apply_correction'
is disabled. Gear moved 1333.2mm, Encoder measured 1135.4mm.
```
- **Não é um erro novo** — é a mesma "zona cega" do item 11 (distância entre o sensor da
  gate e a posição física do encoder, onde o Happy Hare não consegue medir movimento
  porque o filamento ainda não tocou a rodinha).
- **Correção em `mmu/base/mmu_parameters.cfg`:** `gate_endstop_to_encoder: 10 → 210` —
  esse parâmetro informa ao Happy Hare a distância real (em mm) entre o sensor da gate e
  o encoder, calculada pela diferença observada entre movimento da engrenagem e leitura
  do encoder (~200-220mm em duas medições diferentes). Com o valor certo, o Happy Hare já
  espera essa zona cega e não trata mais como slippage anômalo.
- **`bowden_apply_correction` permanece desabilitado (0) — não ativar.** Esse parâmetro
  faz o Happy Hare "acreditar" no encoder e empurrar a engrenagem pra compensar a
  diferença. Como a diferença aqui não é slippage real, ativar isso faria ele
  superinserir ~200mm de filamento a mais tentando corrigir um problema que não existe,
  arriscando esmagamento/grinding.
- **⚠️ PENDENTE (ação do usuário):** depois do `RESTART`, confirmar que o aviso sumiu ou
  diminuiu bastante. Se quiser refinar ainda mais, medir fisicamente a distância real ao
  longo do tubo (sensor da gate → rodinha do encoder) e ajustar esse valor.

### 15. G2/G3 "Unknown command" - arco não habilitado (2026-09-05)
Console cheio de `Unknown command:"G2"` / `Unknown command:"G3"` durante impressão. Causa:
o Orca gera movimento em arco (G2/G3) em vez de várias retas pequenas, mas o Klipper só
entende esses comandos com a seção `[gcode_arcs]` habilitada — que não existia no
`printer.cfg`. Sem isso, o bico ficava parado exatamente onde devia curvar (defeito real
de qualidade, não só log sujo).

- **Correção em `printer.cfg`:** adicionado `[gcode_arcs]` (com `resolution` no padrão,
  1.0mm por segmento).
- **Precisa de `RESTART`.**

Também explicado ao usuário o significado do "Gate Statistics" (`console_gate_stat:
emoticon`) que aparece no fim de cada impressão — é um placar histórico de confiabilidade
por gate (baseado em sucessos/falhas acumuladas), não reflete só a impressão atual. A nota
pior do Gate 0 é resquício das falhas de FlowGuard de antes dos itens 13/14 serem
corrigidos. Pode ser zerado com `MMU_STATS RESET=1` se quiser recomeçar o histórico
(cosmético, não afeta funcionamento).

### 16. Migração forçada Happy Hare v3 → v4 (2026-09-06)
Usuário clicou "Atualize todos os componentes" no Gerenciador de Atualização sem
planejar, e o Happy Hare pulou de v3.4.2 pra **v4.0.0** (major version, sem migração
automática de config — confirmado pelo próprio Happy Hare: "There is no supported
v3 → v4 config migration"). Klipper parou de carregar (`cannot import name 'mmu_unit'`).

- **Processo:** `cd ~/Happy-Hare && ./install.sh -c ~/printer_Trident_data/config`,
  escolhida a opção 2 ("upgrade to v4"). Isso renomeia a pasta v3 inteira pra
  `mmu.V3` (preservada, nada apagado) e roda um assistente interativo (menuconfig)
  pra gerar a config v4 do zero. Passamos por TODAS as telas manualmente, replicando
  cada valor customizado da v3 (documentado abaixo).
- **Estrutura de arquivos mudou:** antes era `mmu/base/{mmu,mmu_hardware,mmu_parameters,
  mmu_macro_vars}.cfg` (arquivos reais) + vários symlinks. Agora é
  `mmu/base/{mmu,mmu_hardware_unit0,mmu_parameters_unit0,mmu_macro_vars}.cfg` (note o
  sufixo `_unit0` — a v4 suporta múltiplas unidades MMU) + uma pasta nova
  `mmu/macros/*.cfg` (todos symlinks). Backup completo da v3 ficou em `trident/mmu.V3/`
  neste repo (não usar/editar, é só histórico).
- **Valores customizados replicados na v4** (todos conferidos manualmente, tela por
  tela, contra a v3): tipo MMX, placa BTT EBB42 CANbus (UUID `f26f15ebcfb6`), encoder
  habilitado (pino `PB4` na FLY-D7), gate sensor compartilhado habilitado (pino `PB3`
  na FLY-D7), sensores de gate/lane entry, toolhead cutter + toolhead sensor
  (`ebb36:PB5`) + extruder sensor (`ebb36:PB6`) com as distâncias medidas
  (93/83/8mm), toolhead preset "A4T WWBMG Bambu TZ3", valores de corte
  (`_MMU_CUT_TIP`: blade position 67, retract 20, pin location 3,286, pin park
  -5.0, rip length 2.0, fast move fraction 0.85), EndlessSpool habilitado, retry
  automático de troca de ferramenta habilitado, FlowGuard por encoder habilitado
  (sync-feedback desabilitado, sem esse hardware), autotune de bowden habilitado,
  calibração de rotação/encoder não pulada, corrente sincronizada da engrenagem 70%,
  velocidades de bowden ajustadas (80mm/s carga normal, 18mm/s homing), velocidade de
  purga aumentada de 2 pra 5 (estava muito lenta), e os caminhos/nomes de serviço do
  Pi multi-instância (`gcodes` dir, `klipper-Trident.service`,
  `moonraker-Trident.service` — o assistente veio com valores errados/genéricos aqui,
  mesmo tipo de erro já visto antes nesse Pi).
- **Bugs pós-instalação corrigidos:**
  - `Duplicate canbus_uuid`: o instalador não removeu a declaração antiga
    `[mcu mmu]` do `printer.cfg` (linha solta, fora da pasta `mmu/` gerenciada) —
    ficou duplicada com o novo `[mcu unit0]` do `mmu_hardware_unit0.cfg`, mesmo
    UUID. **Corrigido:** removida a seção `[mcu mmu]` do `printer.cfg`.
  - `gate_parking_distance` inválido: a v4 **inverteu o sinal** desse parâmetro
    comparado à v3 (v3: positivo = recuar; v4: negativo = recuar, convenção padrão
    do Klipper). O assistente aceitou `25` (copiado literal da v3) sem validar na
    hora, mas o Klipper rejeitou no boot exigindo `<= 0` pro tipo de endstop
    `mmu_shared_exit`. **Corrigido:** `25 → -25` em `mmu_parameters_unit0.cfg`.
  - **`mmu/mmu_vars.cfg` vazio** (só o template, `mmu__revision = 0`) — o
    `install.sh` migra a config estática (hardware/parameters) mas **não migra as
    variáveis persistidas de estado/calibração**. Todo o resultado calibrado de
    verdade (`mmu_calibration_bowden_lengths = 1333.2`,
    `mmu_encoder_resolution = 0.9752` — valor real medido, não o `1.0` de partida,
    `mmu_gear_rotation_distances`, `mmu_selector_angles`, estatísticas por gate)
    ficou intacto só no backup `mmu.V3/mmu_vars.cfg`. **Corrigido:** copiado o
    conteúdo de calibração do `mmu.V3/mmu_vars.cfg` pro `mmu/mmu_vars.cfg` novo —
    o próprio comentário do arquivo template confirma que reaproveitar um arquivo
    de variáveis existente é suportado. Evita ter que refazer
    `MMU_CALIBRATE_GEAR`/`MMU_CALIBRATE_ENCODER`/`MMU_CALIBRATE_BOWDEN` do zero.
- **⚠️ PENDENTE (ação do usuário):** testar impressão completa com troca de cor
  pra confirmar que a v4 está estável, e conferir no console (`MMU_STATUS` ou
  similar) que os valores calibrados (bowden 1333.2mm, encoder 0.9752) realmente
  foram reconhecidos pela v4 após copiar o `mmu_vars.cfg` — se a v4 usar nomes de
  variável diferentes internamente (ex: com prefixo do unit), pode ignorar
  silenciosamente esses valores antigos e exigir recalibração mesmo assim. O item
  da checklist antiga sobre o patch do `mmu.py` (item 3, causa raiz #3) **não se
  aplica mais** — a v4 reestruturou o código do MMU inteiro, e o `install.sh`
  sempre reescreve esses arquivos do zero agora.
- **Confirmado (2026-09-06):** a v4 realmente não reconheceu os valores copiados do
  `mmu_vars.cfg` v3 — pediu recalibração completa (`MMU_CALIBRATE_GEAR`,
  `MMU_CALIBRATE_ENCODER`, `MMU_CALIBRATE_GATE` por gate). Durante a recalibração,
  `MMU_TEST_MOVE MOVE=100` moveu o filamento **na direção contrária** (puxando pra
  trás em vez de alimentar). Causa: o assistente de instalação gerou
  `dir_pin: unit0:PD1` pro `stepper_mmu_gear` (`mmu_hardware_unit0.cfg`) **sem** a
  inversão `!` que a v3 tinha (`dir_pin: !mmu:MMU_GEAR_DIR`). **Corrigido:**
  `dir_pin: !unit0:PD1`. Recalibração da engrenagem/encoder/gates precisa ser
  refeita do zero de qualquer forma (ver pendência abaixo).

### 17. Pesquisa aprofundada v4 + revisão overnight (2026-09-06, madrugada)
Usuário foi dormir no meio da recalibração pós-migração e pediu pra eu (a) pesquisar a
fundo a documentação oficial da v4 (`https://moggieuk.github.io/Happy-Hare-Doc/`),
(b) responder se a v4 já tem macro de corte de filamento built-in ou se precisa manter
a customizada, (c) comparar v3 (`mmu.V3/`) vs v4 (`mmu/`) atrás de mais melhorias, e
(d) corrigir o que desse pra corrigir sozinho (só arquivos de config — não tenho acesso
ao console da impressora pra rodar G-code).

**Resposta sobre o cortador de filamento:** a v4 **usa exatamente a mesma macro
`_MMU_CUT_TIP`** que a v3, com as mesmas variáveis (`pin_loc_xy`, `pin_park_dist`,
`cut_fast_move_fraction`, etc. em `_MMU_CUT_TIP_VARS`) — já configuramos tudo isso
certinho no menuconfig ontem (item 16). **Não precisa de nada customizado extra, nem
trocar nada** — sua `CORTE_FILAMENTO` (que chama `_MMU_CUT_TIP`) continua válida.

**Achados da pesquisa + correções aplicadas:**
- `gate_endstop_to_encoder` **ainda existe** na v4 (`mmu_parameters_unit0.cfg`) — só não
  apareceu no assistente interativo (menuconfig) que passamos ontem, por isso ficou
  esquecido no valor padrão `10`. **Corrigido: `10 → 210`** (mesma distância física
  medida na v3, item 14).
- Confirmado no `mmu_vars.cfg` atual que a v4 usa variáveis com **prefixo `unit0_`**
  para dados por-gate (`mmu_unit0_gear_rotation_distances`,
  `mmu_unit0_bowden_lengths`) — diferente das antigas que copiamos do backup v3 (que
  ficaram órfãs/sem uso, exceto `mmu_selector_angles`, que parece ter sido reconhecida
  sem prefixo). Confirma que **o bowden também precisa ser recalibrado**
  (`mmu_unit0_bowden_lengths` está `[-1,-1,-1,-1]`, vazio) — não só engrenagem/encoder
  como pensávamos ontem.
- **`endless_spool_groups` está vazio** (`mmu.cfg`) — o EndlessSpool está habilitado
  (`endless_spool_enabled: 1`) mas sem grupos definidos ele não tem o que fazer (não
  sabe quais gates são "backup" um do outro). **Não configurei sozinho** porque depende
  de qual gate físico tem o mesmo material/cor de qual — isso só o usuário sabe. Ver
  pendência abaixo com a sintaxe.
- **FlowGuard confirmado:** com `flowguard_encoder_mode: 2` (automático), o parâmetro
  antigo `flowguard_max_relief` é ignorado — quem importa agora é `desired_headroom`
  (na seção do encoder, `mmu_parameters_unit0.cfg`). Se o falso clog voltar a acontecer,
  o ajuste certo agora é aumentar `desired_headroom`, não mais `flowguard_max_relief`.
- Achei um comando de diagnóstico útil pra rodar amanhã antes de mais nada:
  **`MMU_SENSORS`** — relata o estado de todos os sensores de todas as unidades (gate,
  pre-gate, toolhead, extruder, encoder). Bom pra confirmar que a migração não bagunçou
  nenhum sensor silenciosamente.

**⚠️ PENDENTE — comandos pra rodar quando acordar (nessa ordem):**
```
MMU_SENSORS                    # confirma que todos os sensores estão OK primeiro
MMU_CALIBRATE_ENCODER           # gate 0 ainda selecionado, encoder ainda nao calibrado
MMU_CALIBRATE_GATE GATE=1       # repete pros gates 1, 2 e 3
MMU_CALIBRATE_GATE GATE=2
MMU_CALIBRATE_GATE GATE=3
MMU_CALIBRATE_BOWDEN            # confirmar se pede BOWDEN_LENGTH= ou roda sozinho
                                 # (na v3 rodou sem parametro nenhum, usando o toolhead sensor)
```
Se `MMU_CALIBRATE_GATE` (singular) não existir como comando, tentar `MMU_CALIBRATE_GATES`
(plural) — a documentação usa os dois nomes em páginas diferentes, não confirmei qual é
o certo pra essa versão exata sem poder rodar o comando eu mesmo.

**Decisão pendente do usuário:** configurar `endless_spool_groups` em `mmu.cfg` (linha
190) se quiser que o EndlessSpool funcione de verdade — sintaxe:
`MMU_ENDLESS_SPOOL_GROUPS GROUPS=<lista de 4 numeros, um por gate, mesmo numero = mesmo
grupo/material>` (ex: gates 0 e 2 com o mesmo material de backup = `0,1,0,1`).

## Checklist de pendências pro usuário confirmar

- [ ] Trocar ordem do End G-code no OrcaSlicer para `MMU_END` antes de `PRINT_END`
      (ver item 6).
- [ ] Opcional: zerar de vez o "volume de ramming" em Filament Settings → Multimaterial
      no OrcaSlicer (item 5) — não crítico, já está seguro.
- [ ] Testar impressão completa com troca de cor na v4 (item 16) pra confirmar
      estabilidade da migração.
- [ ] Rodar os comandos de calibração pendentes do item 17 (encoder, gates 1-3, bowden).
- [ ] Decidir e configurar `endless_spool_groups` (item 17) se quiser EndlessSpool
      funcionando de verdade.
- [ ] Decidir se quer trocar `channel: dev` para algo mais estável no `moonraker.conf`.

## Dicas úteis pra próxima sessão

- Sempre `git pull --rebase origin main` antes de editar (cron de backup pode ter
  avançado o remoto).
- Não confundir os arquivos symlink (mostram só um caminho de texto quando lidos aqui)
  com arquivos reais — ver lista na seção de estrutura do repo.
- Para qualquer dúvida sobre parâmetros do Happy Hare, os comentários dentro de
  `mmu_parameters.cfg` e `mmu_macro_vars.cfg` são bem detalhados e específicos por
  fabricante de MMU (inclusive citam "A4T-A4C" que é a família do cabeçote do usuário).
- O usuário acessa o Pi via SSH e a impressora via Mainsail — não tem tela física
  (nem BTT Pad nem KlipperScreen físico usado no fluxo de trabalho comum).
