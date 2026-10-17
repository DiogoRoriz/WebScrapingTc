<#
.SYNOPSIS
    Agenda a coleta diaria de precos no Agendador de Tarefas do Windows.

.DESCRIPTION
    Cria (ou atualiza) a tarefa "TCC - Coleta diaria de precos", que executa
    main.py todos os dias no horario informado (padrao 03:00, RNF01), sem
    janela de console. Se o computador estiver desligado ou dormindo no
    horario, a coleta roda assim que ele estiver disponivel.

    A tarefa roda com o usuario atual e somente com a sessao do Windows
    aberta (o Chrome precisa da sessao para abrir a janela fora da tela).
    Nao requer permissao de administrador.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\agendar_tarefa.ps1
    powershell -ExecutionPolicy Bypass -File .\agendar_tarefa.ps1 -Horario 04:30
#>
param(
    [string]$Horario = "03:00",
    [string]$NomeTarefa = "TCC - Coleta diaria de precos",
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$pasta = Split-Path -Parent $MyInvocation.MyCommand.Path

# Localiza o pythonw.exe (Python sem janela de console).
if (-not $Python) {
    $candidatos = @(Get-ChildItem "$env:LOCALAPPDATA\Python\pythoncore-*\pythonw.exe" -ErrorAction SilentlyContinue |
                    Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
    $candidatos += @(Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\pythonw.exe" -ErrorAction SilentlyContinue |
                     Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
    $Python = $candidatos | Select-Object -First 1
}
if (-not $Python -or -not (Test-Path $Python)) {
    throw "pythonw.exe nao encontrado. Informe o caminho com -Python 'C:\...\pythonw.exe'"
}
$python_console = Join-Path (Split-Path $Python) "python.exe"

# Confere se as dependencias estao instaladas nesse Python.
& $python_console -c "import pandas, openpyxl, selenium, bs4, requests"
if ($LASTEXITCODE -ne 0) {
    throw "Dependencias ausentes. Rode: `"$python_console`" -m pip install -r `"$pasta\requirements.txt`""
}

$acao = New-ScheduledTaskAction -Execute $Python -Argument "`"$pasta\main.py`"" -WorkingDirectory $pasta
$gatilho = New-ScheduledTaskTrigger -Daily -At $Horario
$opcoes = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 5) `
    -MultipleInstances IgnoreNew `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 30)
$usuario = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $NomeTarefa -Action $acao -Trigger $gatilho `
    -Settings $opcoes -Principal $usuario -Force `
    -Description "Pipeline do TCC: coleta precos (KaBuM!, Pichau, Terabyte, Amazon), carrega e trata os dados em $pasta\dados" | Out-Null

$tarefa = Get-ScheduledTask -TaskName $NomeTarefa
$info = $tarefa | Get-ScheduledTaskInfo
Write-Host "Tarefa '$NomeTarefa' agendada."
Write-Host "  Python:         $Python"
Write-Host "  Script:         $pasta\main.py"
Write-Host "  Proxima coleta: $($info.NextRunTime)"
Write-Host ""
Write-Host "Para executar agora:  Start-ScheduledTask -TaskName '$NomeTarefa'"
Write-Host "Para remover:         powershell -ExecutionPolicy Bypass -File .\remover_tarefa.ps1"
