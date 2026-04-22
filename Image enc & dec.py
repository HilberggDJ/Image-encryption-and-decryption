"""
Projekt M-II: Chaotyczne przekształcanie obrazu cyfrowego
COMMIT 2 – Naprawione algorytmy + panel metryk

Zmiany względem commit 1:
  - Etap 2: prawdziwa permutacja zig-zag z przeskokami sterowanymi kluczem
    (zamiast placeholder Fisher-Yates na pikselach)
  - Etap 1: poprawiony edge-case gdy height == 1
  - Metryki: korelacja Pearsona sasiadow + MSE + PSNR
  - Panel metryk w GUI (wyswietla wyniki po kazdej operacji)
  - Obsluga obrazow z kanalem alpha (konwersja do RGB)
  - Poprawiona kolejnosc operacji w etap3_unscramble (blad logiczny w v1)
  - Status bar pokazuje czas operacji
  - Testy jednostkowe: python main.py --test
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import os
import time


# ══════════════════════════════════════════════════════════════
#  ALGORYTMY
# ══════════════════════════════════════════════════════════════

class ImageProcessor:
    """
    Trzy etapy scramblingu obrazu.

    Kazdy etap eksponuje pare metod:
        etapN_scramble(arr, key)   -> arr
        etapN_unscramble(arr, key) -> arr

    Algorytm odwrotny korzysta TYLKO z obrazu wynikowego i klucza.
    """

    # ──────────────────────────────────────────────────────────
    # ETAP 1: Naiwny scrambling – cykliczne przesuwanie kolumn
    # ──────────────────────────────────────────────────────────
    #
    # Dla kazdej kolumny c:
    #   offset(c) = (key + c) % height
    #   np.roll przesuwa piksele cyklicznie o +offset (scramble)
    #   i -offset (unscramble).
    #
    # Slabos: poziome struktury obrazu przetrwaja (wartosci
    # pikseli sa niezmienione, zmienia sie tylko ich pozycja
    # wertykalna w obrebie kolumny).

    @staticmethod
    def etap1_scramble(img: np.ndarray, key: int) -> np.ndarray:
        h, w = img.shape[:2]
        if h <= 1:
            return img.copy()
        result = img.copy()
        for c in range(w):
            offset = (key + c) % h
            result[:, c] = np.roll(img[:, c], offset, axis=0)
        return result

    @staticmethod
    def etap1_unscramble(img: np.ndarray, key: int) -> np.ndarray:
        h, w = img.shape[:2]
        if h <= 1:
            return img.copy()
        result = img.copy()
        for c in range(w):
            offset = (key + c) % h
            result[:, c] = np.roll(img[:, c], -offset, axis=0)
        return result

    # ──────────────────────────────────────────────────────────
    # ETAP 2: Czysta permutacja zig-zag sterowana kluczem
    # ──────────────────────────────────────────────────────────
    #
    # Krok 1 – Odczyt zig-zag:
    #   Piksel (row, col) jest odczytywany w kolejnosci:
    #     wiersz parzy  -> lewo do prawa
    #     wiersz nieparz-> prawo do lewa
    #   Wynikiem jest wektor N pikseli (N = h*w).
    #
    # Krok 2 – Permutacja Fisher-Yates sterowana seedem (key):
    #   P: {0..N-1} -> {0..N-1}
    #   Wektorze pikseli jest przetasowywany wg P.
    #
    # Unscramble:
    #   1. P^-1 = argsort(P)  – odwraca permutacje
    #   2. Odwrotny zig-zag   – wstawia piksele z powrotem na oryginalne pozycje
    #
    # Permutacja nie zmienia wartosci pikseli – tylko ich polozenie.

    @staticmethod
    def _zigzag_indices(h: int, w: int) -> np.ndarray:
        """
        Liniowe indeksy pikseli w kolejnosci zig-zag (jak skan JPEG).
        Indeks liniowy pixel(r,c) = r * w + c.
        """
        indices = []
        for row in range(h):
            cols = range(w) if row % 2 == 0 else range(w - 1, -1, -1)
            for col in cols:
                indices.append(row * w + col)
        return np.array(indices, dtype=np.int64)

    @staticmethod
    def _fisher_yates(n: int, seed: int) -> np.ndarray:
        """
        Deterministyczna permutacja Fisher-Yates.
        Zwraca tablice P dlugosci n, gdzie P[i] = docelowy indeks.
        Seed normalizowany do uint64 (obsluguje klucze ujemne).
        """
        seed_norm = int(seed) & 0xFFFFFFFFFFFFFFFF   # zawsze nieujemny
        rng = np.random.default_rng(seed_norm)
        perm = np.arange(n, dtype=np.int64)
        rng.shuffle(perm)
        return perm

    @staticmethod
    def etap2_scramble(img: np.ndarray, key: int) -> np.ndarray:
        h, w = img.shape[:2]
        n = h * w

        # 1. Odczyt zig-zag -> wektor pikseli
        zz = ImageProcessor._zigzag_indices(h, w)
        flat_zz = img.reshape(n, -1)[zz]

        # 2. Permutacja Fisher-Yates
        perm = ImageProcessor._fisher_yates(n, seed=key)
        permuted = flat_zz[perm]

        # 3. Zapis wg standardowego raster-scan (wynik scramblingu)
        return permuted.reshape(img.shape)

    @staticmethod
    def etap2_unscramble(img: np.ndarray, key: int) -> np.ndarray:
        h, w = img.shape[:2]
        n = h * w

        # 1. Odczyt raster-scan ze scrambled
        flat = img.reshape(n, -1)

        # 2. P^-1 (odwrotna permutacja)
        perm = ImageProcessor._fisher_yates(n, seed=key)
        inv_perm = np.argsort(perm)
        unpermuted = flat[inv_perm]          # piksele w kolejnosci zig-zag

        # 3. Odwrotny zig-zag – wstaw na oryginalne pozycje
        zz = ImageProcessor._zigzag_indices(h, w)
        result = np.empty_like(img.reshape(n, -1))
        result[zz] = unpermuted
        return result.reshape(img.shape)

    # ──────────────────────────────────────────────────────────
    # ETAP 3: Hybryda – permutacja zig-zag + substytucja XOR
    # ──────────────────────────────────────────────────────────
    #
    # Scramble:
    #   1. Permutacja zig-zag (Etap 2)
    #   2. XOR kazdego bajtu z maska PRNG(key XOR 0xDEADBEEF)
    #
    # Unscramble (ODWROTNA kolejnosc operacji):
    #   1. XOR z ta sama maska  (XOR jest inwolucja: m XOR m = 0)
    #   2. Odwrotna permutacja  (Etap 2)
    #
    # Maska uzyw innego seeda niz permutacja – zmiana klucza o 1 bit
    # wplywa na oba komponenty niezaleznie.

    @staticmethod
    def _xor_mask(shape: tuple, key: int) -> np.ndarray:
        seed = int(key) ^ 0xDEADBEEF
        rng = np.random.default_rng(seed & 0xFFFFFFFFFFFFFFFF)
        return rng.integers(0, 256, size=shape, dtype=np.uint8)

    @staticmethod
    def etap3_scramble(img: np.ndarray, key: int) -> np.ndarray:
        permuted = ImageProcessor.etap2_scramble(img, key)
        mask = ImageProcessor._xor_mask(img.shape, key)
        return (permuted.astype(np.uint16) ^ mask).astype(np.uint8)

    @staticmethod
    def etap3_unscramble(img: np.ndarray, key: int) -> np.ndarray:
        # Odwrotna kolejnosc: najpierw XOR, potem odwrotna permutacja
        mask = ImageProcessor._xor_mask(img.shape, key)
        de_xored = (img.astype(np.uint16) ^ mask).astype(np.uint8)
        return ImageProcessor.etap2_unscramble(de_xored, key)


# ══════════════════════════════════════════════════════════════
#  METRYKI
# ══════════════════════════════════════════════════════════════

class Metrics:
    """
    Metryki eksperymentalne wymagane przez specyfikacje projektu.

    korelacja_sasiadow:
        Korelacja Pearsona miedzy pikselami (i,j) i (i,j+1)
        w kanale jasnosci. Bliska 1.0 = silna korelacja (natural image).
        Bliska 0.0 = brak korelacji (dobry scrambling).

    mse:
        Mean Squared Error miedzy oryginalem a obrazem odtworzonym.
        MSE == 0 -> odwracalnosc perfekcyjna.

    psnr:
        Peak Signal-to-Noise Ratio. inf gdy MSE==0.
    """

    @staticmethod
    def _luma(arr: np.ndarray) -> np.ndarray:
        return (0.299 * arr[:, :, 0] +
                0.587 * arr[:, :, 1] +
                0.114 * arr[:, :, 2]).astype(np.float64)

    @staticmethod
    def korelacja_sasiadow(arr: np.ndarray) -> float:
        lum = Metrics._luma(arr)
        x = lum[:, :-1].ravel()
        y = lum[:, 1:].ravel()
        if x.std() < 1e-10 or y.std() < 1e-10:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])

    @staticmethod
    def mse(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))

    @staticmethod
    def psnr(a: np.ndarray, b: np.ndarray) -> float:
        m = Metrics.mse(a, b)
        if m == 0:
            return float('inf')
        return 10.0 * np.log10(255.0 ** 2 / m)


# ══════════════════════════════════════════════════════════════
#  GUI – stale i styl
# ══════════════════════════════════════════════════════════════

IMG_W, IMG_H = 240, 240

ETAPY = {
    "Etap 1 – Naiwny (przesuwanie kolumn)": (
        ImageProcessor.etap1_scramble,
        ImageProcessor.etap1_unscramble,
    ),
    "Etap 2 – Permutacja zig-zag": (
        ImageProcessor.etap2_scramble,
        ImageProcessor.etap2_unscramble,
    ),
    "Etap 3 – Hybryda (permutacja + XOR)": (
        ImageProcessor.etap3_scramble,
        ImageProcessor.etap3_unscramble,
    ),
}

C = {
    "bg":      "#0f0f1a",
    "panel":   "#16162a",
    "accent":  "#00c8ff",
    "accent2": "#ff6b35",
    "ok":      "#39d353",
    "err":     "#ff4444",
    "text":    "#d0d0e0",
    "muted":   "#666680",
    "border":  "#2a2a44",
    "canvas":  "#080810",
}


def arr_to_photo(arr: np.ndarray, size=(IMG_W, IMG_H)) -> ImageTk.PhotoImage:
    img = Image.fromarray(arr.astype(np.uint8))
    img.thumbnail(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img)


# ══════════════════════════════════════════════════════════════
#  GUI – panel metryk
# ══════════════════════════════════════════════════════════════

class MetricsPanel(tk.Frame):
    ROWS = [
        ("corr_orig",      "Oryg. korelacja:"),
        ("corr_scrambled", "Scr. korelacja: "),
        ("corr_recovered", "Odtw. korelacja:"),
        ("mse",            "MSE (odtw.):     "),
        ("psnr",           "PSNR (odtw.):    "),
        ("time",           "Czas operacji:   "),
    ]

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["panel"], **kw)
        tk.Label(self, text="METRYKI", bg=C["panel"], fg=C["accent"],
                 font=("Consolas", 8, "bold")).pack(anchor=tk.W, padx=8, pady=(8, 3))
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, padx=8)

        self._vals = {}
        for key, label in self.ROWS:
            row = tk.Frame(self, bg=C["panel"])
            row.pack(fill=tk.X, padx=8, pady=1)
            tk.Label(row, text=label, bg=C["panel"], fg=C["muted"],
                     font=("Consolas", 8), anchor=tk.W, width=18).pack(side=tk.LEFT)
            v = tk.Label(row, text="—", bg=C["panel"], fg=C["text"],
                         font=("Consolas", 8, "bold"), anchor=tk.W)
            v.pack(side=tk.LEFT)
            self._vals[key] = v

        tk.Frame(self, bg=C["panel"], height=6).pack()

    def set(self, key: str, text: str, color: str | None = None):
        if key in self._vals:
            self._vals[key].config(text=text, fg=color or C["text"])

    def clear_field(self, key: str):
        if key in self._vals:
            self._vals[key].config(text="—", fg=C["text"])

    def clear_all(self):
        for v in self._vals.values():
            v.config(text="—", fg=C["text"])


# ══════════════════════════════════════════════════════════════
#  GUI – glowne okno
# ══════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Projekt M-II  ·  Chaotyczne przeksztalcanie obrazu")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.minsize(960, 580)

        self.orig_arr:      np.ndarray | None = None
        self.scrambled_arr: np.ndarray | None = None
        self.recovered_arr: np.ndarray | None = None

        self._apply_styles()
        self._build()

    # ── Style ttk ────────────────────────────────────────────────────────────

    def _apply_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame",       background=C["bg"])
        s.configure("TLabel",       background=C["bg"],    foreground=C["text"],  font=("Consolas", 9))
        s.configure("TButton",      background=C["panel"], foreground=C["text"],
                    font=("Consolas", 9, "bold"), padding=(8, 5), relief="flat", borderwidth=0)
        s.map("TButton",
              background=[("active", C["border"])],
              foreground=[("active", C["accent"])])
        s.configure("Accent.TButton", background=C["accent"], foreground=C["bg"],
                    font=("Consolas", 10, "bold"), padding=(10, 6))
        s.map("Accent.TButton",
              background=[("active", "#00a8d8"), ("pressed", "#006f9a")])
        s.configure("TCombobox", fieldbackground=C["panel"], background=C["panel"],
                    foreground=C["text"], selectbackground=C["border"], font=("Consolas", 9))
        s.configure("TEntry",    fieldbackground=C["panel"], foreground=C["text"],
                    insertcolor=C["accent"], font=("Consolas", 10))

    # ── Budowanie layoutu ────────────────────────────────────────────────────

    def _build(self):
        # Naglowek
        hdr = tk.Frame(self, bg=C["bg"], pady=8)
        hdr.pack(fill=tk.X, padx=20)
        tk.Label(hdr, text="PROJEKT M-II", bg=C["bg"], fg=C["accent"],
                 font=("Consolas", 15, "bold")).pack(side=tk.LEFT)
        tk.Label(hdr, text="  ·  Chaotyczne przeksztalcanie obrazu cyfrowego",
                 bg=C["bg"], fg=C["muted"], font=("Consolas", 9)).pack(side=tk.LEFT, pady=2)

        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, padx=20)

        # Body
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Panel lewy
        left = tk.Frame(body, bg=C["panel"],
                        highlightthickness=1, highlightbackground=C["border"])
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12), ipadx=12, ipady=6)
        self._build_left(left)

        # Panel prawy
        right = tk.Frame(body, bg=C["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_images(right)

        # Status bar
        self.status_var = tk.StringVar(value="Wczytaj obraz aby rozpoczac.")
        tk.Label(self, textvariable=self.status_var,
                 bg=C["bg"], fg=C["muted"], font=("Consolas", 7),
                 anchor=tk.W, padx=20, pady=3).pack(fill=tk.X, side=tk.BOTTOM)

    def _sep(self, parent, pady=(8, 4)):
        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X, pady=pady)

    def _section(self, parent, text):
        tk.Label(parent, text=text, bg=C["panel"], fg=C["accent"],
                 font=("Consolas", 7, "bold")).pack(anchor=tk.W, pady=(10, 0))
        self._sep(parent, pady=(2, 6))

    def _build_left(self, parent):
        # Obraz
        self._section(parent, "OBRAZ WEJSCIOWY")
        ttk.Button(parent, text="📂  Wczytaj obraz (PNG / JPG / BMP)",
                   command=self._load).pack(fill=tk.X)
        self.path_lbl = tk.Label(parent, text="(brak)", bg=C["panel"], fg=C["muted"],
                                 font=("Consolas", 7), wraplength=210, anchor=tk.W)
        self.path_lbl.pack(anchor=tk.W, pady=(3, 0))

        # Etap
        self._section(parent, "ETAP ALGORYTMU")
        self.etap_var = tk.StringVar(value=list(ETAPY.keys())[0])
        ttk.Combobox(parent, textvariable=self.etap_var,
                     values=list(ETAPY.keys()), state="readonly", width=30).pack(fill=tk.X)

        # Klucze
        self._section(parent, "KLUCZE")
        tk.Label(parent, text="Poprawny klucz (int):", bg=C["panel"],
                 fg=C["text"], font=("Consolas", 8)).pack(anchor=tk.W)
        self.key_var = tk.StringVar(value="1337")
        ttk.Entry(parent, textvariable=self.key_var, width=20).pack(anchor=tk.W, pady=(2, 8))

        tk.Label(parent, text="Bledny klucz (do testu):", bg=C["panel"],
                 fg=C["text"], font=("Consolas", 8)).pack(anchor=tk.W)
        self.wrong_var = tk.StringVar(value="1338")
        ttk.Entry(parent, textvariable=self.wrong_var, width=20).pack(anchor=tk.W, pady=(2, 0))

        # Operacje
        self._section(parent, "OPERACJE")
        ttk.Button(parent, text="🔀  SCRAMBLE",
                   style="Accent.TButton", command=self._scramble).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(parent, text="🔁  Unscramble  [✓ poprawny klucz]",
                   command=lambda: self._unscramble(correct=True)).pack(fill=tk.X, pady=2)
        ttk.Button(parent, text="❌  Unscramble  [✗ bledny klucz]",
                   command=lambda: self._unscramble(correct=False)).pack(fill=tk.X, pady=2)

        self._sep(parent, pady=(10, 4))
        ttk.Button(parent, text="💾  Zapisz obrazy",
                   command=self._save).pack(fill=tk.X)

        # Metryki
        self._sep(parent, pady=(10, 0))
        self.metrics = MetricsPanel(parent)
        self.metrics.pack(fill=tk.X)

    def _build_images(self, parent):
        col_labels = ["ORYGINAL", "PO SCRAMBLINGU", "ODTWORZONE"]
        self._canvases  = []
        self._img_infos = []

        for lbl in col_labels:
            col = tk.Frame(parent, bg=C["bg"])
            col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

            tk.Label(col, text=lbl, bg=C["bg"], fg=C["accent"],
                     font=("Consolas", 8, "bold")).pack(pady=(0, 4))

            c = tk.Canvas(col, width=IMG_W, height=IMG_H, bg=C["canvas"],
                          highlightthickness=1, highlightbackground=C["border"])
            c.pack()
            self._canvases.append(c)

            info = tk.Label(col, text="—", bg=C["bg"], fg=C["muted"],
                            font=("Consolas", 7))
            info.pack(pady=(3, 0))
            self._img_infos.append(info)

    # ── Akcje ─────────────────────────────────────────────────────────────────

    def _load(self):
        path = filedialog.askopenfilename(
            title="Wczytaj obraz",
            filetypes=[("Obrazy", "*.png *.jpg *.jpeg *.bmp *.tiff"),
                       ("Wszystkie", "*.*")]
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Blad wczytywania", str(e))
            return

        self.orig_arr = np.array(img, dtype=np.uint8)
        self.scrambled_arr = None
        self.recovered_arr = None

        self.path_lbl.config(text=os.path.basename(path))
        self._show(0, self.orig_arr, f"{img.width}x{img.height} px")
        self._clr(1)
        self._clr(2)

        corr = Metrics.korelacja_sasiadow(self.orig_arr)
        self.metrics.clear_all()
        self.metrics.set("corr_orig", f"{corr:.4f}")
        self.status_var.set(f"Wczytano: {os.path.basename(path)}  |  {img.width}x{img.height} px")

    def _get_key(self, correct: bool) -> int | None:
        raw = (self.key_var if correct else self.wrong_var).get().strip()
        try:
            return int(raw)
        except ValueError:
            messagebox.showerror("Bledny klucz", f"Klucz musi byc liczba calkowita.\nWpisano: '{raw}'")
            return None

    def _scramble(self):
        if self.orig_arr is None:
            messagebox.showwarning("Brak obrazu", "Najpierw wczytaj obraz.")
            return
        key = self._get_key(correct=True)
        if key is None:
            return

        fn_sc, _ = ETAPY[self.etap_var.get()]
        self.status_var.set("Scrambling...")
        self.update_idletasks()

        t0 = time.perf_counter()
        self.scrambled_arr = fn_sc(self.orig_arr, key)
        dt = (time.perf_counter() - t0) * 1000

        self.recovered_arr = None
        self._show(1, self.scrambled_arr, f"klucz: {key}")
        self._clr(2)

        corr_s = Metrics.korelacja_sasiadow(self.scrambled_arr)
        self.metrics.set("corr_scrambled", f"{corr_s:.4f}",
                          C["ok"] if abs(corr_s) < 0.15 else C["accent2"])
        self.metrics.clear_field("corr_recovered")
        self.metrics.clear_field("mse")
        self.metrics.clear_field("psnr")
        self.metrics.set("time", f"{dt:.1f} ms")

        etap_short = self.etap_var.get().split("–")[0].strip()
        self.status_var.set(
            f"Scramble OK  |  {etap_short}  |  klucz: {key}"
            f"  |  korelacja: {corr_s:.4f}  |  {dt:.0f} ms"
        )

    def _unscramble(self, correct: bool):
        if self.scrambled_arr is None:
            messagebox.showwarning("Brak danych", "Najpierw wykonaj Scramble.")
            return
        key = self._get_key(correct=correct)
        if key is None:
            return

        _, fn_usc = ETAPY[self.etap_var.get()]
        self.status_var.set("Unscrambling...")
        self.update_idletasks()

        t0 = time.perf_counter()
        self.recovered_arr = fn_usc(self.scrambled_arr, key)
        dt = (time.perf_counter() - t0) * 1000

        tag  = "poprawny" if correct else "BLEDNY"
        col  = C["ok"] if correct else C["err"]
        self._show(2, self.recovered_arr, f"klucz: {key}  [{tag}]", color=col)

        corr_r = Metrics.korelacja_sasiadow(self.recovered_arr)
        self.metrics.set("corr_recovered", f"{corr_r:.4f}")
        self.metrics.set("time", f"{dt:.1f} ms")

        if self.orig_arr is not None:
            m   = Metrics.mse(self.orig_arr, self.recovered_arr)
            p   = Metrics.psnr(self.orig_arr, self.recovered_arr)
            p_s = "inf dB (idealne)" if p == float('inf') else f"{p:.2f} dB"
            self.metrics.set("mse",  f"{m:.2f}",
                              C["ok"] if m == 0.0 else C["err"])
            self.metrics.set("psnr", p_s,
                              C["ok"] if p == float('inf') else C["accent2"])

        self.status_var.set(
            f"Unscramble [{tag}]  |  klucz: {key}  |  {dt:.0f} ms"
        )

    def _save(self):
        pairs = [(n, a) for n, a in [
            ("oryginal.png",  self.orig_arr),
            ("scrambled.png", self.scrambled_arr),
            ("recovered.png", self.recovered_arr),
        ] if a is not None]

        if not pairs:
            messagebox.showwarning("Brak danych", "Brak obrazow do zapisania.")
            return

        folder = filedialog.askdirectory(title="Wybierz folder zapisu")
        if not folder:
            return

        saved = []
        for name, arr in pairs:
            Image.fromarray(arr.astype(np.uint8)).save(os.path.join(folder, name))
            saved.append(name)

        self.status_var.set(f"Zapisano: {', '.join(saved)}  -> {folder}")
        messagebox.showinfo("Zapisano", "Pliki:\n" + "\n".join(saved) + f"\n\n-> {folder}")

    # ── Helpers canvas ────────────────────────────────────────────────────────

    def _show(self, idx: int, arr: np.ndarray, info: str = "", color: str | None = None):
        photo = arr_to_photo(arr)
        c = self._canvases[idx]
        c._photo = photo                     # trzymaj referencje (gc)
        c.delete("all")
        c.create_image(IMG_W // 2, IMG_H // 2, anchor=tk.CENTER, image=photo)
        self._img_infos[idx].config(text=info or "—", fg=color or C["muted"])

    def _clr(self, idx: int):
        self._canvases[idx].delete("all")
        self._img_infos[idx].config(text="—", fg=C["muted"])


# ══════════════════════════════════════════════════════════════
#  TESTY JEDNOSTKOWE  (python main.py --test)
# ══════════════════════════════════════════════════════════════

def _run_tests():
    import sys
    print("=" * 60)
    print("TESTY JEDNOSTKOWE – odwracalnosc algorytmow")
    print("=" * 60)
    passed = failed = 0
    shapes = [(4, 4, 3), (8, 9, 3), (1, 8, 3), (100, 100, 3), (50, 73, 3)]
    keys   = [0, 1, 42, 1337, -5, 999999]

    for shape in shapes:
        img = np.random.randint(0, 256, shape, dtype=np.uint8)
        for key in keys:
            for name, sc, usc in [
                ("Etap1", ImageProcessor.etap1_scramble, ImageProcessor.etap1_unscramble),
                ("Etap2", ImageProcessor.etap2_scramble, ImageProcessor.etap2_unscramble),
                ("Etap3", ImageProcessor.etap3_scramble, ImageProcessor.etap3_unscramble),
            ]:
                s = sc(img, key)
                r = usc(s, key)
                ok = np.array_equal(img, r)
                diff_scramble = not np.array_equal(img, s)
                if ok:
                    passed += 1
                else:
                    failed += 1
                    print(f"  FAIL  {name}  shape={shape}  key={key}  "
                          f"diff_scramble={diff_scramble}")

    print(f"\nWynik: {passed} OK  |  {failed} BLEDOW")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        _run_tests()
    else:
        App().mainloop()
