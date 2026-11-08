#!/usr/bin/env python3
"""
RAR BruteForce - Minecraft Style
----------------------------------
Ein kleines GUI-Tool, um das Passwort einer EIGENEN RAR-Datei per
Brute-Force wiederzufinden. Nutzt dein installiertes WinRAR
(UnRAR.exe), es muss nichts zusaetzlich installiert werden.

WICHTIG: Nur fuer eigene Dateien verwenden, bei denen du das
Passwort vergessen hast / zu denen du berechtigt bist!

Start: einfach doppelklicken oder "python rar_bruteforce.py"
(Python 3 muss installiert sein - hast du laut deiner Angabe schon.)
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import itertools
import string
import os
import time
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

CHUNK_SIZE = 60  # Passwoerter pro Haeppchen, das an einen Prozess geht

# ---------- Minecraft-Style Farben ----------
BG_DARK = "#1b1b1b"
BG_PANEL = "#2b2b2b"
GREEN = "#5fba45"
GREEN_DARK = "#3e7a2d"
BROWN = "#7a5230"
BROWN_DARK = "#4e341f"
TEXT_LIGHT = "#f5f5f5"
TEXT_GRAY = "#aaaaaa"
RED = "#c84b3f"

FONT_TITLE = ("Courier New", 20, "bold")
FONT_NORMAL = ("Courier New", 11)
FONT_SMALL = ("Courier New", 9)


def find_unrar():
    """Sucht UnRAR.exe an typischen WinRAR-Installationsorten."""
    candidates = [
        r"C:\Program Files\WinRAR\UnRAR.exe",
        r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
        r"C:\Program Files\WinRAR\Rar.exe",
        r"C:\Program Files (x86)\WinRAR\Rar.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def test_password(unrar_path, rar_path, password):
    """Testet ein Passwort gegen die RAR-Datei. Gibt True zurueck, wenn es passt."""
    try:
        result = subprocess.run(
            [unrar_path, "t", f"-p{password}", rar_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def build_charset(use_digits, use_lower, use_upper, use_special):
    charset = ""
    if use_digits:
        charset += string.digits
    if use_lower:
        charset += string.ascii_lowercase
    if use_upper:
        charset += string.ascii_uppercase
    if use_special:
        charset += "!@#$%^&*()-_=+"
    return charset


def test_chunk(unrar_path, rar_path, chunk):
    """Laeuft in einem eigenen Prozess: testet eine Liste von Passwoertern.
    Gibt (gefundenes_passwort_oder_None, anzahl_getestet) zurueck."""
    for pw in chunk:
        if test_password(unrar_path, rar_path, pw):
            return pw, chunk.index(pw) + 1
    return None, len(chunk)


def chunked(iterable, size):
    it = iter(iterable)
    while True:
        batch = list(itertools.islice(it, size))
        if not batch:
            return
        yield batch


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RAR BruteForce")
        self.configure(bg=BG_DARK)
        self.geometry("560x620")
        self.resizable(False, False)

        self.rar_path = None
        self.unrar_path = find_unrar()
        self.stop_flag = False
        self.running = False

        self._build_ui()

        if not self.unrar_path:
            self._log("⚠ WinRAR/UnRAR.exe wurde nicht automatisch gefunden.", RED)
            self._log("  Bitte Pfad manuell waehlen (Knopf unten).", TEXT_GRAY)

    # ---------- UI ----------
    def _build_ui(self):
        title = tk.Label(
            self, text="⛏ RAR BRUTEFORCE ⛏",
            font=FONT_TITLE, bg=BG_DARK, fg=GREEN,
        )
        title.pack(pady=(18, 4))

        subtitle = tk.Label(
            self, text="nur fuer eigene Dateien benutzen!",
            font=FONT_SMALL, bg=BG_DARK, fg=TEXT_GRAY,
        )
        subtitle.pack(pady=(0, 14))

        # Datei waehlen
        file_frame = tk.Frame(self, bg=BG_PANEL, bd=2, relief="ridge")
        file_frame.pack(fill="x", padx=20, pady=6)

        self.file_label = tk.Label(
            file_frame, text="Keine Datei gewaehlt",
            font=FONT_NORMAL, bg=BG_PANEL, fg=TEXT_LIGHT, anchor="w"
        )
        self.file_label.pack(side="left", padx=10, pady=10, fill="x", expand=True)

        choose_btn = self._mc_button(file_frame, "Datei waehlen (.rar)", self.choose_file, GREEN, GREEN_DARK)
        choose_btn.pack(side="right", padx=10, pady=8)

        # UnRAR Pfad (falls nicht gefunden)
        unrar_frame = tk.Frame(self, bg=BG_DARK)
        unrar_frame.pack(fill="x", padx=20, pady=2)
        unrar_btn = self._mc_button(unrar_frame, "WinRAR-Pfad manuell waehlen", self.choose_unrar, BROWN, BROWN_DARK)
        unrar_btn.pack(side="left")

        # Zeichenarten
        opt_frame = tk.LabelFrame(
            self, text="Zeichenarten", font=FONT_NORMAL,
            bg=BG_PANEL, fg=TEXT_LIGHT, bd=2, relief="ridge"
        )
        opt_frame.pack(fill="x", padx=20, pady=10)

        self.var_digits = tk.BooleanVar(value=True)
        self.var_lower = tk.BooleanVar(value=False)
        self.var_upper = tk.BooleanVar(value=False)
        self.var_special = tk.BooleanVar(value=False)

        for text, var in [
            ("Nur Zahlen (0-9)", self.var_digits),
            ("Kleinbuchstaben (a-z)", self.var_lower),
            ("Grossbuchstaben (A-Z)", self.var_upper),
            ("Sonderzeichen (!@#...)", self.var_special),
        ]:
            cb = tk.Checkbutton(
                opt_frame, text=text, variable=var,
                font=FONT_NORMAL, bg=BG_PANEL, fg=TEXT_LIGHT,
                selectcolor=BG_DARK, activebackground=BG_PANEL,
                activeforeground=GREEN, anchor="w",
            )
            cb.pack(fill="x", padx=10, pady=2)

        # Laenge
        len_frame = tk.LabelFrame(
            self, text="Passwortlaenge", font=FONT_NORMAL,
            bg=BG_PANEL, fg=TEXT_LIGHT, bd=2, relief="ridge"
        )
        len_frame.pack(fill="x", padx=20, pady=6)

        inner = tk.Frame(len_frame, bg=BG_PANEL)
        inner.pack(pady=8)

        tk.Label(inner, text="von", font=FONT_NORMAL, bg=BG_PANEL, fg=TEXT_LIGHT).grid(row=0, column=0, padx=4)
        self.min_len = tk.Spinbox(inner, from_=1, to=12, width=4, font=FONT_NORMAL)
        self.min_len.delete(0, "end")
        self.min_len.insert(0, "4")
        self.min_len.grid(row=0, column=1, padx=4)

        tk.Label(inner, text="bis", font=FONT_NORMAL, bg=BG_PANEL, fg=TEXT_LIGHT).grid(row=0, column=2, padx=4)
        self.max_len = tk.Spinbox(inner, from_=1, to=12, width=4, font=FONT_NORMAL)
        self.max_len.delete(0, "end")
        self.max_len.insert(0, "4")
        self.max_len.grid(row=0, column=3, padx=4)

        # Buttons
        btn_frame = tk.Frame(self, bg=BG_DARK)
        btn_frame.pack(pady=14)

        self.start_btn = self._mc_button(btn_frame, "▶ BRUTE FORCE", self.start, GREEN, GREEN_DARK, big=True)
        self.start_btn.pack(side="left", padx=8)

        self.stop_btn = self._mc_button(btn_frame, "■ STOP", self.stop, RED, "#8a2f27", big=True)
        self.stop_btn.pack(side="left", padx=8)

        close_btn = self._mc_button(btn_frame, "✕ SCHLIESSEN", self.destroy, BROWN, BROWN_DARK, big=True)
        close_btn.pack(side="left", padx=8)

        # Status / Log
        self.status_label = tk.Label(
            self, text="Bereit.", font=FONT_NORMAL, bg=BG_DARK, fg=TEXT_LIGHT
        )
        self.status_label.pack(pady=(4, 2))

        self.log_box = tk.Text(
            self, height=8, width=62, font=FONT_SMALL,
            bg="#111111", fg=GREEN, bd=2, relief="sunken"
        )
        self.log_box.pack(padx=20, pady=6)
        self.log_box.configure(state="disabled")

    def _mc_button(self, parent, text, command, color, color_dark, big=False):
        btn = tk.Button(
            parent, text=text, command=command,
            font=("Courier New", 12 if big else 10, "bold"),
            bg=color, fg="white", activebackground=color_dark,
            activeforeground="white", relief="raised", bd=4,
            padx=10, pady=6 if big else 4, cursor="hand2",
        )
        return btn

    # ---------- Logik ----------
    def _log(self, text, color=None):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        if color:
            pass  # einfache Variante ohne Farb-Tags pro Zeile
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="RAR-Datei waehlen",
            filetypes=[("RAR-Dateien", "*.rar"), ("Alle Dateien", "*.*")],
        )
        if path:
            self.rar_path = path
            self.file_label.config(text=os.path.basename(path))
            self._log(f"Datei gewaehlt: {path}")

    def choose_unrar(self):
        path = filedialog.askopenfilename(
            title="UnRAR.exe oder Rar.exe waehlen",
            filetypes=[("EXE-Dateien", "*.exe")],
        )
        if path:
            self.unrar_path = path
            self._log(f"WinRAR-Pfad gesetzt: {path}")

    def start(self):
        if self.running:
            return
        if not self.rar_path:
            messagebox.showwarning("Fehlt", "Bitte zuerst eine .rar-Datei waehlen.")
            return
        if not self.unrar_path or not os.path.isfile(self.unrar_path):
            messagebox.showwarning("Fehlt", "UnRAR.exe/Rar.exe wurde nicht gefunden. Bitte manuell waehlen.")
            return

        charset = build_charset(
            self.var_digits.get(), self.var_lower.get(),
            self.var_upper.get(), self.var_special.get()
        )
        if not charset:
            messagebox.showwarning("Fehlt", "Bitte mindestens eine Zeichenart auswaehlen.")
            return

        try:
            min_l = int(self.min_len.get())
            max_l = int(self.max_len.get())
        except ValueError:
            messagebox.showwarning("Fehler", "Ungueltige Laengenangabe.")
            return
        if min_l < 1 or max_l < min_l:
            messagebox.showwarning("Fehler", "Laengenbereich ist ungueltig.")
            return

        total = sum(len(charset) ** n for n in range(min_l, max_l + 1))
        self._log(f"Starte... Zeichensatz: {len(charset)} Zeichen, Laenge {min_l}-{max_l}")
        self._log(f"Maximal zu testende Kombinationen: {total:,}".replace(",", "."))

        self.stop_flag = False
        self.running = True
        thread = threading.Thread(target=self._run_bruteforce, args=(charset, min_l, max_l, total), daemon=True)
        thread.start()

    def stop(self):
        self.stop_flag = True
        self._log("Stop angefordert...")

    def _run_bruteforce(self, charset, min_l, max_l, total):
        tested = 0
        start_time = time.time()
        found = None

        workers = max(1, os.cpu_count() or 1)
        self._log(f"Nutze {workers} CPU-Kerne parallel...")

        def all_candidates():
            for length in range(min_l, max_l + 1):
                for combo in itertools.product(charset, repeat=length):
                    yield "".join(combo)

        try:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                pending = {}
                gen = chunked(all_candidates(), CHUNK_SIZE)

                # Pipeline fuellen: pro Worker ein paar Haeppchen vorab einreichen
                for _ in range(workers * 2):
                    try:
                        chunk = next(gen)
                    except StopIteration:
                        break
                    fut = executor.submit(test_chunk, self.unrar_path, self.rar_path, chunk)
                    pending[fut] = chunk

                while pending and not found and not self.stop_flag:
                    done_fut = next(as_completed(pending))
                    chunk = pending.pop(done_fut)
                    pw, count = done_fut.result()
                    tested += count

                    if pw:
                        found = pw
                        break

                    elapsed = max(time.time() - start_time, 0.001)
                    speed = tested / elapsed
                    pct = (tested / total * 100) if total else 0
                    self.status_label.config(
                        text=f"{tested:,}/{total:,} ({pct:.2f}%)  |  {speed:.0f}/s  |  {workers} Kerne".replace(",", ".")
                    )

                    if not self.stop_flag:
                        try:
                            next_chunk = next(gen)
                            new_fut = executor.submit(test_chunk, self.unrar_path, self.rar_path, next_chunk)
                            pending[new_fut] = next_chunk
                        except StopIteration:
                            pass

                if found or self.stop_flag:
                    for f in pending:
                        f.cancel()
        except Exception as e:
            self._log(f"Fehler: {e}")

        elapsed = max(time.time() - start_time, 0.001)
        speed = tested / elapsed
        self.running = False

        if found:
            self.status_label.config(text=f"✔ GEFUNDEN: {found}")
            self._log(f"✔ PASSWORT GEFUNDEN: {found}")
            self._log(f"  Getestet: {tested:,}  |  Dauer: {elapsed:.1f}s  |  Speed: {speed:.0f}/s".replace(",", "."))
            messagebox.showinfo("Gefunden!", f"Passwort gefunden:\n\n{found}")
        elif self.stop_flag:
            self.status_label.config(text="Gestoppt.")
            self._log(f"Gestoppt nach {tested:,} Versuchen.".replace(",", "."))
        else:
            self.status_label.config(text="Nicht gefunden (Bereich erschoepft).")
            self._log(f"Kein Passwort im gewaehlten Bereich gefunden. Getestet: {tested:,}".replace(",", "."))
            messagebox.showinfo("Fertig", "Kein Passwort im gewaehlten Bereich gefunden.")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()  # wichtig fuer Windows + ProcessPoolExecutor
    if sys.platform != "win32":
        print("Hinweis: Dieses Tool ist fuer Windows gedacht (nutzt WinRAR/UnRAR.exe).")
    app = App()
    app.mainloop()
