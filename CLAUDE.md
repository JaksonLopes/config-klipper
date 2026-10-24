# Instruções do projeto — config-klipper

## Idioma

**Responder sempre em português** — tanto perguntas quanto respostas, nunca em inglês.
Nomes de comandos, arquivos, seções de config e valores técnicos podem ficar em inglês
(é o padrão do Klipper/Happy Hare), mas todo texto explicativo deve ser em português.

## Estrutura do repositório

Este repositório guarda a configuração do Klipper de várias impressoras, todas
hospedadas no mesmo BTT Pi (setup multi-instância):

- `trident/` — Voron Trident com MMU MMX (Happy Hare). Histórico detalhado de
  diagnósticos/correções em [`trident/SESSION_NOTES.md`](trident/SESSION_NOTES.md).
- `ender3/` — Ender 3 (placa FLY_D5). Histórico em
  [`ender3/SESSION_NOTES.md`](ender3/SESSION_NOTES.md).
- `outra/` — outra impressora no mesmo Pi (config ainda mínima/pouco explorada).

**Sempre que uma sessão de trabalho substancial for feita numa impressora**, criar ou
atualizar um arquivo `SESSION_NOTES.md` dentro da respectiva pasta (seguindo o modelo de
`trident/SESSION_NOTES.md`), documentando o que foi diagnosticado, corrigido e o que
ficou pendente. Não misturar o histórico de impressoras diferentes num único arquivo —
cada uma tem hardware e problemas próprios.

## Pi multi-instância — cuidados válidos pra qualquer impressora deste Pi

- O BTT Pi hospeda 4 instâncias Klipper (`printer_data`, `printer_Ender3_data`,
  `printer_outra_data`, `printer_Trident_data`), cada uma com seu próprio serviço
  systemd nomeado `klipper-<Nome>.service` / `moonraker-<Nome>.service`. **Não existe
  `klipper.service` "pelado" nesse Pi** — sempre confirmar o nome real com
  `systemctl list-units --all | grep -i klipper` antes de reiniciar algo.
- `~/klipper` e `~/Happy-Hare` são **compartilhados** entre as instâncias — uma mudança
  na fonte do Klipper (ex: reverter uma versão) afeta as 4 impressoras, não só uma que
  está sendo trabalhada no momento. Só a Trident usa Happy Hare/MMU.
- Existe um **cron de backup automático** rodando no Pi que commita e dá push
  periodicamente (commits "Backup automático: DATA"). **Sempre rodar
  `git pull --rebase origin main` antes de editar** qualquer arquivo deste repositório,
  pra não entrar em conflito com o backup.
- Cuidado com atualizações "tudo de uma vez" (Klipper + addons tipo Happy Hare + o
  sistema operacional do Pi) — foi exatamente essa combinação que causou o incidente
  grande documentado em `trident/SESSION_NOTES.md`. Antes de atualizar o Klipper numa
  impressora que usa um addon como Happy Hare, vale checar se a versão instalada do
  addon já é compatível com a versão nova antes de aceitar a atualização.
- Vários arquivos de config podem ser **symlinks reais no Pi** que, quando o backup
  automático os traz pra este repositório, aparecem aqui como um texto simples contendo
  só o caminho do link (o script de backup não segue o link). Antes de editar um arquivo
  aqui, checar se o conteúdo faz sentido como config de verdade — se for só uma linha
  com um caminho, é um symlink, e a edição de verdade precisa ser feita direto no Pi (ou
  no projeto de onde o link aponta, como o Happy-Hare).
- A Trident usa um módulo Klipper próprio, `trident/extras/servo_gear_buzz.py`, que precisa
  de um link em `~/klipper/klippy/extras/servo_gear_buzz.py` (comando no item 35 de
  `trident/SESSION_NOTES.md`). Se o Klipper/Pi for reinstalado e o link sumir, a Trident
  para com erro de seção `[servo_gear_buzz]` inválida — basta recriar o link.

## Acesso de rede ao Pi (IPs e portas)

IP do Pi na rede local: **`192.168.3.17`**

| Impressora    | Porta API Moonraker | Porta Mainsail dedicada (sem seleção) |
|---------------|----------------------|----------------------------------------|
| Voron Trident | `7126`               | `8126`                                  |
| Ender 3       | `7125`               | `8125`                                  |
| Outra         | não confirmada ainda | não configurada ainda                   |

- **Porta da API Moonraker** (`7125`/`7126`) — usar no OrcaSlicer como "Upload do Host de
  Impressão" (ex: `192.168.3.17:7126` pra Trident) pra enviar G-code. Acessar só essa
  porta direto no navegador mostra uma tela crua "Welcome to Moonraker" (é só a API, sem
  interface visual).
- **Porta Mainsail dedicada** (`8125`/`8126`) — site NGINX próprio criado em 2026-10-01
  (`/etc/nginx/sites-available/mainsail-trident` e `mainsail-ender3`, mesmo `root
  /home/biqu/mainsail` do site principal, cada um com seu próprio `upstream` apontando
  pra porta Moonraker certa) pra conseguir ver a interface visual de uma impressora
  específica sem precisar passar pela tela de seleção. Ainda pede a tela de seleção uma
  vez ao abrir (o `config.json` do Mainsail é compartilhado entre os sites), mas depois
  de selecionar funciona normal — e o envio de arquivo pelo Orca funciona direto nessa
  porta sem precisar selecionar nada.
- **`http://192.168.3.17`** (porta 80, sem porta nenhuma) — Mainsail "principal", mostra
  a tela "Select Printer" pra escolher entre Ender 3 / Voron Trident / Outra.
- Link direto pra pular a tela de seleção (funciona num navegador normal, mas não
  funciona de dentro do navegador embutido do OrcaSlicer):
  `http://192.168.3.17/?printer=Voron%20Trident`

## Fluxo de edição: direto no Pi por SSH (preferido)

Decisão do dono em 2026-10-24: **mudanças de configuração (Ender e Trident) são feitas
direto no host, por SSH**, sem passar antes pelo git local. O cron de backup traz o
resultado pra este repositório, e o dono depois dá `git pull` na máquina dele.

- Acesso: `ssh biqu@192.168.3.17` com chave sem senha já autorizada (`C:\Users\Jakson\.ssh\id_ed25519`).
  O `sudo` do Pi pede senha e Claude não digita senha: passos com root (arquivos em
  `/etc`, regras udev, `systemctl`, `dfu-util`) viram um script em `/tmp` que o dono
  executa com `sudo bash` na aba de terminal dele.
- Onde ficam as configs: Ender em `~/printer_Ender3_data/config/`, Trident em
  `~/printer_Trident_data/config/` (mesmos arquivos que o backup espelha em `ender3/` e `trident/`).
- Antes de editar um arquivo no Pi, fazer uma cópia datada ao lado dele
  (`printer-AAAAMMDD_HHMMSS.cfg`, padrão que já existe na pasta).
- Depois de editar: `FIRMWARE_RESTART` pela API do Moonraker
  (`curl -X POST localhost:7125/printer/firmware_restart` na Ender, `7126` na Trident) e
  conferir `printer/info`. Só reiniciar a Trident com ela parada.
- O `SESSION_NOTES.md` de cada impressora também existe na pasta `config/` do Pi — pode
  ser atualizado direto lá, junto da mudança.
- O dono autorizou também editar/commitar direto na `main` deste repositório (projeto
  pessoal), quando a edição for mesmo aqui. O hook `branch-protection` do plugin zcode
  pode bloquear Edit/Write na `main`; editar no Pi evita isso e é o fluxo preferido.

## Redes CAN no Pi (duas, independentes)

- `can_trident` = ponte da Trident (placa `stm32f072xb`, serial USB `3E001B001353303650373120`);
  os 4 MCUs da Trident (`[mcu]`, `ebb36`, `eddy`, `unit0` do Happy Hare) têm
  `canbus_interface: can_trident` explícito. **Nunca usar `can0`/`can1`:** são nomes do
  kernel e mudam de ordem no boot (em 2026-10-24 a D5 pegou `can0` e a Trident parou).
- `can_ender` = ponte da Fly D5 da Ender 3 (serial USB `450049000757465036383420`).
- Os nomes e a subida (1000000 de bitrate, `txqueuelen 1024`, `up`) vêm da regra udev
  `/etc/udev/rules.d/70-can-bridges.rules`, por serial USB, a cada reconexão da ponte.
  O `ifupdown` não gerencia mais essas interfaces. Uma ponte nova precisa ganhar a regra dela.
  Detalhes e UUIDs em [`ender3/SESSION_NOTES.md`](ender3/SESSION_NOTES.md).
- Binários/configs de firmware: `~/firmware-backup`, `~/klipper/config.d5`,
  `~/klipper/config.ebb36`, `~/katapult/config.ebb36` (compilar com `KCONFIG_CONFIG=` próprio
  e nunca mexer em `~/klipper/.config`, que é compartilhado).

## Push para o git

Quando o usuário pedir pra "subir os ajustes", "enviar pro git", "mandar pro repositório"
ou equivalente, pode **commitar e dar `git push` direto**, sem pedir confirmação extra
antes do push — essa autorização já vale antecipadamente pra esse tipo de pedido neste
repositório (ainda assim, sempre rodar `git pull --rebase origin main` antes, por causa
do cron de backup automático).
