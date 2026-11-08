$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = if ($env:VOICE_STUDIO_PYTHON) { $env:VOICE_STUDIO_PYTHON } else { 'python' }
$port = if ($env:VOICE_STUDIO_PORT) { $env:VOICE_STUDIO_PORT } else { '8003' }
$url = "http://127.0.0.1:$port"
try { $ready = (Invoke-WebRequest "$url/config" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { $ready=$false }
if (!$ready) {
 Start-Process -FilePath $python -ArgumentList '-B',"`"$root/app.py`"" -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput "$root/stdout.log" -RedirectStandardError "$root/stderr.log"
 for ($i=0; $i -lt 30; $i++) { Start-Sleep -Seconds 1; try { $ready=(Invoke-WebRequest "$url/config" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {}; if($ready){break} }
}
if (!$ready) { throw "Voice Studio failed to start; inspect stderr.log" }
Start-Process $url
