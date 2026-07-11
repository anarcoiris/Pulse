# Forge Studio launcher — uses Python 3.12 explicitly (avoids KiCad/hermes venv OPENSSL crash).
$Py312 = "C:\Users\soyko\AppData\Local\Programs\Python\Python312\python.exe"
$RepoRoot = Split-Path $PSScriptRoot -Parent

if (-not (Test-Path $Py312)) {
    Write-Error "Python 3.12 not found at $Py312"
    exit 1
}

Set-Location $RepoRoot
$env:PYTHONIOENCODING = "utf-8"
& $Py312 -m studio @args
