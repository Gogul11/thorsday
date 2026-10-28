$figure = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')) 'report\BTECH_2026\5\figures\planner_tool_selection_results.png'
$overall = Join-Path (Split-Path $figure) 'planner_tool_selection_overall.png'
$category = Join-Path (Split-Path $figure) 'planner_tool_selection_category.png'
Add-Type -AssemblyName System.Drawing
$source = New-Object System.Drawing.Bitmap($figure)
try {
    $overallRect = New-Object System.Drawing.Rectangle(80, 120, 850, 780)
    $categoryRect = New-Object System.Drawing.Rectangle(980, 120, 1340, 780)
    $source.Clone($overallRect, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb).Save($overall, [System.Drawing.Imaging.ImageFormat]::Png)
    $source.Clone($categoryRect, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb).Save($category, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output "Wrote $overall"
    Write-Output "Wrote $category"
}
finally {
    $source.Dispose()
}
