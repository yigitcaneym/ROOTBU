from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

import customtkinter as ctk

from rootbu_logic import (
    STATUS_ERROR,
    STATUS_INFO,
    STATUS_OK,
    STATUS_WARN,
    build_action_state,
    build_install_plan,
    build_open_plan,
    build_prerequisite_plan,
    build_setup_guidance,
    clean_command_output_lines,
    collect_system_report,
    command_to_text,
    has_wsl_kernel_update_error,
    has_wsl_miniforge_directory_error,
    has_wsl_miniforge_preflight_error,
    has_wsl_restart_required_marker,
    has_wsl_virtualization_error,
    status_icon,
    windows_creation_flags,
    wsl_kernel_update_error_guidance,
    wsl_miniforge_directory_error_guidance,
    wsl_miniforge_preflight_error_guidance,
    wsl_restart_required_guidance,
    wsl_virtualization_error_guidance,
)

APP_FOOTER_TEXT = "ROOTBU — Created by Yiğitcan Koç © 2026"
ABOUT_TEXT = "\n".join(
    [
        "ROOTBU",
        "A beginner-friendly CERN ROOT installer.",
        "Created and maintained by Yiğitcan Koç with AI-assisted development.",
        "Copyright © 2026 Yiğitcan Koç.",
        "License: MIT License.",
    ]
)

# ---------------------------------------------------------------------------
# Beamline palette — derived from the ROOTBU logo (navy hull, azure beam).
# Gold is reserved for completion moments only.
# ---------------------------------------------------------------------------
VOID = "#04070e"
HULL = "#0a1120"
HULL2 = "#0d1628"
PANEL = "#101a2f"
CARD = "#0e1729"
LINE = "#22304d"
LINE2 = "#31446b"
INK = "#e9f0fc"
DIM = "#8ca3c8"
FAINT = "#5a6f93"
AZURE = "#3d8bff"
AZURE_DK = "#2f6fd0"
BEAM = "#7fb8ff"
FLARE = "#f6c34d"
FLARE_DK = "#c79a3a"
OK_COLOR = "#3ecf8e"
WARN_COLOR = "#f0a93b"
ERR_COLOR = "#f26d5e"
CTA_TEXT = "#06101f"

STAGE_SCAN, STAGE_WSL, STAGE_UBUNTU, STAGE_WSL2, STAGE_MINIFORGE, STAGE_ROOT, STAGE_LAUNCH = range(7)
STATION_LABELS = ["SCAN", "WSL", "UBUNTU", "WSL 2", "MINIFORGE", "ROOT", "LAUNCH"]
STAGE_COUNT = len(STATION_LABELS)


def resource_path(relative_path: str) -> str:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base_path / relative_path)


def set_window_icon(root: tk.Tk) -> None:
    try:
        if sys.platform.startswith("win"):
            icon_path = resource_path("assets/rootbu_icon.ico")
            if Path(icon_path).is_file():
                root.iconbitmap(icon_path)
            return

        icon_path = resource_path("assets/rootbu_icon.png")
        if Path(icon_path).is_file():
            image = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, image)
            root._rootbu_icon_image = image
    except Exception:
        return


def load_bundled_display_font() -> None:
    """Register the bundled Michroma face privately on Windows (no install)."""
    if not sys.platform.startswith("win"):
        return
    font_path = Path(resource_path("assets/fonts/Michroma-Regular.ttf"))
    if not font_path.is_file():
        return
    try:
        import ctypes

        FR_PRIVATE = 0x10
        ctypes.windll.gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0)
    except Exception:
        return


def pick_family(root: tk.Misc, wanted: list[str], fallback: str) -> str:
    try:
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    for name in wanted:
        if name in families:
            return name
    return fallback


def blend_hex(color_a: str, color_b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    a = tuple(int(color_a[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(color_b[i : i + 2], 16) for i in (1, 3, 5))
    mixed = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


STAGE_TEXT = {
    STAGE_SCAN: (
        "Sequence 01 · Diagnostics",
        "System scan",
        "ROOTBU inspects what is already installed and builds the installation sequence. "
        "Nothing is installed or changed in this step.",
    ),
    STAGE_WSL: (
        "Sequence 02 · Prerequisite",
        "Install WSL",
        "ROOT runs inside Linux. On Windows, ROOTBU uses the Windows Subsystem for Linux — "
        "nothing on your Windows side is changed.",
    ),
    STAGE_UBUNTU: (
        "Sequence 03 · Prerequisite",
        "Install Ubuntu",
        "WSL needs a Linux distribution. ROOTBU recommends Ubuntu — after install, Ubuntu asks "
        "you to create a Linux username and password.",
    ),
    STAGE_WSL2: (
        "Sequence 04 · Prerequisite",
        "Convert to WSL 2",
        "Conda requires WSL version 2. This converts the Ubuntu distribution in place — your "
        "files inside Ubuntu are kept.",
    ),
    STAGE_MINIFORGE: (
        "Sequence 05 · Prerequisite",
        "Install Miniforge",
        "Miniforge is a small, open-source conda. It installs into your home folder only — "
        "no sudo, no system changes.",
    ),
    STAGE_ROOT: (
        "Sequence 06 · Payload",
        "Install CERN ROOT",
        "ROOTBU creates its own conda environment — rootbu_root_env — and installs ROOT from "
        "conda-forge into it. Nothing else is touched.",
    ),
    STAGE_LAUNCH: (
        "Sequence 07 · Ignition",
        "Open ROOT",
        "Everything is installed. ROOTBU opens a terminal with the environment already "
        "activated — no commands to remember.",
    ),
}

STAGE_SAFETY = {
    STAGE_WSL: [
        "May require Administrator permission",
        "May require a Windows restart",
        "ROOT is not installed in this step",
    ],
    STAGE_UBUNTU: [
        "Ubuntu will ask you to create a Linux username",
        "May require a restart",
        "ROOT is not installed in this step",
    ],
    STAGE_WSL2: [
        "May show a UAC administrator prompt",
        "A Windows restart may be required",
        "Installs the official WSL 2 kernel if missing",
        "Your files inside the distribution are kept",
        "BIOS virtualization cannot be changed by ROOTBU",
    ],
    STAGE_MINIFORGE: [
        "No sudo",
        "Nothing is deleted",
        "Existing ~/miniforge3 is never overwritten",
        "conda init is not run automatically",
    ],
    STAGE_ROOT: [
        "Creates only the env rootbu_root_env",
        "Packages come from conda-forge only",
        "Your system Python is untouched",
    ],
}

STAGE_CTA = {
    STAGE_WSL: "Install WSL",
    STAGE_UBUNTU: "Install Ubuntu",
    STAGE_WSL2: "Convert to WSL 2",
    STAGE_MINIFORGE: "Install Miniforge",
}


def derive_stage(report, plan, action_state) -> int:
    if report is None:
        return STAGE_SCAN
    if plan is not None and plan.needed:
        summary = plan.summary_command or ""
        if summary == "wsl --install":
            return STAGE_WSL
        if summary == "wsl --install -d Ubuntu":
            return STAGE_UBUNTU
        if summary.startswith("wsl --set-version"):
            return STAGE_WSL2
        return STAGE_MINIFORGE
    if action_state.open_root_enabled and not action_state.install_root_enabled:
        return STAGE_LAUNCH
    if action_state.install_root_enabled:
        return STAGE_ROOT
    if action_state.install_prerequisites_enabled:
        return STAGE_MINIFORGE
    return STAGE_ROOT


class BeamlineRing(tk.Canvas):
    """Accelerator-ring progress instrument: seven stations, a beam arc that
    fills as stages complete, an orbiting particle, and a collision finale."""

    def __init__(self, master, display_family_name: str, mono_family_name: str, **kwargs) -> None:
        super().__init__(master, bg=HULL, highlightthickness=0, **kwargs)
        self.display_family = display_family_name
        self.mono_family = mono_family_name
        self.stage = 0
        self.station_states = ["active"] + ["pending"] * (STAGE_COUNT - 1)
        self.finale = False
        self.busy = False
        self.center_lines = ("01 / 07", "SCAN", "STANDING BY")
        self.particle_angle = 90.0
        self.pulse_phase = 0.0
        self.burst_frame = -1
        self.burst_rays: list[tuple[float, float, float]] = []
        self._animating = False
        self._suspend_deadline = 0.0
        self._anim_ids: dict | None = None
        self._label_font = None
        self._win_probe = None
        self._gui_probe = None
        self._last_window_pos: tuple[int, int] | None = None
        self.bind("<Configure>", lambda _e: self.redraw())

    # -- public API ---------------------------------------------------------
    def set_state(self, stage: int, station_states: list[str], busy: bool, finale: bool) -> None:
        self.stage = stage
        self.station_states = station_states
        self.busy = busy
        self.finale = finale
        self.redraw()

    def set_center(self, step: str, name: str, status: str) -> None:
        self.center_lines = (step, name, status)
        self.redraw()

    def start_animation(self) -> None:
        if not self._animating:
            self._animating = True
            self._tick()

    def suspend(self, milliseconds: int = 350) -> None:
        """Pause the animation briefly (e.g. while the window is dragged) so
        timer callbacks do not starve the native move/size loop."""
        self._suspend_deadline = time.monotonic() + milliseconds / 1000.0

    def start_burst(self) -> None:
        import random

        self.burst_frame = 0
        self.burst_rays = [
            (random.uniform(0, 360), random.uniform(0.45, 0.95), random.uniform(-26, 26))
            for _ in range(30)
        ]

    # -- geometry helpers ---------------------------------------------------
    def _geometry(self) -> tuple[float, float, float]:
        w = max(self.winfo_width(), 10)
        h = max(self.winfo_height(), 10)
        size = min(w, h)
        return w / 2, h / 2, size * 0.355

    def _station_angle(self, index: int) -> float:
        return 90.0 - index * (360.0 / STAGE_COUNT)

    def _point(self, cx: float, cy: float, radius: float, angle_deg: float) -> tuple[float, float]:
        rad = math.radians(angle_deg)
        return cx + radius * math.cos(rad), cy - radius * math.sin(rad)

    # -- drawing ------------------------------------------------------------
    def redraw(self) -> None:
        self.delete("static")
        cx, cy, radius = self._geometry()
        if radius < 40:
            return

        ring_color = blend_hex(HULL, BEAM, 0.14)
        self.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius,
            outline=ring_color, width=2, tags="static",
        )

        progress = STAGE_COUNT if self.finale else self.stage
        arc_color = FLARE if self.finale else AZURE
        arc_bright = FLARE if self.finale else BEAM
        if progress > 0:
            extent = -359.9 if progress >= STAGE_COUNT else -progress * (360.0 / STAGE_COUNT)
            glow = blend_hex(HULL, arc_color, 0.4)
            self.create_arc(
                cx - radius, cy - radius, cx + radius, cy + radius,
                start=90, extent=extent, style=tk.ARC,
                outline=glow, width=7, tags="static",
            )
            self.create_arc(
                cx - radius, cy - radius, cx + radius, cy + radius,
                start=90, extent=extent, style=tk.ARC,
                outline=arc_bright, width=2, tags="static",
            )

        label_radius = radius + max(16, radius * 0.12)
        if self._label_font is None:
            try:
                self._label_font = tkfont.Font(family=self.display_family, size=8)
            except Exception:
                self._label_font = False
        label_font = self._label_font or None
        canvas_width = max(self.winfo_width(), 10)
        for index, label in enumerate(STATION_LABELS):
            angle = self._station_angle(index)
            x, y = self._point(cx, cy, radius, angle)
            state = self.station_states[index] if index < len(self.station_states) else "pending"
            if self.finale:
                state = "done"

            if state == "done":
                fill = FLARE if self.finale else AZURE
                dot = 5
                text_color = FLARE if self.finale else BEAM
            elif state == "active":
                fill = INK
                dot = 6
                text_color = INK
            elif state == "attention":
                fill = WARN_COLOR
                dot = 5
                text_color = WARN_COLOR
            elif state == "skip":
                fill = blend_hex(HULL, FAINT, 0.5)
                dot = 3
                text_color = blend_hex(HULL, FAINT, 0.75)
            else:
                fill = blend_hex(HULL, FAINT, 0.7)
                dot = 3
                text_color = FAINT

            self.create_oval(x - dot, y - dot, x + dot, y + dot, fill=fill, outline="", tags="static")

            lx, ly = self._point(cx, cy, label_radius, angle)
            anchor = "center"
            text_width = label_font.measure(label) if label_font else len(label) * 7
            if lx < cx - radius * 0.5:
                anchor = "e"
                lx = max(lx, text_width + 4)
            elif lx > cx + radius * 0.5:
                anchor = "w"
                lx = min(lx, canvas_width - text_width - 4)
            else:
                lx = min(max(lx, text_width / 2 + 4), canvas_width - text_width / 2 - 4)
            self.create_text(
                lx, ly, text=label, fill=text_color, anchor=anchor,
                font=(self.display_family, 8), tags="static",
            )

        step, name, status = self.center_lines
        name_color = FLARE if self.finale else BEAM
        self.create_text(
            cx, cy - radius * 0.18, text=step, fill=INK,
            font=(self.display_family, max(15, int(radius * 0.16))), tags="static",
        )
        self.create_text(
            cx, cy + radius * 0.06, text=name, fill=name_color,
            font=(self.display_family, max(9, int(radius * 0.062))), tags="static",
        )
        self.create_text(
            cx, cy + radius * 0.24, text=status, fill=FAINT,
            font=(self.mono_family, max(7, int(radius * 0.048))), tags="static",
        )
        try:
            self.tag_raise("anim")
            self.tag_raise("burst")
        except tk.TclError:
            pass

    def _window_is_moving(self) -> bool:
        """Poll the native window position. During a drag Windows runs a
        modal move loop in which Tk may deliver no <Configure> events, but
        timers still fire — so the animation tick itself must detect motion.
        A plain GetWindowRect query is safe here (no callbacks, no Tcl)."""
        if not sys.platform.startswith("win"):
            return False
        try:
            import ctypes
            from ctypes import wintypes

            if self._win_probe is None:
                user32 = ctypes.windll.user32
                top = self.winfo_toplevel()
                hwnd = user32.GetParent(top.winfo_id()) or top.winfo_id()
                self._win_probe = (user32, hwnd, wintypes.RECT())
            user32, hwnd, rect = self._win_probe
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return False
            position = (rect.left, rect.top)
            if position != self._last_window_pos:
                moved = self._last_window_pos is not None
                self._last_window_pos = position
                return moved
            return False
        except Exception:
            return False

    def _in_native_move_loop(self) -> bool:
        """True while Windows runs its modal move/size loop for this thread
        (the whole time the title bar is held, even without motion). Uses
        GetGUIThreadInfo's GUI_INMOVESIZE flag — a plain query, no hooks."""
        if not sys.platform.startswith("win"):
            return False
        try:
            import ctypes
            from ctypes import wintypes

            if self._gui_probe is None:
                class GUITHREADINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("flags", wintypes.DWORD),
                        ("hwndActive", wintypes.HWND),
                        ("hwndFocus", wintypes.HWND),
                        ("hwndCapture", wintypes.HWND),
                        ("hwndMenuOwner", wintypes.HWND),
                        ("hwndMoveSize", wintypes.HWND),
                        ("hwndCaret", wintypes.HWND),
                        ("rcCaret", wintypes.RECT),
                    ]

                info = GUITHREADINFO()
                info.cbSize = ctypes.sizeof(GUITHREADINFO)
                thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
                self._gui_probe = (ctypes.windll.user32, thread_id, info)
            user32, thread_id, info = self._gui_probe
            if not user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
                return False
            GUI_INMOVESIZE = 0x0002
            return bool(info.flags & GUI_INMOVESIZE) or bool(info.hwndMoveSize)
        except Exception:
            return False

    def _tick(self) -> None:
        delay = 50
        try:
            if self._in_native_move_loop() or self._window_is_moving():
                self._suspend_deadline = time.monotonic() + 0.4
            if time.monotonic() < self._suspend_deadline:
                # window is being dragged (or was moments ago): draw nothing
                # and wake rarely so the move loop stays fully responsive
                delay = 150
            else:
                self._draw_anim_layer()
        except tk.TclError:
            self._animating = False
            return
        self.after(delay, self._tick)

    def _ensure_anim_items(self) -> dict:
        """Create the persistent animation items once; later frames only move
        them with coords()/itemconfigure(), which is far cheaper than
        delete-and-recreate and keeps window dragging responsive."""
        if self._anim_ids is not None:
            return self._anim_ids
        ids = {
            "trail": [
                self.create_oval(0, 0, 0, 0, fill=HULL, outline="",
                                 state="hidden", tags="anim")
                for _ in range(6)
            ],
            "p1": self.create_oval(0, 0, 0, 0, fill=BEAM, outline="",
                                   state="hidden", tags="anim"),
            "p2": self.create_oval(0, 0, 0, 0, fill=BEAM, outline="",
                                   state="hidden", tags="anim"),
            "halo": self.create_oval(0, 0, 0, 0, outline=BEAM, width=2,
                                     fill="", state="hidden", tags="anim"),
        }
        self._anim_ids = ids
        return ids

    def _draw_anim_layer(self) -> None:
        cx, cy, radius = self._geometry()
        if radius < 40:
            return
        ids = self._ensure_anim_items()

        # orbiting particle with a fading trail (reused items)
        speed = 5.6 if self.busy else 1.8
        self.particle_angle -= speed
        particle_color = FLARE if self.finale else BEAM
        for k in range(6, 0, -1):
            item = ids["trail"][k - 1]
            trail_angle = self.particle_angle + k * 3.4
            tx, ty = self._point(cx, cy, radius, trail_angle)
            trail_r = max(1, 3 - k * 0.4)
            trail_color = blend_hex(HULL, particle_color, max(0.12, 0.75 - k * 0.11))
            self.coords(item, tx - trail_r, ty - trail_r, tx + trail_r, ty + trail_r)
            self.itemconfigure(item, fill=trail_color, state="normal")
        px, py = self._point(cx, cy, radius, self.particle_angle)
        self.coords(ids["p1"], px - 3.4, py - 3.4, px + 3.4, py + 3.4)
        self.itemconfigure(ids["p1"], fill=particle_color, state="normal")
        if self.finale:
            qx, qy = self._point(cx, cy, radius, -self.particle_angle + 180)
            self.coords(ids["p2"], qx - 3.4, qy - 3.4, qx + 3.4, qy + 3.4)
            self.itemconfigure(ids["p2"], state="normal")
        else:
            self.itemconfigure(ids["p2"], state="hidden")

        # pulsing halo on the active station (reused item)
        if not self.finale:
            self.pulse_phase += 0.22
            halo = 8 + 2.6 * math.sin(self.pulse_phase)
            angle = self._station_angle(min(self.stage, STAGE_COUNT - 1))
            hx, hy = self._point(cx, cy, radius, angle)
            self.coords(ids["halo"], hx - halo, hy - halo, hx + halo, hy + halo)
            self.itemconfigure(ids["halo"], state="normal")
        else:
            self.itemconfigure(ids["halo"], state="hidden")

        # collision burst (short-lived, so delete/create is acceptable here)
        if self.burst_frame >= 0:
            self.delete("burst")
            frames = 26
            t = self.burst_frame / frames
            eased = 1 - (1 - t) ** 2.2
            for angle, length, bend in self.burst_rays:
                ray = radius * length * eased
                mid = ray * 0.55
                x1, y1 = cx, cy
                x2, y2 = self._point(cx, cy, mid, angle + bend * 0.4)
                x3, y3 = self._point(cx, cy, ray, angle + bend * 0.15)
                fade = max(0.0, 1.0 - t * 1.15)
                base = FLARE if (int(angle) % 3) else BEAM
                color = blend_hex(HULL, base, max(0.1, fade))
                self.create_line(x1, y1, x2, y2, x3, y3, smooth=True,
                                 fill=color, width=2, tags="burst")
            flash = max(0.0, 1.0 - t * 2.4)
            if flash > 0:
                fr = radius * 0.4 * (0.3 + t * 2)
                flash_color = blend_hex(HULL, "#ffffff", flash * 0.85)
                self.create_oval(cx - fr, cy - fr, cx + fr, cy + fr,
                                 outline=flash_color, width=3, tags="burst")
            self.burst_frame += 1
            if self.burst_frame > frames:
                self.burst_frame = -1
                self.delete("burst")
                self.redraw()


class PrerequisiteConfirmationDialog(ctk.CTkToplevel):
    def __init__(self, parent: "RootBUApp", plan, commands_text: str, platform_label: str) -> None:
        super().__init__(parent, fg_color=HULL)
        self.parent = parent
        self.commands_text = commands_text
        self.copy_text = plan.summary_command or commands_text
        if self.is_wsl_version_plan(plan) and plan.manual_commands:
            # the conversion is two commands (feature enable + set-version):
            # copying only the summary would lose the dism step
            self.copy_text = "\n".join(plan.manual_commands)
        self.result = False

        self.title("Install Missing Prerequisite")
        self.geometry("760x640")
        self.minsize(680, 560)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        title = ctk.CTkLabel(
            self,
            text=self.install_button_label(plan).upper(),
            font=parent.font_display_lg,
            text_color=INK,
            anchor="w",
        )
        title.grid(row=0, column=0, padx=24, pady=(22, 10), sticky="ew")

        summary = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12,
                               border_width=1, border_color=LINE)
        summary.grid(row=1, column=0, padx=24, pady=(0, 12), sticky="ew")
        summary.grid_columnconfigure(1, weight=1)
        for row_index, (label_text, value_text) in enumerate(self.summary_rows(plan, platform_label)):
            self._add_summary_row(summary, row_index, label_text, value_text)

        safety = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12,
                              border_width=1, border_color=LINE)
        safety.grid(row=2, column=0, padx=24, pady=(0, 12), sticky="ew")
        safety.grid_columnconfigure((0, 1), weight=1)
        safety_title = ctk.CTkLabel(
            safety,
            text="SAFETY",
            font=parent.font_display_xs,
            text_color=FAINT,
            anchor="w",
        )
        safety_title.grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 4), sticky="ew")
        safety_points = self.safety_points(plan)
        for index, point in enumerate(safety_points):
            label = ctk.CTkLabel(
                safety, text=f"✓ {point}", anchor="w", justify="left",
                text_color=DIM, font=parent.font_body_sm,
            )
            label.grid(row=1 + index // 2, column=index % 2, padx=16, pady=2, sticky="ew")

        preview = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12,
                               border_width=1, border_color=LINE)
        preview.grid(row=3, column=0, padx=24, pady=(0, 12), sticky="nsew")
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(1, weight=1)

        preview_label = ctk.CTkLabel(
            preview,
            text="COMMAND PREVIEW",
            font=parent.font_display_xs,
            text_color=FAINT,
            anchor="w",
        )
        preview_label.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="ew")

        command_box = ctk.CTkTextbox(
            preview,
            wrap="word",
            font=parent.font_mono,
            height=170,
            fg_color=VOID,
            text_color=BEAM,
            border_width=1,
            border_color=LINE,
        )
        command_box.grid(row=1, column=0, padx=16, pady=(4, 16), sticky="nsew")
        command_box.insert(tk.END, commands_text)
        command_box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, padx=24, pady=(0, 20), sticky="ew")
        footer.grid_columnconfigure(1, weight=1)

        self.status_label = ctk.CTkLabel(
            footer,
            text="",
            text_color=FAINT,
            font=parent.font_body_sm,
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, padx=(0, 12), sticky="ew")

        copy_button = ctk.CTkButton(
            footer,
            text="Copy Command" if self.is_single_windows_command_plan(plan) else "Copy Commands",
            width=140,
            fg_color="transparent",
            hover_color=HULL2,
            border_width=1,
            border_color=LINE2,
            text_color=DIM,
            command=self.copy_commands,
        )
        copy_button.grid(row=0, column=2, padx=(8, 0), sticky="e")

        cancel_button = ctk.CTkButton(
            footer,
            text="Cancel",
            width=110,
            fg_color="transparent",
            hover_color=HULL2,
            border_width=1,
            border_color=LINE2,
            text_color=DIM,
            command=self.cancel,
        )
        cancel_button.grid(row=0, column=3, padx=(8, 0), sticky="e")

        install_button = ctk.CTkButton(
            footer,
            text=self.install_button_label(plan),
            width=160,
            fg_color=AZURE,
            hover_color=BEAM,
            text_color=CTA_TEXT,
            font=parent.font_body_bold,
            command=self.confirm,
        )
        install_button.grid(row=0, column=4, padx=(8, 0), sticky="e")

        self.after(100, self.lift)
        self.after(120, self.focus_force)

    def is_wsl_plan(self, plan) -> bool:
        return plan.summary_command == "wsl --install"

    def is_wsl_distribution_plan(self, plan) -> bool:
        return plan.summary_command == "wsl --install -d Ubuntu"

    def is_wsl_version_plan(self, plan) -> bool:
        return plan.summary_command.startswith("wsl --set-version")

    def is_single_windows_command_plan(self, plan) -> bool:
        return self.is_wsl_plan(plan) or self.is_wsl_distribution_plan(plan)

    def install_button_label(self, plan) -> str:
        if self.is_wsl_plan(plan):
            return "Install WSL"
        if self.is_wsl_distribution_plan(plan):
            return "Install Ubuntu"
        if self.is_wsl_version_plan(plan):
            return "Convert to WSL 2"
        return "Install Miniforge"

    def summary_rows(self, plan, platform_label: str) -> list[tuple[str, str]]:
        if self.is_wsl_plan(plan):
            return [
                ("Missing prerequisite", "Windows Subsystem for Linux (WSL)"),
                ("Command", plan.summary_command),
                ("Platform", platform_label),
            ]
        if self.is_wsl_distribution_plan(plan):
            return [
                ("Missing prerequisite", "WSL Linux distribution"),
                ("Recommended distribution", "Ubuntu"),
                ("Command", plan.summary_command),
            ]
        if self.is_wsl_version_plan(plan):
            return [
                ("Missing prerequisite", "WSL 2 conversion"),
                ("Distribution", plan.install_location or "Ubuntu distribution"),
                ("Command", plan.summary_command),
            ]

        return [
            ("Missing prerequisite", "Conda / Miniforge"),
            ("Target location", plan.install_location or "~/miniforge3"),
            ("Platform", platform_label),
        ]

    def safety_points(self, plan) -> list[str]:
        if self.is_wsl_plan(plan):
            return [
                "This may require Administrator permission",
                "This may require a Windows restart",
                "ROOTBU will not install ROOT in this step",
                "After restart, open ROOTBU again and run a system scan",
            ]
        if self.is_wsl_version_plan(plan):
            return [
                "A UAC administrator prompt may appear",
                "A Windows restart may be required",
                "The official WSL 2 kernel from Microsoft is installed if missing",
                "Files inside the distribution are kept — nothing is deleted",
                "CPU virtualization in BIOS/UEFI cannot be enabled by ROOTBU",
                "ROOTBU will not install ROOT in this step",
            ]
        if self.is_wsl_distribution_plan(plan):
            return [
                "This may require a restart",
                "After installation, Ubuntu may open and ask you to create a Linux username/password",
                "Complete Ubuntu username/password setup before returning to ROOTBU",
                "ROOTBU will not install ROOT in this step",
                "After Ubuntu setup finishes, reopen ROOTBU and run a system scan",
            ]

        return [
            "No sudo",
            "No deletion",
            "No overwrite of existing ~/miniforge3",
            "ROOT will not be installed in this step",
            "conda init will not be run automatically",
        ]

    def _add_summary_row(self, parent: ctk.CTkFrame, row: int, label_text: str, value_text: str) -> None:
        label = ctk.CTkLabel(
            parent,
            text=label_text,
            text_color=FAINT,
            font=self.parent.font_body_sm,
            anchor="w",
        )
        label.grid(row=row, column=0, padx=(16, 12), pady=(10 if row == 0 else 4, 10 if row == 2 else 4), sticky="w")

        value = ctk.CTkLabel(
            parent,
            text=value_text,
            font=self.parent.font_mono,
            text_color=INK,
            anchor="w",
            justify="left",
        )
        value.grid(row=row, column=1, padx=(0, 16), pady=(10 if row == 0 else 4, 10 if row == 2 else 4), sticky="ew")

    def copy_commands(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.copy_text)
        self.status_label.configure(text="Commands copied.")

    def cancel(self) -> None:
        self.result = False
        self.destroy()

    def confirm(self) -> None:
        self.result = True
        self.destroy()


class RootBUApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__(fg_color=VOID)

        self.title("ROOTBU")
        set_window_icon(self)
        self.geometry("1120x750")
        self.minsize(1000, 660)

        self.is_busy = False
        self.current_report = None
        self.prerequisite_plan = None
        self.last_command_output = ""
        self.root_launched = False
        self.console_open = False
        self.log_line_count = 0

        display = pick_family(self, ["Michroma"], "Segoe UI" if sys.platform.startswith("win") else "Helvetica")
        mono = pick_family(
            self,
            ["Cascadia Mono", "Cascadia Code", "Consolas", "Menlo", "DejaVu Sans Mono"],
            "Courier",
        )
        self.display_family = display
        self.mono_family = mono

        self.font_display_lg = ctk.CTkFont(family=display, size=21)
        self.font_display_md = ctk.CTkFont(family=display, size=13)
        self.font_display_sm = ctk.CTkFont(family=display, size=10)
        self.font_display_xs = ctk.CTkFont(family=display, size=9)
        self.font_body = ctk.CTkFont(family="Segoe UI" if sys.platform.startswith("win") else "Helvetica", size=13)
        self.font_body_sm = ctk.CTkFont(family=self.font_body.cget("family"), size=12)
        self.font_body_bold = ctk.CTkFont(family=self.font_body.cget("family"), size=13, weight="bold")
        self.font_mono = ctk.CTkFont(family=mono, size=12)
        self.font_mono_sm = ctk.CTkFont(family=mono, size=11)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_deck()
        self._build_console()
        self._build_footer()

        self.log(STATUS_INFO, "Ready. Run a system scan before installing ROOT.")
        self.update_action_states()
        self.ring.start_animation()

        # Pause the ring animation while the window is being dragged or
        # resized: continuous timer redraws starve the native move loop on
        # Windows, which makes the window trail behind the cursor.
        self._window_position: tuple[int, int] | None = None
        self.bind("<Configure>", self._on_window_configure)

        # High-polling-rate mice flood the native title-bar move loop with
        # more messages than Tk windows can drain, which makes dragging
        # stutter in proportion to the widget count. The fix: drop the native
        # caption and drag via the app's own dark header at a throttled rate.
        self._drag_offset: tuple[int, int] | None = None
        self._last_manual_move = 0.0
        self._native_move_probe = None
        if self.uses_custom_titlebar():
            self.after(250, self._strip_native_caption)

    def _on_window_configure(self, event) -> None:
        if event.widget is not self:
            return
        position = (self.winfo_x(), self.winfo_y())
        if self._window_position is not None and position != self._window_position:
            self.ring.suspend(500)
        self._window_position = position

    # ------------------------------------------------- custom titlebar drag
    @staticmethod
    def uses_custom_titlebar() -> bool:
        return sys.platform.startswith("win") and os.environ.get("ROOTBU_NATIVE_TITLEBAR") != "1"

    def _strip_native_caption(self) -> None:
        """Remove the white Windows caption (WS_CAPTION) so the dark header
        acts as the title bar. The resizing frame, taskbar entry and
        Win+arrow snapping are kept."""
        try:
            import ctypes
            from ctypes import wintypes

            GWL_STYLE = -16
            WS_CAPTION = 0x00C00000
            SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            get_style = user32.GetWindowLongPtrW
            get_style.restype = ctypes.c_ssize_t
            get_style.argtypes = (wintypes.HWND, ctypes.c_int)
            set_style = user32.SetWindowLongPtrW
            set_style.restype = ctypes.c_ssize_t
            set_style.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)

            hwnd = user32.GetParent(self.winfo_id())
            if not hwnd:
                return
            style = get_style(hwnd, GWL_STYLE)
            set_style(hwnd, GWL_STYLE, style & ~WS_CAPTION)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        except Exception:
            return

    def _begin_window_drag(self, event) -> None:
        self._drag_offset = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_window(self, _event) -> None:
        if self._drag_offset is None:
            return
        now = time.monotonic()
        if now - self._last_manual_move < 1 / 90:  # cap the move rate
            return
        self._last_manual_move = now
        self.ring.suspend(250)
        offset_x, offset_y = self._drag_offset
        # use the live pointer position, not the event's coordinates: queued
        # motion events carry stale positions, which reads as glitchy jumps
        x = self.winfo_pointerx() - offset_x
        y = self.winfo_pointery() - offset_y
        if not self._move_window_native(x, y):
            self.geometry(f"+{x}+{y}")

    def _move_window_native(self, x: int, y: int) -> bool:
        """Move via SetWindowPos with SWP_NOCOPYBITS: stops Windows from
        blitting stale window pixels at each step, which otherwise smears
        ghost trails on slow or loaded machines."""
        if not sys.platform.startswith("win"):
            return False
        try:
            import ctypes

            if self._native_move_probe is None:
                user32 = ctypes.windll.user32
                hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
                self._native_move_probe = (user32, hwnd)
            user32, hwnd = self._native_move_probe
            SWP_FLAGS = 0x0001 | 0x0004 | 0x0010 | 0x0100  # NOSIZE|NOZORDER|NOACTIVATE|NOCOPYBITS
            return bool(user32.SetWindowPos(hwnd, 0, int(x), int(y), 0, 0, SWP_FLAGS))
        except Exception:
            return False

    def _end_window_drag(self, _event) -> None:
        self._drag_offset = None

    def _make_drag_surface(self, widget) -> None:
        widget.bind("<ButtonPress-1>", self._begin_window_drag)
        widget.bind("<B1-Motion>", self._drag_window)
        widget.bind("<ButtonRelease-1>", self._end_window_drag)

    # ------------------------------------------------------------------ UI
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=HULL2, corner_radius=0,
                              border_width=0, height=62)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(2, weight=1)

        self.logo_image = None
        try:
            logo_path = resource_path("assets/rootbu_icon.png")
            if Path(logo_path).is_file():
                raw = tk.PhotoImage(file=logo_path)
                factor = max(1, raw.width() // 34)
                self.logo_image = raw.subsample(factor, factor)
        except Exception:
            self.logo_image = None

        logo_label = None
        if self.logo_image is not None:
            logo_label = tk.Label(header, image=self.logo_image, bg=HULL2, bd=0)
            logo_label.grid(row=0, column=0, rowspan=2, padx=(18, 12), pady=8)

        name = ctk.CTkLabel(header, text="R O O T B U", font=self.font_display_md,
                            text_color=INK, anchor="w")
        name.grid(row=0, column=1, sticky="sw", pady=(10, 0))
        sub = ctk.CTkLabel(header, text="CERN ROOT · GUIDED INSTALL",
                           font=self.font_display_xs, text_color=FAINT, anchor="w")
        sub.grid(row=1, column=1, sticky="nw", pady=(0, 10))

        about_button = ctk.CTkButton(
            header, text="About", width=84, height=30,
            fg_color="transparent", hover_color=HULL,
            border_width=1, border_color=LINE2, text_color=DIM,
            command=self.show_about,
        )
        about_button.grid(row=0, column=3, rowspan=2, padx=(0, 10))

        if self.uses_custom_titlebar():
            minimize_button = ctk.CTkButton(
                header, text="─", width=38, height=30,
                fg_color="transparent", hover_color=HULL,
                border_width=1, border_color=LINE2, text_color=DIM,
                command=self.iconify,
            )
            minimize_button.grid(row=0, column=4, rowspan=2, padx=(0, 6))
            close_button = ctk.CTkButton(
                header, text="✕", width=38, height=30,
                fg_color="transparent", hover_color="#5c2430",
                border_width=1, border_color=LINE2, text_color=DIM,
                command=self.destroy,
            )
            close_button.grid(row=0, column=5, rowspan=2, padx=(0, 14))

        # the dark header is the window's drag handle (throttled manual move,
        # immune to high-polling-rate mouse message floods)
        for surface in (header, name, sub, logo_label):
            if surface is not None:
                self._make_drag_surface(surface)

        separator = ctk.CTkFrame(self, fg_color=LINE, height=1, corner_radius=0)
        separator.grid(row=0, column=0, sticky="sew")

    def _build_deck(self) -> None:
        deck = ctk.CTkFrame(self, fg_color=HULL, corner_radius=0)
        deck.grid(row=1, column=0, sticky="nsew")
        deck.grid_columnconfigure(0, weight=0, minsize=430)
        deck.grid_columnconfigure(2, weight=1)
        deck.grid_rowconfigure(0, weight=1)

        ring_side = ctk.CTkFrame(deck, fg_color=HULL, corner_radius=0)
        ring_side.grid(row=0, column=0, sticky="nsew")
        ring_side.grid_columnconfigure(0, weight=1)
        ring_side.grid_rowconfigure(0, weight=1)

        self.ring = BeamlineRing(ring_side, self.display_family, self.mono_family,
                                 width=420, height=460)
        self.ring.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        divider = ctk.CTkFrame(deck, fg_color=LINE, width=1, corner_radius=0)
        divider.grid(row=0, column=1, sticky="ns")

        self.stage_panel = ctk.CTkFrame(deck, fg_color=HULL, corner_radius=0)
        self.stage_panel.grid(row=0, column=2, sticky="nsew", padx=(28, 28), pady=(24, 16))
        self.stage_panel.grid_columnconfigure(0, weight=1)

    def _build_console(self) -> None:
        console = ctk.CTkFrame(self, fg_color=VOID, corner_radius=0,
                               border_width=0)
        console.grid(row=2, column=0, sticky="ew")
        console.grid_columnconfigure(0, weight=1)

        top_line = ctk.CTkFrame(console, fg_color=LINE, height=1, corner_radius=0)
        top_line.grid(row=0, column=0, sticky="ew")

        head = ctk.CTkFrame(console, fg_color="transparent")
        head.grid(row=1, column=0, sticky="ew")
        head.grid_columnconfigure(1, weight=1)

        self.console_toggle = ctk.CTkButton(
            head,
            text="▸  CONSOLE — FULL COMMAND TRANSPARENCY",
            fg_color="transparent",
            hover_color=HULL,
            text_color=FAINT,
            font=self.font_display_xs,
            anchor="w",
            command=self.toggle_console,
        )
        self.console_toggle.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=2)

        self.console_count = ctk.CTkLabel(head, text="0", font=self.font_mono_sm,
                                          text_color=FAINT)
        self.console_count.grid(row=0, column=2, padx=(0, 18))

        self.log_box = ctk.CTkTextbox(
            console,
            wrap="word",
            font=self.font_mono_sm,
            fg_color=VOID,
            text_color=DIM,
            height=128,
            border_width=0,
        )
        self.log_box.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.log_box.grid_remove()
        try:
            self.log_box.tag_config("lvl_ok", foreground=OK_COLOR)
            self.log_box.tag_config("lvl_warn", foreground=WARN_COLOR)
            self.log_box.tag_config("lvl_err", foreground=ERR_COLOR)
            self.log_box.tag_config("lvl_info", foreground=FAINT)
            self.log_box.tag_config("lvl_cmd", foreground=BEAM)
        except Exception:
            pass
        self.log_box.configure(state="disabled")

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color=VOID, corner_radius=0)
        footer.grid(row=3, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        footer_label = ctk.CTkLabel(
            footer,
            text=APP_FOOTER_TEXT,
            font=self.font_body_sm,
            text_color=FAINT,
            anchor="w",
        )
        footer_label.grid(row=0, column=0, sticky="ew", padx=18, pady=(2, 8))

    def toggle_console(self) -> None:
        self.set_console_open(not self.console_open)

    def set_console_open(self, open_console: bool) -> None:
        self.console_open = open_console
        if open_console:
            self.log_box.grid()
            self.console_toggle.configure(text="▾  CONSOLE — FULL COMMAND TRANSPARENCY")
        else:
            self.log_box.grid_remove()
            self.console_toggle.configure(text="▸  CONSOLE — FULL COMMAND TRANSPARENCY")

    # --------------------------------------------------------------- stage
    def _clear_stage_panel(self) -> None:
        for child in self.stage_panel.winfo_children():
            child.destroy()

    def _stage_header(self, stage: int) -> int:
        eyebrow_text, title_text, desc_text = STAGE_TEXT[stage]
        eyebrow = ctk.CTkLabel(self.stage_panel, text=eyebrow_text.upper(),
                               font=self.font_display_xs, text_color=AZURE, anchor="w")
        eyebrow.grid(row=0, column=0, sticky="ew")
        title = ctk.CTkLabel(self.stage_panel, text=title_text.upper(),
                             font=self.font_display_lg, text_color=INK, anchor="w")
        title.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        desc = ctk.CTkLabel(self.stage_panel, text=desc_text, font=self.font_body,
                            text_color=DIM, anchor="w", justify="left", wraplength=520)
        desc.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        return 3

    def _command_card(self, row: int, commands_text: str, safety: list[str] | None) -> int:
        card = ctk.CTkFrame(self.stage_panel, fg_color=PANEL, corner_radius=12,
                            border_width=1, border_color=LINE)
        card.grid(row=row, column=0, sticky="ew", pady=(18, 0))
        card.grid_columnconfigure(0, weight=1)

        card_title = ctk.CTkLabel(card, text="WHAT ROOTBU WILL RUN",
                                  font=self.font_display_xs, text_color=FAINT, anchor="w")
        card_title.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 4))

        lines = max(1, min(4, commands_text.count("\n") + 1))
        command_box = ctk.CTkTextbox(
            card, wrap="none", font=self.font_mono, fg_color=VOID,
            text_color=BEAM, height=26 * lines + 18,
            border_width=1, border_color=LINE,
        )
        command_box.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        command_box.insert(tk.END, commands_text)
        command_box.configure(state="disabled")

        if safety:
            chips = ctk.CTkFrame(card, fg_color="transparent")
            chips.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))
            chips.grid_columnconfigure((0, 1), weight=1)
            for index, point in enumerate(safety):
                chip = ctk.CTkLabel(
                    chips, text=f"✓ {point}", font=self.font_body_sm,
                    text_color=DIM, fg_color=HULL2, corner_radius=6,
                    anchor="w", padx=10, pady=3,
                )
                chip.grid(row=index // 2, column=index % 2, sticky="ew",
                          padx=(0, 8), pady=3)
        return row + 1

    def _button_row(self, row: int) -> ctk.CTkFrame:
        holder = ctk.CTkFrame(self.stage_panel, fg_color="transparent")
        holder.grid(row=row, column=0, sticky="ew", pady=(14, 0))
        return holder

    @staticmethod
    def _grid_buttons(buttons: list[ctk.CTkButton]) -> None:
        for index, button in enumerate(buttons):
            button.grid(row=0, column=index, padx=(0 if index == 0 else 10, 0))

    def _make_cta(self, parent, text: str, command, enabled: bool = True, gold: bool = False) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text.upper(),
            command=command,
            height=44,
            font=self.font_display_sm,
            fg_color=(FLARE if gold else AZURE),
            hover_color=(blend_hex(FLARE, "#ffffff", 0.18) if gold else BEAM),
            text_color=CTA_TEXT,
            corner_radius=8,
            state="normal" if enabled else "disabled",
        )

    def _make_secondary(self, parent, text: str, command) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=44,
            fg_color="transparent",
            hover_color=HULL2,
            border_width=1,
            border_color=LINE2,
            text_color=DIM,
            corner_radius=8,
        )

    def _busy_block(self, row: int) -> int:
        bar = ctk.CTkProgressBar(self.stage_panel, mode="indeterminate",
                                 progress_color=AZURE, fg_color=HULL2, height=4)
        bar.grid(row=row, column=0, sticky="ew", pady=(26, 0))
        bar.start()
        note = ctk.CTkLabel(
            self.stage_panel,
            text="EXECUTING — output streams to the console below.",
            font=self.font_mono_sm, text_color=FAINT, anchor="w",
        )
        note.grid(row=row + 1, column=0, sticky="ew", pady=(10, 0))
        return row + 2

    def render_stage(self) -> None:
        self._clear_stage_panel()
        stage = self.current_stage
        state = build_action_state(self.current_report)
        plan = self.prerequisite_plan
        row = self._stage_header(stage)

        if self.is_busy:
            self._busy_block(row)
            return

        if stage == STAGE_SCAN:
            if self.current_report is None:
                holder = self._button_row(row)
                self._grid_buttons([
                    self._make_cta(holder, "Initiate System Scan", self.check_system),
                ])
                hint = ctk.CTkLabel(self.stage_panel, text="read-only · takes a few seconds",
                                    font=self.font_mono_sm, text_color=FAINT, anchor="w")
                hint.grid(row=row + 1, column=0, sticky="ew", pady=(10, 0))
            else:
                row = self._checks_block(row)
                holder = self._button_row(row)
                self._grid_buttons([
                    self._make_secondary(holder, "↻  Re-scan", self.check_system),
                ])
            return

        if stage in (STAGE_WSL, STAGE_UBUNTU, STAGE_WSL2, STAGE_MINIFORGE):
            commands_text = ""
            if plan is not None:
                if plan.summary_command:
                    commands_text = plan.summary_command
                elif plan.manual_commands:
                    commands_text = "\n".join(plan.manual_commands)
                elif plan.steps:
                    commands_text = "\n".join(command_to_text(step.command) for step in plan.steps)
            if commands_text:
                note = commands_text
                if plan is not None and plan.steps and plan.summary_command:
                    note = commands_text + "\n# Full command is shown before you confirm."
                row = self._command_card(row, note, STAGE_SAFETY.get(stage))

            holder = self._button_row(row)
            buttons: list[ctk.CTkButton] = []
            if plan is not None and plan.needed and plan.can_run:
                buttons.append(self._make_cta(
                    holder, STAGE_CTA.get(stage, state.install_prerequisites_label),
                    self.install_prerequisites,
                    enabled=state.install_prerequisites_enabled,
                ))
            elif plan is not None and plan.needed:
                buttons.append(self._make_cta(
                    holder, state.install_prerequisites_label,
                    self.install_prerequisites,
                    enabled=state.install_prerequisites_enabled,
                ))
            else:
                buttons.append(ctk.CTkButton(
                    holder, text="Install Prerequisites",
                    command=self.install_prerequisites,
                    height=44, font=self.font_display_sm,
                    fg_color=AZURE, hover_color=BEAM, text_color=CTA_TEXT,
                    state="normal" if state.install_prerequisites_enabled else "disabled",
                ))
            if commands_text:
                copy_label = "Copy Command" if "\n" not in commands_text else "Copy Commands"
                buttons.append(self._make_secondary(
                    holder, copy_label,
                    lambda text=commands_text: self._copy_with_toast(text),
                ))
            buttons.append(self._make_secondary(holder, "↻", self.check_system))
            self._grid_buttons(buttons)
            return

        if stage == STAGE_ROOT:
            install_plan = build_install_plan(self.current_report) if self.current_report else None
            commands_text = ""
            if install_plan is not None and install_plan.has_commands:
                commands_text = "\n".join(command_to_text(command) for command in install_plan.commands)
            if commands_text:
                row = self._command_card(row, commands_text, STAGE_SAFETY.get(stage))
            holder = self._button_row(row)
            buttons = [self._make_cta(
                holder, state.install_root_label, self.install_root,
                enabled=state.install_root_enabled,
            )]
            if commands_text:
                buttons.append(self._make_secondary(
                    holder, "Copy Command",
                    lambda text=commands_text: self._copy_with_toast(text),
                ))
            buttons.append(self._make_secondary(holder, "↻", self.check_system))
            self._grid_buttons(buttons)
            return

        # STAGE_LAUNCH
        open_plan = build_open_plan(self.current_report) if self.current_report else None
        commands_text = ""
        if open_plan is not None:
            if open_plan.command is not None:
                commands_text = command_to_text(open_plan.command)
            elif open_plan.manual_command:
                commands_text = open_plan.manual_command
        if commands_text:
            row = self._command_card(row, commands_text, None)
        if self.root_launched:
            done = ctk.CTkLabel(
                self.stage_panel,
                text="✓ ROOT terminal launched — check your taskbar.",
                font=self.font_body_bold, text_color=FLARE, anchor="w",
            )
            done.grid(row=row, column=0, sticky="ew", pady=(16, 0))
            row += 1
        holder = self._button_row(row)
        self._grid_buttons([
            self._make_cta(
                holder, state.open_root_label, self.open_root,
                enabled=state.open_root_enabled, gold=True,
            ),
            self._make_secondary(holder, "↻", self.check_system),
        ])

    def _checks_block(self, row: int) -> int:
        card = ctk.CTkFrame(self.stage_panel, fg_color=PANEL, corner_radius=12,
                            border_width=1, border_color=LINE)
        card.grid(row=row, column=0, sticky="ew", pady=(18, 0))
        card.grid_columnconfigure(0, weight=1)
        badge_colors = {
            STATUS_OK: OK_COLOR,
            STATUS_WARN: WARN_COLOR,
            STATUS_ERROR: ERR_COLOR,
            STATUS_INFO: FAINT,
        }
        badge_labels = {
            STATUS_OK: "NOMINAL",
            STATUS_WARN: "MISSING",
            STATUS_ERROR: "ERROR",
            STATUS_INFO: "INFO",
        }
        for index, item in enumerate(self.current_report.checks):
            row_frame = ctk.CTkFrame(card, fg_color="transparent")
            row_frame.grid(row=index, column=0, sticky="ew", padx=14, pady=(8 if index == 0 else 2, 2))
            row_frame.grid_columnconfigure(1, weight=1)
            name = ctk.CTkLabel(row_frame, text=item.name, font=self.font_body_sm,
                                text_color=INK, anchor="w", width=170)
            name.grid(row=0, column=0, sticky="w")
            detail = ctk.CTkLabel(row_frame, text=item.detail, font=self.font_mono_sm,
                                  text_color=FAINT, anchor="w")
            detail.grid(row=0, column=1, sticky="ew", padx=(10, 10))
            badge = ctk.CTkLabel(
                row_frame, text=badge_labels.get(item.status, item.status.upper()),
                font=self.font_display_xs,
                text_color=badge_colors.get(item.status, FAINT),
                anchor="e",
            )
            badge.grid(row=0, column=2, sticky="e")
        spacer = ctk.CTkFrame(card, fg_color="transparent", height=8)
        spacer.grid(row=len(self.current_report.checks), column=0)
        return row + 1

    def _copy_with_toast(self, text: str) -> None:
        self.copy_text_to_clipboard(text)
        self.log(STATUS_OK, "Command copied to the clipboard.", decorate=True)

    # ------------------------------------------------------------ ring sync
    def _station_states(self, stage: int) -> list[str]:
        states = []
        for index in range(STAGE_COUNT):
            if index < stage:
                states.append("done")
            elif index == stage:
                states.append("active" if stage == STAGE_SCAN or not self._stage_needs_attention(stage) else "attention")
            else:
                states.append("pending")
        if self.current_report is not None and self.current_report.os_name != "Windows":
            for index in (STAGE_WSL, STAGE_UBUNTU, STAGE_WSL2):
                if index < stage:
                    states[index] = "skip"
        return states

    def _stage_needs_attention(self, stage: int) -> bool:
        return stage in (STAGE_WSL, STAGE_UBUNTU, STAGE_WSL2, STAGE_MINIFORGE)

    def _center_status(self, stage: int) -> str:
        if self.root_launched:
            return "env rootbu_root_env active"
        if self.is_busy:
            return "EXECUTING…"
        if stage == STAGE_SCAN:
            return "scan complete" if self.current_report is not None else "standing by"
        if stage == STAGE_LAUNCH:
            return "ready to launch"
        return "awaiting confirmation"

    def sync_ring(self) -> None:
        stage = self.current_stage
        finale = self.root_launched
        self.ring.set_state(stage, self._station_states(stage), self.is_busy, finale)
        if finale:
            self.ring.set_center("◈", "ROOT LIVE", self._center_status(stage))
        else:
            step = f"{stage + 1:02d} / {STAGE_COUNT:02d}"
            self.ring.set_center(step, STATION_LABELS[stage], self._center_status(stage))

    # ---------------------------------------------------------------- log
    def log(self, level: str, message: str, *, decorate: bool = False) -> None:
        self.after(0, self._append_log, level, message, decorate)

    def _append_log(self, level: str, message: str, decorate: bool = False) -> None:
        lines = clean_command_output_lines(message)
        if not lines:
            return

        icon = status_icon(level) if decorate else ""
        suffix = f" {icon}" if icon else ""
        tag = {
            STATUS_OK: "lvl_ok",
            STATUS_WARN: "lvl_warn",
            STATUS_ERROR: "lvl_err",
        }.get(level, "lvl_info")
        self.log_box.configure(state="normal")
        for line in lines:
            try:
                self.log_box.insert(tk.END, f"[{level}] {line}{suffix}\n", tag)
            except Exception:
                self.log_box.insert(tk.END, f"[{level}] {line}{suffix}\n")
            self.log_line_count += 1
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")
        self.console_count.configure(text=str(self.log_line_count))

    # ------------------------------------------------------------- actions
    def set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        if busy:
            self.set_console_open(True)
        self.update_action_states()

    def update_action_states(self) -> None:
        state = build_action_state(self.current_report)
        self.current_stage = derive_stage(self.current_report, self.prerequisite_plan, state)
        self.sync_ring()
        self.render_stage()

    def set_current_report(self, report) -> None:
        self.current_report = report
        self.prerequisite_plan = build_prerequisite_plan(report)
        self.update_action_states()

    def run_task(self, name: str, target) -> None:
        if self.is_busy:
            self.log(STATUS_WARN, "A task is already running.")
            return

        self.set_busy(True)
        self.log(STATUS_INFO, f"Starting: {name}")
        thread = threading.Thread(target=self._task_wrapper, args=(name, target), daemon=True)
        thread.start()

    def _task_wrapper(self, name: str, target) -> None:
        try:
            target()
        except Exception as exc:
            self.log(STATUS_ERROR, f"{name} failed: {exc}", decorate=True)
        finally:
            self.log(STATUS_INFO, f"Finished: {name}")
            self.after(0, self.set_busy, False)

    def check_system(self) -> None:
        self.run_task("System Scan", self._check_system_task)

    def install_root(self) -> None:
        self.run_task("Install ROOT", self._install_root_task)

    def open_root(self) -> None:
        self.run_task("Open ROOT", self._open_root_task)

    def install_prerequisites(self) -> None:
        self.run_task("Install Prerequisites", self._install_prerequisites_task)

    def _check_system_task(self):
        self.refresh_system_state()

    def refresh_system_state(self):
        report = collect_system_report()
        self._log_report(report)
        guidance = build_setup_guidance(report)
        self._log_guidance(guidance)
        self.after(0, self.set_current_report, report)
        return report

    def _install_prerequisites_task(self):
        report = self.refresh_system_state()
        plan = build_prerequisite_plan(report)
        self._log_prerequisite_plan(plan)

        if not plan.needed:
            self.log(STATUS_OK, "No missing prerequisites were detected.", decorate=True)
            return

        if not plan.can_run:
            message = self._prerequisite_confirmation_text(plan, manual=True)
            if plan.has_manual_commands:
                copy_commands = self.ask_yes_no(plan.title, message + "\n\nCopy the manual command(s) to the clipboard?")
                if copy_commands:
                    self.copy_text_to_clipboard("\n".join(plan.manual_commands))
                    self.log(STATUS_OK, "Manual prerequisite command(s) copied to the clipboard.", decorate=True)
            else:
                self.show_info(plan.title, message)
            return

        confirmed = self.ask_prerequisite_confirmation(plan)
        if not confirmed:
            self.log(STATUS_WARN, "Prerequisite installation cancelled before running commands.", decorate=True)
            return

        for step in plan.steps:
            self.log(STATUS_INFO, step.label)
            exit_code = self.stream_command(step.command)
            # dism exits with 3010 when the enabled feature needs a Windows
            # restart; the elevated path forwards the same code. Running the
            # remaining steps before that restart cannot succeed, so stop
            # here with explicit instructions instead of a cryptic failure.
            if exit_code == 3010 or has_wsl_restart_required_marker(self.last_command_output):
                self.log_wsl_restart_required()
                return
            if exit_code != 0:
                if has_wsl_kernel_update_error(self.last_command_output):
                    self.log_wsl_kernel_update_error()
                    return
                if has_wsl_virtualization_error(self.last_command_output):
                    self.log_wsl_virtualization_error()
                    return
                if has_wsl_miniforge_preflight_error(self.last_command_output):
                    self.log_wsl_miniforge_preflight_error(report)
                    return
                if has_wsl_miniforge_directory_error(self.last_command_output):
                    self.log_wsl_miniforge_directory_error()
                    return
                self.log(STATUS_ERROR, f"Command exited with code {exit_code}.", decorate=True)
                return

        if plan.summary_command == "wsl --install -d Ubuntu":
            self.verify_wsl_distribution_after_install()
            return

        self.log(STATUS_OK, "Finished prerequisite installation.", decorate=True)
        if plan.summary_command == "wsl --install":
            self.log(
                STATUS_INFO,
                "WSL installation may require a restart. Please restart Windows if prompted, then reopen ROOTBU and run a system scan.",
            )
        self.log(STATUS_INFO, "Refreshing the system scan after prerequisite installation.")
        self.refresh_system_state()

    def verify_wsl_distribution_after_install(self):
        self.log(STATUS_INFO, "Checking for installed WSL distributions after Ubuntu setup.")
        report = self.refresh_system_state()
        if report.wsl_distribution_available:
            self.log(STATUS_OK, "Ubuntu distribution was detected. Continue with the next prerequisite step.", decorate=True)
            return

        self.log(STATUS_WARN, "Ubuntu distribution installation has not completed yet.", decorate=True)
        self.log(
            STATUS_INFO,
            "Open Ubuntu from the Start menu or run `wsl -d Ubuntu`, finish the Linux username/password setup, then reopen ROOTBU and run a system scan.",
        )
        self.log(STATUS_INFO, "If Windows asked for a restart, restart Windows first.")

    def log_wsl_restart_required(self) -> None:
        messages = wsl_restart_required_guidance()
        for index, message in enumerate(messages):
            self.log(STATUS_WARN if index == 0 else STATUS_INFO, message, decorate=index == 0)
        self.show_info("Restart required", "\n\n".join(messages))

    def log_wsl_kernel_update_error(self) -> None:
        messages = wsl_kernel_update_error_guidance()
        for index, message in enumerate(messages):
            self.log(STATUS_ERROR if index == 0 else STATUS_INFO, message, decorate=index == 0)
        self.show_info("WSL 2 kernel update needed", "\n\n".join(messages))

    def log_wsl_virtualization_error(self) -> None:
        messages = wsl_virtualization_error_guidance()
        for index, message in enumerate(messages):
            self.log(STATUS_ERROR if index == 0 else STATUS_INFO, message, decorate=index == 0)
        self.show_info("Virtualization needed (BIOS/UEFI)", "\n\n".join(messages))

    def log_wsl_miniforge_directory_error(self) -> None:
        for index, message in enumerate(wsl_miniforge_directory_error_guidance()):
            self.log(STATUS_ERROR if index == 0 else STATUS_INFO, message, decorate=index == 0)

    def log_wsl_miniforge_preflight_error(self, report=None) -> None:
        distro = getattr(report, "wsl_distribution_name", "") or "Ubuntu"
        for index, message in enumerate(wsl_miniforge_preflight_error_guidance(distro)):
            self.log(STATUS_ERROR if index == 0 else STATUS_INFO, message, decorate=index == 0)

    def _install_root_task(self):
        report = collect_system_report()
        self._log_report(report)
        self.after(0, self.set_current_report, report)
        plan = build_install_plan(report)

        self.log(STATUS_INFO, f"Install context: {plan.context}")
        for message in plan.messages:
            self.log(STATUS_INFO, message)

        if not plan.has_commands:
            if report.os_name == "Windows":
                conda_missing = not report.wsl_conda_available
            else:
                conda_missing = report.native_conda is None
            if conda_missing:
                self.log(STATUS_WARN, "Install ROOT is disabled until conda is detected. Run a system scan or Install Prerequisites first.", decorate=True)
            else:
                self.log(STATUS_WARN, "No installation command will be run.", decorate=True)
            return

        self.log(STATUS_INFO, "Dry run: ROOTBU would run the following command.")
        for command in plan.commands:
            self.log(STATUS_INFO, f"$ {command_to_text(command)}")

        confirmed = self.ask_yes_no(
            "Confirm ROOT installation",
            "ROOTBU will run only the command shown in the log. Continue?",
        )
        if not confirmed:
            self.log(STATUS_WARN, "Installation cancelled before running commands.", decorate=True)
            return

        for command in plan.commands:
            exit_code = self.stream_command(command)
            if exit_code != 0:
                self.log(STATUS_ERROR, f"Command exited with code {exit_code}.", decorate=True)
                return

        self.log(STATUS_OK, "ROOT installation command finished successfully.", decorate=True)
        self.log(STATUS_INFO, "Refreshing the system scan after ROOT installation.")
        self.refresh_system_state()

    def _open_root_task(self):
        report = collect_system_report()
        self.after(0, self.set_current_report, report)
        plan = build_open_plan(report)

        self.log(STATUS_INFO, f"Open context: {plan.context}")
        for message in plan.messages:
            self.log(STATUS_INFO, message)

        if not plan.can_open or plan.command is None:
            if plan.manual_command:
                self.log(STATUS_WARN, "ROOTBU could not find a terminal launcher for this platform.", decorate=True)
                self.log(STATUS_INFO, f"Manual command: {plan.manual_command}")
                return
            self.log(STATUS_ERROR, "ROOT is not available. Run a system scan or Install ROOT first.", decorate=True)
            return

        if plan.manual_command:
            self.log(STATUS_INFO, f"Interactive ROOT command: {plan.manual_command}")
        self.log(STATUS_INFO, f"Launcher command: {command_to_text(plan.command)}")
        try:
            subprocess.Popen(
                plan.command,
                creationflags=windows_creation_flags(),
                start_new_session=True,
            )
        except OSError as exc:
            self.log(STATUS_ERROR, f"Could not open ROOT: {exc}", decorate=True)
            return

        self.log(STATUS_OK, "Interactive ROOT terminal launch command started.", decorate=True)
        self.after(0, self._on_root_launched)

    def _on_root_launched(self) -> None:
        self.root_launched = True
        self.ring.start_burst()
        self.update_action_states()

    def _log_report(self, report) -> None:
        self.log(STATUS_INFO, f"Detected OS: {report.platform_label}", decorate=True)
        for item in report.checks:
            self.log(item.status, f"{item.name}: {item.detail}", decorate=True)

    def _log_guidance(self, guidance) -> None:
        self.log(STATUS_INFO, guidance.title)
        for message in guidance.messages:
            self.log(STATUS_INFO, message)
        if guidance.commands:
            self.log(STATUS_INFO, "Suggested command(s):")
            for command in guidance.commands:
                self.log(STATUS_INFO, f"$ {command}")

    def _log_prerequisite_plan(self, plan) -> None:
        self.log(STATUS_INFO, plan.title)
        for message in plan.messages:
            self.log(STATUS_INFO, message)
        if plan.manual_commands and not plan.can_run:
            self.log(STATUS_INFO, "Manual command(s):")
            for command in plan.manual_commands:
                self.log(STATUS_INFO, f"$ {command}")
        if plan.can_run:
            self.log(STATUS_INFO, "Prerequisite command(s) ROOTBU will run after confirmation:")
            for step in plan.steps:
                self.log(STATUS_INFO, f"{step.label} {command_to_text(step.command)}")

    def _prerequisite_confirmation_text(self, plan, manual: bool = False) -> str:
        lines = [
            f"Prerequisite: {plan.install_name or plan.title}",
            f"Where: {plan.install_location or plan.context}",
        ]
        if plan.download_url:
            lines.append(f"Download: {plan.download_url}")
        lines.extend(
            [
                "",
                "Safety:",
                "- ROOTBU will not use sudo.",
                "- ROOTBU will not remove anything.",
                "- ROOTBU will not overwrite an existing conda installation.",
                "- ROOTBU will not install ROOT in this step.",
                "- ROOTBU will not run conda init automatically.",
            ]
        )
        if manual:
            lines.append("")
            lines.append("ROOTBU will not run this system-level prerequisite automatically.")
            if plan.manual_commands:
                lines.append("Manual command(s):")
                lines.extend(f"$ {command}" for command in plan.manual_commands)
            return "\n".join(lines)

        lines.append("")
        lines.append("ROOTBU will run these command(s):")
        for step in plan.steps:
            lines.append(f"$ {command_to_text(step.command)}")
        lines.append("")
        lines.append("Continue?")
        return "\n".join(lines)

    def prerequisite_commands_text(self, plan) -> str:
        return "\n".join(command_to_text(step.command) for step in plan.steps)

    def prerequisite_platform_label(self, plan) -> str:
        if plan.context == "Windows / WSL":
            if plan.summary_command == "wsl --install":
                return "Windows"
            if plan.summary_command == "wsl --install -d Ubuntu":
                return "Windows / WSL"
            return "WSL"
        if plan.context == "Linux":
            return "Linux"
        if plan.context == "macOS":
            if "MacOSX-arm64" in plan.download_url:
                return "macOS Apple Silicon"
            if "MacOSX-x86_64" in plan.download_url:
                return "macOS Intel"
            return "macOS"
        return plan.context

    def ask_prerequisite_confirmation(self, plan) -> bool:
        done = threading.Event()
        answer = {"value": False}

        def ask() -> None:
            dialog = PrerequisiteConfirmationDialog(
                self,
                plan,
                self.prerequisite_commands_text(plan),
                self.prerequisite_platform_label(plan),
            )

            def finish() -> None:
                answer["value"] = bool(dialog.result)
                done.set()

            dialog.bind("<Destroy>", lambda event: finish() if event.widget is dialog and not done.is_set() else None)

        self.after(0, ask)
        done.wait()
        return answer["value"]

    def ask_yes_no(self, title: str, message: str) -> bool:
        done = threading.Event()
        answer = {"value": False}

        def ask() -> None:
            answer["value"] = bool(messagebox.askyesno(title, message, parent=self))
            done.set()

        self.after(0, ask)
        done.wait()
        return answer["value"]

    def show_info(self, title: str, message: str) -> None:
        done = threading.Event()

        def show() -> None:
            messagebox.showinfo(title, message, parent=self)
            done.set()

        self.after(0, show)
        done.wait()

    def show_about(self) -> None:
        messagebox.showinfo("About ROOTBU", ABOUT_TEXT, parent=self)

    def copy_text_to_clipboard(self, text: str) -> None:
        if threading.current_thread() is threading.main_thread():
            # Called from a button handler on the Tk main thread: copy
            # directly. Blocking on done.wait() here would deadlock the
            # event loop, because the scheduled callback could never run.
            self.clipboard_clear()
            self.clipboard_append(text)
            return

        done = threading.Event()

        def copy() -> None:
            self.clipboard_clear()
            self.clipboard_append(text)
            done.set()

        self.after(0, copy)
        done.wait()

    def stream_command(self, command: list[str]) -> int:
        self.log(STATUS_INFO, f"Running: {command_to_text(command)}")
        output_lines: list[str] = []
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=windows_creation_flags(),
        )

        if process.stdout:
            for line in process.stdout:
                # wsl.exe emits UTF-16 messages; decoded as UTF-8 they carry a
                # NUL between every character, which breaks substring-based
                # error detection and clutters the console.
                clean = line.replace("\x00", "").rstrip()
                if clean:
                    output_lines.append(clean)
                    self.log(STATUS_INFO, clean, decorate=False)

        exit_code = process.wait()
        self.last_command_output = "\n".join(output_lines)
        return exit_code


def main() -> None:
    load_bundled_display_font()
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = RootBUApp()
    app.mainloop()


if __name__ == "__main__":
    main()
