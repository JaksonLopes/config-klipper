# Notas de sessão — Ender 3 (placa FLY_D5)

> Documento de contexto para futuras sessões. Resume o que foi diagnosticado e corrigido,
> o que ficou pendente, e armadilhas conhecidas desse setup específico.
> Última atualização: sessão de 2026-08-08.
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

## Dicas úteis pra próxima sessão

- Sempre `git pull --rebase origin main` antes de editar (cron de backup pode ter
  avançado o remoto).
- `mainsail.cfg` aqui é symlink real no Pi — aparece no repo só como texto do caminho
  (`/home/biqu/mainsail-config/mainsail.cfg`), não adianta editar aqui.
- Bed mesh, PID (extrusora e mesa) e z_offset do BLTouch já estão calibrados e salvos no
  bloco `SAVE_CONFIG` do `printer.cfg` — não foram tocados nesta sessão.
