"""
Projekt M-II: Chaotyczne przekształcanie obrazu cyfrowego
Szkielet prototypu - do uzupełnienia algorytmami

Struktura:
  - ImageProcessor: klasa z algorytmami (TODO sekcje)
  - App: GUI w Tkinter
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import random
import os


# ─────────────────────────────────────────────
# ALGORYTMY
# ─────────────────────────────────────────────

class ImageProcessor:
    """Wszystkie algorytmy scramblingu / unscramblingu."""

    # ── ETAP 1: Naiwny scrambling (przesuwanie kolumn) ──────────────────────

    @staticmethod
    def etap1_scramble(img_array: np.ndarray, key: int) -> np.ndarray:
        """
        Cykliczne przesunięcie każdej kolumny o offset zależny od klucza i indeksu kolumny.
        offset(col) = (key + col) % height
        """
        result = img_array.copy()
        h, w = img_array.shape[:2]

        for col in range(w):
            offset = (key + col) % h
            result[:, col] = np.roll(img_array[:, col], offset, axis=0)

        return result

    @staticmethod
    def etap1_unscramble(img_array: np.ndarray, key: int) -> np.ndarray:
        """Odwrotność: przesunięcie o -offset."""
        result = img_array.copy()
        h, w = img_array.shape[:2]

        for col in range(w):
            offset = (key + col) % h
            result[:, col] = np.roll(img_array[:, col], -offset, axis=0)

        return result

    # ── ETAP 2: Czysta permutacja zig-zag sterowana kluczem ─────────────────

    @staticmethod
    def _generate_permutation(n: int, seed: int) -> np.ndarray:
        """Fisher-Yates sterowany seedem -> tablica permutacji P[i] = nowy_indeks."""
        rng = np.random.default_rng(seed)
        perm = np.arange(n)
        rng.shuffle(perm)
        return perm

    @staticmethod
    def etap2_scramble(img_array: np.ndarray, key: int) -> np.ndarray:
        """
        Permutacja pikseli (zigzag + seed).
        TODO: zamień na permutację zig-zag z przeskokami zależnymi od klucza.
        Na razie: prosta Fisher-Yates jako placeholder.
        """
        h, w = img_array.shape[:2]
        flat = img_array.reshape(h * w, -1)

        perm = ImageProcessor._generate_permutation(h * w, seed=key)
        scrambled_flat = flat[perm]

        return scrambled_flat.reshape(img_array.shape)

    @staticmethod
    def etap2_unscramble(img_array: np.ndarray, key: int) -> np.ndarray:
        """Odwrotna permutacja: P^-1."""
        h, w = img_array.shape[:2]
        flat = img_array.reshape(h * w, -1)

        perm = ImageProcessor._generate_permutation(h * w, seed=key)
        inv_perm = np.argsort(perm)
        unscrambled_flat = flat[inv_perm]

        return unscrambled_flat.reshape(img_array.shape)

    # ── ETAP 3: Hybryda (permutacja Etap 2 + XOR z maską PRNG) ─────────────

    @staticmethod
    def _generate_xor_mask(shape: tuple, key: int) -> np.ndarray:
        """Maska XOR generowana PRNG z seedem."""
        rng = np.random.default_rng(key + 12345)  # inny seed niż permutacja
        # TODO: rozważ chaotyczny PRNG (np. mapa logistyczna) zamiast numpy
        mask = rng.integers(0, 256, size=shape, dtype=np.uint8)
        return mask

    @staticmethod
    def etap3_scramble(img_array: np.ndarray, key: int) -> np.ndarray:
        """
        1. Permutacja (jak Etap 2)
        2. XOR każdego kanału z maską PRNG
        """
        # Krok 1: permutacja
        permuted = ImageProcessor.etap2_scramble(img_array, key)

        # Krok 2: substytucja XOR
        mask = ImageProcessor._generate_xor_mask(img_array.shape, key)
        result = permuted.astype(np.uint8) ^ mask

        return result

    @staticmethod
    def etap3_unscramble(img_array: np.ndarray, key: int) -> np.ndarray:
        """
        1. Odwrotny XOR (XOR jest samo-odwrotne przy tej samej masce)
        2. Odwrotna permutacja
        """
        # Krok 1: odwrotny XOR
        mask = ImageProcessor._generate_xor_mask(img_array.shape, key)
        de_xored = img_array.astype(np.uint8) ^ mask

        # Krok 2: odwrotna permutacja
        result = ImageProcessor.etap2_unscramble(de_xored, key)

        return result


# ─────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────

IMG_DISPLAY_SIZE = (220, 220)

ETAPY = {
    "Etap 1 – Naiwny (kolumny)": (ImageProcessor.etap1_scramble, ImageProcessor.etap1_unscramble),
    "Etap 2 – Permutacja zig-zag": (ImageProcessor.etap2_scramble, ImageProcessor.etap2_unscramble),
    "Etap 3 – Hybryda (perm + XOR)": (ImageProcessor.etap3_scramble, ImageProcessor.etap3_unscramble),
}


def arr_to_photoimage(arr: np.ndarray) -> ImageTk.PhotoImage:
    img = Image.fromarray(arr.astype(np.uint8))
    img.thumbnail(IMG_DISPLAY_SIZE, Image.LANCZOS)
    return ImageTk.PhotoImage(img)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Projekt M-II – Chaotyczne przekształcanie obrazu")
        self.resizable(True, True)
        self.configure(bg="#1a1a2e")

        self.original_array: np.ndarray | None = None
        self.scrambled_array: np.ndarray | None = None
        self.recovered_array: np.ndarray | None = None

        self._build_ui()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#1a1a2e")
        style.configure("TLabel", background="#1a1a2e", foreground="#e0e0e0", font=("Consolas", 10))
        style.configure("TButton", font=("Consolas", 10, "bold"), padding=6)
        style.configure("Header.TLabel", font=("Consolas", 13, "bold"), foreground="#00d4ff")
        style.configure("Sub.TLabel", font=("Consolas", 9), foreground="#888")
        style.configure("TCombobox", font=("Consolas", 10))

        # ── Nagłówek
        hdr = ttk.Label(self, text="PROJEKT M-II  ·  CHAOTYCZNE PRZEKSZTAŁCANIE OBRAZU",
                        style="Header.TLabel", padding=(16, 12))
        hdr.pack(fill=tk.X)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16)

        # ── Panel kontrolny (lewa strona)
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        ctrl = ttk.Frame(main)
        ctrl.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 16))

        self._build_controls(ctrl)

        # ── Panel obrazów (prawa strona)
        imgs = ttk.Frame(main)
        imgs.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_image_panel(imgs)

        # ── Pasek statusu
        self.status_var = tk.StringVar(value="Wczytaj obraz i wybierz etap.")
        status = ttk.Label(self, textvariable=self.status_var, style="Sub.TLabel", padding=(16, 6))
        status.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_controls(self, parent):
        # Wczytywanie obrazu
        ttk.Label(parent, text="OBRAZ", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 4))
        ttk.Button(parent, text="📂  Wczytaj obraz", command=self._load_image).pack(fill=tk.X)
        self.path_label = ttk.Label(parent, text="(brak)", style="Sub.TLabel", wraplength=180)
        self.path_label.pack(anchor=tk.W, pady=(2, 12))

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # Wybór etapu
        ttk.Label(parent, text="ETAP").pack(anchor=tk.W)
        self.etap_var = tk.StringVar(value=list(ETAPY.keys())[0])
        etap_cb = ttk.Combobox(parent, textvariable=self.etap_var,
                                values=list(ETAPY.keys()), state="readonly", width=26)
        etap_cb.pack(fill=tk.X, pady=(2, 12))

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # Klucz
        ttk.Label(parent, text="KLUCZ (liczba całkowita)").pack(anchor=tk.W)
        self.key_var = tk.StringVar(value="42")
        key_entry = ttk.Entry(parent, textvariable=self.key_var, font=("Consolas", 11), width=14)
        key_entry.pack(anchor=tk.W, pady=(2, 4))

        ttk.Label(parent, text="KLUCZ BŁĘDNY (do testu)").pack(anchor=tk.W, pady=(8, 0))
        self.wrong_key_var = tk.StringVar(value="43")
        wrong_entry = ttk.Entry(parent, textvariable=self.wrong_key_var, font=("Consolas", 11), width=14)
        wrong_entry.pack(anchor=tk.W, pady=(2, 12))

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # Przyciski akcji
        ttk.Button(parent, text="🔀  SCRAMBLE", command=self._do_scramble).pack(fill=tk.X, pady=3)
        ttk.Button(parent, text="🔁  UNSCRAMBLE (poprawny klucz)", command=lambda: self._do_unscramble(correct=True)).pack(fill=tk.X, pady=3)
        ttk.Button(parent, text="❌  UNSCRAMBLE (błędny klucz)", command=lambda: self._do_unscramble(correct=False)).pack(fill=tk.X, pady=3)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        ttk.Button(parent, text="💾  Zapisz wyniki", command=self._save_results).pack(fill=tk.X)

    def _build_image_panel(self, parent):
        """Trzy panele: Oryginał | Scrambled | Odtworzone"""
        labels_text = ["ORYGINAŁ", "PO SCRAMBLINGU", "ODTWORZONE"]
        self.img_labels = []
        self.img_displays = []

        for i, txt in enumerate(labels_text):
            col_frame = ttk.Frame(parent)
            col_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)

            ttk.Label(col_frame, text=txt, style="Header.TLabel").pack(pady=(0, 6))

            # Canvas jako placeholder obrazu
            canvas = tk.Canvas(col_frame, width=IMG_DISPLAY_SIZE[0], height=IMG_DISPLAY_SIZE[1],
                                bg="#0d0d1a", highlightthickness=1, highlightbackground="#333")
            canvas.pack()
            self.img_displays.append(canvas)

            info_lbl = ttk.Label(col_frame, text="—", style="Sub.TLabel")
            info_lbl.pack(pady=(4, 0))
            self.img_labels.append(info_lbl)

    # ── Akcje ────────────────────────────────────────────────────────────────

    def _load_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Obrazy", "*.png *.jpg *.jpeg *.bmp"), ("Wszystkie", "*.*")]
        )
        if not path:
            return

        img = Image.open(path).convert("RGB")
        self.original_array = np.array(img)
        self.scrambled_array = None
        self.recovered_array = None

        self.path_label.config(text=os.path.basename(path))
        self._show_image(0, self.original_array)
        self._clear_image(1)
        self._clear_image(2)
        self.status_var.set(f"Wczytano: {img.width}×{img.height} px")

    def _get_key(self, correct: bool = True) -> int:
        try:
            raw = self.key_var.get() if correct else self.wrong_key_var.get()
            return int(raw)
        except ValueError:
            messagebox.showerror("Błąd", "Klucz musi być liczbą całkowitą.")
            raise

    def _get_algorithm(self):
        return ETAPY[self.etap_var.get()]

    def _do_scramble(self):
        if self.original_array is None:
            messagebox.showwarning("Uwaga", "Najpierw wczytaj obraz.")
            return
        try:
            key = self._get_key(correct=True)
        except ValueError:
            return

        scramble_fn, _ = self._get_algorithm()
        self.status_var.set("Scrambling...")
        self.update()

        self.scrambled_array = scramble_fn(self.original_array, key)
        self._show_image(1, self.scrambled_array)
        self._clear_image(2)
        self.img_labels[1].config(text=f"klucz: {key}")
        self.status_var.set(f"Scramble gotowy. Etap: {self.etap_var.get().split('–')[0].strip()}")

    def _do_unscramble(self, correct: bool):
        if self.scrambled_array is None:
            messagebox.showwarning("Uwaga", "Najpierw wykonaj scramble.")
            return
        try:
            key = self._get_key(correct=correct)
        except ValueError:
            return

        _, unscramble_fn = self._get_algorithm()
        self.status_var.set("Unscrambling...")
        self.update()

        self.recovered_array = unscramble_fn(self.scrambled_array, key)
        self._show_image(2, self.recovered_array)
        tag = "✓ poprawny" if correct else "✗ błędny"
        self.img_labels[2].config(text=f"klucz: {key}  [{tag}]")
        self.status_var.set(f"Unscramble gotowy. Użyty klucz: {key}  [{tag}]")

    def _save_results(self):
        if all(a is None for a in [self.original_array, self.scrambled_array, self.recovered_array]):
            messagebox.showwarning("Uwaga", "Brak obrazów do zapisania.")
            return

        folder = filedialog.askdirectory(title="Wybierz folder zapisu")
        if not folder:
            return

        for name, arr in [("oryginal.png", self.original_array),
                           ("scrambled.png", self.scrambled_array),
                           ("recovered.png", self.recovered_array)]:
            if arr is not None:
                Image.fromarray(arr.astype(np.uint8)).save(os.path.join(folder, name))

        self.status_var.set(f"Zapisano do: {folder}")
        messagebox.showinfo("Zapisano", f"Obrazy zapisane do:\n{folder}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _show_image(self, idx: int, arr: np.ndarray):
        photo = arr_to_photoimage(arr)
        canvas = self.img_displays[idx]
        canvas._photo = photo  # trzymaj referencję
        canvas.delete("all")
        x, y = IMG_DISPLAY_SIZE[0] // 2, IMG_DISPLAY_SIZE[1] // 2
        canvas.create_image(x, y, anchor=tk.CENTER, image=photo)

    def _clear_image(self, idx: int):
        canvas = self.img_displays[idx]
        canvas.delete("all")
        self.img_labels[idx].config(text="—")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
