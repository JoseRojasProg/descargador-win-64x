#!/usr/bin/env python3
"""
Descargador de Videos — GUI
Proyecto Ola Digital · Flet 0.84 / Python 3.12
"""

import os
import re
import shutil
import sys
import asyncio
import yt_dlp
import flet as ft

# ─────────────────────────────────────────────
#  CONFIGURACIÓN DE RUTAS
# ─────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    _DIR_BASE = sys._MEIPASS
else:
    _DIR_BASE = os.path.dirname(os.path.realpath(__file__))

LOGO_PATH = os.path.join(_DIR_BASE, "assets", "logo_POD.png")
ICON_PATH = os.path.join(_DIR_BASE, "assets", "logo_POD.ico")

# ─────────────────────────────────────────────
#  PRE-INSTALAR RUNTIME DE FLET DESDE EL BUNDLE
# ─────────────────────────────────────────────


def _instalar_flet_runtime():
    """
    Si el runtime de Flet no está en el caché del usuario,
    lo extrae desde el zip incluido en el bundle.
    Solo aplica cuando se corre como ejecutable empaquetado.
    """
    if not getattr(sys, 'frozen', False):
        return  # En desarrollo no hace falta

    import zipfile

    FLET_VERSION = "0.84.0"
    flet_cache = os.path.join(
        os.path.expanduser("~"), ".flet", "client",
        f"flet-desktop-full-{FLET_VERSION}", "flet"
    )

    if os.path.exists(flet_cache) and os.listdir(flet_cache):
        return  # Ya instalado

    # Buscar el zip del runtime dentro del bundle
    runtime_zip = os.path.join(_DIR_BASE, "flet-runtime", "flet-windows.zip")
    if not os.path.exists(runtime_zip):
        return  # No incluido en el bundle, Flet intentará descargarlo

    os.makedirs(flet_cache, exist_ok=True)
    with zipfile.ZipFile(runtime_zip, 'r') as z:
        z.extractall(flet_cache)


_instalar_flet_runtime()

# ─────────────────────────────────────────────
#  UTILIDADES
# ─────────────────────────────────────────────

# FIX: se calcula una sola vez al arrancar en lugar de llamarlo 3 veces
_FFMPEG_OK = shutil.which("ffmpeg") is not None


def ffmpeg_ok() -> bool:
    return _FFMPEG_OK


def extraer_id(url: str) -> str | None:
    m = re.search(r'(\d{10,20})', url)
    return m.group(1) if m else None


def normalizar_url(url_raw: str) -> str:
    if "facebook.com" in url_raw:
        vid = extraer_id(url_raw)
        if vid:
            return f"https://www.facebook.com/watch/?v={vid}"
    return url_raw


def fmt_bytes(n: int | None) -> str:
    # FIX: renombrado parámetro a 'n' para no mutar el argumento original
    if n is None:
        return "?"
    valor = float(n)
    for u in ['B', 'KB', 'MB', 'GB']:
        if valor < 1024:
            return f"{valor:.1f} {u}"
        valor /= 1024
    return f"{valor:.1f} GB"


def fmt_eta(eta: int | None) -> str:
    """Formatea ETA de forma legible sin decimales"""
    if eta is None or eta < 0:
        return ""
    if eta < 60:
        return f"ETA {eta:.0f}s"
    elif eta < 3600:
        mins = eta // 60
        secs = eta % 60
        return f"ETA {mins}m {secs:.0f}s"
    else:
        hours = eta // 3600
        mins = (eta % 3600) // 60
        return f"ETA {hours}h {mins}m"


def PAD(h=0, v=0): return ft.Padding(left=h, right=h, top=v, bottom=v)
def PAD_ALL(n): return ft.Padding(left=n, top=n, right=n, bottom=n)


def BORDER(w, c):
    s = ft.BorderSide(w, c)
    return ft.Border(top=s, right=s, bottom=s, left=s)


def BORDER_ONLY(top=None, bottom=None, left=None, right=None):
    # FIX: usar 'is None' en lugar de 'or n' para no descartar BorderSide válidos
    n = ft.BorderSide(0)
    return ft.Border(
        top=top if top is not None else n,
        bottom=bottom if bottom is not None else n,
        left=left if left is not None else n,
        right=right if right is not None else n,
    )


# ─────────────────────────────────────────────
#  PALETA OLA DIGITAL — DARK
# ─────────────────────────────────────────────
OLA = "#4ECDC4"
SURFISTA = "#E87722"
MAREA = "#2E6DA4"
D_BG = "#0F1923"
D_SURF = "#162030"
D_PANEL = "#1C2B3A"
D_CARD = "#1F3245"
D_BOR = "#2A4060"
D_TXT = "#F5F7FA"
D_MUT = "#D4F6F9"
D_HINT = "#4A6A88"
ERR = "#E05050"
BLANCO = "#FFFFFF"

# ─────────────────────────────────────────────
#  APP PRINCIPAL
# ─────────────────────────────────────────────


def main(page: ft.Page):
    page.window.resizable = True
    page.title = "Descargador de Videos"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = D_BG
    page.padding = 0

    if os.path.exists(ICON_PATH):
        page.window.icon = ICON_PATH
    elif os.path.exists(LOGO_PATH):
        page.window.icon = LOGO_PATH

    # Variables de estado
    carpeta = [os.path.join(os.path.expanduser("~"), "Downloads")]
    bajando = [False]
    listo = [False]
    es_playlist = [False]
    modo = ["1"]
    main_loop = None

    # ─────────────────────────────────────────
    #  FUNCIONES DE UI
    # ─────────────────────────────────────────
    def page_update():
        try:
            page.update()
        except Exception:
            pass

    def btn_style(bg):
        return ft.ButtonStyle(
            bgcolor=bg, color=BLANCO,
            shape=ft.RoundedRectangleBorder(radius=8),
            elevation={ft.ControlState.DEFAULT: 0, ft.ControlState.HOVERED: 6},
            animation_duration=150,
        )

    def btn_txt(label):
        return ft.Text(label, size=14, weight=ft.FontWeight.W_700,
                       color=BLANCO, no_wrap=True,
                       style=ft.TextStyle(letter_spacing=1.5))

    def sec_label(t):
        return ft.Text(t, size=10, color=D_MUT, weight=ft.FontWeight.W_600,
                       style=ft.TextStyle(letter_spacing=1.8))

    # ─────────────────────────────────────────
    #  SELECTOR DE CARPETA (multiplataforma)
    # ─────────────────────────────────────────
    def on_pick_dir(e):
        import threading
        import tkinter as tk
        from tkinter import filedialog

        def _pick():
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes('-topmost', True)
            ruta = filedialog.askdirectory(
                title="Seleccionar carpeta de destino",
                initialdir=carpeta[0]
            )
            root.destroy()
            if ruta:
                carpeta[0] = ruta
                lbl_carpeta.value = ruta
                page_update()
        threading.Thread(target=_pick, daemon=True).start()

    # ─────────────────────────────────────────
    #  CABECERA CON VERSIÓN V2.0 EN NEGRITAS
    # ─────────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Container(
                    content=ft.Text("▶", size=18, color=BLANCO),
                    bgcolor=SURFISTA, border_radius=8,
                    padding=PAD(h=10, v=7),
                ),
                ft.Column([
                    ft.Text("DESCARGADOR DE VIDEOS", size=17,
                            weight=ft.FontWeight.W_800, color=OLA,
                            style=ft.TextStyle(letter_spacing=2)),
                    ft.Row([
                        ft.Text("YouTube · Facebook · Instagram · X · TikTok · ",
                                size=11, color=D_MUT),
                        ft.Text("v2.0", size=11,
                                weight=ft.FontWeight.BOLD, color=OLA),
                    ], spacing=0),
                ], spacing=2),
            ], spacing=14),
            ft.Container(
                content=ft.Image(src=LOGO_PATH, width=75,
                                 height=75, fit="contain"),
                border_radius=10,
                ink=True,
                tooltip="Visitar Proyecto Ola Digital",
                url="https://proyectooladigital.github.io/proyecto-ola-digital/",
            ) if os.path.exists(LOGO_PATH) else ft.Container(),
        ], spacing=14, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=PAD(h=24, v=16),
        border=BORDER_ONLY(bottom=ft.BorderSide(2, OLA)),
        bgcolor=D_SURF,
    )

    # ─────────────────────────────────────────
    #  CONTROLES PRINCIPALES
    # ─────────────────────────────────────────
    lbl_carpeta = ft.Text(carpeta[0], size=11, color=D_MUT,
                          overflow=ft.TextOverflow.ELLIPSIS, expand=True)

    url_field = ft.TextField(
        hint_text="Pega el enlace aquí…",
        hint_style=ft.TextStyle(color=D_HINT, size=13),
        text_style=ft.TextStyle(color=D_TXT, size=13),
        border_color=D_BOR,
        focused_border_color=OLA,
        cursor_color=SURFISTA,
        bgcolor=D_PANEL,
        border_radius=8,
        content_padding=PAD(h=14, v=12),
        expand=True,
        prefix_icon=ft.Icons.LINK,
    )

    # ─────────────────────────────────────────
    #  FORMATOS (PILLS)
    # ─────────────────────────────────────────
    pills = []
    PILL_SEL = "#1A3A4A"

    def hacer_pill(val, icono, corto, desc, warn):
        def click(e, v=val):
            modo[0] = v
            for p in pills:
                sel = p.data == modo[0]
                p.border = BORDER(2, OLA if sel else D_BOR)
                p.bgcolor = PILL_SEL if sel else D_PANEL
            page_update()
        return ft.Container(
            content=ft.Column([
                ft.Icon(icono, size=22, color=OLA),
                ft.Text(corto, size=13, weight=ft.FontWeight.W_700,
                        color=D_TXT, text_align=ft.TextAlign.CENTER, no_wrap=True),
                ft.Text(desc, size=10,
                        color=D_MUT if not warn else SURFISTA,
                        text_align=ft.TextAlign.CENTER, no_wrap=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
            width=168, height=96, border_radius=10,
            border=BORDER(2, D_BOR), bgcolor=D_PANEL,
            padding=PAD_ALL(12),
            on_click=click,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            data=val,
        )

    # FIX: _FFMPEG_OK ya cacheado — no se llama 3 veces a shutil.which
    modos_cfg = [
        ("1", ft.Icons.HD,           "HD",        "Alta calidad", not _FFMPEG_OK),
        ("2", ft.Icons.PHONE_ANDROID, "WhatsApp", "Ligero 480p",  False),
        ("3", ft.Icons.MUSIC_NOTE,   "MP3",       "Solo audio", not _FFMPEG_OK),
    ]

    for m in modos_cfg:
        pills.append(hacer_pill(*m))
    pills[0].border = BORDER(2, OLA)
    pills[0].bgcolor = PILL_SEL
    pills_row = ft.Row(pills, spacing=8, alignment=ft.MainAxisAlignment.CENTER)

    # ─────────────────────────────────────────
    #  BARRA DE PROGRESO Y ESTADO
    # ─────────────────────────────────────────
    barra = ft.ProgressBar(value=0, color=SURFISTA, bgcolor=D_BOR,
                           border_radius=4, visible=False)
    lbl_pct = ft.Text("", size=13, color=SURFISTA, weight=ft.FontWeight.W_600)
    lbl_vel = ft.Text("", size=11, color=D_MUT)
    lbl_eta = ft.Text("", size=11, color=D_MUT)
    stats = ft.Row([lbl_pct, ft.Container(expand=True),
                    lbl_vel, ft.Text("·", color=D_MUT), lbl_eta],
                   visible=False)
    estado = ft.Text("", size=12, color=D_MUT, text_align=ft.TextAlign.CENTER)

    # ─────────────────────────────────────────
    #  INFO DEL VIDEO
    # ─────────────────────────────────────────
    info_titulo = ft.Text("", size=13, color=D_TXT,
                          overflow=ft.TextOverflow.ELLIPSIS)
    info_dur = ft.Text("", size=11, color=D_MUT)
    info_tam = ft.Text("", size=11, color=D_MUT)

    info_box = ft.Container(
        content=ft.Column([
            ft.Row([ft.Icon(ft.Icons.MOVIE, size=14, color=OLA),
                   info_titulo], spacing=8),
            ft.Row([ft.Icon(ft.Icons.TIMER, size=12, color=D_MUT), info_dur,
                    ft.Container(width=12),
                    ft.Icon(ft.Icons.DATA_USAGE, size=12, color=D_MUT), info_tam], spacing=6),
        ], spacing=6),
        visible=False, bgcolor=D_CARD, border_radius=8,
        padding=PAD(h=14, v=10), border=BORDER(1, OLA),
    )

    # ─────────────────────────────────────────
    #  PLAYLIST
    # ─────────────────────────────────────────
    r_ini = ft.TextField(
        value="1", width=68, text_align=ft.TextAlign.CENTER,
        text_style=ft.TextStyle(color=D_TXT, size=13), hint_text="Desde",
        border_color=D_BOR, focused_border_color=OLA,
        bgcolor=D_PANEL, border_radius=6, content_padding=PAD(h=6, v=6),
    )
    r_fin = ft.TextField(
        value="", width=68, text_align=ft.TextAlign.CENTER,
        text_style=ft.TextStyle(color=D_TXT, size=13), hint_text="Hasta",
        border_color=D_BOR, focused_border_color=OLA,
        bgcolor=D_PANEL, border_radius=6, content_padding=PAD(h=6, v=6),
    )
    playlist_box = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.PLAYLIST_PLAY, size=16, color=OLA),
            ft.Text("Playlist — rango:", size=12, color=D_MUT),
            r_ini, ft.Text("→", color=D_MUT), r_fin,
            ft.Text("(vacío = todos)", size=10, color=D_MUT),
        ], spacing=8),
        visible=False, bgcolor=D_CARD, border_radius=8,
        padding=PAD(h=14, v=10), border=BORDER(1, D_BOR),
    )

    # ─────────────────────────────────────────
    #  BOTONES
    # ─────────────────────────────────────────
    btn_carpeta = ft.OutlinedButton(
        content=ft.Text("ELEGIR", size=11, color=OLA, no_wrap=True,
                        style=ft.TextStyle(letter_spacing=1)),
        style=ft.ButtonStyle(
            side=ft.BorderSide(1, OLA),
            shape=ft.RoundedRectangleBorder(radius=6),
        ),
        on_click=on_pick_dir,
    )
    carpeta_row = ft.Row([
        ft.Icon(ft.Icons.FOLDER_OPEN, size=16, color=D_MUT),
        lbl_carpeta, btn_carpeta,
    ], spacing=8)

    # FIX: usa _FFMPEG_OK cacheado
    aviso_ff = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.WARNING_AMBER, size=14, color=SURFISTA),
            ft.Text("FFmpeg no detectado — HD y MP3 pueden fallar",
                    size=11, color=D_TXT),
        ], spacing=6),
        visible=not _FFMPEG_OK,
        bgcolor="#2A1A0A", border_radius=6,
        padding=PAD(h=12, v=6), border=BORDER(1, "#5A3A10"),
    )

    btn = ft.Button(
        content=btn_txt("DESCARGAR"),
        bgcolor=SURFISTA, style=btn_style(SURFISTA),
        height=52, expand=True,
    )

    btn_limpiar = ft.IconButton(
        icon=ft.Icons.CLOSE, icon_color=D_MUT,
        icon_size=18, tooltip="Limpiar",
    )

    # ─────────────────────────────────────────
    #  FUNCIONES DE CONTROL
    # ─────────────────────────────────────────
    def reset_ui(limpiar_url=False):
        listo[0] = False
        bajando[0] = False
        btn.disabled = False
        btn.content = btn_txt("DESCARGAR")
        btn.bgcolor = SURFISTA
        barra.value = 0
        barra.visible = False
        stats.visible = False
        lbl_pct.value = lbl_vel.value = lbl_eta.value = ""
        estado.value = ""
        estado.color = D_MUT
        if limpiar_url:
            url_field.value = ""
            info_titulo.value = ""
            info_dur.value = ""
            info_tam.value = ""
            info_box.visible = False
            playlist_box.visible = False
        page_update()

    def set_estado(msg, color=None):
        estado.value = msg
        if color:
            estado.color = color
        page_update()

    # ─────────────────────────────────────────
    #  PROGRESS HOOK
    # ─────────────────────────────────────────
    def hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            dl = d.get('downloaded_bytes', 0)
            vel = d.get('speed')
            eta = d.get('eta')
            if total and total > 0:
                pct = dl / total
                barra.value = pct
                lbl_pct.value = f"{pct*100:.1f}%"
            else:
                barra.value = None
                lbl_pct.value = "...%"
            lbl_vel.value = f"{fmt_bytes(vel)}/s" if vel else "---"
            lbl_eta.value = fmt_eta(eta)
            if main_loop and main_loop.is_running():
                asyncio.run_coroutine_threadsafe(_async_update(), main_loop)
        elif d['status'] == 'finished':
            if main_loop and main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    _async_set_estado("⚙ Procesando…", D_MUT), main_loop)
        elif d['status'] == 'error':
            if main_loop and main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    _async_set_estado("Error en fragmento", ERR), main_loop)

    async def _async_update():
        if not stats.visible:
            stats.visible = True
        page_update()

    async def _async_set_estado(msg, color):
        estado.value = msg
        if color:
            estado.color = color
        page_update()

    # ─────────────────────────────────────────
    #  OBTENER INFORMACIÓN DEL VIDEO
    # ─────────────────────────────────────────
    # FIX: obtener_info ya NO modifica widgets directamente.
    # Devuelve un dict con los datos; descarga_async actualiza la UI
    # desde el hilo correcto, eliminando la condición de carrera.
    def obtener_info(url: str, opts_base: dict) -> dict:
        opts = {**opts_base, 'quiet': True,
                'no_warnings': True, 'progress_hooks': [],
                'extract_flat': False}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                titulo = info.get('title', 'Sin título')
                dur = info.get('duration')
                entries = info.get('entries')
                if entries:
                    total = len(list(entries))
                    return {
                        'ok': True,
                        'es_playlist': True,
                        'titulo': f"Playlist: {titulo}",
                        'dur': f"{total} videos",
                        'tam': "",
                    }
                else:
                    tam = info.get('filesize') or info.get('filesize_approx')
                    ds = f"{dur//60}:{dur % 60:02d}" if dur else "--:--"
                    return {
                        'ok': True,
                        'es_playlist': False,
                        'titulo': titulo,
                        'dur': ds,
                        'tam': fmt_bytes(tam),
                    }
        except Exception as ex:
            return {'ok': False, 'error': str(ex)}

    # ─────────────────────────────────────────
    #  DESCARGA ASÍNCRONA
    # ─────────────────────────────────────────
    async def descarga_async():
        nonlocal main_loop
        main_loop = asyncio.get_running_loop()
        bajando[0] = True
        listo[0] = False
        btn.disabled = True
        btn.content = btn_txt("DESCARGANDO…")
        btn.bgcolor = MAREA
        barra.visible = True
        barra.value = 0
        stats.visible = True
        page_update()

        url_raw = (url_field.value or "").strip()
        if not url_raw:
            set_estado("Pega un enlace primero.", ERR)
            reset_ui()
            return

        url = normalizar_url(url_raw)
        dest = carpeta[0]
        os.makedirs(dest, exist_ok=True)

        m = modo[0]
        if m == "2":
            tag, fmt, post = "[WA]", "bestvideo[height<=480][vcodec^=avc]+bestaudio/best[height<=480]/best", []
        elif m == "3":
            tag, fmt, post = "[MP3]", "bestaudio/best", [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        else:
            tag, fmt, post = "[HD]", "bestvideo+bestaudio/best", []

        ydl_opts = {
            'format': fmt,
            'outtmpl': os.path.join(dest, f'%(title).60s {tag}.%(ext)s'),
            'nocheckcertificate': True,
            'merge_output_format': 'mp4',
            'progress_hooks': [hook],
            'postprocessors': post,
            'quiet': True,
            'no_warnings': False,
            'extractor_args': {
                'youtube': {'player_client': ['web', 'android'], 'player_skip': ['webpage', 'configs']},
                'facebook': {'rewrite_display_id': True},
            },
        }

        # FIX: usa _DIR_BASE en lugar de __file__ para funcionar correctamente
        # tanto en desarrollo como empaquetado con PyInstaller
        cookie_path = os.path.join(_DIR_BASE, "cookies.txt")
        if os.path.exists(cookie_path):
            ydl_opts['cookiefile'] = cookie_path

        set_estado("Obteniendo información…", D_MUT)

        # FIX: obtener_info ahora devuelve datos; la UI se actualiza aquí,
        # en el hilo del loop de asyncio, sin condición de carrera
        resultado = await main_loop.run_in_executor(None, obtener_info, url, ydl_opts)

        if not resultado['ok']:
            set_estado(f"Info no disponible: {resultado['error']}", D_MUT)
        else:
            es_playlist[0] = resultado['es_playlist']
            info_titulo.value = resultado['titulo']
            info_dur.value = resultado['dur']
            info_tam.value = resultado['tam']
            playlist_box.visible = resultado['es_playlist']
            info_box.visible = True
            page_update()

        if es_playlist[0]:
            ini = r_ini.value.strip()
            fin = r_fin.value.strip()
            if ini and fin:
                ydl_opts['playlist_items'] = f"{ini}-{fin}"
            elif ini:
                ydl_opts['playlist_items'] = f"{ini}-"

        try:
            set_estado(f"Descargando {tag}…", D_MUT)
            await main_loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
            barra.value = 1.0
            barra.color = OLA
            lbl_pct.value = "100%"
            lbl_vel.value = lbl_eta.value = ""
            estado.value = f"✓ Guardado en: {dest}"
            estado.color = OLA
            btn.content = btn_txt("✓ LISTO  —  clic para nueva descarga")
            btn.bgcolor = OLA
            btn.disabled = False
            listo[0] = True
        except Exception as ex:
            estado.value = f"✗ {ex}"
            estado.color = ERR
            btn.content = btn_txt("REINTENTAR")
            btn.bgcolor = ERR
            btn.disabled = False
            listo[0] = False
        finally:
            bajando[0] = False
            page_update()

    def on_descargar(e):
        if bajando[0]:
            return
        if listo[0]:
            reset_ui(limpiar_url=True)
            return
        asyncio.create_task(descarga_async())

    def on_limpiar(e):
        if not bajando[0]:
            reset_ui(limpiar_url=True)

    btn.on_click = on_descargar
    btn_limpiar.on_click = on_limpiar

    # ─────────────────────────────────────────
    #  SECCIONES UI
    # ─────────────────────────────────────────
    def sec(titulo, widget):
        return ft.Column([sec_label(titulo), widget], spacing=8)

    cuerpo = ft.Container(
        content=ft.Column([
            sec("ENLACE", ft.Row([url_field, btn_limpiar], spacing=8)),
            sec("FORMATO", pills_row),
            sec("DESTINO", carpeta_row),
            aviso_ff,
            info_box,
            playlist_box,
            ft.Divider(height=1, color=D_BOR),
            ft.Row([btn]),
            barra,
            stats,
            ft.Container(content=estado, alignment=ft.Alignment(0, 0)),
        ], spacing=16),
        padding=PAD(h=26, v=22),
        expand=True, bgcolor=D_BG,
    )

    # ─────────────────────────────────────────
    #  FOOTER CON REDES SOCIALES
    # ─────────────────────────────────────────
    REDES = [
        ("logo_instagram.png", "https://www.instagram.com/proyectooladigital/",
         "#E1306C", "Instagram"),
        ("logo_telegram.png", "https://t.me/ProyectoOlaDigital", "#2AABEE", "Telegram"),
        ("logo_tiktok.png", "https://www.tiktok.com/@proyectooladigita",
         "#69C9D0", "TikTok"),
        ("logo_facebook.png", "https://www.facebook.com/ProyectoOlaDigital/",
         "#1877F2", "Facebook"),
        ("logo_x.png", "https://x.com/Proy_oladigital", "#FFFFFF", "X"),
    ]

    def hacer_icono_red(logo, url, color, tip):
        ruta_icono = os.path.join(_DIR_BASE, "assets", logo)
        tam = 24 if logo == "logo_x.png" else 28
        return ft.Container(
            content=ft.Image(src=ruta_icono, width=tam,
                             height=tam, fit="contain"),
            padding=PAD_ALL(7),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.15, color),
            tooltip=tip,
            ink=True,
            url=url,
        )

    iconos_redes = ft.Row(
        [hacer_icono_red(*r) for r in REDES],
        spacing=6,
        alignment=ft.MainAxisAlignment.CENTER,
    )

    footer = ft.Container(
        content=iconos_redes,
        padding=PAD(h=26, v=10),
        border=BORDER_ONLY(top=ft.BorderSide(2, OLA)),
        bgcolor=D_SURF,
    )

    # ─────────────────────────────────────────
    #  ENSAMBLAR TODO
    # ─────────────────────────────────────────
    page.add(ft.Column([header, ft.Container(content=cuerpo, expand=True), footer],
                       expand=True, spacing=0))

    page_update()


# ─────────────────────────────────────────────
#  CONFIGURACIÓN PREVIA
# ─────────────────────────────────────────────
def before_main(page: ft.Page):
    page.window.width = 560
    page.window.height = 700
    page.window.min_width = 520
    page.window.min_height = 640
    page.window.bgcolor = "#0F1923"
    page.bgcolor = "#0F1923"
    page.title = "Descargador de Videos"
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL)
    page.theme_mode = ft.ThemeMode.DARK


if __name__ == "__main__":
    ft.run(main, before_main=before_main)
