$ErrorActionPreference = "Stop"

# 1. Define paths and set up logging
$projectPath = "c:\Users\Markuhhh\Desktop\Jr\Projects\Projects\Deeks"
$logDir = "$projectPath\logs"
$startupLog = "$logDir\startup.log"
$ollamaLog = "$logDir\ollama.log"
$deeksLog = "$logDir\deeks.log"

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $Message"
    Add-Content -Path $startupLog -Value $logMessage
    Write-Host $logMessage
}

Write-Log "--- Starting Deeks Startup Sequence ---"

# 2. Launch the llama server process in the background
Write-Log "Launching Ollama server in the background..."
# Start-Process with -WindowStyle Hidden ensures no terminal is visible
# We redirect standard output and error to our log file so we can debug later
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -RedirectStandardOutput $ollamaLog -RedirectStandardError $ollamaLog

# 3. Poll the llama server's local endpoint until it responds
$ollamaUrl = "http://localhost:11434/"
$maxRetries = 30
$retryDelaySeconds = 2
$isReady = $false

Write-Log "Polling $ollamaUrl to check if Ollama is ready..."

for ($i = 1; $i -le $maxRetries; $i++) {
    try {
        # -UseBasicParsing is used for broader compatibility
        # -ErrorAction Stop ensures that if the server isn't up, it drops into the catch block
        $response = Invoke-WebRequest -Uri $ollamaUrl -UseBasicParsing -ErrorAction Stop
        
        if ($response.StatusCode -eq 200 -and $response.Content -match "Ollama is running") {
            Write-Log "Ollama is up and responding! (Attempt $i)"
            $isReady = $true
            break
        }
    } catch {
        Write-Log "Attempt $i/$maxRetries: Ollama not ready yet. Waiting $retryDelaySeconds seconds..."
    }
    
    Start-Sleep -Seconds $retryDelaySeconds
}

# 4. Error handling if the health check fails
if (-not $isReady) {
    $errorMsg = "ERROR: Ollama server failed to become ready within $($maxRetries * $retryDelaySeconds) seconds."
    Write-Log $errorMsg
    
    # Show a visible error message box so the failure isn't silent
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($errorMsg, "Deeks Startup Error", "OK", "Error")
    
    exit 1
}

# 5. Launch Deeks now that the health check passed
Write-Log "Ollama health check passed. Launching Deeks..."

$pythonCmd = "python"
if (Test-Path "$projectPath\venv\Scripts\python.exe") {
    $pythonCmd = "$projectPath\venv\Scripts\python.exe"
}

# Run the python script in the background, logging output
Start-Process -FilePath $pythonCmd -ArgumentList "main.py" -WorkingDirectory $projectPath -WindowStyle Hidden -RedirectStandardOutput $deeksLog -RedirectStandardError $deeksLog

Write-Log "Deeks has been launched successfully in the background."
