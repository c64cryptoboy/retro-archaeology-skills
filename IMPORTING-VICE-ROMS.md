# Importing VICE ROMs: a setup handoff for the importing AI

This handoff covers **VICE and ROM prerequisites**, not importing skills into a Windows-specific harness. For harness-neutral skill registration and first-use checks, follow [IMPORTING-SKILLS.md](IMPORTING-SKILLS.md). Keep the repository layout intact while provisioning its optional dependencies.

The steps below obtain **C64 BASIC V2, KERNAL revision 3, and the original 1541 drive ROM** from a Windows VICE distribution. They install local prerequisites, not new files to redistribute. Downloading VICE is not necessary for ROM-free tools, and merely installing it does not provide an agent/MCP debugger connection.

## 1. Choose paths and a Windows build

Use **VICE 3.10, GTK3, Windows 64-bit** as the reproducible example here. Confirm the target can run that Windows x64 build; do not assume it is suitable for every Windows architecture. Use the [official VICE site](https://vice-emu.sourceforge.io/) and its [3.10 Windows GTK3 download](https://sourceforge.net/projects/vice-emu/files/releases/binaries/windows/GTK3VICE-3.10-win64.zip/download), not a third-party repack. The official site also links development builds; a newer build is not automatically equivalent to this example.

Use an ordinary writable location, without administrator installation or system-wide PATH changes:

```text
Repository:    <your chosen folder>\retro-archaeology-skills
Tool archive:  %LOCALAPPDATA%\6502-reversing-tools\GTK3VICE-3.10-win64.zip
Extraction:    %LOCALAPPDATA%\6502-reversing-tools\vice-3.10\
VICE root:     <extraction>\GTK3VICE-3.10-win64\
Executable:    <VICE root>\bin\x64sc.exe
ROM target:    <repository>\skills\c64-rom-reference\assets\roms\
```

These are proposed local paths, not dependencies on the exporter author's machine. Preserve any existing emulator installation and settings. Set `$Repo` to the actual imported repository root; an unattended importing AI should substitute the known absolute path rather than wait on `Read-Host`. Use PowerShell 5.1+ or PowerShell 7 and Python 3.10+ (`python`, or adapt commands to `py -3` if that is the installed launcher).

The **actual 3.10 ZIP** was inspected: 47,330,416 bytes, SHA-256 `beb3791d90e98f7e012c0028f26fbaa6545c8fce676f852a67f8ad893dee9d08`. This is an observed artifact-identity pin, not a publisher signature or a general safety certification. The ROM bytes in it matched this repository's independent ROM manifest. Windows execution and the PowerShell commands below have not been tested on native Windows.

## 2. Download and extract without overwriting another installation

Run in PowerShell; retain these variables for the next sections:

```powershell
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path -LiteralPath (Read-Host 'Full path to the repository root')).Path
if (-not (Test-Path -LiteralPath (Join-Path $Repo 'skills\c64-rom-reference\scripts\rom_manifest.py') -PathType Leaf)) {
    throw 'This is not the expected repository root.'
}
$Tools = Join-Path $env:LOCALAPPDATA '6502-reversing-tools'
$Zip = Join-Path $Tools 'GTK3VICE-3.10-win64.zip'
$Extract = Join-Path $Tools 'vice-3.10'
$Vice = Join-Path $Extract 'GTK3VICE-3.10-win64'
$RomDir = Join-Path $Repo 'skills\c64-rom-reference\assets\roms'
if (Test-Path -LiteralPath $Extract) {
    throw 'Extraction directory already exists. Inspect/reuse it deliberately, or choose a fresh directory.'
}
New-Item -ItemType Directory -Path $Tools -Force | Out-Null
# Direct download route for the same official SourceForge project artifact.
$Url = 'https://downloads.sourceforge.net/project/vice-emu/releases/binaries/windows/GTK3VICE-3.10-win64.zip'
if (-not (Test-Path -LiteralPath $Zip)) {
    Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing
}
$ZipHash = 'beb3791d90e98f7e012c0028f26fbaa6545c8fce676f852a67f8ad893dee9d08'
if ((Get-Item -LiteralPath $Zip).Length -ne 47330416 -or
    (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash -ne $ZipHash) {
    throw 'Archive identity differs. Do not extract/run it or silently change the expected hash.'
}
Expand-Archive -LiteralPath $Zip -DestinationPath $Extract
$Emulator = Join-Path $Vice 'bin\x64sc.exe'
if (-not (Test-Path -LiteralPath $Emulator -PathType Leaf)) {
    throw 'Expected executable not found: inspect the extracted layout before proceeding.'
}
```

If the download fails or returns HTML, stop; do not weaken the checks. A browser download from the official link above may work when automated requests receive HTTP 403. An interrupted archive is not reusable: inspect/remove only that failed download, then retry. If the official artifact has genuinely changed, record the new source, version, hash, and layout after review instead of pretending it is this pinned archive. Do not disable Windows security controls to run it.

For an existing approved VICE installation, skip download/extraction and set `$Vice` to its real root. If you plan an optional launch, also set `$Emulator` to that installation's actual `x64sc.exe` and verify `Test-Path -LiteralPath $Emulator -PathType Leaf` is true; do not reuse a stale executable path from another session/installation. In the inspected 3.10 layout it is `Join-Path $Vice 'bin\x64sc.exe'`. Discover actual files before copying; layouts can differ in other builds (for example, a `data` subdirectory or older generic names). Filenames alone never establish a matching revision.

## 3. Copy the three requested ROMs, with exact identity checks

Paths below are relative to the verified **VICE root**, not its `bin` directory:

| VICE 3.10 source | Destination under `$RomDir` | Required size |
|---|---|---:|
| `C64\basic-901226-01.bin` | `basic.bin` | 8,192 bytes |
| `C64\kernal-901227-03.bin` | `kernal.bin` | 8,192 bytes |
| `DRIVES\dos1541-325302-01+901229-05.bin` | `dos1541.bin` | 16,384 bytes |

Do **not** substitute KERNAL `-01`/`-02`, JiffyDOS, or the 1541-II ROM (`dos1541ii-251968-03.bin`). The requested 1541 image is already the complete combined `$C000-$FFFF` ROM; it has no PRG load-address header. A lone 8 KiB drive-ROM half is not sufficient. See the [ROM manifest](skills/c64-rom-reference/references/rom-manifest.md) and [machine-readable pins](skills/c64-rom-reference/scripts/rom_manifest.py).

This block checks all sources and existing destinations before copying. Existing matching files are retained; unexpected files are not overwritten. Run it after section 2, or explicitly set `$Repo`, `$Vice`, and `$RomDir` for an existing installation.

```powershell
$ErrorActionPreference = 'Stop'
$Specs = @(
    @{ Source = 'C64\basic-901226-01.bin'; Name = 'basic.bin'; Bytes = 8192;
       SHA256 = '89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d' },
    @{ Source = 'C64\kernal-901227-03.bin'; Name = 'kernal.bin'; Bytes = 8192;
       SHA256 = '83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721' },
    @{ Source = 'DRIVES\dos1541-325302-01+901229-05.bin'; Name = 'dos1541.bin'; Bytes = 16384;
       SHA256 = 'd1d45afb46fd4e2b48d93ca367b889d75654a3b7acf73044e51f6d880c09369e' }
)
foreach ($Spec in $Specs) {
    $Source = Join-Path $Vice $Spec.Source
    $Target = Join-Path $RomDir $Spec.Name
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Missing source: $Source" }
    if ((Get-Item -LiteralPath $Source).Length -ne $Spec.Bytes -or
        (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash -ne $Spec.SHA256) {
        throw "Wrong source size/hash: $Source"
    }
    if (Test-Path -LiteralPath $Target) {
        if (-not (Test-Path -LiteralPath $Target -PathType Leaf)) { throw "Not a file: $Target" }
        if ((Get-Item -LiteralPath $Target).Length -ne $Spec.Bytes -or
            (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -ne $Spec.SHA256) {
            throw "Existing target differs; preserve and investigate: $Target"
        }
    }
}
New-Item -ItemType Directory -Path $RomDir -Force | Out-Null
foreach ($Spec in $Specs) {
    $Source = Join-Path $Vice $Spec.Source
    $Target = Join-Path $RomDir $Spec.Name
    if (-not (Test-Path -LiteralPath $Target)) {
        [System.IO.File]::Copy($Source, $Target, $false)  # Refuse overwrite, including a race.
    }
    if ((Get-Item -LiteralPath $Target).Length -ne $Spec.Bytes -or
        (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -ne $Spec.SHA256) {
        throw "Installed file failed verification: $Target"
    }
    Write-Output "Verified $Target"
}
```

**Optional fourth ROM:** VICE also supplies `C64\chargen-901225-01.bin`. It maps to `chargen.bin`, 4,096 bytes, SHA-256 `fd0d53b8480e86163ac98998976c72cc58d5dd8eb824ed7b829774e74213b420`. Apply the same source/destination checks if copying it. It is not one of the three requested prerequisites, but supplying it allows the four-ROM verifier to run with no missing files.

## 4. Verify, then integrate with the agent

Require all **three mandatory files** to exist, then run the repository's size/hash verifier. This gate also works after the fallback downloader below. Temporarily set its location explicitly so an inherited `C64_ROM_DIR` cannot accidentally select another directory:

```powershell
$ErrorActionPreference = 'Stop'
foreach ($Name in @('basic.bin', 'kernal.bin', 'dos1541.bin')) {
    if (-not (Test-Path -LiteralPath (Join-Path $RomDir $Name) -PathType Leaf)) {
        throw "Required ROM is missing: $Name"
    }
}
$PreviousRomDir = $env:C64_ROM_DIR
try {
    $env:C64_ROM_DIR = $RomDir
    python -B (Join-Path $Repo 'skills\c64-rom-reference\scripts\rom-tool.py') verify --allow-missing
    if ($LASTEXITCODE -ne 0) { throw 'ROM verification failed.' }
} finally {
    $env:C64_ROM_DIR = $PreviousRomDir
}
```

Here `--allow-missing` permits the deliberately omitted **character ROM**, not omission of any of the three files required by the preceding existence check. Do not remove that check: the verifier option alone does not prove that the required three exist. Expect BASIC, KERNAL, and DOS1541 `OK`; character ROM may say `MISSING (allowed)`. If you also installed `chargen.bin`, omit `--allow-missing` and require four `OK` results.

- The repository-local target is the default for ROM/RND tools. An **external** folder can instead be selected with `C64_ROM_DIR` for individual tools, but the full runner clears that variable. For `python -B tests/run.py`, place BASIC/KERNAL in the repository-local target described above.
- Full RND C-backed tests need **GCC and a POSIX/little-endian environment**. Installing Windows VICE/Python alone does not satisfy that requirement. If using WSL, translate actual Windows paths with `wslpath` and run the tests in a suitable Linux environment; do not pass a Windows `C:\...` path to a Linux interpreter. See [TESTING.md](TESTING.md). Large-metadata skips remain independent of ROM acquisition.
- An optional emulator smoke launch is `Start-Process -FilePath $Emulator`. It is unnecessary for extracting ROMs. Preserve the whole VICE tree (DLLs/data included), not just `x64sc.exe`. Use an absolute executable path rather than changing system PATH. Install/configure any agent debugging bridge separately; do not assume these skills expose VICE controls automatically.
- Keep repository-relative imports and cross-skill links working when registering skills. Smoke-test a ROM-free example from [IMPORTING-SKILLS.md](IMPORTING-SKILLS.md#4-check-a-small-example), then the intended ROM-backed operation. Report actual results, not just successful copying or emulator startup.

## If this VICE package is unavailable

Do not accept a near-match ROM revision. An existing explicit downloader can acquire just these pinned inputs instead, validating the source pieces and combining the two 1541 halves in address order:

```powershell
python -B (Join-Path $Repo 'skills\c64-rom-reference\scripts\download-roms.py') basic kernal dos1541 --output-dir $RomDir
if ($LASTEXITCODE -ne 0) { throw 'Pinned ROM acquisition failed; report the failure.' }
```

This fallback does **not** install VICE. Its sources are recorded in the manifest; availability is not guaranteed. It retains valid existing files and refuses invalid replacements by default. Do not add `--replace-invalid` without inspecting/preserving the conflicting files. Run section 4's complete verification block (three-file existence check plus size/hash verification); it needs no VICE source directory. Do not use `--allow-missing` alone as the acceptance gate.

## Completion report and redistribution boundary

The importing AI should leave the chosen VICE version/download URL/archive hash, actual executable and ROM paths, each ROM's size/hash, verifier output, any tests run/skipped/failed, and any missing debugger integration in its **local setup record**, not machine-specific additions to shared skill documents. Distinguish archive/ROM inspection from native Windows/emulator validation.

Keep the ZIP, extracted emulator, and ROMs local. The repository's `.gitignore` excludes the local ROM `.bin` files, but that does not protect a plain folder/ZIP export: explicitly omit them from any redistribution. Keep [attribution and license notices](THIRD_PARTY_NOTICES.md); local acquisition does not newly license these assets under the repository's MIT license.
