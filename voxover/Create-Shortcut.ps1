# Creates Voxover shortcuts beside the app and in the current user's Start menu.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$icon = Join-Path $root 'assets\app-icon\voxover.ico'
$localLauncher = Join-Path $root 'Open Voxover.cmd'
$shell = New-Object -ComObject WScript.Shell
$destinations = @($root, [Environment]::GetFolderPath('Programs'))
foreach ($destination in $destinations) {
    $path = Join-Path $destination 'Voxover.lnk'
    $link = $shell.CreateShortcut($path)
    if (Test-Path -LiteralPath $localLauncher) {
        $link.TargetPath = $localLauncher
    } else {
        $link.TargetPath = (Get-Command powershell.exe -ErrorAction Stop).Source
        $link.Arguments = '-NoProfile -File "' + (Join-Path $root 'Open-GUI.ps1') + '"'
    }
    $link.WorkingDirectory = $root
    $link.IconLocation = "$icon,0"
    $link.Description = 'Voxover'
    $link.Save()
    Write-Output $path
}
