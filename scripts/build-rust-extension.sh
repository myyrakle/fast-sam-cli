#!/usr/bin/env bash
set -euo pipefail

PYO3_BUILD_EXTENSION_MODULE=1 cargo build --release -p sam-build-py

case "$(uname -s)" in
  Darwin) ext="dylib" ;;
  Linux) ext="so" ;;
  MINGW*|MSYS*|CYGWIN*) ext="dll" ;;
  *) echo "Unsupported platform" >&2; exit 1 ;;
esac

src="target/release/lib_sam_build_core.${ext}"
python_bin="${PYTHON_BIN:-}"
if [[ -z "${python_bin}" ]]; then
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    python_bin="${VIRTUAL_ENV}/bin/python"
  elif [[ -x ".venv/bin/python" ]]; then
    python_bin=".venv/bin/python"
  else
    python_bin="python3"
  fi
fi
python_ext_suffix="$("${python_bin}" - <<'PY'
import sysconfig
print(sysconfig.get_config_var("EXT_SUFFIX") or ".so")
PY
)"
dest="samcli/lib/build/_sam_build_core${python_ext_suffix}"

cp "$src" "$dest"
echo "Copied $src -> $dest"
