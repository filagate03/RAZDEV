param(
    [string]$TunnelDomain,
    [switch]$DisableWebhook,
    [int]$Port = 5000,
    [switch]$UseNgrok,
    [string]$NgrokPath = "$HOME\ngrok\ngrok.exe"
)

$ErrorActionPreference = "Stop"

function Write-Step($message) {
    Write-Host "[run] $message" -ForegroundColor Cyan
}

function Test-PortInUse {
    param([int]$TestPort)
    try {
        $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
        return $listeners | Where-Object { $_.Port -eq $TestPort }
    } catch {
        return $false
    }
}

function Start-NgrokTunnel {
    param(
        [string]$Executable,
        [int]$Port
    )
    Write-Step "Starting ngrok tunnel on port $Port"
    $proc = Start-Process -FilePath $Executable -ArgumentList "http", $Port -WindowStyle Minimized -PassThru
    $publicUrl = $null
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2 -ErrorAction Stop
            $publicUrl = ($tunnels.tunnels | Where-Object { $_.proto -eq 'https' } | Select-Object -First 1).public_url
            if ($publicUrl) { break }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $publicUrl) {
        Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue
        throw "Failed to obtain ngrok public URL. Ensure ngrok is running and not blocked by firewall."
    }
    Write-Step "ngrok tunnel active: $publicUrl"
    return [pscustomobject]@{ Process = $proc; Url = $publicUrl }
}

Write-Step "ImageGenBot local launcher"
Write-Step "Usage: .\\run_local.ps1 [-TunnelDomain https://xxxx.ngrok.io] [-DisableWebhook] [-Port 5000] [-UseNgrok] [-NgrokPath <path>]"

try {
    $python = (Get-Command python -ErrorAction Stop).Source
    Write-Step "Found Python at $python"
} catch {
    Write-Error "Python 3.11+ is required. Install it and re-run the script."
    exit 1
}

if (-not (Test-Path ".venv")) {
    Write-Step "Creating virtual environment (.venv)"
    & $python -m venv .venv
} else {
    Write-Step "Virtual environment already exists"
}

$venvPython = Join-Path -Path ".venv" -ChildPath "Scripts/python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "Unable to find $venvPython"
    exit 1
}

Write-Step "Upgrading pip"
& $venvPython -m pip install --upgrade pip | Out-Host

Write-Step "Installing dependencies"
& $venvPython -m pip install -r requirements.txt | Out-Host

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Step "Creating .env from .env.example"
        Copy-Item ".env.example" ".env"
    } else {
        Write-Warning "No .env found. Create it manually before running the bot."
    }
} else {
    Write-Step ".env already exists"
}

if ($DisableWebhook.IsPresent) {
    Write-Step "Setting USE_WEBHOOK=False"
    $env:USE_WEBHOOK = "False"
    Write-Step "Reminder: polling mode not implemented; bot will receive no updates until you re-enable webhooks."
} else {
    $env:USE_WEBHOOK = "True"
}

$selectedPort = $Port
$attempts = 0
while (Test-PortInUse -TestPort $selectedPort) {
    $attempts++
    if ($attempts -gt 20) {
        throw "Unable to find free port starting from $Port. Close the conflicting process or pass -Port."
    }
    $selectedPort++
}

if ($selectedPort -ne $Port) {
    Write-Step "Port $Port is busy. Using $selectedPort instead."
} else {
    Write-Step "Using port $selectedPort"
}
$env:PORT = $selectedPort.ToString()

$ngrokContext = $null
try {
    if ($UseNgrok) {
        if (-not (Test-Path $NgrokPath)) {
            throw "ngrok executable not found at $NgrokPath. Install ngrok or specify -NgrokPath."
        }
        $ngrokContext = Start-NgrokTunnel -Executable $NgrokPath -Port $selectedPort
        $TunnelDomain = $ngrokContext.Url
    }

    if ($TunnelDomain) {
        $normalized = $TunnelDomain.TrimEnd('/')
        $domainOnly = $normalized -replace '^https?://', ''
        Write-Step "Setting REPLIT_DOMAINS=$domainOnly for webhook autoconfig"
        $env:REPLIT_DOMAINS = $domainOnly
        $env:WEBHOOK_HOST = $normalized
    } else {
        Write-Step "No tunnel domain supplied. Telegram updates require manual webhook setup."
    }

    Write-Step "Launching bot (Ctrl+C to stop)"
    & $venvPython main.py
}
finally {
    if ($ngrokContext -and $ngrokContext.Process -and -not $ngrokContext.Process.HasExited) {
        Write-Step "Stopping ngrok (PID=$($ngrokContext.Process.Id))"
        Stop-Process -Id $ngrokContext.Process.Id -ErrorAction SilentlyContinue
    }
}