param(
    [int]$Port = 8000,
    [int]$Timeout = 60,
    [switch]$Cleanup
)

Write-Host "[verify] Local Docker verification for Quetie_mbg"

function Fail([string]$msg, [int]$code=1) {
    Write-Host "[verify][error] $msg"
    exit $code
}

try {
    docker version | Out-Null
} catch {
    Fail "Docker does not appear to be running or accessible."
}

$image = 'quetie_mbg:local'
$container = 'quetie_mbg_local'

Write-Host "[verify] Building Docker image $image..."
docker build -t $image . | Write-Host

Write-Host "[verify] Removing existing container if present..."
try { docker rm -f $container -ErrorAction SilentlyContinue | Out-Null } catch {}

Write-Host "[verify] Starting container (mapping host:$Port -> container:8000)..."
$runArgs = @('--env-file', '.env', '-d', '--name', $container, '-p', "$Port`:8000", $image)
docker run @runArgs | Out-Null

Write-Host "[verify] Waiting for /health on http://localhost:$Port (timeout ${Timeout}s)"
$elapsed = 0
while ($elapsed -lt $Timeout) {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:$Port/health" -TimeoutSec 5 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            Write-Host "[verify] Health response:`n$($resp.Content)"
            Write-Host "[verify] Startup successful. Showing container logs (Ctrl+C to stop):"
            docker logs -f --tail 200 $container
            if ($Cleanup) {
                Write-Host "[verify] Cleanup requested: stopping and removing container"
                docker rm -f $container | Out-Null
            }
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 2
        $elapsed += 2
    }
}

Write-Host "[verify][error] Health endpoint did not respond within $Timeout seconds"
Write-Host "[verify] Container last logs:"
docker logs --tail 200 $container
exit 2
