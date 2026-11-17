#!/usr/bin/env sh
# Startet das AM-Magazin. Nutzt die virtuelle Umgebung .venv, falls vorhanden.
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python magazin.py "$@"
fi
exec python3 magazin.py "$@"
