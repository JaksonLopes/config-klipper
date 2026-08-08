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
- `ender3/` — Ender 3 (placa FLY_D5). Ainda sem sessão de trabalho registrada.
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
