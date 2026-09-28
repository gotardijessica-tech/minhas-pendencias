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
- `instalar.bat` / `desinstalar.bat`: duplo-clique em vez de abrir o
  PowerShell à mão (mais simples para quem instala do zero). Só chamam
  `powershell -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"` (o segundo
  com `-Remover`) e dão `pause` no fim para a janela não sumir sozinha.
  `%~dp0` resolve o caminho da PASTA DO .bat, então funciona de qualquer
  lugar — não precisam de `cd`. Escritos em **ASCII puro, sem acento e sem
  BOM**: de propósito — `.bat` usa a code page do console (não UTF-8) e um
  BOM no início pode atrapalhar o `@echo off`; a mensagem em si não tem
  acento, então não há por que arriscar. Mantidos fora de `ARQUIVOS_DO_APP`
  porque nada os chama depois da primeira instalação — só servem para quem
  ainda vai instalar.
- Quando o app abre sozinho: gatilhos da Tarefa Agendada = logon, desbloqueio
  da tela (é o que pega a volta do Modern Standby, que não gera o evento de
  "volta da suspensão") e evento 1 do Power-Troubleshooter (volta do S3 / da
  hibernação). O app filtra para aparecer só na primeira vez do dia.
- O logo do botão "Abrir o Flow" fica **dentro** do `pendencias.pyw`, em
  `LOGO_FLOW_28` e `LOGO_FLOW_42` (PNGs em base64, cantos transparentes, sem a
  sombra do original, reduzidos com bilinear — o bicúbico cria um contorno
  escuro no traço branco). O de 42 px é usado com zoom ≥ 125%. Embutido de
  propósito: o atualizador dos PCs antigos só baixa os arquivos da lista
  *deles*, então um arquivo de imagem novo não chegaria.
- **Nitidez com zoom do Windows:** `ativar_nitidez()` (chamado no começo de
  `main()`) avisa o Windows que o app lida com o zoom; sem isso ele estica a
  janela e tudo fica borrado. Por isso **toda medida em pixels passa por
  `self.px()`** (tamanho da janela, colunas, altura de linha, padx/pady),
  escrita pensando em 100% — `px()` multiplica pelo zoom. Fontes em pontos
  (`("Segoe UI", 10)`) já crescem sozinhas. Medida nova sem `px()` fica
  pequena em telas com zoom.
- Os botões de baixo são empacotados **primeiro** (`side="bottom"`) para
  nunca sumirem quando a janela fica baixa; o tamanho mínimo da janela é
  medido depois de montar tudo (`winfo_reqheight`).
- Nunca versionar dados de cada PC: `config.json`, `minhas_pendencias.json`,
  `estado.json`, `cache_flow.json` (estão no `.gitignore`).
- O app **só lê** o Flow (o `dados.json` do AtasApp ou o site publicado). Nunca
  escrever no `dados.json`.
- Commit e push só quando a dona pedir.
- Testar em uma cópia da pasta (no %TEMP%), nunca nos arquivos de dados reais.
