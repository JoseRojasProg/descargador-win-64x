#!/usr/bin/env python3
"""
empaquetar.py — Proyecto Ola Digital
Empaqueta main.py con flet pack (PyInstaller) para Linux 64 o Windows 64.

Uso:
    python empaquetar.py           # empaqueta para la plataforma actual
    python empaquetar.py --limpiar # borra build/ y dist/ antes de empaquetar
"""

import os
import sys
import platform
import shutil
import subprocess
import argparse

# ─────────────────────────────────────────────────────────────
#  CONFIGURACIÓN DEL PROYECTO — edita aquí si cambias algo
# ─────────────────────────────────────────────────────────────
SCRIPT = "main.py"           # script principal
APP_NAME = "DescargadorOlaDigital"
VERSION = "1.0.0"
COMPANY = "Proyecto Ola Digital"
COPYRIGHT = "© 2026 Proyecto Ola Digital"
DESCRIPTION = "Descargador de Videos — Proyecto Ola Digital"

# Icono según plataforma (pon los archivos en assets/)
ICON_LINUX = os.path.join("assets", "logo_POD.png")
# necesita .ico en Windows
ICON_WINDOWS = os.path.join("assets", "logo_POD.ico")

# Datos extra que deben ir dentro del ejecutable
# formato: ("origen", "destino_dentro_del_bundle")
# Se incluye toda la carpeta assets/ para que los iconos y logos estén disponibles
ARCHIVOS_EXTRA = [
    ("assets", "assets"),
]

# Carpeta de salida
DIST_DIR = "dist"

# ─────────────────────────────────────────────────────────────
#  UTILIDADES
# ─────────────────────────────────────────────────────────────


def log(msg, color="\033[96m"):
    reset = "\033[0m"
    print(f"{color}▶ {msg}{reset}")


def error(msg):
    print(f"\033[91m✗ {msg}\033[0m")
    sys.exit(1)


def ok(msg):
    print(f"\033[92m✓ {msg}\033[0m")


def detectar_plataforma():
    s = platform.system()
    if s == "Linux":
        return "linux"
    elif s == "Windows":
        return "windows"
    elif s == "Darwin":
        return "macos"
    else:
        error(f"Plataforma no soportada: {s}")


def verificar_dependencias():
    log("Verificando dependencias…")

    # flet pack
    if shutil.which("flet") is None:
        error("'flet' no encontrado. Instala con: pip install flet-cli==0.84.0")

    # pyinstaller (flet pack lo necesita internamente)
    try:
        import PyInstaller
        ok(f"PyInstaller {PyInstaller.__version__}")
    except ImportError:
        error("PyInstaller no instalado. Corre: pip install pyinstaller")

    # flet
    try:
        import flet
        ok(f"Flet {flet.__version__}")
    except ImportError:
        error("Flet no instalado. Corre: pip install flet==0.84.0")

    # yt_dlp
    try:
        import yt_dlp
        ok("yt-dlp presente")
    except ImportError:
        error("yt-dlp no instalado. Corre: pip install yt-dlp")


def verificar_archivos():
    log("Verificando archivos del proyecto…")

    if not os.path.exists(SCRIPT):
        error(
            f"No se encontró '{SCRIPT}'. Ejecuta este script desde la carpeta del proyecto.")

    for origen, _ in ARCHIVOS_EXTRA:
        if not os.path.exists(origen):
            error(f"Carpeta/archivo faltante: '{origen}'")
        else:
            if os.path.isdir(origen):
                archivos = os.listdir(origen)
                ok(f"Carpeta encontrada: {origen}/ ({len(archivos)} archivos)")
            else:
                ok(f"Encontrado: {origen}")


def limpiar():
    log("Limpiando build/ y dist/…")
    for carpeta in ["build", "dist", "__pycache__"]:
        if os.path.exists(carpeta):
            shutil.rmtree(carpeta)
            ok(f"Eliminado: {carpeta}/")


def construir_comando(plataforma):
    """Arma el comando flet pack con todos los argumentos."""
    cmd = [
        "flet", "pack", SCRIPT,
        "--name",             APP_NAME,
        "--distpath",         DIST_DIR,
        "--product-name",     APP_NAME,
        "--product-version",  VERSION,
        "--file-version",     VERSION,
        "--company-name",     COMPANY,
        "--copyright",        COPYRIGHT,
        "--file-description", DESCRIPTION,
    ]

    # Icono
    if plataforma == "windows" and os.path.exists(ICON_WINDOWS):
        cmd += ["--icon", ICON_WINDOWS]
        ok(f"Usando icono: {ICON_WINDOWS}")
    elif plataforma == "linux" and os.path.exists(ICON_LINUX):
        cmd += ["--icon", ICON_LINUX]
        ok(f"Usando icono: {ICON_LINUX}")
    else:
        log("Sin icono personalizado (opcional)", "\033[93m")

    # Archivos extra (logo, assets)
    for origen, destino in ARCHIVOS_EXTRA:
        # flet pack usa SOURCE:DEST
        sep = ";" if plataforma == "windows" else ":"
        cmd += ["--add-data", f"{origen}{sep}{destino}"]

    # Hidden imports que yt-dlp puede necesitar
    for mod in ["yt_dlp", "yt_dlp.extractor", "yt_dlp.postprocessor"]:
        cmd += ["--hidden-import", mod]

    return cmd


def empaquetar(plataforma):
    log(f"Empaquetando para: {plataforma.upper()} 64-bit…")

    cmd = construir_comando(plataforma)

    print("\n\033[90m" + " ".join(cmd) + "\033[0m\n")

    resultado = subprocess.run(cmd, text=True)

    if resultado.returncode != 0:
        error("El empaquetado falló. Revisa los mensajes de arriba.")


def mostrar_resultado(plataforma):
    """Busca el ejecutable generado y muestra su ruta."""
    sufijo = ".exe" if plataforma == "windows" else ""
    exe = os.path.join(DIST_DIR, f"{APP_NAME}{sufijo}")

    print()
    if os.path.exists(exe):
        size_mb = os.path.getsize(exe) / (1024 * 1024)
        ok(f"Ejecutable generado: {exe}  ({size_mb:.1f} MB)")
    else:
        # En Linux a veces queda sin extensión o en subcarpeta
        for root, dirs, files in os.walk(DIST_DIR):
            for f in files:
                if APP_NAME.lower() in f.lower():
                    ruta = os.path.join(root, f)
                    size_mb = os.path.getsize(ruta) / (1024 * 1024)
                    ok(f"Ejecutable generado: {ruta}  ({size_mb:.1f} MB)")
                    return
        log("Revisa la carpeta dist/ manualmente.", "\033[93m")

# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Empaqueta el Descargador de Videos de Ola Digital."
    )
    parser.add_argument(
        "--limpiar", action="store_true",
        help="Borra build/ y dist/ antes de empaquetar"
    )
    args = parser.parse_args()

    print("\n\033[1m\033[96m╔══════════════════════════════════════╗")
    print("║   Empaquetador — Proyecto Ola Digital  ║")
    print("╚══════════════════════════════════════╝\033[0m\n")

    plataforma = detectar_plataforma()
    log(f"Sistema detectado: {platform.system()} {platform.machine()}")

    verificar_dependencias()
    verificar_archivos()

    if args.limpiar:
        limpiar()

    empaquetar(plataforma)
    mostrar_resultado(plataforma)

    print()
    ok("¡Listo! Puedes distribuir el ejecutable de dist/")
    print()


if __name__ == "__main__":
    main()
