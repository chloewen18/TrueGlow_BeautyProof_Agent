param([int]$ApiPort = 8000, [int]$UiPort = 8503)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Install dependencies into .venv first.' }
foreach ($port in @($ApiPort, $UiPort)) {
    $probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
    try { $probe.Start() } catch { throw "Port $port is in use. Select another port; no existing process was stopped." } finally { $probe.Stop() }
}
$logs = Join-Path $root 'backend/data/runtime'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$env:BEAUTYPROOF_API_BASE_URL = "http://127.0.0.1:$ApiPort"
$env:PYTHONUTF8 = '1'
$api = Start-Process -FilePath $python -ArgumentList "-m uvicorn backend.app.main:app --host 127.0.0.1 --port $ApiPort" -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput "$logs/api-$ApiPort.stdout.log" -RedirectStandardError "$logs/api-$ApiPort.stderr.log" -PassThru
$ui = Start-Process -FilePath $python -ArgumentList "-m streamlit run app.py --server.address 127.0.0.1 --server.port $UiPort --server.headless true --browser.gatherUsageStats false" -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput "$logs/ui-$UiPort.stdout.log" -RedirectStandardError "$logs/ui-$UiPort.stderr.log" -PassThru
Write-Output "Frontend: http://127.0.0.1:$UiPort/ (launcher PID $($ui.Id))"
Write-Output "API: http://127.0.0.1:$ApiPort/docs (launcher PID $($api.Id))"
