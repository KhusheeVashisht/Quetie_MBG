<#
Lightweight Docker verification script for Quetie_mbg (PowerShell)
- Builds the image
- Starts the container (python main.py --mode all)
- Waits for /health to respond
- Tails logs
#>

param(
    [switch]$Cleanup
)

Set-StrictMode -Version Latest
$Image = 'quetie_mbg:local'
$Container = 'quetie_mbg_local'
$Port = if ($env:PORT) { [int]$env:PORT } else { 8000 }
$EnvFile = '.env'
$MaxWait = 60

Write-Host "== Quetie_mbg Docker verification (PowerShell) =="

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not available in PATH"
    exit 2
}

Write-Host "Removing existing container if present: $Container"
try { docker rm -f $Container | Out-Null } catch {}

Write-Host "Building Docker image: $Image"
docker build -t $Image .

$runArgs = @('run','-d','-p',"$Port`:8000","--name",$Container)
if (Test-Path $EnvFile) {
    Write-Host "Using env file: $EnvFile"
    $runArgs += @('--env-file',$EnvFile)
} else {
    Write-Warning "$EnvFile not found. Environment variables may be missing."
}
$runArgs += $Image

Write-Host "Starting container..."
docker @runArgs | Out-Null

Write-Host "Waiting up to $MaxWait seconds for /health..."
$success = $false
for ($i=0; $i -lt $MaxWait; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 5
        Write-Host "Health response:`n" ($resp | ConvertTo-Json -Depth 5)
        $success = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $success) {
    Write-Host "Health check failed. Displaying container logs..."
    docker logs --tail 200 $Container
    exit 1
}

Write-Host "Application started successfully. Tailing logs (Ctrl+C to stop)."
docker logs -f $Container

if ($Cleanup) {
    Write-Host "Cleaning up container..."
    docker rm -f $Container | Out-Null
    Write-Host "Container removed."
}
