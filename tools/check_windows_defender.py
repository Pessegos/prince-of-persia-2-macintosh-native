"""Record active Defender protection and scan only the supplied test bundle."""

import argparse
import json
import os
from pathlib import Path
import subprocess


def check(directory, scan=False, require_exclusions=False):
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise ValueError('Choose an extracted portable test bundle')
    env = {name: value for name, value in os.environ.items() if name.upper() != 'PSMODULEPATH'}
    env['POP2_DEFENDER_TARGET'] = str(directory)
    env['POP2_DEFENDER_SCAN'] = '1' if scan else '0'
    env['POP2_DEFENDER_REQUIRE_EXCLUSIONS'] = '1' if require_exclusions else '0'
    script = r'''
$ErrorActionPreference = 'Stop'
$status = Get-MpComputerStatus
if (!$status.AntivirusEnabled -or !$status.RealTimeProtectionEnabled -or $status.AMRunningMode -ne 'Normal') {
    throw 'Microsoft Defender real-time protection is not active in Normal mode'
}
$target = $env:POP2_DEFENDER_TARGET
$tool = Join-Path $env:ProgramFiles 'Windows Defender/MpCmdRun.exe'
$checks = @($target, (Join-Path $target 'PoP2Mac.exe'),
            (Join-Path $target '_internal/python/python.exe'),
            (Join-Path $target '_internal/python/pythonw.exe'))
$verified = 0
$query = 'verified'
foreach ($path in $checks) {
    $output = & $tool -CheckExclusion -Path $path 2>&1 | Out-String
    if ($LASTEXITCODE -eq 1) { $verified++; continue }
    if ($output.Contains('0x80070005') -and $env:POP2_DEFENDER_REQUIRE_EXCLUSIONS -ne '1') {
        $query = 'unavailable_without_administrator'
        continue
    }
    throw ('Exclusion check failed or path is excluded: ' + $output)
}
$scanned = $false
if ($env:POP2_DEFENDER_SCAN -eq '1') {
    Start-MpScan -ScanType CustomScan -ScanPath $target -ErrorAction Stop
    $scanned = $true
}
$detections = @(Get-MpThreatDetection | Where-Object {
    @($_.Resources | Where-Object {
        $_.IndexOf($target, [StringComparison]::OrdinalIgnoreCase) -ge 0
    }).Count -gt 0
})
if ($detections.Count) { throw 'Defender recorded a detection in this test bundle' }
[pscustomobject]@{antivirus=$status.AntivirusEnabled; real_time=$status.RealTimeProtectionEnabled;
    mode=$status.AMRunningMode; signature=$status.AntivirusSignatureVersion;
    exclusions_checked=$verified; exclusion_query=$query;
    scan_command_succeeded=$scanned; detections=$detections.Count} | ConvertTo-Json -Compress
'''
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            env=env, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or 'Defender verification failed')
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--scan', action='store_true')
    parser.add_argument('--require-exclusions', action='store_true', help='Fail unless exclusion queries are permitted')
    args = parser.parse_args()
    print(json.dumps(check(args.directory, args.scan, args.require_exclusions), indent=2))


if __name__ == '__main__':
    main()
