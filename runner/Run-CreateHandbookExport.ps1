[CmdletBinding()]
param(
    [ValidateSet("sample", "full")]
    [string]$Scope = "sample",

    [string]$ServerPackPath,

    [string]$OutputRoot,

    [switch]$KeepWorkDirectory,

    [switch]$AcceptMinecraftEula,

    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ServerPackUrl = "https://www.curseforge.com/api/v1/mods/1518930/files/8478465/download"
$ServerPackFileName = "All_of_Create_-_Aeronautics_v2.1_serverpack.zip"
$ServerPackSha256 = "4b835f2362dd97b62d03c6322febebcd3490f2c00b4114f4b972b46e818a5c8b"
$ServerPackBytes = 314214774
$MinecraftEulaUrl = "https://www.minecraft.net/eula"
$ExporterJarName = "create_runtime_exporter-0.2.1.jar"
$ExporterHashFileName = "create_runtime_exporter-0.2.1.sha256"
$ExpectedMinecraftVersion = "1.21.1"
$ExpectedNeoForgeVersion = "21.1.233"
$ExpectedPackVersion = "v2.1"
$TotalStages = 8
$script:TranscriptStarted = $false
$script:CurrentPhase = "startup"
$script:RunLogPath = $null
$script:RunDirectory = $null
$script:OutputDirectory = $null

function Get-StatusTimestamp {
    return [DateTime]::Now.ToString("HH:mm:ss")
}

function Write-Stage {
    param(
        [Parameter(Mandatory = $true)][int]$Number,
        [Parameter(Mandatory = $true)][string]$Title,
        [string]$Detail
    )

    $script:CurrentPhase = $Title
    Write-Host ""
    Write-Host "[$(Get-StatusTimestamp)] Stage $Number/$TotalStages - $Title" -ForegroundColor Cyan
    if (-not [string]::IsNullOrWhiteSpace($Detail)) {
        Write-Host "    $Detail"
    }
}

function Write-Status {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[$(Get-StatusTimestamp)] $Message"
}

function Stop-RunnerTranscript {
    if ($script:TranscriptStarted) {
        try {
            Stop-Transcript | Out-Null
        } catch {
            Write-Warning "The runner could not close its transcript cleanly: $($_.Exception.Message)"
        }
        $script:TranscriptStarted = $false
    }
}

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-FileHash {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256,
        [long]$ExpectedBytes = -1
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file is missing: $Path"
    }

    if ($ExpectedBytes -ge 0) {
        $actualBytes = (Get-Item -LiteralPath $Path).Length
        if ($actualBytes -ne $ExpectedBytes) {
            throw "File-size check failed for $Path. Expected $ExpectedBytes bytes; found $actualBytes."
        }
    }

    $actualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $ExpectedSha256.ToLowerInvariant()) {
        throw "SHA-256 check failed for $Path. The file will not be used."
    }
}

function Assert-DisposablePath {
    param(
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$RunsRoot
    )

    $normalizedRoot = (Get-NormalizedPath -Path $RunsRoot).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    $normalizedRun = Get-NormalizedPath -Path $RunDirectory
    $comparison = [System.StringComparison]::OrdinalIgnoreCase

    if (-not $normalizedRun.StartsWith($normalizedRoot, $comparison)) {
        throw "Refusing cleanup because the run directory is outside the dedicated runs root."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $normalizedRun ".handbook-disposable-instance") -PathType Leaf)) {
        throw "Refusing cleanup because the disposable-instance marker is missing."
    }
}

function Set-TemporaryVariable {
    param(
        [Parameter(Mandatory = $true)][string]$VariablesPath,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $content = [System.IO.File]::ReadAllText($VariablesPath)
    $pattern = "(?m)^" + [Regex]::Escape($Name) + "=.*$"
    if (-not [Regex]::IsMatch($content, $pattern)) {
        throw "The verified server pack is missing the expected $Name setting."
    }
    $updated = [Regex]::Replace($content, $pattern, "$Name=$Value", 1)
    [System.IO.File]::WriteAllText(
        $VariablesPath,
        $updated,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Set-TemporaryServerProperty {
    param(
        [Parameter(Mandatory = $true)][string]$PropertiesPath,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $content = [System.IO.File]::ReadAllText($PropertiesPath)
    $pattern = "(?m)^" + [Regex]::Escape($Name) + "=.*$"
    $replacement = "$Name=$Value"
    if ([Regex]::IsMatch($content, $pattern)) {
        $content = [Regex]::Replace($content, $pattern, $replacement, 1)
    } else {
        $content = $content.TrimEnd() + "`r`n" + $replacement + "`r`n"
    }
    [System.IO.File]::WriteAllText(
        $PropertiesPath,
        $content,
        [System.Text.UTF8Encoding]::new($false)
    )
}

trap {
    $failureMessage = $_.Exception.Message
    Write-Host ""
    Write-Host "[$(Get-StatusTimestamp)] EXPORT FAILED during: $script:CurrentPhase" -ForegroundColor Red
    Write-Host "Reason: $failureMessage" -ForegroundColor Red
    if (-not [string]::IsNullOrWhiteSpace($script:RunDirectory) -and
            (Test-Path -LiteralPath $script:RunDirectory -PathType Container)) {
        Write-Host "Disposable diagnostic directory: $script:RunDirectory"
        $failureServerLog = Join-Path $script:RunDirectory "logs\latest.log"
        if (Test-Path -LiteralPath $failureServerLog -PathType Leaf) {
            Write-Host "Minecraft/NeoForge log: $failureServerLog"
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($script:RunLogPath)) {
        Write-Host "Human-readable runner log: $script:RunLogPath"
    }
    Stop-RunnerTranscript
    exit 1
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$exporterJar = Join-Path $scriptDirectory $ExporterJarName
$exporterHashPath = Join-Path $scriptDirectory $ExporterHashFileName

if (-not (Test-Path -LiteralPath $exporterHashPath -PathType Leaf)) {
    throw "Exporter checksum file is missing: $exporterHashPath"
}
$exporterHash = ([System.IO.File]::ReadAllText($exporterHashPath)).Trim().Split()[0]
if ($exporterHash -notmatch "^[0-9a-fA-F]{64}$") {
    throw "Exporter checksum file is invalid."
}
Assert-FileHash -Path $exporterJar -ExpectedSha256 $exporterHash

if ($ValidateOnly) {
    $validationBytes = (Get-Item -LiteralPath $exporterJar).Length
    Assert-FileHash `
        -Path $exporterJar `
        -ExpectedSha256 $exporterHash `
        -ExpectedBytes $validationBytes
    Write-Host "Runner package validation passed." -ForegroundColor Green
    Write-Host "File-size validation path passed with a primitive Int64 value."
    Write-Host "Official server pack: project 1518930, file 8478465"
    Write-Host "Locked runtime: Minecraft $ExpectedMinecraftVersion, NeoForge $ExpectedNeoForgeVersion, pack $ExpectedPackVersion"
    exit 0
}

$localAppData = [Environment]::GetFolderPath("LocalApplicationData")
if ([string]::IsNullOrWhiteSpace($localAppData)) {
    throw "Windows did not provide a LocalApplicationData directory."
}
$runnerRoot = Join-Path $localAppData "CreateHandbookExporter"
$cacheRoot = Join-Path $runnerRoot "cache"
$runsRoot = Join-Path $runnerRoot "runs"
$logsRoot = Join-Path $runnerRoot "logs"
$runId = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss") + "-" + [Guid]::NewGuid().ToString("N").Substring(0, 8)

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $documents = [Environment]::GetFolderPath("MyDocuments")
    if ([string]::IsNullOrWhiteSpace($documents)) {
        throw "Windows did not provide a Documents directory. Supply -OutputRoot explicitly."
    }
    $OutputRoot = Join-Path $documents "Create-Handbook-Exports"
}
$OutputRoot = Get-NormalizedPath -Path $OutputRoot

[System.IO.Directory]::CreateDirectory($cacheRoot) | Out-Null
[System.IO.Directory]::CreateDirectory($runsRoot) | Out-Null
[System.IO.Directory]::CreateDirectory($logsRoot) | Out-Null
[System.IO.Directory]::CreateDirectory($OutputRoot) | Out-Null

$script:RunLogPath = Join-Path $logsRoot "create-export-$runId.log"
$script:MinecraftLogPath = Join-Path $logsRoot "create-export-$runId-minecraft.log"
Start-Transcript -LiteralPath $script:RunLogPath | Out-Null
$script:TranscriptStarted = $true

Write-Host "Create 6.0.10 Handbook Runtime Exporter" -ForegroundColor Green
Write-Host "This runs a new, disposable local server. It does not inspect or modify CurseForge or Bisect."
Write-Host "Every major operation is timestamped below. A transcript is saved for debugging."

Write-Stage -Number 1 -Title "Validate runner and version locks" `
    -Detail "Checking the bundled exporter and declaring the exact supported modpack runtime."
Write-Status "Exporter jar verified: $ExporterJarName"
Write-Status "Locked runtime: Minecraft $ExpectedMinecraftVersion; NeoForge $ExpectedNeoForgeVersion; pack $ExpectedPackVersion."
Write-Status "Scope: $Scope"
Write-Status "Human-readable run log: $script:RunLogPath"

Write-Stage -Number 2 -Title "Acquire the official server pack" `
    -Detail "Using only CurseForge project 1518930, file 8478465; cached copies must pass exact verification."
if ([string]::IsNullOrWhiteSpace($ServerPackPath)) {
    $ServerPackPath = Join-Path $cacheRoot $ServerPackFileName
    $needDownload = $true
    if (Test-Path -LiteralPath $ServerPackPath -PathType Leaf) {
        try {
            Assert-FileHash -Path $ServerPackPath -ExpectedSha256 $ServerPackSha256 -ExpectedBytes $ServerPackBytes
            $needDownload = $false
            Write-Status "Using the previously downloaded and verified official v2.1 server pack."
        } catch {
            Write-Warning "The cached server pack failed verification and will not be used."
            $invalidPath = "$ServerPackPath.invalid-$([Guid]::NewGuid().ToString('N').Substring(0, 8))"
            Move-Item -LiteralPath $ServerPackPath -Destination $invalidPath
            Write-Warning "The unverified file was preserved at: $invalidPath"
        }
    }

    $partialPath = "$ServerPackPath.partial"
    if ($needDownload -and (Test-Path -LiteralPath $partialPath -PathType Leaf)) {
        Write-Status "Found a previous server-pack download that did not reach the cache-promotion step."
        Write-Status "Verifying it before deciding whether another 300 MB download is necessary."
        try {
            Assert-FileHash -Path $partialPath -ExpectedSha256 $ServerPackSha256 -ExpectedBytes $ServerPackBytes
            Move-Item -LiteralPath $partialPath -Destination $ServerPackPath
            $needDownload = $false
            Write-Status "Recovered the complete verified download from the previous run; no re-download is needed."
        } catch {
            $invalidPartialPath = "$partialPath.invalid-$([Guid]::NewGuid().ToString('N').Substring(0, 8))"
            Move-Item -LiteralPath $partialPath -Destination $invalidPartialPath
            Write-Warning "The previous partial file was incomplete or invalid and was preserved at: $invalidPartialPath"
        }
    }

    if ($needDownload) {
        Write-Status "Download 1: official All of Create - Aeronautics v2.1 server pack."
        Write-Status "Source: CurseForge project 1518930, file 8478465."
        Write-Status "Expected size: 314,214,774 bytes (about 300 MB)."
        Write-Status "This file contains the stock server configuration and mod jars."
        $downloadStarted = [DateTime]::UtcNow
        Invoke-WebRequest -UseBasicParsing -Uri $ServerPackUrl -OutFile $partialPath
        $downloadSeconds = [Math]::Round(([DateTime]::UtcNow - $downloadStarted).TotalSeconds, 1)
        Write-Status "Official server-pack download finished in $downloadSeconds seconds; verification follows."
        Assert-FileHash -Path $partialPath -ExpectedSha256 $ServerPackSha256 -ExpectedBytes $ServerPackBytes
        Move-Item -LiteralPath $partialPath -Destination $ServerPackPath
        Write-Status "Download 1 passed size and SHA-256 verification and was moved into the local cache."
    }
} else {
    $ServerPackPath = Get-NormalizedPath -Path $ServerPackPath
    Write-Status "Using the caller-supplied server-pack path; exact verification is still mandatory."
}

Write-Status "Performing final server-pack size and SHA-256 verification."
Assert-FileHash -Path $ServerPackPath -ExpectedSha256 $ServerPackSha256 -ExpectedBytes $ServerPackBytes
Write-Status "Official server pack verified successfully."

Write-Stage -Number 3 -Title "Confirm legal and export scope" `
    -Detail "The disposable Minecraft server will not start without explicit EULA acceptance."
if (-not $AcceptMinecraftEula) {
    Write-Host ""
    Write-Host "Minecraft requires you to accept its EULA before this disposable server can run."
    Write-Host $MinecraftEulaUrl -ForegroundColor Yellow
    $eulaResponse = ((Read-Host "After reviewing it, type I ACCEPT to continue").Trim() -replace "\s+", " ")
    if ($eulaResponse -ine "I ACCEPT") {
        throw "Minecraft EULA acceptance was not confirmed. Nothing was started."
    }
}
Write-Status "Minecraft EULA acceptance confirmed for this local disposable-server run."

if ($Scope -eq "full") {
    Write-Host ""
    Write-Host "Full scope exports every loaded create:* item and block fact supported by this exporter."
    $fullResponse = ((Read-Host "Type EXPORT ALL CREATE FACTS to continue").Trim() -replace "\s+", " ")
    if ($fullResponse -ine "EXPORT ALL CREATE FACTS") {
        throw "Full-export confirmation was not provided."
    }
}
Write-Status "Export scope confirmed: $Scope"

$runDirectory = Join-Path $runsRoot $runId
$outputDirectory = Join-Path $OutputRoot "create-6.0.10-$Scope-$runId"
$outputZip = "$outputDirectory.zip"
$script:RunDirectory = $runDirectory
$script:OutputDirectory = $outputDirectory

[System.IO.Directory]::CreateDirectory($runDirectory) | Out-Null
[System.IO.File]::WriteAllText(
    (Join-Path $runDirectory ".handbook-disposable-instance"),
    "create-handbook-disposable-v1",
    [System.Text.UTF8Encoding]::new($false)
)

Write-Stage -Number 4 -Title "Prepare the disposable local server" `
    -Detail "Extracting the verified pack, inserting the exporter, and applying loopback-only safety settings."
Write-Status "Disposable server directory: $runDirectory"
Write-Status "Clean evidence destination: $outputDirectory"
Expand-Archive -LiteralPath $ServerPackPath -DestinationPath $runDirectory
Write-Status "Server-pack extraction completed."

$modsDirectory = Join-Path $runDirectory "mods"
$startScript = Join-Path $runDirectory "start.ps1"
$variablesPath = Join-Path $runDirectory "variables.txt"
$serverPropertiesPath = Join-Path $runDirectory "server.properties"
if (-not (Test-Path -LiteralPath $modsDirectory -PathType Container)) {
    throw "The verified server pack did not contain its expected mods directory."
}
if (-not (Test-Path -LiteralPath $startScript -PathType Leaf)) {
    throw "The verified server pack did not contain start.ps1."
}
if (-not (Test-Path -LiteralPath $variablesPath -PathType Leaf)) {
    throw "The verified server pack did not contain variables.txt."
}
if (-not (Test-Path -LiteralPath $serverPropertiesPath -PathType Leaf)) {
    throw "The verified server pack did not contain server.properties."
}

Copy-Item -LiteralPath $exporterJar -Destination (Join-Path $modsDirectory $ExporterJarName)
Write-Status "Added the verified exporter jar to the disposable instance."
Set-TemporaryVariable -VariablesPath $variablesPath -Name "WAIT_FOR_USER_INPUT" -Value "false"
Set-TemporaryVariable -VariablesPath $variablesPath -Name "RESTART" -Value "false"
Set-TemporaryServerProperty -PropertiesPath $serverPropertiesPath -Name "server-ip" -Value "127.0.0.1"
Set-TemporaryServerProperty -PropertiesPath $serverPropertiesPath -Name "server-port" -Value "0"
Set-TemporaryServerProperty -PropertiesPath $serverPropertiesPath -Name "enable-query" -Value "false"
Set-TemporaryServerProperty -PropertiesPath $serverPropertiesPath -Name "enable-rcon" -Value "false"
Set-TemporaryServerProperty -PropertiesPath $serverPropertiesPath -Name "max-players" -Value "1"
Set-TemporaryServerProperty -PropertiesPath $serverPropertiesPath -Name "motd" -Value "Create Handbook Disposable Exporter"
[System.IO.File]::WriteAllText(
    (Join-Path $runDirectory "eula.txt"),
    "eula=true`r`n",
    [System.Text.UTF8Encoding]::new($false)
)
Write-Status "Applied settings: loopback-only address, ephemeral port, query off, RCON off, no restart."
Write-Status "Wrote EULA acceptance only inside the disposable server directory."

$previousEnvironment = @{}
$runtimeEnvironment = @{
    "HANDBOOK_EXPORT_ENABLED" = "true"
    "HANDBOOK_EXPORT_CONFIRM" = "DISPOSABLE_INSTANCE"
    "HANDBOOK_EXPORT_PACK_VERSION" = $ExpectedPackVersion
    "HANDBOOK_EXPORT_SCOPE" = $Scope
    "HANDBOOK_EXPORT_OUTPUT" = $outputDirectory
    "HANDBOOK_EXPORT_AUTOSTOP" = "true"
    "HANDBOOK_EXPORT_FULL_CONFIRM" = if ($Scope -eq "full") { "EXPORT_ALL_CREATE_RUNTIME_FACTS" } else { "" }
}

Write-Stage -Number 5 -Title "Bootstrap Minecraft, NeoForge, and the exporter" `
    -Detail "This is normally the longest stage on the first run."
Write-Status "The verified stock server script is now taking control."
Write-Status "It may perform up to three additional setup downloads:"
Write-Host "    1. Temurin Java 21, but only if no compatible Java is available."
Write-Host "    2. NeoForge ServerStarterJar and the NeoForge 21.1.233 server installation."
Write-Host "    3. Minecraft 1.21.1 server libraries required by NeoForge."
Write-Status "The mod jars are already inside the verified server pack."
Write-Status "Technical lines below come from the stock server installer and Minecraft/NeoForge."
Write-Status "Look for [HANDBOOK EXPORT] lines when data collection begins."
Write-Status "The disposable server is restricted to 127.0.0.1 on an ephemeral local port."
Write-Status "First-time bootstrap can take several minutes; leave this window open while output changes."
foreach ($entry in $runtimeEnvironment.GetEnumerator()) {
    $previousEnvironment[$entry.Key] = [Environment]::GetEnvironmentVariable($entry.Key, "Process")
    [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
}

$serverExitCode = 1
Push-Location $runDirectory
try {
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $startScript
    $serverExitCode = $LASTEXITCODE
} finally {
    Pop-Location
    foreach ($entry in $previousEnvironment.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
    }
}
Write-Status "The stock server process exited with code $serverExitCode."
$serverLatestLog = Join-Path $runDirectory "logs\latest.log"
if (Test-Path -LiteralPath $serverLatestLog -PathType Leaf) {
    try {
        Copy-Item -LiteralPath $serverLatestLog -Destination $script:MinecraftLogPath -ErrorAction Stop
        Write-Status "Minecraft/NeoForge log preserved: $script:MinecraftLogPath"
    } catch {
        Write-Warning "Could not preserve the Minecraft/NeoForge log: $($_.Exception.Message)"
    }
} else {
    Write-Warning "The disposable server did not produce logs\latest.log."
}

Write-Stage -Number 6 -Title "Validate the runtime evidence" `
    -Detail "Checking for the exporter manifest, provenance, counts, and sample reconciliation."
$manifestPath = Join-Path $outputDirectory "manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    Write-Host ""
    Write-Host "The disposable server did not produce an export manifest." -ForegroundColor Red
    Write-Host "Server exit code: $serverExitCode"
    Write-Host "Disposable run retained for diagnosis: $runDirectory"
    $latestLog = Join-Path $runDirectory "logs\latest.log"
    if (Test-Path -LiteralPath $latestLog -PathType Leaf) {
        Write-Host "Server log: $latestLog"
    }
    throw "Runtime export failed. No output ZIP was created."
}
Write-Status "Export manifest found."

$provenancePath = Join-Path $outputDirectory "provenance.json"
if (-not (Test-Path -LiteralPath $provenancePath -PathType Leaf)) {
    throw "Runtime export is incomplete: provenance.json is missing."
}
$provenance = Get-Content -LiteralPath $provenancePath -Raw | ConvertFrom-Json
Write-Status "Observed $($provenance.counts.mods) loaded mods."
Write-Status "Captured $($provenance.counts.items) items, $($provenance.counts.blocks) blocks, and $($provenance.counts.recipes) Create-related recipes."
Write-Status "Captured $($provenance.counts.item_tag_memberships) item-tag and $($provenance.counts.block_tag_memberships) block-tag memberships."
Write-Status "Captured $($provenance.counts.mechanics) effective mechanics facts and $($provenance.counts.effective_config_values) effective server settings."

$diagnosticsPath = Join-Path $outputDirectory "introspection-diagnostics.jsonl"
if (-not (Test-Path -LiteralPath $diagnosticsPath -PathType Leaf)) {
    throw "Runtime export is incomplete: introspection-diagnostics.jsonl is missing."
}
$diagnosticFindings = @(
    Get-Content -LiteralPath $diagnosticsPath |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { $_ | ConvertFrom-Json } |
        Where-Object { $_.status -ne "ok" }
)
if ($diagnosticFindings.Count -gt 0) {
    Write-Warning "Create runtime introspection reported $($diagnosticFindings.Count) non-ok subsystem result(s). The evidence and diagnostic logs are preserved for review."
    foreach ($finding in $diagnosticFindings) {
        $fieldErrorCount = if ($null -ne $finding.field_error_count) {
            "; unreadable fields: $($finding.field_error_count)"
        } else {
            ""
        }
        Write-Warning "$($finding.subsystem): status=$($finding.status); rows=$($finding.row_count)$fieldErrorCount; $($finding.error_class): $($finding.error_message)"
    }
} else {
    Write-Status "Create stress-registry and server-config introspection both completed successfully."
}

$reconciliationPath = Join-Path $outputDirectory "sample-reconciliation.json"
if (-not (Test-Path -LiteralPath $reconciliationPath -PathType Leaf)) {
    throw "Runtime export is incomplete: sample-reconciliation.json is missing."
}
$reconciliation = Get-Content -LiteralPath $reconciliationPath -Raw | ConvertFrom-Json
$missingItemCount = @($reconciliation.missing_item_ids).Count
$missingBlockCount = @($reconciliation.missing_block_ids).Count
if ($missingItemCount -gt 0 -or $missingBlockCount -gt 0) {
    Write-Warning "Sample reconciliation found $missingItemCount missing item IDs and $missingBlockCount missing block IDs. The output is preserved for review."
} else {
    Write-Status "All requested sample item and block IDs were reconciled."
}

Write-Stage -Number 7 -Title "Package the clean evidence" `
    -Detail "Creating a shareable ZIP containing only the exporter JSON and JSONL records."
Compress-Archive -Path (Join-Path $outputDirectory "*") -DestinationPath $outputZip
Write-Status "Evidence ZIP created: $outputZip"
Write-Status "Evidence ZIP size: $([Math]::Round((Get-Item -LiteralPath $outputZip).Length / 1KB, 1)) KB"

Write-Stage -Number 8 -Title "Finalize and report" `
    -Detail "Removing only the marker-guarded disposable server while retaining the verified download cache."
if (-not $KeepWorkDirectory) {
    Assert-DisposablePath -RunDirectory $runDirectory -RunsRoot $runsRoot
    Remove-Item -LiteralPath $runDirectory -Recurse -Force
    Write-Status "Disposable server directory removed after successful export."
} else {
    Write-Status "Disposable server directory retained because -KeepWorkDirectory was supplied."
}

Write-Host ""
Write-Host "[$(Get-StatusTimestamp)] EXPORT COMPLETE" -ForegroundColor Green
Write-Host "Upload this ZIP in our chat:"
Write-Host $outputZip -ForegroundColor Yellow
Write-Host ""
Write-Host "The verified server-pack download remains cached for later runs."
Write-Host "Human-readable run log:"
Write-Host $script:RunLogPath -ForegroundColor Yellow
if (Test-Path -LiteralPath $script:MinecraftLogPath -PathType Leaf) {
    Write-Host "Minecraft/NeoForge log:"
    Write-Host $script:MinecraftLogPath -ForegroundColor Yellow
}

Stop-RunnerTranscript
try {
    Start-Process explorer.exe -ArgumentList "/select,`"$outputZip`""
} catch {
    Write-Warning "The export succeeded, but Explorer could not be opened automatically."
}
exit 0
