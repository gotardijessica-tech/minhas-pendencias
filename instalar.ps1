# Instala o "Minhas Pendências":
#   - Tarefa Agendada que abre a lista ao entrar no Windows e ao voltar da
#     suspensão (o próprio app só aparece na primeira vez do dia).
#   - Atalhos na Área de Trabalho e no Menu Iniciar para abrir quando quiser.
# Pode rodar de novo sem problema: ele substitui o que já existe.
# Para desinstalar: .\instalar.ps1 -Remover

param([switch]$Remover)

$ErrorActionPreference = 'Stop'
$pasta = $PSScriptRoot
$script = Join-Path $pasta 'pendencias.pyw'
$nomeTarefa = 'Minhas Pendencias'
$atalhos = @(
  (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Minhas Pendências.lnk'),
  (Join-Path ([Environment]::GetFolderPath('Programs')) 'Minhas Pendências.lnk')
)

if ($Remover) {
  schtasks /Delete /TN $nomeTarefa /F | Out-Null
  foreach ($a in $atalhos) { if (Test-Path $a) { Remove-Item $a } }
  Write-Host 'Removido (a tarefa e os atalhos). Seus arquivos nesta pasta continuam aqui.'
  return
}

# ---- Python (o app é um programa Python) ----
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
  Write-Host 'O Python não está instalado. Instale pelo site https://www.python.org/downloads/'
  Write-Host '(marque "Add python.exe to PATH" na instalação) e rode este instalar.ps1 de novo.'
  return
}

# ---- cloudflared (só para quem busca as pendências no SITE do Flow) ----
# Quem tem o dados.json no PC (a editora) não precisa dele.
$dadosFlow = Join-Path $env:USERPROFILE 'Documents\AtasApp\dados.json'
$precisaCloudflared = -not (Test-Path $dadosFlow)
$config = Join-Path $pasta 'config.json'
if (Test-Path $config) {
  $precisaCloudflared = ((Get-Content $config -Raw -Encoding UTF8 | ConvertFrom-Json).fonte -eq 'site')
}
if ($precisaCloudflared -and -not (Get-Command cloudflared -ErrorAction SilentlyContinue) `
    -and -not (Test-Path "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe")) {
  Write-Host 'Instalando o cloudflared (programa oficial da Cloudflare para o login no Flow)...'
  winget install --id Cloudflare.cloudflared --exact --silent --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) { throw 'Não consegui instalar o cloudflared pelo winget.' }
}

$usuario = "$env:USERDOMAIN\$env:USERNAME"

# Gatilhos:
#  1. Ao fazer logon (ligar o PC / entrar), com 15 s de folga para o Windows assentar.
#  2. Ao voltar da suspensão/hibernação: evento 1 da fonte
#     Microsoft-Windows-Power-Troubleshooter no log Sistema.
# MultipleInstancesPolicy=Parallel: se a janela ficou aberta desde ontem, a
# nova execução só a traz para frente.
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Mostra a lista de pendências na primeira vez que o PC é usado no dia.</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$usuario</UserId>
      <Delay>PT15S</Delay>
    </LogonTrigger>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
      <Delay>PT5S</Delay>
    </EventTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$usuario</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>Parallel</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <StartWhenAvailable>true</StartWhenAvailable>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$pythonw</Command>
      <Arguments>"$script" --auto</Arguments>
      <WorkingDirectory>$pasta</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$arqXml = Join-Path $env:TEMP 'minhas-pendencias-tarefa.xml'
$xml | Out-File -FilePath $arqXml -Encoding unicode
schtasks /Create /TN $nomeTarefa /XML $arqXml /F
$codigo = $LASTEXITCODE
Remove-Item $arqXml
if ($codigo -ne 0) { throw "Não consegui criar a Tarefa Agendada (código $codigo)." }

$shell = New-Object -ComObject WScript.Shell
foreach ($a in $atalhos) {
  $lnk = $shell.CreateShortcut($a)
  $lnk.TargetPath = $pythonw
  $lnk.Arguments = "`"$script`""
  $lnk.WorkingDirectory = $pasta
  $lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,76"
  $lnk.Description = 'Minhas Pendências'
  $lnk.Save()
}

Write-Host ''
Write-Host 'Pronto!'
Write-Host " - Tarefa agendada '$nomeTarefa' criada (logon + volta da suspensão)."
Write-Host ' - Atalho "Minhas Pendências" na Área de Trabalho e no Menu Iniciar.'
