# Read-only inspection: no container or firewall configuration changes.
$ErrorActionPreference = 'Stop'
$results = [ordered]@{}

function Read-DockerJson([string[]]$Arguments) {
    $raw = & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Docker inspection failed: ' + ($Arguments -join ' ')) }
    return ($raw | ConvertFrom-Json)
}

function Test-NoPorts($Container) {
    return (-not $Container.HostConfig.PortBindings -or @($Container.HostConfig.PortBindings.PSObject.Properties).Count -eq 0)
}

try {
    $containers = @(Read-DockerJson -Arguments @('inspect', 'erp-vps-gpu-worker-1', 'erp-vps-gpu-link-1'))
    $worker = $containers | Where-Object { $_.Name -eq '/erp-vps-gpu-worker-1' }
    $link = $containers | Where-Object { $_.Name -eq '/erp-vps-gpu-link-1' }
    if (-not $worker -or -not $link) { throw 'Expected worker and SSH connector not found.' }

    foreach ($entry in @(@{Label='worker'; Container=$worker}, @{Label='ssh_link'; Container=$link})) {
        $label = $entry.Label
        $container = $entry.Container
        $results[$label + '_running'] = [bool]$container.State.Running
        $results[$label + '_not_privileged'] = (-not $container.HostConfig.Privileged)
        $results[$label + '_not_host_network'] = ($container.HostConfig.NetworkMode -ne 'host')
        $results[$label + '_no_published_ports'] = Test-NoPorts $container
        $results[$label + '_all_capabilities_dropped'] = (@($container.HostConfig.CapDrop) -contains 'ALL')
        $results[$label + '_no_new_privileges'] = (@($container.HostConfig.SecurityOpt) -match '^no-new-privileges(:true|=true)?$').Count -gt 0
        $results[$label + '_all_mounts_readonly'] = @($container.Mounts | Where-Object { $_.RW -ne $false }).Count -eq 0
        $results[$label + '_no_docker_socket'] = @($container.Mounts | Where-Object { $_.Source -match '(docker|containerd)\.sock|docker_engine' -or $_.Destination -match '(docker|containerd)\.sock|docker_engine' }).Count -eq 0
        Write-Host ("`n" + $label + ' actual mounts (RW=False means read-only):')
        # Format-List prevents the RW column from being hidden on narrow terminals.
        $container.Mounts | Select-Object Type, Source, Destination, RW | Format-List | Out-Host
        Write-Host ($label + ' configured user: ' + $(if ($container.Config.User) { $container.Config.User } else { '(default root)' }))
    }

    $mounts = @($worker.Mounts)
    $code = @($mounts | Where-Object { $_.Destination -eq '/srv/erp' })
    $models = @($mounts | Where-Object { $_.Destination -eq '/models' })
    $results['worker_only_expected_mounts'] = $mounts.Count -eq 2 -and $code.Count -eq 1 -and $models.Count -eq 1
    $results['worker_code_is_release_directory'] = $code.Count -eq 1 -and $code[0].Type -eq 'bind' -and (($code[0].Source -replace '\\','/') -match '(?i)^(?:/run/desktop/mnt/host/d|d:)/VPS-Local/ERP/gpu/releases/[0-9a-f]{40}/backend/?$')
    $results['worker_models_expected_volume'] = $models.Count -eq 1 -and $models[0].Type -eq 'volume' -and $models[0].Name -eq 'proyecto_erp_vlm-models'

    $expectedLinkFiles = @{
        '/keys/link_ed25519' = 'link_ed25519'
        '/keys/known_hosts' = 'known_hosts'
        '/connector.sh' = 'connector.sh'
    }
    $unexpectedLink = @($link.Mounts | Where-Object {
        -not $expectedLinkFiles.ContainsKey($_.Destination) -or $_.Type -ne 'bind' -or
        (($_.Source -replace '\\','/') -notmatch ('(?i)^(?:/run/desktop/mnt/host/d|d:)/VPS-Local/ERP/gpu/' + [regex]::Escape($expectedLinkFiles[$_.Destination]) + '$'))
    })
    $results['ssh_link_only_expected_mounts'] = @($link.Mounts).Count -eq 3 -and $unexpectedLink.Count -eq 0
    $results['ssh_link_root_filesystem_readonly'] = [bool]$link.HostConfig.ReadonlyRootfs
    $results['ssh_link_nonroot_user'] = [bool]$link.Config.User -and $link.Config.User -notmatch '^(root|0)(:|$)'

    $workerNetworks = @($worker.NetworkSettings.Networks.PSObject.Properties.Name)
    $linkNetworks = @($link.NetworkSettings.Networks.PSObject.Properties.Name)
    $results['worker_one_network'] = $workerNetworks.Count -eq 1
    $results['ssh_link_two_networks'] = $linkNetworks.Count -eq 2
    if ($workerNetworks.Count -eq 1) {
        $network = @(Read-DockerJson -Arguments @('network', 'inspect', $workerNetworks[0]))[0]
        $results['worker_network_internal'] = [bool]$network.Internal
        $results['ssh_link_shares_worker_network'] = $linkNetworks -contains $workerNetworks[0]
    }

    Write-Host ('Inspected at: ' + (Get-Date -Format o))
    $results | ConvertTo-Json
    if (@($results.Values | Where-Object { -not $_ }).Count) {
        Write-Warning 'Some checks failed. Share this output before changing the configuration.'
        exit 1
    }
    Write-Host 'All GPU mount and container boundary checks passed.'
} catch {
    Write-Error ('Inspection incomplete: ' + $_.Exception.Message) -ErrorAction Continue
    exit 1
}
