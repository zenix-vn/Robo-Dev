# Build firmware Robo Dev.
#
#   .\build.ps1               chuẩn bị thư viện xiaozhi-esp32 rồi build board robo-dev-s3
#   .\build.ps1 -PrepareOnly  chỉ chuẩn bị (áp patch, gắn board), không build
#   .\build.ps1 -Reset        trả thư viện xiaozhi-esp32 về nguyên gốc (gỡ patch, gỡ board)
#
# "Chuẩn bị" gồm 3 bước, chạy lại bao nhiêu lần cũng được:
#   1. Tải thư viện xiaozhi-esp32 (git submodule) nếu chưa có, giữ kiểu xuống dòng LF để patch áp được.
#   2. Áp lần lượt các file patches\*.patch vào thư viện (bỏ qua patch đã áp).
#   3. Gắn thư mục robo-dev-s3\ vào xiaozhi-esp32\main\boards\ bằng junction (sửa ở robo-dev-s3\ là thấy ngay).
param(
    [switch]$PrepareOnly,
    [switch]$Reset,
    [string]$Board = "robo-dev-s3"
)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Lib = Join-Path $Root "xiaozhi-esp32"
$Link = Join-Path $Lib "main\boards\$Board"

function Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }

function Git-Ok {
    # Chạy git chỉ để hỏi (có/không); PowerShell 5.1 coi chữ git in ra stderr là lỗi nên tạm bỏ "Stop"
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & git -C $Lib @args 2>&1 | Out-Null
    $ok = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $old
    return $ok
}

function Git-Lib {
    & git -C $Lib @args
    if ($LASTEXITCODE -ne 0) { throw "git $args thất bại" }
}

if ($Reset) {
    Step "Trả xiaozhi-esp32 về nguyên gốc"
    if (Test-Path $Link) { (Get-Item $Link).Delete() }
    Git-Lib checkout -- .
    Write-Host "Xong." -ForegroundColor Green
    return
}

# 1. Thư viện xiaozhi-esp32 -------------------------------------------------------------
if (-not (Test-Path (Join-Path $Lib "CMakeLists.txt"))) {
    Step "Tải thư viện xiaozhi-esp32 (git submodule)"
    & git -C $Root -c core.autocrlf=false submodule update --init --depth 1 -- xiaozhi-esp32
    if ($LASTEXITCODE -ne 0) { throw "Không tải được submodule xiaozhi-esp32" }
}
if ((& git -C $Lib config core.autocrlf) -ne "false") {
    Git-Lib config core.autocrlf false
    Git-Lib checkout -f -- .
}

# 2. Patch -------------------------------------------------------------------------------
foreach ($patch in Get-ChildItem (Join-Path $Root "patches\*.patch") | Sort-Object Name) {
    if (Git-Ok apply --check $patch.FullName) {
        Step "Áp patch $($patch.Name)"
        Git-Lib apply $patch.FullName
        continue
    }
    if (Git-Ok apply --reverse --check $patch.FullName) {
        Write-Host "    đã áp: $($patch.Name)"
        continue
    }
    throw "Patch $($patch.Name) không áp được. Chạy '.\build.ps1 -Reset' rồi thử lại, hoặc sửa patch cho khớp phiên bản xiaozhi-esp32."
}

# 3. Gắn board ---------------------------------------------------------------------------
if (-not (Test-Path $Link)) {
    Step "Gắn board $Board vào xiaozhi-esp32\main\boards"
    New-Item -ItemType Junction -Path $Link -Target (Join-Path $Root $Board) | Out-Null
}
$exclude = & git -C $Lib rev-parse --git-path info/exclude
if (-not (Test-Path $exclude) -or -not (Select-String -Path $exclude -SimpleMatch "main/boards/$Board" -Quiet)) {
    Add-Content -Path $exclude -Value "main/boards/$Board"
}

if ($PrepareOnly) {
    Write-Host "Đã chuẩn bị xong xiaozhi-esp32." -ForegroundColor Green
    return
}

# 4. Build -------------------------------------------------------------------------------
# ESP-IDF và build.py in thông tin ra stderr; PowerShell 5.1 coi đó là lỗi nếu để "Stop"
$ErrorActionPreference = "Continue"
if (-not (Get-Command idf.py -ErrorAction SilentlyContinue)) {
    . (Join-Path $Root "idf-env.ps1")
}
if (-not (Get-Command idf.py -ErrorAction SilentlyContinue)) {
    throw "Chưa mở được môi trường ESP-IDF. Kiểm tra đường dẫn trong idf-env.ps1."
}
Step "Build board $Board"
Push-Location $Lib
try {
    python scripts/build.py $Board
    if ($LASTEXITCODE -ne 0) { throw "Build thất bại (mã $LASTEXITCODE)" }
} finally {
    Pop-Location
}
Write-Host "Build xong: firmware\xiaozhi-esp32\build\" -ForegroundColor Green
