"""
Projekt M-II: Chaotyczne przekształcanie obrazu cyfrowego
COMMIT 4 – UX, eksperymenty, formalizm i finalizacja interfejsu

Najważniejsze zmiany względem commit 3:
  - Dodany jawny test formalny permutacji: P(i), P^-1(i), P^-1(P(i)) = i
  - Rozszerzone metryki: korelacja pozioma, pionowa, diagonalna, MSE, PSNR, MAE, udział różnych pikseli
  - Dodany generator obrazu testowego (szachownica / gradient / tekst) do eksperymentów bez zewnętrznych plików
  - Dodany panel 'Analiza formalna' z tabelą indeksów dla Etapu 2 i 3
  - Dodany zapis raportu TXT z metrykami i wynikami testu formalnego
  - Ulepszony GUI: zakładki, lepsze opisy, lepszy status, bardziej akademicki wygląd
  - Dodany prosty motyw/branding UWB w nagłówku jako stylizowany element prezentacyjny
  - Zachowana pełna odwracalność wszystkich etapów przy poprawnym kluczu
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import numpy as np
import os
import sys
import time


class ImageProcessor:
    """Algorytmy scramblingu / unscramblingu zgodne z wymaganiami projektu."""

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

    @staticmethod
    def _zigzag_indices(h: int, w: int) -> np.ndarray:
        indices = []
        for row in range(h):
            cols = range(w) if row % 2 == 0 else range(w - 1, -1, -1)
            for col in cols:
                indices.append(row * w + col)
        return np.array(indices, dtype=np.int64)

    @staticmethod
    def _fisher_yates(n: int, seed: int) -> np.ndarray:
        seed_norm = int(seed) & 0xFFFFFFFFFFFFFFFF
        rng = np.random.default_rng(seed_norm)
        perm = np.arange(n, dtype=np.int64)
        rng.shuffle(perm)
        return perm

    @staticmethod
    def _inverse_permutation(perm: np.ndarray) -> np.ndarray:
        inv = np.empty_like(perm)
        inv[perm] = np.arange(len(perm))
        return inv

    @staticmethod
    def etap2_scramble(img: np.ndarray, key: int) -> np.ndarray:
        h, w = img.shape[:2]
        n = h * w
        zz = ImageProcessor._zigzag_indices(h, w)
        flat_zz = img.reshape(n, -1)[zz]
        perm = ImageProcessor._fisher_yates(n, seed=key)
        permuted = flat_zz[perm]
        return permuted.reshape(img.shape)

    @staticmethod
    def etap2_unscramble(img: np.ndarray, key: int) -> np.ndarray:
        h, w = img.shape[:2]
        n = h * w
        flat = img.reshape(n, -1)
        perm = ImageProcessor._fisher_yates(n, seed=key)
        inv_perm = np.argsort(perm)
        unpermuted = flat[inv_perm]
        zz = ImageProcessor._zigzag_indices(h, w)
        result = np.empty_like(img.reshape(n, -1))
        result[zz] = unpermuted
        return result.reshape(img.shape)

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
        mask = ImageProcessor._xor_mask(img.shape, key)
        de_xored = (img.astype(np.uint16) ^ mask).astype(np.uint8)
        return ImageProcessor.etap2_unscramble(de_xored, key)

    @staticmethod
    def formal_permutation_rows(n: int, key: int, sample_indices=None):
        perm = ImageProcessor._fisher_yates(n, key)
        inv = ImageProcessor._inverse_permutation(perm)
        if sample_indices is None:
            sample_indices = [0, 1, 2, min(10, n - 1), min(25, n - 1)]
        rows = []
        for i in sample_indices:
            rows.append({
                'i': int(i),
                'P(i)': int(perm[i]),
                'P^-1(i)': int(inv[i]),
                'P^-1(P(i))': int(inv[perm[i]])
            })
        return rows


class Metrics:
    @staticmethod
    def _luma(arr: np.ndarray) -> np.ndarray:
        return (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.float64)

    @staticmethod
    def _corr_pairs(a: np.ndarray, b: np.ndarray) -> float:
        x = a.ravel()
        y = b.ravel()
        if x.std() < 1e-10 or y.std() < 1e-10:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])

    @staticmethod
    def corr_horizontal(arr: np.ndarray) -> float:
        lum = Metrics._luma(arr)
        return Metrics._corr_pairs(lum[:, :-1], lum[:, 1:])

    @staticmethod
    def corr_vertical(arr: np.ndarray) -> float:
        lum = Metrics._luma(arr)
        return Metrics._corr_pairs(lum[:-1, :], lum[1:, :])

    @staticmethod
    def corr_diagonal(arr: np.ndarray) -> float:
        lum = Metrics._luma(arr)
        return Metrics._corr_pairs(lum[:-1, :-1], lum[1:, 1:])

    @staticmethod
    def mse(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))

    @staticmethod
    def mae(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.mean(np.abs(a.astype(np.float64) - b.astype(np.float64))))

    @staticmethod
    def differing_ratio(a: np.ndarray, b: np.ndarray) -> float:
        diff = np.any(a != b, axis=2) if a.ndim == 3 else (a != b)
        return float(np.mean(diff))

    @staticmethod
    def psnr(a: np.ndarray, b: np.ndarray) -> float:
        m = Metrics.mse(a, b)
        if m == 0:
            return float('inf')
        return 10.0 * np.log10(255.0 ** 2 / m)


IMG_W, IMG_H = 250, 250
ETAPY = {
    'Etap 1 – Naiwny (przesuwanie kolumn)': (ImageProcessor.etap1_scramble, ImageProcessor.etap1_unscramble),
    'Etap 2 – Permutacja zig-zag': (ImageProcessor.etap2_scramble, ImageProcessor.etap2_unscramble),
    'Etap 3 – Hybryda (permutacja + XOR)': (ImageProcessor.etap3_scramble, ImageProcessor.etap3_unscramble),
}

C = {
    'bg': '#0b1020',
    'panel': '#121a30',
    'panel2': '#0f1730',
    'accent': '#00d4ff',
    'accent2': '#ff8a3d',
    'ok': '#39d98a',
    'err': '#ff5d73',
    'text': '#e9efff',
    'muted': '#8c95ae',
    'border': '#24304d',
    'canvas': '#08101d',
}


def arr_to_photo(arr: np.ndarray, size=(IMG_W, IMG_H)) -> ImageTk.PhotoImage:
    img = Image.fromarray(arr.astype(np.uint8))
    img.thumbnail(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img)


def generate_demo_image(kind='checker', size=(320, 240)):
    w, h = size
    img = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(img)
    if kind == 'checker':
        block = 20
        for y in range(0, h, block):
            for x in range(0, w, block):
                color = (20, 20, 20) if ((x // block) + (y // block)) % 2 == 0 else (235, 235, 235)
                draw.rectangle([x, y, x + block - 1, y + block - 1], fill=color)
    elif kind == 'gradient':
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                arr[y, x] = [int(255 * x / max(1, w - 1)), int(255 * y / max(1, h - 1)), 120]
        return arr
    elif kind == 'text':
        draw.rectangle([0, 0, w, h], fill=(245, 245, 245))
        try:
            font = ImageFont.truetype('DejaVuSans-Bold.ttf', 30)
            small = ImageFont.truetype('DejaVuSans.ttf', 18)
        except Exception:
            font = ImageFont.load_default()
            small = ImageFont.load_default()
        draw.text((20, 30), 'Projekt M-II', fill=(20, 30, 80), font=font)
        draw.text((20, 90), 'Chaotyczne przekształcanie obrazu', fill=(100, 20, 20), font=small)
        draw.text((20, 125), 'tekst / struktura / kontrast', fill=(20, 120, 70), font=small)
        draw.rectangle([18, 170, 302, 205], outline=(10, 10, 10), width=2)
    return np.array(img, dtype=np.uint8)


def create_logo(width=360, height=76):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 10, 56, 66), radius=16, fill=(0, 212, 255, 255))
    d.polygon([(14, 28), (28, 50), (42, 28)], fill=(11, 16, 32, 255))
    d.rectangle((25, 32, 31, 58), fill=(11, 16, 32, 255))
    try:
        font_big = ImageFont.truetype('DejaVuSans-Bold.ttf', 20)
        font_small = ImageFont.truetype('DejaVuSans.ttf', 11)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    d.text((72, 12), 'UWB Wilno', fill=(234, 242, 255, 255), font=font_big)
    d.text((72, 40), 'Projekt M-II · Chaotyczne przekształcanie obrazu', fill=(140, 152, 180, 255), font=font_small)
    return ImageTk.PhotoImage(img)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Projekt M-II · Chaotyczne przekształcanie obrazu')
        self.configure(bg=C['bg'])
        self.geometry('1480x920')
        self.minsize(1180, 760)

        self.orig_arr = None
        self.scrambled_arr = None
        self.recovered_arr = None
        self.last_report = ''
        self.logo_img = None

        self._apply_styles()
        self._build()

    def _apply_styles(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('TFrame', background=C['bg'])
        s.configure('Panel.TFrame', background=C['panel'])
        s.configure('TLabel', background=C['bg'], foreground=C['text'], font=('Segoe UI', 10))
        s.configure('Panel.TLabel', background=C['panel'], foreground=C['text'], font=('Segoe UI', 10))
        s.configure('Header.TLabel', background=C['bg'], foreground=C['accent'], font=('Segoe UI Semibold', 16))
        s.configure('Sub.TLabel', background=C['bg'], foreground=C['muted'], font=('Segoe UI', 9))
        s.configure('TButton', font=('Segoe UI Semibold', 10), padding=8)
        s.configure('Accent.TButton', font=('Segoe UI Semibold', 10), padding=8)
        s.configure('TCombobox', fieldbackground=C['panel2'], foreground=C['text'])
        s.configure('TEntry', fieldbackground=C['panel2'], foreground=C['text'])
        s.configure('TNotebook', background=C['bg'], borderwidth=0)
        s.configure('TNotebook.Tab', font=('Segoe UI Semibold', 10), padding=(12, 6))

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=18, pady=(14, 8))
        self.logo_img = create_logo()
        ttk.Label(top, image=self.logo_img, style='Header.TLabel').pack(side=tk.LEFT)
        info = ttk.Frame(top)
        info.pack(side=tk.LEFT, padx=14)
        ttk.Label(info, text='Analizator etapów 1 / 2 / 3', style='Header.TLabel').pack(anchor=tk.W)
        ttk.Label(info, text='permutacja · odwrotność · błędny klucz · metryki eksperymentalne', style='Sub.TLabel').pack(anchor=tk.W, pady=(4, 0))

        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 12))

        left = ttk.Frame(main, style='Panel.TFrame')
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))
        left.configure(width=360)
        left.pack_propagate(False)

        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_left(left)
        self._build_right(right)

        self.status_var = tk.StringVar(value='Wczytaj obraz lub wygeneruj obraz testowy.')
        ttk.Label(self, textvariable=self.status_var, style='Sub.TLabel').pack(fill=tk.X, padx=18, pady=(0, 12))

    def _build_left(self, parent):
        wrap = ttk.Frame(parent, style='Panel.TFrame')
        wrap.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        ttk.Label(wrap, text='Obraz', style='Panel.TLabel', font=('Segoe UI Semibold', 12)).pack(anchor=tk.W)
        ttk.Button(wrap, text='Wczytaj obraz', command=self._load).pack(fill=tk.X, pady=(8, 6))
        self.path_lbl = ttk.Label(wrap, text='(brak)', style='Panel.TLabel', wraplength=300)
        self.path_lbl.pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(wrap, text='Szybki obraz testowy', style='Panel.TLabel', font=('Segoe UI Semibold', 12)).pack(anchor=tk.W, pady=(6, 0))
        demo_row = ttk.Frame(wrap, style='Panel.TFrame')
        demo_row.pack(fill=tk.X, pady=(6, 12))
        ttk.Button(demo_row, text='Szachownica', command=lambda: self._load_demo('checker')).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(demo_row, text='Gradient', command=lambda: self._load_demo('gradient')).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(demo_row, text='Tekst', command=lambda: self._load_demo('text')).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        ttk.Separator(wrap, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(wrap, text='Etap', style='Panel.TLabel', font=('Segoe UI Semibold', 12)).pack(anchor=tk.W)
        self.etap_var = tk.StringVar(value=list(ETAPY.keys())[0])
        ttk.Combobox(wrap, textvariable=self.etap_var, values=list(ETAPY.keys()), state='readonly').pack(fill=tk.X, pady=(6, 12))

        ttk.Label(wrap, text='Klucz poprawny', style='Panel.TLabel').pack(anchor=tk.W)
        self.key_var = tk.StringVar(value='1337')
        ttk.Entry(wrap, textvariable=self.key_var).pack(fill=tk.X, pady=(4, 8))
        ttk.Label(wrap, text='Klucz błędny', style='Panel.TLabel').pack(anchor=tk.W)
        self.wrong_var = tk.StringVar(value='1338')
        ttk.Entry(wrap, textvariable=self.wrong_var).pack(fill=tk.X, pady=(4, 12))

        ttk.Button(wrap, text='Scramble', style='Accent.TButton', command=self._scramble).pack(fill=tk.X, pady=4)
        ttk.Button(wrap, text='Unscramble – poprawny klucz', command=lambda: self._unscramble(True)).pack(fill=tk.X, pady=4)
        ttk.Button(wrap, text='Unscramble – błędny klucz', command=lambda: self._unscramble(False)).pack(fill=tk.X, pady=4)
        ttk.Button(wrap, text='Test formalny P⁻¹(P(i))', command=self._run_formal_table).pack(fill=tk.X, pady=(10, 4))
        ttk.Button(wrap, text='Zapisz wyniki', command=self._save).pack(fill=tk.X, pady=(4, 4))

        ttk.Separator(wrap, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(wrap, text='Skrót wymagań', style='Panel.TLabel', font=('Segoe UI Semibold', 12)).pack(anchor=tk.W)
        note = (
            'Etap 2: czysta permutacja bez zmiany wartości pikseli.\n'
            'Etap 3: mechanizm wzmacniający, w pełni odwracalny.\n'
            'Testy: poprawny i błędny klucz, metryki, analiza formalna.'
        )
        ttk.Label(wrap, text=note, style='Panel.TLabel', wraplength=300, foreground=C['muted']).pack(anchor=tk.W, pady=(6, 0))

    def _build_right(self, parent):
        top_imgs = ttk.Frame(parent)
        top_imgs.pack(fill=tk.X)

        labels = ['ORYGINAŁ', 'PO SCRAMBLINGU', 'ODTWORZONE']
        self._canvases = []
        self._infos = []
        for lbl in labels:
            card = ttk.Frame(top_imgs, style='Panel.TFrame')
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)
            inner = ttk.Frame(card, style='Panel.TFrame')
            inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
            ttk.Label(inner, text=lbl, style='Panel.TLabel', font=('Segoe UI Semibold', 12)).pack(pady=(0, 8))
            c = tk.Canvas(inner, width=IMG_W, height=IMG_H, bg=C['canvas'], highlightthickness=1, highlightbackground=C['border'])
            c.pack()
            info = ttk.Label(inner, text='—', style='Panel.TLabel', foreground=C['muted'])
            info.pack(pady=(8, 0))
            self._canvases.append(c)
            self._infos.append(info)

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        self.metrics_tab = tk.Frame(self.notebook, bg=C['panel'])
        self.formal_tab = tk.Frame(self.notebook, bg=C['panel'])
        self.report_tab = tk.Frame(self.notebook, bg=C['panel'])
        self.notebook.add(self.metrics_tab, text='Metryki')
        self.notebook.add(self.formal_tab, text='Analiza formalna')
        self.notebook.add(self.report_tab, text='Raport')

        self.metrics_text = tk.Text(self.metrics_tab, bg=C['panel2'], fg=C['text'], insertbackground=C['text'], relief=tk.FLAT, wrap='word', font=('Consolas', 10))
        self.metrics_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.formal_text = tk.Text(self.formal_tab, bg=C['panel2'], fg=C['text'], insertbackground=C['text'], relief=tk.FLAT, wrap='none', font=('Consolas', 10))
        self.formal_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.report_text = tk.Text(self.report_tab, bg=C['panel2'], fg=C['text'], insertbackground=C['text'], relief=tk.FLAT, wrap='word', font=('Consolas', 10))
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self._set_text(self.metrics_text, 'Tu pojawią się metryki eksperymentalne.\n')
        self._set_text(self.formal_text, 'Tu pojawi się tabela P(i), P^-1(i), P^-1(P(i)).\n')
        self._set_text(self.report_text, 'Tu pojawi się raport tekstowy do zapisania.\n')

    def _set_text(self, widget, text):
        widget.delete('1.0', tk.END)
        widget.insert('1.0', text)

    def _load(self):
        path = filedialog.askopenfilename(title='Wczytaj obraz', filetypes=[('Obrazy', '*.png *.jpg *.jpeg *.bmp *.tiff'), ('Wszystkie', '*.*')])
        if not path:
            return
        try:
            img = Image.open(path).convert('RGB')
        except Exception as e:
            messagebox.showerror('Błąd wczytywania', str(e))
            return
        self.orig_arr = np.array(img, dtype=np.uint8)
        self.scrambled_arr = None
        self.recovered_arr = None
        self.path_lbl.config(text=os.path.basename(path))
        self._show(0, self.orig_arr, f'{img.width}x{img.height} px')
        self._clear(1)
        self._clear(2)
        self._refresh_original_metrics()
        self.status_var.set(f'Wczytano: {os.path.basename(path)} · {img.width}x{img.height} px')

    def _load_demo(self, kind):
        arr = generate_demo_image(kind)
        self.orig_arr = arr
        self.scrambled_arr = None
        self.recovered_arr = None
        self.path_lbl.config(text=f'[generator] {kind}')
        self._show(0, self.orig_arr, f'{arr.shape[1]}x{arr.shape[0]} px')
        self._clear(1)
        self._clear(2)
        self._refresh_original_metrics()
        self.status_var.set(f'Załadowano obraz testowy: {kind}')

    def _refresh_original_metrics(self):
        if self.orig_arr is None:
            return
        ch = Metrics.corr_horizontal(self.orig_arr)
        cv = Metrics.corr_vertical(self.orig_arr)
        cd = Metrics.corr_diagonal(self.orig_arr)
        txt = (
            f'Obraz oryginalny\n'
            f'- Korelacja pozioma:   {ch:.6f}\n'
            f'- Korelacja pionowa:   {cv:.6f}\n'
            f'- Korelacja diagonalna:{cd:.6f}\n'
        )
        self._set_text(self.metrics_text, txt)
        self._set_text(self.report_text, txt)

    def _get_key(self, correct=True):
        raw = (self.key_var if correct else self.wrong_var).get().strip()
        try:
            return int(raw)
        except ValueError:
            messagebox.showerror('Błędny klucz', f'Klucz musi być liczbą całkowitą.\nWpisano: {raw}')
            return None

    def _scramble(self):
        if self.orig_arr is None:
            messagebox.showwarning('Brak obrazu', 'Najpierw wczytaj obraz.')
            return
        key = self._get_key(True)
        if key is None:
            return
        fn_sc, _ = ETAPY[self.etap_var.get()]
        self.status_var.set('Scrambling...')
        self.update_idletasks()
        t0 = time.perf_counter()
        self.scrambled_arr = fn_sc(self.orig_arr, key)
        dt = (time.perf_counter() - t0) * 1000
        self.recovered_arr = None
        self._show(1, self.scrambled_arr, f'klucz: {key}')
        self._clear(2)

        ch0 = Metrics.corr_horizontal(self.orig_arr)
        cv0 = Metrics.corr_vertical(self.orig_arr)
        cd0 = Metrics.corr_diagonal(self.orig_arr)
        chs = Metrics.corr_horizontal(self.scrambled_arr)
        cvs = Metrics.corr_vertical(self.scrambled_arr)
        cds = Metrics.corr_diagonal(self.scrambled_arr)

        metrics_report = (
            f'Etap: {self.etap_var.get()}\n'
            f'Klucz poprawny: {key}\n'
            f'Czas scramble: {dt:.3f} ms\n\n'
            f'Korelacja oryginału\n'
            f'- pozioma:    {ch0:.6f}\n'
            f'- pionowa:    {cv0:.6f}\n'
            f'- diagonalna: {cd0:.6f}\n\n'
            f'Korelacja po scramblingu\n'
            f'- pozioma:    {chs:.6f}\n'
            f'- pionowa:    {cvs:.6f}\n'
            f'- diagonalna: {cds:.6f}\n'
        )
        self._set_text(self.metrics_text, metrics_report)
        self.last_report = metrics_report
        self._set_text(self.report_text, metrics_report)
        self.status_var.set(f'Scramble OK · {self.etap_var.get()} · {dt:.1f} ms')

    def _unscramble(self, correct=True):
        if self.scrambled_arr is None:
            messagebox.showwarning('Brak danych', 'Najpierw wykonaj Scramble.')
            return
        key = self._get_key(correct)
        if key is None:
            return
        _, fn_usc = ETAPY[self.etap_var.get()]
        self.status_var.set('Unscrambling...')
        self.update_idletasks()
        t0 = time.perf_counter()
        self.recovered_arr = fn_usc(self.scrambled_arr, key)
        dt = (time.perf_counter() - t0) * 1000
        tag = 'poprawny' if correct else 'błędny'
        color = C['ok'] if correct else C['err']
        self._show(2, self.recovered_arr, f'klucz: {key} [{tag}]', color)

        corr_r_h = Metrics.corr_horizontal(self.recovered_arr)
        corr_r_v = Metrics.corr_vertical(self.recovered_arr)
        corr_r_d = Metrics.corr_diagonal(self.recovered_arr)
        mse = Metrics.mse(self.orig_arr, self.recovered_arr)
        mae = Metrics.mae(self.orig_arr, self.recovered_arr)
        psnr = Metrics.psnr(self.orig_arr, self.recovered_arr)
        ratio = Metrics.differing_ratio(self.orig_arr, self.recovered_arr)
        psnr_text = 'inf dB' if psnr == float('inf') else f'{psnr:.6f} dB'

        extra = (
            f'\nUnscramble ({tag})\n'
            f'Klucz użyty: {key}\n'
            f'Czas unscramble: {dt:.3f} ms\n'
            f'- korelacja pozioma:    {corr_r_h:.6f}\n'
            f'- korelacja pionowa:    {corr_r_v:.6f}\n'
            f'- korelacja diagonalna: {corr_r_d:.6f}\n'
            f'- MSE: {mse:.6f}\n'
            f'- MAE: {mae:.6f}\n'
            f'- PSNR: {psnr_text}\n'
            f'- Udział różnych pikseli: {ratio:.6%}\n'
        )
        report = self.last_report + extra
        self._set_text(self.metrics_text, report)
        self._set_text(self.report_text, report)
        self.last_report = report
        self.status_var.set(f'Unscramble [{tag}] · {dt:.1f} ms')

    def _run_formal_table(self):
        try:
            key = int(self.key_var.get().strip())
        except ValueError:
            messagebox.showerror('Błędny klucz', 'Klucz poprawny musi być liczbą całkowitą.')
            return
        n = 256
        rows = ImageProcessor.formal_permutation_rows(n, key, [0, 1, 2, 10, 25])
        lines = []
        lines.append('Formalna analiza permutacji dla Etapu 2 / Etapu 3')
        lines.append('')
        lines.append('i   | P(i) | P^-1(i) | P^-1(P(i))')
        lines.append('-' * 36)
        for row in rows:
            lines.append(f"{row['i']:>3} | {row['P(i)']:>4} | {row['P^-1(i)']:>7} | {row['P^-1(P(i))']:>10}")
        lines.append('')
        lines.append('Wniosek: dla pokazanych indeksów zachodzi P^-1(P(i)) = i.')
        text = '\n'.join(lines)
        self._set_text(self.formal_text, text)
        if self.last_report:
            self._set_text(self.report_text, self.last_report + '\n\n' + text)
        else:
            self._set_text(self.report_text, text)
        self.status_var.set('Wykonano formalny test P^-1(P(i)) = i.')
        self.notebook.select(self.formal_tab)

    def _save(self):
        items = [(n, a) for n, a in [('oryginal.png', self.orig_arr), ('scrambled.png', self.scrambled_arr), ('recovered.png', self.recovered_arr)] if a is not None]
        if not items:
            messagebox.showwarning('Brak danych', 'Brak obrazów do zapisania.')
            return
        folder = filedialog.askdirectory(title='Wybierz folder zapisu')
        if not folder:
            return
        saved = []
        for name, arr in items:
            Image.fromarray(arr.astype(np.uint8)).save(os.path.join(folder, name))
            saved.append(name)
        report = self.report_text.get('1.0', tk.END).strip()
        if report:
            with open(os.path.join(folder, 'raport_metryki.txt'), 'w', encoding='utf-8') as f:
                f.write(report)
            saved.append('raport_metryki.txt')
        self.status_var.set(f'Zapisano: {", ".join(saved)} -> {folder}')
        messagebox.showinfo('Zapisano', 'Pliki:\n' + '\n'.join(saved) + f'\n\n-> {folder}')

    def _show(self, idx, arr, info='—', color=None):
        photo = arr_to_photo(arr)
        canvas = self._canvases[idx]
        canvas._photo = photo
        canvas.delete('all')
        canvas.create_image(IMG_W // 2, IMG_H // 2, anchor=tk.CENTER, image=photo)
        self._infos[idx].config(text=info, foreground=color or C['muted'])

    def _clear(self, idx):
        self._canvases[idx].delete('all')
        self._infos[idx].config(text='—', foreground=C['muted'])


def _run_tests():
    print('=' * 60)
    print('TESTY JEDNOSTKOWE – odwracalność algorytmów')
    print('=' * 60)
    passed = failed = 0
    shapes = [(4, 4, 3), (8, 9, 3), (1, 8, 3), (100, 100, 3), (50, 73, 3)]
    keys = [0, 1, 42, 1337, -5, 999999]
    for shape in shapes:
        img = np.random.randint(0, 256, shape, dtype=np.uint8)
        for key in keys:
            for name, sc, usc in [
                ('Etap1', ImageProcessor.etap1_scramble, ImageProcessor.etap1_unscramble),
                ('Etap2', ImageProcessor.etap2_scramble, ImageProcessor.etap2_unscramble),
                ('Etap3', ImageProcessor.etap3_scramble, ImageProcessor.etap3_unscramble),
            ]:
                s = sc(img, key)
                r = usc(s, key)
                ok = np.array_equal(img, r)
                if ok:
                    passed += 1
                else:
                    failed += 1
                    print(f'FAIL {name} shape={shape} key={key}')
    rows = ImageProcessor.formal_permutation_rows(64, 42, [0, 1, 2, 10])
    formal_ok = all(row['i'] == row['P^-1(P(i))'] for row in rows)
    if formal_ok:
        passed += 1
    else:
        failed += 1
        print('FAIL formal permutation test')
    print(f'\nWynik: {passed} OK | {failed} błędów')
    print('=' * 60)
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    if '--test' in sys.argv:
        _run_tests()
    else:
        App().mainloop()
