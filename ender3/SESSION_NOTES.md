# Notas de sessão — Ender 3 (placa FLY_D5)

> Documento de contexto para futuras sessões. Resume o que foi diagnosticado e corrigido,
> o que ficou pendente, e armadilhas conhecidas desse setup específico.
> Última atualização: sessão de 2026-10-24 (CAN, EBB36, X sensorless, PID, BLTouch na EBB36).
>
> Ver também [`CLAUDE.md`](../CLAUDE.md) na raiz do repositório: idioma padrão
> (sempre português) e cuidados gerais válidos pra qualquer impressora deste Pi
> multi-instância (nomes de serviço, backup automático, symlinks, etc.).

## Visão geral do hardware

- **Impressora:** Ender 3, cinemática cartesiana, mesa ~247x230 útil (`position_max` de
  X/Y no `printer.cfg`).
- **Placa principal:** FLY_D5 (MCU `stm32f072xb`), pinos mapeados em `FLY_D5.cfg`.
- **Host:** mesmo BTT Pi multi-instância das outras impressoras deste repo
  (`printer_Ender3_data`).
- **Sonda:** BLTouch (genérico/clone), `x_offset: -45`, `y_offset: -1`.
- **Drivers:** TMC2209 em UART em todos os eixos + extrusora.
- **Extrusora:** `rotation_distance: 7.895` (já calibrado), `pressure_advance: 0.16`
  (já calibrado).
- **Input shaper:** já calibrado — `shaper_freq_x = 74.8` (MZV), `shaper_freq_y = 36.0`
  (MZV). Frequência de Y bem mais baixa que X sugere mais flex nesse eixo (tensão de
  correia/rigidez do gantry) — não corrigido nesta sessão, só observado.

## O que foi corrigido nesta sessão (2026-08-08)

### 1. `moonraker.conf` — nome de serviço errado
`[update_manager mainsail-config]` tinha `managed_services: klipper` — mesmo bug já
identificado e corrigido na Trident (ver
[`trident/SESSION_NOTES.md`](../trident/SESSION_NOTES.md)). Nesse Pi não existe
`klipper.service` "pelado", cada instância tem o seu (`klipper-<Nome>.service`).
- **Correção:** trocado para `klipper-Ender3`.
- **⚠️ PENDENTE:** não foi possível confirmar o nome real do serviço rodando no Pi a
  partir desta sessão (sem acesso SSH direto) — segui o mesmo padrão de nomenclatura da
  Trident. Confirmar com `systemctl list-units --all | grep -i klipper` antes da próxima
  atualização via Moonraker.

### 2. `channel: dev` no `[update_manager]`
Mesmo risco sinalizado (e ainda não resolvido) na Trident: canal de desenvolvimento pode
trazer builds que quebram compatibilidade sem aviso.
- **Correção:** trocado para `channel: stable`.

### 3. Tuning dos drivers TMC2209 (`printer.cfg`)
- `interpolate: false` → **`true`** nos 4 drivers (X, Y, Z, extrusora) — estava
  desativada a interpolação de microstepping sem motivo aparente; reativado pra
  movimento mais suave/silencioso.
- `stealthchop_threshold: 0` → **`150`** nos 4 drivers — antes rodava sempre em
  SpreadCycle (mais torque, mais barulho). Agora usa StealthChop (silencioso) abaixo de
  150mm/s e volta pra SpreadCycle acima disso. Valor escolhido pelo usuário (opção
  "ativar só em baixa velocidade", já que `max_velocity: 200`).

### 4. `[exclude_object]` adicionado
Não existia no `printer.cfg`. Adicionado pra permitir cancelar objetos individuais pela
web (Mainsail), mesmo recurso já validado na Trident.
- **⚠️ PENDENTE (ação do usuário, fora deste repo):** habilitar "Label objects" no
  fatiador usado pra Ender3, senão o Klipper não recebe os marcadores
  `EXCLUDE_OBJECT_DEFINE/START/END` no gcode e a feature fica sem efeito.

### 5. Limpeza de backups automáticos versionados por engano
5 arquivos `ender3/printer-<timestamp>.cfg` estavam commitados no repo — são os
snapshots que o próprio Klipper cria automaticamente a cada `SAVE_CONFIG` (mesma
categoria do que já tinha acontecido com a pasta `mmu-<timestamp>/` da Trident).
- **Correção:** removidos do git (`git rm --cached`, continuam no disco local) e
  adicionado padrão `**/printer-????????_??????.cfg` ao `.gitignore` da raiz do repo pra
  não repetir.

## Malha da mesa não sendo aplicada automaticamente (2026-09-03)

Sintoma: `BED_MESH_PROFILE LOAD="default"` está no `START_PRINT`, mas a malha nunca era
aplicada nas impressões.

- **Causa raiz:** não é bug no `macros.cfg` — o **Start G-code do Orca Slicer** configurado
  pra essa impressora é o G-code genérico padrão (`G90` / `M83` / `M140` / `M104` / `G4 S10`
  / `G28` / posicionamento), que **nunca chama a macro `START_PRINT`**. O mesmo vale pro End
  G-code (padrão do Orca, não chama `END_PRINT` — como consequência, o bico nunca era
  desligado no fim da impressão, só a mesa).
- **Correção (feita no Orca Slicer, fora deste repo)** — Printer Settings → Custom G-code:
  - Start G-code:
    ```
    G90
    M83
    START_PRINT BED_TEMP=[bed_temperature_initial_layer_single] EXTRUDER_TEMP=[nozzle_temperature_initial_layer]
    ```
  - End G-code:
    ```
    END_PRINT
    ```
  - **⚠️ PENDENTE:** não confirmado se o usuário já aplicou essa troca no perfil do Orca.
- **Melhorias aplicadas no `START_PRINT` (`macros.cfg`) enquanto investigava:**
  - Adicionado `M83` logo no início da macro, pra ela não depender de quem a chamou já ter
    setado extrusão relativa (a linha de purga usa `E10` duas vezes, assumindo modo
    relativo).
  - `BED_MESH_PROFILE LOAD="default"` agora só roda se o perfil `default` existir
    (`{% if 'default' in printer.bed_mesh.profiles %}`) — antes, se o perfil não existisse
    por qualquer motivo (impressora nova, perfil renomeado), o comando dava erro e abortava
    a impressão inteira no meio do aquecimento.
  - Lift inicial de segurança (`G1 Z...` enquanto espera esquentar) de 5mm para 10mm — mais
    folga.
- **Verificar depois de aplicar a troca no Orca:** abrir o `.gcode` gerado e confirmar que
  `START_PRINT BED_TEMP=... EXTRUDER_TEMP=...` aparece no início, e `END_PRINT` no fim.

## Checklist de pendências pro usuário confirmar

- [ ] Confirmar nome real do serviço systemd da Ender3 (`systemctl list-units --all |
      grep -i klipper`) e ajustar `managed_services` no `moonraker.conf` se for
      diferente de `klipper-Ender3`.
- [ ] Habilitar "Label objects" no fatiador usado pra Ender3, pra `[exclude_object]`
      funcionar de fato.
- [ ] Testar impressão depois da mudança de `stealthchop_threshold`/`interpolate` —
      checar se não há perda de passo em movimentos rápidos (viagem acima de 150mm/s
      volta pro SpreadCycle, então risco baixo, mas vale conferir).
- [ ] Opcional: investigar rigidez do eixo Y (correia/gantry) dado o
      `shaper_freq_y = 36.0` bem mais baixo que o X (74.8) — não é bug, só uma
      oportunidade de melhoria mecânica.

## Armadilha conhecida: lista de gcodes sumindo da interface

Depois dos reinícios seguidos de Klipper/Moonraker na sessão de ajustes de 2026-08-08
(vários `SAVE_CONFIG` em sequência), a lista de arquivos gcode na interface (Mainsail)
passou a mostrar só os arquivos enviados depois dos restarts — os antigos (confirmados
presentes em `/home/biqu/printer_Ender3_data/gcodes` via `ls`) sumiram da tela, mesmo com
upload de arquivo novo funcionando normalmente (log do Moonraker sem erro, `201` no
`POST /api/files/local`).

- **Causa provável:** o Moonraker faz um escaneamento completo da pasta `gcodes` (com
  extração de metadata de cada gcode) sempre que o serviço reinicia. Com vários restarts
  em sequência rápida, esse escaneamento parece ter sido interrompido no meio (talvez por
  algum arquivo com nome "difícil" — há vários com colchetes, parênteses e espaços) e a
  lista ficou incompleta. Arquivos novos continuaram aparecendo porque são adicionados de
  forma incremental (watch do sistema de arquivos), sem precisar do escaneamento
  completo.
- **Correção que funcionou:** `sudo systemctl restart moonraker-Ender3` — o
  reescaneamento completou direito na tentativa seguinte e a lista toda voltou.
- **Se acontecer de novo:** tentar o restart do Moonraker primeiro. Se não resolver, olhar
  o log (`/home/biqu/printer_Ender3_data/logs/moonraker.log`) procurando erro/exception
  logo depois de alguma linha `Updating File List <gcodes>...`, pra identificar se é um
  arquivo específico travando o escaneamento (nesse caso, renomear esse arquivo removendo
  caracteres especiais costuma resolver).

## Migração para CAN: D5 como ponte USB-CAN + EBB36 v1.2 (2026-10-24)

Objetivo: usar a cabeça A4T com a placa **BTT EBB36 v1.2** (STM32G0B1) por CAN. O Pi não tem
CAN, então a **D5 virou ponte USB-CAN** e criou uma segunda rede CAN no Pi, independente da
da Trident. (Depois do primeiro reboot do Pi a Trident precisou passar para `can_trident`, ver
`trident/SESSION_NOTES.md` item 43; a D5 e a Trident agora têm nomes fixos.)

### O que foi feito
- **D5:** já tinha Katapult (bootloader). Entrou nele com `flashtool.py -r` e recebeu o
  firmware de ponte: STM32F072, bootloader 8KiB, cristal 8 MHz, "USB to CAN bus bridge
  (USB on PA11/PA12)", CAN em PB8/PB9, 1000000. Compilado com `KCONFIG_CONFIG=config.d5`
  em `~/klipper` e gravado com `flashtool.py -f out/klipper.bin -d /dev/serial/by-id/usb-katapult_...`.
- **EBB36 v1.2 (placa nova):** Katapult compilado (`~/katapult/config.ebb36`: G0B1, offset
  8KiB, cristal 8 MHz, CAN PB0/PB1, 1000000) e gravado por **DFU** (`dfu-util ... 0x08000000:force:mass-erase:leave`,
  jumper VUSB, BOOT+RESET; precisou de `sudo`). Depois o Klipper (`~/klipper/config.ebb36`,
  mesmos parâmetros) foi gravado **por CAN**: `flashtool.py -i can_ender -u a961f4b5f8c1 -f ~/firmware-backup/klipper_EBB36.bin`.
- **Rede no Pi:** a D5 aparece como `gs_usb` `1d50:606f`, serial USB `450049000757465036383420`.
  Regra `/etc/udev/rules.d/70-can-bridges.rules` renomeia para `can_ender`, configura bitrate
  1000000 e sobe a interface a cada reconexão. A Trident é `can_trident` (serial
  `3E001B001353303650373120`).
- **UUIDs CAN:** D5 `cb9f5f3a6f91`, EBB36 `a961f4b5f8c1`
  (`~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can_ender`).
- **`printer.cfg`:** `[mcu]` agora usa `canbus_uuid`/`canbus_interface: can_ender`; novo
  `[mcu EBBCan]`; `[temperature_sensor EBB36_mcu]`; o termistor do `[extruder]` passou
  para `sensor_pin: EBBCan:PA3` (o aquecedor ainda sai pela D5, `HEAT0`).
- Binários e backups: `~/firmware-backup/` (`klipper_D5_bridge.bin`, `klipper_EBB36.bin`, `katapult_EBB36.bin`).

### Armadilhas encontradas
- No menuconfig do Klipper/Katapult para a G0B1, o CAN é `STM32_MMENU_CANBUS_PB0_PB1`
  ("Communication interface"). `STM32_CMENU_...` é o menu secundário (ponte) e foi ignorado:
  a primeira compilação saiu com USB sem avisar. Sempre conferir o `.config` resultante.
- `ifupdown` (`allow-hotplug`) deixava a interface DOWN quando a D5 reconectava
  (`already configured`). Resolvido com a regra udev acima (sem arquivo em `interfaces.d`).
- `dfu-util` sem root dá `LIBUSB_ERROR_ACCESS`; o erro `Error during download get_status`
  depois do `leave` é normal.
- Ao ligar o `printer.cfg` novo, o Klipper desligou com `MCU 'mcu' shutdown: ADC out of range`:
  o termistor do hotend antigo (`HEAT0_TEMP` na D5) estava desconectado. Por isso o sensor
  foi movido para a EBB36 (PA3). Também apareceu `Failed to verify BLTouch probe is raised`
  (conferir se o BLTouch está ligado).

### Pendências
1. ~~Ligar o termistor na EBB36~~ **Feito (2026-10-24):** com o termistor em TH0/PA3 o Klipper
   subiu (`Printer is ready`), extrusora lendo ~25,6 °C, mesa 26,4 °C, MCU da EBB36 ~34,6 °C,
   BLTouch sem erro. Falta confirmar o tipo real do termistor da A4T (hoje `EPCOS 100K B57560G104F`,
   provisório; comparar com a temperatura ambiente e, depois, com o aquecimento real).
2. ~~Migrar o resto para a EBB36~~ **Feito** (ver seção seguinte). Pinos usados: aquecedor `EBBCan:PB13`, motor do extrusor
   (`PD0` step, `!PD1` dir, `!PD2` enable, TMC2209 UART `PA15`), ventilador de peça `PA0`,
   ventilador do hotend `PA1`.
3. ~~Reboot de teste do Pi~~ Feito em 2026-10-24 sem querer: expôs a corrida de nomes `can0`/`can1`
   (a Trident parou) e levou aos nomes fixos `can_trident`/`can_ender`. Reboot de teste feito em 2026-10-24 depois da correção: no boot a D5 ainda pegou `can0` e a
   Trident `can1` no kernel, e a regra udev renomeou as duas (`can_ender`, `can_trident`);
   as duas impressoras subiram em `Printer is ready`.
4. Terminação de 120 Ω: confirmar jumper na EBB36 e se a D5 tem a dela.

## EBB36 completa, X sensorless, PID e BLTouch na EBB36 (2026-10-24, continuação)

### Tudo da cabeça na EBB36 (`printer.cfg`)
Mesma cabeça A4T, hotend, sensor e aquecedor da Trident, então os valores vieram do
`trident/toolhead.cfg`:
- `[extruder]`: step `EBBCan:PD0`, dir `!EBBCan:PD1`, enable `!EBBCan:PD2`, aquecedor `EBBCan:PB13`,
  termistor `EBBCan:PA3` tipo `NTC 100K MGB18-104F39050L32` com `pullup_resistor: 4700`,
  `gear_ratio: 50:17`, `rotation_distance: 13.10`, `pressure_advance: 0.064` (os três herdados da
  Trident, **recalibrar na Ender**), `max_temp: 300`, `min_extrude_temp: 170`.
- `[tmc2209 extruder]`: UART `EBBCan:PA15`, 0,55 A, `sense_resistor: 0.110`, spreadCycle.
- `[fan]` (peça) `EBBCan:PA1`, `[heater_fan ventoinha_hotend]` `EBBCan:PA0` (igual à fiação da Trident;
  o exemplo da BTT inverte PA0/PA1). Conferido no teste: cada um gira na hora certa.
- `[bltouch]`: `sensor_pin: ^EBBCan:PB8`, `control_pin: EBBCan:PB9` (porta Probe da EBB36; antes
  `^D3_STOP`/PA8 na D5, que ficaram livres). Offsets da A4T: `x_offset: -38.7`, `y_offset: 16.6`.
- Dependentes dos offsets, recalculados: `safe_z_home` em `156,101` (BLTouch cai em ~117,117),
  `mesh_min: 10, 20` (Y mínimo alcançável pelo BLTouch = 16,6), `zero_reference_position: 117, 117`,
  parafusos do `screws_tilt_adjust` em X 66,4/236,4 e Y 27,4/197,4 (mesmos parafusos físicos,
  convertidos dos offsets antigos -45/-1).
- **Ainda não montados pelo Jakson:** BLTouch e motor do extrusor (config pronta).

### PID do hotend (EBB36)
`PID_CALIBRATE HEATER=extruder TARGET=240`: Kp 34.385, Ki 15.282, Kd 19.342 (a Trident, mesmo hotend,
tem 33.038/14.684/18.584). Gravado com `SAVE_CONFIG` pelo Jakson. Teste de aquecimento: 25 -> 61 °C em ~10 s.

### X sensorless (TMC2209 + DIAG)
- Config: `endstop_pin: tmc2209_stepper_x:virtual_endstop`, `diag_pin: ^D0_STOP` (PB4 = XSTOP),
  `homing_speed: 20` (= rotation_distance/2, recomendação do Klipper), `homing_retract_dist: 0`,
  `driver_SGTHRS: 53`.
- Macro `G28` (rename para `G28.1`) + `_HOME_X`: homing do X com **0,5 A** (`variable_home_cur`),
  `G4 P2000` antes, afasta 5 mm depois e volta pra corrente normal (0,7 A). Y e Z seguem o G28 normal.
- **Calibração** (procedimento do Klipper, carro no centro, 0,5 A, 20 mm/s): SGTHRS 255..70 para cedo;
  60 = primeiro que chega no batente (máximo); abaixo de ~50 estala/perde passo (observado pelo
  Jakson). Final 53. **Se mudar corrente de homing ou velocidade, recalibrar.**
- `[force_move] enable_force_move: True` adicionado (como na Trident), usado pros testes sem batente.

### Armadilhas do sensorless (custaram horas)
1. **O módulo TMC2209 não tinha os 2 pinos DIAG soldados.** O driver Fly tem 2 pinos extras no meio da
   ponta que entram em 2 furos do encaixe da D5; o jumper DIAG (par vertical ao lado do capacitor de
   100 µF, junto à coluna azul) liga esses furos ao XSTOP. Sem os pinos, o chip sobe o DIAG
   (`DUMP_TMC REGISTER=IOIN` mostra `diag=1`) mas o sinal não sai do módulo. Sintoma: o X lia
   `TRIGGERED` sempre em repouso (a D5 tem pull-up no XSTOP) e o homing nunca parava. Solução: soldar
   a barra de 2 pinos. Teste sem bater: andar 5 mm, deixar `SGTHRS=255` + `TCOOLTHRS=0xFFFFF` (DIAG fica
   em 1 parado) e ver `QUERY_ENDSTOPS` mudar entre `TRIGGERED` e `open`.
2. **`[safe_z_home] z_hop`**: com o Z não homado, TODO `G28` (até `G28 X`) zera o Z e sobe `z_hop` mm.
   Testes repetidos subiram o Z ~80 mm. Ficou `z_hop: 0` durante os testes e voltou a 10 com o BLTouch
   na config.
3. Inverter o `diag_pin` (`^!`) não resolve falta de sinal: leitura parada não prova polaridade.
4. Drivers com pinos DIAG soldados mas sem uso: sem jumper DIAG na placa não fazem nada. **Nunca pôr
   jumper DIAG no D3**: o `D3_STOP` (PB5) era o sinal do BLTouch (hoje livre, mas fica a regra) e com
   jumper o fim de curso correspondente tem que ficar vazio.

### Pendências
1. Montar o BLTouch na EBB36 (PB8/PB9) e rodar `PROBE_CALIBRATE` + `SAVE_CONFIG`: o `z_offset: 1.830`
   salvo é do BLTouch antigo. **Não imprimir antes disso.**
2. Refazer a malha (`BED_MESH_CALIBRATE` + `SAVE_CONFIG`): a salva foi feita com os offsets antigos.
3. Ligar o motor do extrusor na EBB36, conferir sentido e calibrar `rotation_distance` (herdado 13.10).
4. Calibrar pressure advance na Ender (herdado 0.064).
5. Opcional: remover `[force_move]` depois que tudo estiver calibrado.

## Dicas úteis pra próxima sessão

- Mudanças de config são feitas direto no Pi por SSH (ver `CLAUDE.md`); o cron de backup
  traz pro repositório. Se editar no clone local, rodar `git pull --rebase origin main` antes.
- `mainsail.cfg` aqui é symlink real no Pi — aparece no repo só como texto do caminho
  (`/home/biqu/mainsail-config/mainsail.cfg`), não adianta editar aqui.
- Bed mesh, PID (extrusora e mesa) e z_offset do BLTouch já estão calibrados e salvos no
  bloco `SAVE_CONFIG` do `printer.cfg` — não foram tocados nesta sessão.
