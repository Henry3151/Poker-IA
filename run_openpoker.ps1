# Poker AI Tournament Lab - Open Poker (VIRTUAL CHIPS ONLY) - one controlled session.
# The API key is read without echo, kept only in this process environment, never written to disk.
param([int]$MaxHands = 30, [int]$BuyIn = 2000)
Set-Location -Path $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) { Write-Host "Rode setup.bat primeiro."; exit 1 }
$secure = Read-Host -Prompt "OPEN_POKER_API_KEY (nao sera exibida)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:OPEN_POKER_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  $env:OPEN_POKER_ENABLED = "1"
  & .venv\Scripts\python.exe -m poker_lab.integrations.openpoker.run --max-hands $MaxHands --buy-in $BuyIn
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  Remove-Item Env:\OPEN_POKER_API_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:\OPEN_POKER_ENABLED -ErrorAction SilentlyContinue
}
