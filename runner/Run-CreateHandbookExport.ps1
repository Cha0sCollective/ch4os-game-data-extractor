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
$ExporterJarName = "create_runtime_exporter-0.1.0.jar"
$ExporterHashFileName = "create_runtime_exporter-0.1.0.sha256"
$ExpectedMinecraftVersion = "1.21.1"
$ExpectedNeoForgeVersion = "21.1.233"
$ExpectedPackVersion = "v2.1"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-FileHash {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256,
        [Nullable[long]]$ExpectedBytes
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file is missing: $Path"
    }

    if ($null -ne $ExpectedBytes) {
        $actualBytes = (Get-Item -LiteralPath $Path).Length
        if ($actualBytes -ne $ExpectedBytes.Value) {
            throw "File-size check failed for $Path. Expected $($ExpectedBytes.Value) bytes; found $actualBytes."
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
    Write-Host "Runner package validation passed." -ForegroundColor Green
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
[System.IO.Directory]::CreateDirectory($OutputRoot) | Out-Null

Write-Host "Create 6.0.10 Handbook Runtime Exporter" -ForegroundColor Green
Write-Host "This runs a new, disposable local server. It does not inspect or modify CurseForge or Bisect."

if ([string]::IsNullOrWhiteSpace($ServerPackPath)) {
    $ServerPackPath = Join-Path $cacheRoot $ServerPackFileName
    $needDownload = $true
    if (Test-Path -LiteralPath $ServerPackPath -PathType Leaf) {
        try {
            Assert-FileHash -Path $ServerPackPath -ExpectedSha256 $ServerPackSha256 -ExpectedBytes $ServerPackBytes
            $needDownload = $false
            Write-Step "Using the previously verified official v2.1 server pack."
        } catch {
            Write-Warning "The cached server pack failed verification and will not be used."
            $invalidPath = "$ServerPackPath.invalid-$([Guid]::NewGuid().ToString('N').Substring(0, 8))"
            Move-Item -LiteralPath $ServerPackPath -Destination $invalidPath
            Write-Warning "The unverified file was preserved at: $invalidPath"
        }
    }

    if ($needDownload) {
        Write-Step "Downloading the official All of Create - Aeronautics v2.1 server pack (about 300 MB)."
        $partialPath = "$ServerPackPath.partial"
        if (Test-Path -LiteralPath $partialPath) {
            Remove-Item -LiteralPath $partialPath -Force
        }
        Invoke-WebRequest -UseBasicParsing -Uri $ServerPackUrl -OutFile $partialPath
        Assert-FileHash -Path $partialPath -ExpectedSha256 $ServerPackSha256 -ExpectedBytes $ServerPackBytes
        Move-Item -LiteralPath $partialPath -Destination $ServerPackPath
    }
} else {
    $ServerPackPath = Get-NormalizedPath -Path $ServerPackPath
}

Write-Step "Verifying the official server-pack hash and file size."
Assert-FileHash -Path $ServerPackPath -ExpectedSha256 $ServerPackSha256 -ExpectedBytes $ServerPackBytes

if (-not $AcceptMinecraftEula) {
    Write-Host ""
    Write-Host "Minecraft requires you to accept its EULA before this disposable server can run."
    Write-Host $MinecraftEulaUrl -ForegroundColor Yellow
    $eulaResponse = Read-Host "After reviewing it, type I ACCEPT to continue"
    if ($eulaResponse -cne "I ACCEPT") {
        throw "Minecraft EULA acceptance was not confirmed. Nothing was started."
    }
}

if ($Scope -eq "full") {
    Write-Host ""
    Write-Host "Full scope exports every loaded create:* item and block fact supported by this exporter."
    $fullResponse = Read-Host "Type EXPORT ALL CREATE FACTS to continue"
    if ($fullResponse -cne "EXPORT ALL CREATE FACTS") {
        throw "Full-export confirmation was not provided."
    }
}

$runId = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss") + "-" + [Guid]::NewGuid().ToString("N").Substring(0, 8)
$runDirectory = Join-Path $runsRoot $runId
$outputDirectory = Join-Path $OutputRoot "create-6.0.10-$Scope-$runId"
$outputZip = "$outputDirectory.zip"

[System.IO.Directory]::CreateDirectory($runDirectory) | Out-Null
[System.IO.File]::WriteAllText(
    (Join-Path $runDirectory ".handbook-disposable-instance"),
    "create-handbook-disposable-v1",
    [System.Text.UTF8Encoding]::new($false)
)

Write-Step "Extracting the verified server pack into a disposable local directory."
Expand-Archive -LiteralPath $ServerPackPath -DestinationPath $runDirectory

$modsDirectory = Join-Path $runDirectory "mods"
$startScript = Join-Path $runDirectory "start.ps1"
$variablesPath = Join-Path $runDirectory "variables.txt"
if (-not (Test-Path -LiteralPath $modsDirectory -PathType Container)) {
    throw "The verified server pack did not contain its expected mods directory."
}
if (-not (Test-Path -LiteralPath $startScript -PathType Leaf)) {
    throw "The verified server pack did not contain start.ps1."
}
if (-not (Test-Path -LiteralPath $variablesPath -PathType Leaf)) {
    throw "The verified server pack did not contain variables.txt."
}

Copy-Item -LiteralPath $exporterJar -Destination (Join-Path $modsDirectory $ExporterJarName)
Set-TemporaryVariable -VariablesPath $variablesPath -Name "WAIT_FOR_USER_INPUT" -Value "false"
Set-TemporaryVariable -VariablesPath $variablesPath -Name "RESTART" -Value "false"
[System.IO.File]::WriteAllText(
    (Join-Path $runDirectory "eula.txt"),
    "eula=true`r`n",
    [System.Text.UTF8Encoding]::new($false)
)

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

Write-Step "Starting the isolated server. First run may download Java 21 and NeoForge support files."
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

Write-Step "Packaging the clean JSON evidence files."
Compress-Archive -Path (Join-Path $outputDirectory "*") -DestinationPath $outputZip

if (-not $KeepWorkDirectory) {
    Assert-DisposablePath -RunDirectory $runDirectory -RunsRoot $runsRoot
    Remove-Item -LiteralPath $runDirectory -Recurse -Force
}

Write-Host ""
Write-Host "Export complete." -ForegroundColor Green
Write-Host "Upload this ZIP in our chat:"
Write-Host $outputZip -ForegroundColor Yellow
Write-Host ""
Write-Host "The verified server-pack download remains cached for later runs."

Start-Process explorer.exe -ArgumentList "/select,`"$outputZip`""
exit 0
