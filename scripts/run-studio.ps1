$Py312 = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py312 -or -not (Test-Path $Py312)) {
    $Py312 = Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"
}
if (-not (Test-Path $Py312)) {
    $Py312 = "python"
}

Set-Location $RepoRoot
$env:PYTHONIOENCODING = "utf-8"
& $Py312 -m studio @args
