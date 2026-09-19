$retryCount = 0
while ($retryCount -lt 60) {
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Write-Host "Ollama is installed, starting pull..."
        ollama pull phi4-mini
        exit 0
    }
    Write-Host "Waiting for Ollama to be in PATH..."
    Start-Sleep -Seconds 10
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $retryCount = $retryCount + 1
}
Write-Host "Timeout waiting for Ollama install"
exit 1
