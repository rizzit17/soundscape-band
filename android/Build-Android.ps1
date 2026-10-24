$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $modelPath = Join-Path $PSScriptRoot 'app/src/main/assets/yamnet.tflite'
    if (-not (Test-Path -LiteralPath $modelPath)) {
        New-Item -ItemType Directory -Force (Split-Path $modelPath) | Out-Null
        Invoke-WebRequest 'https://storage.googleapis.com/mediapipe-models/audio_classifier/yamnet/float32/latest/yamnet.tflite' -OutFile $modelPath
    }
    if ((Get-FileHash $modelPath -Algorithm SHA256).Hash -ne '4D8B4A53282DC83EF04E3E7DBC4FBC98082E34E44ED798E16C3A0CDD4C584FAF') {
        throw 'Unexpected model hash. Check model provenance before building.'
    }
    & .\gradlew.bat assembleDebug testDebugUnitTest lintDebug --console=plain
    if ($LASTEXITCODE -ne 0) { throw 'Android build or verification failed.' }
    Write-Output "APK: $PSScriptRoot\app\build\outputs\apk\debug\app-debug.apk"
} finally { Pop-Location }
