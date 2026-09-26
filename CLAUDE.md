# CLAUDE.md

App "Minhas Pendências" (Python + tkinter, um arquivo só: `pendencias.pyw`).
Código, comentários e textos em **português (pt-BR)**. A dona está aprendendo a
programar: prefira código simples e legível a abstrações espertas.

## Regras

- **Ao mudar o `pendencias.pyw`, suba `VERSAO`** (ex.: "1.1" → "1.2") no topo do
  arquivo. É assim que os PCs dos colegas descobrem que há versão nova: o app
  baixa o `pendencias.pyw` do GitHub (repositório público
  `gotardijessica-tech/minhas-pendencias`, branch `main`) e compara o `VERSAO`.
  Sem subir o número, ninguém recebe a mudança.
- Os arquivos que a atualização baixa estão em `ARQUIVOS_DO_APP`. Se criar ou
  renomear um arquivo que o app precisa, atualize essa lista.
- **Mudou o `instalar.ps1`?** Nos PCs dos colegas o app roda ele sozinho,
  escondido, na primeira abertura depois da atualização (compara o SHA-256 do
  arquivo com `instaladorAplicado` no `estado.json`). Por isso o instalador tem
  que poder rodar de novo sem perguntar nada e sair com código ≠ 0 quando
  falhar. No PC da editora (pasta do git) isso não acontece: rode-o à mão.
- O `instalar.ps1` precisa ficar em **UTF-8 com BOM**: sem o BOM, o PowerShell
  5.1 lê os acentos errado (o atalho "Minhas Pendências" sai com nome
  quebrado).
- Quando o app abre sozinho: gatilhos da Tarefa Agendada = logon, desbloqueio
  da tela (é o que pega a volta do Modern Standby, que não gera o evento de
  "volta da suspensão") e evento 1 do Power-Troubleshooter (volta do S3 / da
  hibernação). O app filtra para aparecer só na primeira vez do dia.
- Nunca versionar dados de cada PC: `config.json`, `minhas_pendencias.json`,
  `estado.json`, `cache_flow.json` (estão no `.gitignore`).
- O app **só lê** o Flow (o `dados.json` do AtasApp ou o site publicado). Nunca
  escrever no `dados.json`.
- Commit e push só quando a dona pedir.
- Testar em uma cópia da pasta (no %TEMP%), nunca nos arquivos de dados reais.
