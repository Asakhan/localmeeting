$ErrorActionPreference = 'Stop'
$appExe = Join-Path $PSScriptRoot 'dist\LocalMeeting\LocalMeeting.exe'
if (-not (Test-Path -LiteralPath $appExe)) { throw '먼저 build.py로 EXE를 빌드하세요.' }
$shortcutFile = Join-Path ([Environment]::GetFolderPath('Desktop')) '로컬 회의록.lnk'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutFile)
$shortcut.TargetPath = $appExe
$shortcut.WorkingDirectory = Split-Path -LiteralPath $appExe
$shortcut.Description = '로컬 녹음, 전사, 화자 분리 및 Word 회의록'
$shortcut.Save()
Write-Output $shortcutFile
