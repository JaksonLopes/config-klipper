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

Reorganizado nesta sessão. Estrutura atual:

```
trident/
├── printer.cfg          # Só includes, [mcu]/[mcu mmu], [printer] (cinemática) e SAVE_CONFIG
├── toolhead.cfg          # EBB36 (extrusora/fans/tmc) + Eddy (sonda) — fundidos aqui
├── steppers.cfg          # stepper_x/y/z/z1/z2 + tmc2209 + adxl345/resonance_tester
├── bed_leveling.cfg      # safe_z_home, z_tilt, bed_mesh
├── heaters_fans.cfg      # sensores de temperatura, heater_bed, controller_fan
├── misc.cfg              # idle_timeout, virtual_sdcard, exclude_object
├── macros.cfg            # PRINT_START, PRINT_END, LIMPAR_BICO, CORTE_FILAMENTO, _MMU_PURGE_CUSTOM
├── mainsail.cfg           # symlink real no Pi (aqui aparece só como texto do caminho)
├── moonraker.conf
└── mmu/
    ├── base/              # mmu.cfg, mmu_hardware.cfg, mmu_parameters.cfg, mmu_macro_vars.cfg
    │                        são arquivos REAIS e editáveis.
    │                        Os demais (mmu_cut_tip.cfg, mmu_form_tip.cfg, mmu_purge.cfg,
    │                        mmu_sequence.cfg, mmu_software.cfg, mmu_state.cfg, mmu_leds.cfg,
    │                        mmu_heater_vent.cfg) são SYMLINKS reais no Pi apontando pra
    │                        ~/Happy-Hare/config/base/ — aqui no repo aparecem só como um
    │                        texto com o caminho (o backup automático não segue o symlink).
    │                        NÃO adianta editar esses no repo, o conteúdo real está no Pi.
    ├── addons/            # mmu_erec_cutter.cfg (não usado), blobifier.cfg (não usado)
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

## Checklist de pendências pro usuário confirmar

- [ ] Trocar ordem do End G-code no OrcaSlicer para `MMU_END` antes de `PRINT_END`
      (ver item 6).
- [ ] Opcional: zerar de vez o "volume de ramming" em Filament Settings → Multimaterial
      no OrcaSlicer (item 5) — não crítico, já está seguro.
- [ ] Ficar de olho: se atualizar o Happy Hare de novo (`install.sh` rodar), o patch do
      `mmu.py` (item 3, causa raiz #3) volta a ser sobrescrito — checar se já saiu
      correção oficial antes, ou reaplicar o patch.
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
