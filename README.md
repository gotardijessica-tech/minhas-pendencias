# Minhas Pendências

Uma janela que aparece sozinha na primeira vez que você usa o PC no dia (ao
ligar ou ao voltar da suspensão) com:

- as suas atividades em aberto no **Flow** (as atas), buscadas no site do Flow;
- uma lista sua de pendências avulsas, que você cria, edita e marca como feitas
  a qualquer hora.

O app se atualiza sozinho: quando sai uma versão nova aqui no GitHub, aparece
uma faixa amarela no topo com o botão **Atualizar agora**.

## O que precisa

1. **Python** instalado. O jeito mais fácil é abrir o PowerShell e rodar:

   ```
   winget install --id Python.Python.3.14 -e --accept-package-agreements --accept-source-agreements
   ```

   Ou baixe em <https://www.python.org/downloads/> e marque **"Add python.exe
   to PATH"** na primeira tela do instalador.
2. O seu **login do Flow** (o e-mail que você usa para abrir o site do Flow).
   Esse e-mail precisa estar cadastrado na equipe do Flow. Se não estiver, peça
   para a Jessica cadastrar e publicar de novo.

## Como instalar

1. Nesta página, clique em **Code → Download ZIP** e descompacte em
   `Documentos\Pendencias`.
2. Dentro da pasta, dê **duplo clique em `instalar.bat`**. Se o Windows
   avisar "O Windows protegeu o computador", clique em **Mais informações** e
   depois em **Executar assim mesmo** — isso aparece em qualquer programa
   baixado da internet, é normal.

   Uma janela preta abre e faz tudo sozinha: instala o `cloudflared`
   (programa oficial da Cloudflare que faz o login no Flow), cria a tarefa
   que abre a lista todo dia e coloca o atalho **Minhas Pendências** na Área
   de Trabalho e no Menu Iniciar. Aperte uma tecla para fechá-la quando
   terminar.

   (Se preferir, dá para rodar pelo PowerShell também:
   `powershell -ExecutionPolicy Bypass -File .\instalar.ps1`)
3. Abra o atalho. Na primeira vez o navegador abre para você entrar no Flow com
   o seu e-mail. Depois disso, o app só pede o login de novo quando ele vence.

## Bom saber

- A lista abre sozinha **uma vez por dia**: na primeira vez que você liga o
  PC, entra no Windows, desbloqueia a tela ou volta da suspensão. Nas outras
  vezes do mesmo dia ela não aparece sozinha; é só usar o atalho.
- O botão **Abrir o Flow**, com o logo, no canto de cima da janela, abre o
  site do Flow no navegador.
- As atividades do Flow aparecem como estavam na última publicação do site. O
  app só lê e nunca muda nada no Flow. Para marcar uma atividade como feita,
  use o site do Flow.
- Sem internet, o app mostra a última versão que baixou.
- Suas pendências e configurações ficam só no seu PC (`minhas_pendencias.json`
  e `config.json`). Atualizar o app não mexe nelas.
- Se o seu nome não for reconhecido, abra o `config.json` e escreva o seu nome
  exatamente como aparece no Flow em `"meuNome"`.
- Se uma atualização der problema, a versão anterior fica guardada como
  `pendencias.pyw.bak`.
- Para desinstalar (seus arquivos continuam na pasta): duplo clique em
  `desinstalar.bat`, ou
  `powershell -ExecutionPolicy Bypass -File .\instalar.ps1 -Remover`.
