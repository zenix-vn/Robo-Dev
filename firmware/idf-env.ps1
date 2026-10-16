# Mở môi trường ESP-IDF trong cửa sổ PowerShell hiện tại.
# Cách dùng (chú ý dấu chấm và dấu cách ở đầu):   . .\idf-env.ps1
#
# Tự tìm ESP-IDF theo thứ tự: biến môi trường IDF_PATH, rồi các chỗ cài thường gặp.
# Cài ở chỗ khác thì đặt một lần:   setx IDF_PATH "E:\duong-dan\esp-idf"   (rồi mở PowerShell mới)

$candidates = @($env:IDF_PATH)
foreach ($drive in "C:", "D:", "E:") {
    $candidates += "$drive\Espressif\esp-idf"
    $candidates += Get-ChildItem "$drive\esp\*\esp-idf" -Directory -ErrorAction SilentlyContinue | ForEach-Object FullName
}
$candidates += "$env:USERPROFILE\esp\esp-idf"
$candidates += Get-ChildItem "$env:USERPROFILE\.espressif\*\esp-idf" -Directory -ErrorAction SilentlyContinue | ForEach-Object FullName

$IdfPath = $candidates | Where-Object { $_ -and (Test-Path "$_\export.ps1") } | Select-Object -First 1
if (-not $IdfPath) {
    Write-Host "Không tìm thấy ESP-IDF. Cài ESP-IDF v6.1, hoặc đặt đường dẫn: setx IDF_PATH `"<thư mục esp-idf>`"" -ForegroundColor Red
    return
}

# Thư mục công cụ (trình biên dịch, python env...) đi kèm ESP-IDF
if (-not $env:IDF_TOOLS_PATH) {
    $tools = @((Join-Path (Split-Path $IdfPath -Parent) "tools"), "C:\Espressif\tools", "D:\Espressif\tools",
               "$env:USERPROFILE\.espressif") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($tools) { $env:IDF_TOOLS_PATH = $tools }
}

# ESP-IDF từ chối chạy khi thấy biến môi trường của Git Bash / MSYS
Get-ChildItem Env: | Where-Object { $_.Name -match '^(MSYS|MINGW)' } | ForEach-Object { Remove-Item "Env:$($_.Name)" }

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"   # export.ps1 in thông tin ra stderr
. "$IdfPath\export.ps1" *> $null
$ErrorActionPreference = $old

Set-Location $PSScriptRoot
if (Get-Command idf.py -ErrorAction SilentlyContinue) {
    Write-Host "Đã mở môi trường ESP-IDF ($IdfPath):" (idf.py --version) -ForegroundColor Green
} else {
    Write-Host "Chạy export.ps1 của $IdfPath nhưng chưa có idf.py. Kiểm tra lại bản cài ESP-IDF." -ForegroundColor Red
}
