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

## Push para o git

Quando o usuário pedir pra "subir os ajustes", "enviar pro git", "mandar pro repositório"
ou equivalente, pode **commitar e dar `git push` direto**, sem pedir confirmação extra
antes do push — essa autorização já vale antecipadamente pra esse tipo de pedido neste
repositório (ainda assim, sempre rodar `git pull --rebase origin main` antes, por causa
do cron de backup automático).
