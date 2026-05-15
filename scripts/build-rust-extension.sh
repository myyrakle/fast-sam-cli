#!/usr/bin/env bash
set -euo pipefail

PYO3_BUILD_EXTENSION_MODULE=1 cargo build -p sam-build-py

case "$(uname -s)" in
  Darwin) ext="dylib" ;;
  Linux) ext="so" ;;
  MINGW*|MSYS*|CYGWIN*) ext="dll" ;;
  *) echo "Unsupported platform" >&2; exit 1 ;;
esac

src="target/debug/lib_sam_build_core.${ext}"
python_ext_suffix="$(python3 - <<'PY'
import sysconfig
print(sysconfig.get_config_var("EXT_SUFFIX") or ".so")
PY
)"
dest="samcli/lib/build/_sam_build_core${python_ext_suffix}"

cp "$src" "$dest"
echo "Copied $src -> $dest"
