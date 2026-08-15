param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$source = [System.IO.File]::OpenRead((Resolve-Path -LiteralPath $InputPath))
try {
    $target = [System.IO.File]::Create($OutputPath)
    try {
        $gzip = [System.IO.Compression.GZipStream]::new(
            $target,
            [System.IO.Compression.CompressionLevel]::Optimal,
            $true
        )
        try {
            $source.CopyTo($gzip)
        }
        finally {
            $gzip.Dispose()
        }
    }
    finally {
        $target.Dispose()
    }
}
finally {
    $source.Dispose()
}
