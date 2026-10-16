# Build firmware Robo Dev.
#
#   .\build.ps1                         chuẩn bị thư viện xiaozhi-esp32 rồi build board robo-dev-s3
#   .\build.ps1 -PrepareOnly            chỉ chuẩn bị (áp patch, gắn board), không build
#   .\build.ps1 -SavePatches            lưu phần đã sửa trong xiaozhi-esp32 vào các patch đang có
#   .\build.ps1 -SavePatches -NewName ten-ngan
#                                       như trên, và gom các file mới sửa thành patch mới NN-ten-ngan.patch
#   .\build.ps1 -Reset                  trả thư viện xiaozhi-esp32 về nguyên gốc (gỡ patch, gỡ board)
#
# Quy tắc: xiaozhi-esp32\ là thư viện của người khác, không commit vào đó. Mọi chỗ buộc phải sửa trong
# thư viện phải nằm trong patches\*.patch (thuộc repo Robo Dev) thì mới được commit.
#
# "Chuẩn bị" gồm 4 bước, chạy lại bao nhiêu lần cũng được:
#   1. Tải thư viện xiaozhi-esp32 (git submodule) nếu chưa có, giữ kiểu xuống dòng LF để patch áp được.
#   2. Áp lần lượt các file patches\*.patch vào thư viện (bỏ qua patch đã áp).
#   3. Gắn thư mục robo-dev-s3\ vào xiaozhi-esp32\main\boards\ bằng junction (sửa ở robo-dev-s3\ là thấy ngay).
#   4. Kiểm tra: còn chỗ nào trong thư viện đã sửa mà chưa lưu vào patch thì cảnh báo.
param(
    [switch]$PrepareOnly,
    [switch]$SavePatches,
    [string]$NewName = "",
    [switch]$Reset,
    [string]$Board = "robo-dev-s3"
)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Lib = Join-Path $Root "xiaozhi-esp32"
$PatchDir = Join-Path $Root "patches"
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

function Get-Patches { Get-ChildItem (Join-Path $PatchDir "*.patch") | Sort-Object Name }

function Get-PatchFiles($patch) {
    # Các file mà một patch sửa (đọc từ dòng "diff --git a/<file> b/<file>")
    Select-String -Path $patch.FullName -Pattern '^diff --git a/(\S+) b/' | ForEach-Object { $_.Matches[0].Groups[1].Value }
}

function Get-ChangedFiles {
    # File trong thư viện khác bản gốc: đã sửa, hoặc file mới (trừ board đã gắn)
    $changed = @(& git -C $Lib diff --name-only) + @(& git -C $Lib ls-files --others --exclude-standard)
    $changed | Where-Object { $_ -and $_ -notlike "main/boards/$Board*" } | Sort-Object -Unique
}

function Write-Diff($files, $path) {
    # git tự ghi file (giữ nguyên UTF-8, LF); file mới phải được "add -N" thì mới có trong diff
    $untracked = @(& git -C $Lib ls-files --others --exclude-standard -- $files)
    if ($untracked.Count) { Git-Lib add -N -- $untracked }
    Git-Lib diff "--output=$path" -- $files
}

function Normalize($path) {
    # So sánh nội dung patch, bỏ qua dòng "index" (mã băm) và khác biệt xuống dòng
    (Get-Content -Raw -Encoding UTF8 $path) -replace "`r", "" -split "`n" |
        Where-Object { $_ -notmatch '^index ' } | ForEach-Object { $_.TrimEnd() }
}

function Test-Unsaved {
    # Trả về danh sách cảnh báo: file sửa ngoài patch, patch cũ hơn phần đang sửa
    $warnings = @()
    $patched = @()
    foreach ($patch in Get-Patches) {
        $files = @(Get-PatchFiles $patch)
        $patched += $files
        $tmp = [IO.Path]::GetTempFileName()
        try {
            Write-Diff $files $tmp
            if (Compare-Object @(Normalize $patch.FullName) @(Normalize $tmp)) {
                $warnings += "Patch $($patch.Name) khác với phần đang sửa trong: $($files -join ', ')"
            }
        } finally {
            Remove-Item $tmp -ErrorAction SilentlyContinue
        }
    }
    foreach ($file in Get-ChangedFiles) {
        if ($patched -notcontains $file) { $warnings += "Đã sửa nhưng chưa có trong patch nào: $file" }
    }
    return $warnings
}

# Trả thư viện về nguyên gốc ---------------------------------------------------------------
if ($Reset) {
    $unsaved = Test-Unsaved
    if ($unsaved) {
        $unsaved | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
        throw "Thư viện còn chỗ sửa chưa lưu vào patch, -Reset sẽ làm mất. Chạy '.\build.ps1 -SavePatches' trước."
    }
    Step "Trả xiaozhi-esp32 về nguyên gốc"
    if (Test-Path $Link) { (Get-Item $Link).Delete() }
    Git-Lib reset -q
    Git-Lib checkout -- .
    Write-Host "Xong." -ForegroundColor Green
    return
}

# Lưu phần sửa trong thư viện vào patch ------------------------------------------------------
if ($SavePatches) {
    $patched = @()
    foreach ($patch in Get-Patches) {
        $files = @(Get-PatchFiles $patch)
        $patched += $files
        Write-Diff $files $patch.FullName
        if ((Get-Item $patch.FullName).Length -eq 0) {
            Remove-Item $patch.FullName
            Write-Host "    bỏ patch rỗng (đã trả các file về nguyên gốc): $($patch.Name)" -ForegroundColor Yellow
        } else {
            Write-Host "    cập nhật: $($patch.Name)"
        }
    }
    $extra = @(Get-ChangedFiles | Where-Object { $patched -notcontains $_ })
    if ($extra.Count) {
        if (-not $NewName) {
            $extra | ForEach-Object { Write-Host "    chưa có patch: $_" -ForegroundColor Yellow }
            throw "Có file mới sửa chưa thuộc patch nào. Chạy lại với tên patch mới, ví dụ: .\build.ps1 -SavePatches -NewName ten-ngan"
        }
        $last = Get-Patches | Select-Object -Last 1
        $number = if ($last -and $last.Name -match '^(\d+)-') { [int]$Matches[1] + 1 } else { 1 }
        $name = "{0:D2}-{1}.patch" -f $number, ($NewName -replace '[^A-Za-z0-9-]', '-').ToLower()
        Write-Diff $extra (Join-Path $PatchDir $name)
        Write-Host "    patch mới: $name ($($extra -join ', '))" -ForegroundColor Green
    }
    Write-Host "Đã lưu. Nhớ ghi patch mới vào bảng trong firmware\README.md rồi commit." -ForegroundColor Green
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
foreach ($patch in Get-Patches) {
    if (Git-Ok apply --check $patch.FullName) {
        Step "Áp patch $($patch.Name)"
        Git-Lib apply $patch.FullName
        continue
    }
    if (Git-Ok apply --reverse --check $patch.FullName) {
        Write-Host "    đã áp: $($patch.Name)"
        continue
    }
    $files = (Get-PatchFiles $patch) -join ', '
    throw ("Patch $($patch.Name) không áp được. Thường do các file của nó trong xiaozhi-esp32 đã bị sửa thêm " +
           "($files). Lưu phần sửa: '.\build.ps1 -SavePatches'. Nếu vừa đổi phiên bản xiaozhi-esp32 thì sửa patch cho khớp.")
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

# 4. Kiểm tra phần sửa chưa lưu ------------------------------------------------------------
$unsaved = Test-Unsaved
if ($unsaved) {
    Write-Host ""
    Write-Host "CẢNH BÁO: trong xiaozhi-esp32 (thư viện của người khác) có chỗ sửa chưa lưu vào patch," -ForegroundColor Yellow
    Write-Host "nên sẽ KHÔNG được commit và sẽ mất khi cập nhật thư viện:" -ForegroundColor Yellow
    $unsaved | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
    Write-Host "Lưu vào patch:  .\build.ps1 -SavePatches   (file mới sửa: thêm -NewName ten-ngan)" -ForegroundColor Yellow
    Write-Host ""
}

if ($PrepareOnly) {
    Write-Host "Đã chuẩn bị xong xiaozhi-esp32." -ForegroundColor Green
    return
}

# 5. Build -------------------------------------------------------------------------------
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
