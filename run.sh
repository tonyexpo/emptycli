#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

has_sdk() {
  "$1" --list-sdks 2>/dev/null | grep -q .
}

if command -v dotnet >/dev/null 2>&1 && has_sdk "$(command -v dotnet)"; then
  # A normal SDK install (apt, tarball, or a snap that actually ships the SDK).
  exec dotnet run --project src/EmptyCli -- "$@"
fi

if [ -x "$HOME/.dotnet/dotnet" ] && has_sdk "$HOME/.dotnet/dotnet"; then
  # Local SDK installed with dotnet-install.sh. This also covers machines where
  # the Ubuntu snap only provides the runtime.
  export DOTNET_ROOT="$HOME/.dotnet"
  export PATH="$DOTNET_ROOT:$PATH"
  exec dotnet run --project src/EmptyCli -- "$@"
fi

# Last resort: a runtime-only dotnet can still play a previously built binary.
for dll in \
  "src/EmptyCli/bin/Release/net10.0/emptycli.dll" \
  "src/EmptyCli/bin/Debug/net10.0/emptycli.dll"; do
  if [ -f "$dll" ] && command -v dotnet >/dev/null 2>&1; then
    exec dotnet "$dll" "$@"
  fi
done

echo "emptycli: a .NET 10 SDK is required to build." >&2
echo "Install it from https://dotnet.microsoft.com/download" >&2
echo "Note: the Ubuntu 'dotnet' snap may contain only the runtime." >&2
exit 1
