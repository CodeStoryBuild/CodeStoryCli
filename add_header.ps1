# -----------------------------------------------------------------------------
# add_license_header.ps1
# Prepends dual-license header to all .py files in codestory directory recursively
# -----------------------------------------------------------------------------

# Path to the codestory directory (change if needed)
$rootDir = ".\codestory"

$licenseHeader = @"
"""
-----------------------------------------------------------------------------
/*
 * Copyright (C) 2025 CodeStory
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; Version 2.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, you can contact us at support@codestory.build.
 */
-----------------------------------------------------------------------------
"""


"@

# Get all .py files recursively in the codestory directory
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
