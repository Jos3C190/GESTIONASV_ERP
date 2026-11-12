# Run from a PowerShell window opened as Administrator.
# Queries current rules and runs existing connectivity probes. Does not change firewall rules.
$ErrorActionPreference = 'Stop'
$vpsRoot = 'D:\VPS-Local'
$results = [ordered]@{}

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Abra PowerShell como administrador y vuelva a ejecutar este archivo.'
    }
    $vm = Get-VM -Name 'VPS-Local-Coolify'
    if ($vm.State -ne 'Running') { throw 'El VPS debe estar encendido para comprobar las conexiones.' }

    Write-Host 'Comparando las reglas activas de Hyper-V con las reglas esperadas...'
    $expected = Get-Content -LiteralPath "$vpsRoot\Estado\acl-expected.json" -Raw | ConvertFrom-Json
    $actual = @(Get-VMNetworkAdapterExtendedAcl -VMName $vm.Name)
    $fields = @('Action', 'Direction', 'LocalIPAddress', 'RemoteIPAddress', 'LocalPort', 'RemotePort', 'Protocol', 'Weight', 'Stateful')
    function Convert-Rule($rule) {
        (($fields | ForEach-Object { [string]$rule.$_ }) -join '|').ToLowerInvariant()
    }
    $expectedRules = @($expected.Rules | ForEach-Object { Convert-Rule $_ } | Sort-Object)
    $actualRules = @($actual | ForEach-Object { Convert-Rule $_ } | Sort-Object)
    $difference = @(Compare-Object -ReferenceObject $expectedRules -DifferenceObject $actualRules)
    $results['hyperv_rules_match'] = ($difference.Count -eq 0)
    if ($difference.Count) {
        Write-Warning 'Las reglas activas difieren de la referencia guardada. Requieren revisión.'
        $difference | Format-Table | Out-Host
    }
    $adapters = @(Get-VMNetworkAdapter -VMName $vm.Name)
    $adapters | Select-Object SwitchName, IPAddresses, MacAddressSpoofing, DhcpGuard, RouterGuard | Format-List | Out-Host

    Write-Host 'Probando el aislamiento público desde el VPS y el contenedor del túnel...'
    # This existing audit uses a temporary probe container which is removed on exit.
    & python -B "$vpsRoot\ERP\herramientas\audit_public.py"
    $results['public_boundary_probes_passed'] = ($LASTEXITCODE -eq 0)

    Write-Host 'Probando los permisos SSH del enlace de IA y la red del trabajador en Windows...'
    & python -B "$vpsRoot\ERP\herramientas\test-isolation.py"
    $results['gpu_boundary_probes_passed'] = ($LASTEXITCODE -eq 0)

    Write-Host 'Consultando privilegios y montajes actuales del trabajador de IA...'
    $raw = & docker inspect erp-vps-gpu-worker-1
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo inspeccionar el trabajador de IA.' }
    $worker = @($raw | ConvertFrom-Json)[0]
    $results['gpu_not_privileged'] = (-not $worker.HostConfig.Privileged)
    $results['gpu_not_host_network'] = ($worker.HostConfig.NetworkMode -ne 'host')
    $results['gpu_no_published_ports'] = (-not $worker.HostConfig.PortBindings -or @($worker.HostConfig.PortBindings.PSObject.Properties).Count -eq 0)
    # Print mount paths, never environment values or file contents.
    $worker.Mounts | Select-Object Type, Source, Destination, RW | Format-Table -AutoSize | Out-Host

    Write-Host ('Comprobación terminada: ' + (Get-Date -Format o))
    $results | ConvertTo-Json
    if (@($results.Values | Where-Object { -not $_ }).Count) {
        Write-Warning 'Hay comprobaciones fallidas. Comparta el resultado para revisarlas; no cambie las reglas todavía.'
        exit 1
    }
    Write-Host 'Todas las comprobaciones ejecutadas pasaron. Los montajes requieren revisar también su alcance.'
} catch {
    Write-Error ('No se completó la comprobación: ' + $_.Exception.Message) -ErrorAction Continue
    exit 1
}
