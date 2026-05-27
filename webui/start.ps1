<#
.Kronos Web UI startup script for Windows
#>

Write-Host "🚀 Starting Kronos Web UI..." -ForegroundColor Cyan
Write-Host "================================"
Write-Host ""

# Check if Python is installed
Write-Host "🔍 Checking Python installation..." -ForegroundColor Gray
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python not installed, please install Python first" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Python found" -ForegroundColor Green
Write-Host ""

# Check if in correct directory
Write-Host "🔍 Checking working directory..." -ForegroundColor Gray
if (-not (Test-Path "app.py")) {
    Write-Host "❌ Please run this script from the webui directory" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Working directory is correct" -ForegroundColor Green
Write-Host ""

# Check dependencies
Write-Host "📦 Checking dependencies..." -ForegroundColor Gray
try {
    python -c "import flask, flask_cors, pandas, numpy, plotly" | Out-Null
    $deps_ok = $true
} catch {
    $deps_ok = $false
}

if (-not $deps_ok) {
    Write-Host "⚠️  Missing dependencies, installing..." -ForegroundColor Yellow
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Dependencies installation failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Dependencies installation completed" -ForegroundColor Green
} else {
    Write-Host "✅ All dependencies installed" -ForegroundColor Green
}
Write-Host ""

# Start application
Write-Host "🌐 Starting Web server..." -ForegroundColor Cyan
Write-Host "Access URL: http://localhost:7070" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop server" -ForegroundColor Gray
Write-Host ""

python app.py
