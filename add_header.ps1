# -----------------------------------------------------------------------------
# add_license_header.ps1
# Prepends dual-license header to all .py files in dslate directory recursively
# -----------------------------------------------------------------------------

# Path to the dslate directory (change if needed)
$rootDir = ".\dslate"

# Define the license header as an array of strings
$licenseHeader = @(
    "# -----------------------------------------------------------------------------",
    "# dslate - Dual Licensed Software",
    "# Copyright (c) 2025 Adem Can",
    "#",
    "# This file is part of DSLATE.",
    "#",
    "# DSLATE is available under a dual-license:",
    "#   1. AGPLv3 (Affero General Public License v3)",
    "#      - See LICENSE.txt and LICENSE-AGPL.txt",
    "#      - Online: https://www.gnu.org/licenses/agpl-3.0.html",
    "#",
    "#   2. Commercial License",
    "#      - For proprietary or revenue-generating use,",
    "#        including SaaS, embedding in closed-source software,",
    "#        or avoiding AGPL obligations.",
    "#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt",
    "#      - Contact: ademfcan@gmail.com",
    "#",
    "# By using this file, you agree to the terms of one of the two licenses above.",
    "# -----------------------------------------------------------------------------",
    "",  # padding line 1
    ""   # padding line 2
)

# Get all .py files recursively in the dslate directory
$pyFiles = Get-ChildItem -Path $rootDir -Recurse -Filter "*.py"

foreach ($file in $pyFiles) {
    # Read existing content
    $originalContent = Get-Content -LiteralPath $file.FullName

    # Prepend license header

    # prepend only if header not already present
    $headerPresent = $false
    # check if starts with header
    if ($originalContent.Length -gt 0 -and $originalContent[0] -eq "# -----------------------------------------------------------------------------") {
        $headerPresent = $true
    }
    if ($headerPresent) {
        Write-Host "License header already present in $($file.FullName)"
        continue
    }
    
    $newContent = $licenseHeader + $originalContent

    # Write back to file
    Set-Content -LiteralPath $file.FullName -Value $newContent
    Write-Host "Prepended license header to $($file.FullName)"
}

Write-Host "License headers added to all .py files in $rootDir."
