<#
.SYNOPSIS
    Remove a tarefa agendada da coleta diaria de precos.
#>
param([string]$NomeTarefa = "TCC - Coleta diaria de precos")

if (Get-ScheduledTask -TaskName $NomeTarefa -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $NomeTarefa -Confirm:$false
    Write-Host "Tarefa '$NomeTarefa' removida."
} else {
    Write-Host "Tarefa '$NomeTarefa' nao existe."
}
