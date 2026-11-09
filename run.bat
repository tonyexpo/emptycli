@echo off
setlocal
cd /d "%~dp0"

dotnet --list-sdks 2>nul | findstr /r "." >nul
if %errorlevel%==0 (
  dotnet run --project src\EmptyCli -- %*
  exit /b %errorlevel%
)

rem Last resort: a runtime-only dotnet can still play a previously built binary.
for %%D in (Release Debug) do (
  if exist "src\EmptyCli\bin\%%D\net10.0\emptycli.dll" (
    dotnet "src\EmptyCli\bin\%%D\net10.0\emptycli.dll" %*
    exit /b %errorlevel%
  )
)

echo emptycli: a .NET 10 SDK is required to build. 1>&2
echo Install it from https://dotnet.microsoft.com/download 1>&2
exit /b 1
