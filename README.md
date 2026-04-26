# Projekt M-II – Chaotyczne przekształcanie obrazu cyfrowego

Projekt został przygotowany jako eksperyment dydaktyczny pokazujący mechanizmy przekształcania obrazu cyfrowego, a nie jako bezpieczny algorytm szyfrowania. Celem pracy jest porównanie działania trzech etapów przekształcania obrazu, analiza ich odwracalności, wpływu klucza oraz pokazanie, dlaczego wizualny chaos nie oznacza bezpieczeństwa. [file:1]

## Cel projektu

Projekt ma pokazać w praktyce:
- różnicę między permutacją a substytucją,
- rolę klucza i parametrów w algorytmie,
- czym jest i czym nie jest chaos oraz pseudo-losowość,
- dlaczego wizualny chaos nie jest równoznaczny z ochroną danych. [file:1]

Zgodnie z wymaganiami projekt składa się z trzech etapów, z których każdy musi mieć poprawny algorytm scramblingu, osobno opisany algorytm odwrotny oraz pełną odwracalność przy poprawnym kluczu. [file:1]

## Struktura rozwiązania

W projekcie zaimplementowano trzy etapy analizy obrazu:

### Etap 1 – Naiwny scrambling

Pierwszy etap realizuje prosty, w pełni odwracalny scrambling oparty na cyklicznym przesuwaniu kolumn obrazu. Jest to celowo słaba metoda, której zadaniem jest pokazanie, że część struktur obrazu może pozostać widoczna nawet po przekształceniu lub po użyciu błędnego klucza. [file:1][file:2]

### Etap 2 – Czysta permutacja sterowana kluczem

Drugi etap realizuje czystą permutację pikseli bez zmiany ich wartości. W implementacji wykorzystywana jest linearyzacja obrazu oraz permutacja sterowana kluczem, a następnie jawnie wyznaczana jest funkcja odwrotna permutacji, co pozwala sprawdzić formalnie zależność \(P^{-1}(P(i)) = i\). [file:1][file:2]

### Etap 3 – Mechanizm wzmacniający

Trzeci etap rozszerza etap drugi o mechanizm modyfikujący wartości pikseli. W zastosowanej wersji użyto hybrydy: permutacji oraz operacji XOR z maską generowaną pseudolosowo z klucza, przy zachowaniu pełnej odwracalności dla poprawnego klucza. [file:1][file:2]

## Funkcje aplikacji

Aplikacja posiada graficzny interfejs użytkownika przygotowany do eksperymentów i analizy wyników. Umożliwia on:
- wczytanie obrazu z pliku,
- wybór etapu 1, 2 lub 3,
- podanie poprawnego i błędnego klucza,
- wykonanie operacji Scramble oraz Unscramble,
- jednoczesne wyświetlenie obrazu oryginalnego, przekształconego i odtworzonego,
- zapis wyników do plików,
- wykonanie testu formalnego dla permutacji,
- podgląd metryk i raportu tekstowego. [file:1][file:2]

Interfejs zawiera również logo uczelni w lewym górnym rogu oraz sekcję raportową ułatwiającą przygotowanie dokumentacji i zrzutów ekranu do prezentacji. [file:2]

## Wymagania

Do uruchomienia projektu wymagany jest Python 3 oraz biblioteki:
- `numpy`,
- `Pillow`,
- `tkinter`.

Przykładowa instalacja zależności:

```bash
pip install numpy pillow
```

`tkinter` w wielu instalacjach Pythona dostępny jest domyślnie. [file:2]

## Uruchomienie

Uruchomienie aplikacji:

```bash
python main_with_logo.py
```

Uruchomienie testów odwracalności:

```bash
python main_with_logo.py --test
```

Aby logo było poprawnie wczytane, plik `logo.png` lub `logo.jpg` powinien znajdować się w tym samym folderze co plik programu. [file:2]

## Przykładowy przebieg użycia

1. Wczytać obraz lub wygenerować obraz testowy.
2. Wybrać etap algorytmu.
3. Wprowadzić poprawny klucz oraz klucz błędny.
4. Uruchomić `Scramble`.
5. Sprawdzić wynik dla poprawnego i błędnego `Unscramble`.
6. Odczytać metryki oraz test formalny permutacji.
7. Zapisać wyniki do plików. [file:1][file:2]

## Metryki i analiza

Projekt przewiduje analizę eksperymentalną zgodną z wymaganiami zadania. W aplikacji i dokumentacji można analizować między innymi:
- korelację sąsiednich pikseli przed i po scramblingu,
- różnicę obrazu po użyciu błędnego klucza,
- pełną odwracalność dla poprawnego klucza,
- porównanie etapów 1, 2 i 3 pod kątem utraty struktury obrazu. [file:1]

## Ograniczenia projektu

Projekt nie jest bezpiecznym systemem kryptograficznym. Jego celem jest analiza dydaktyczna i pokazanie ograniczeń prostych metod przekształcania obrazu. W szczególności sama permutacja nie zapewnia bezpieczeństwa, a wizualnie chaotyczny wynik nie oznacza odporności na analizę. [file:1]

## Pliki projektu

Przykładowa struktura katalogu:

```text
Image enc & dec/
├── main_with_logo.py
├── logo.png / logo.jpg
├── README.md
└── przykładowe obrazy testowe
```

## Autor i przeznaczenie

Projekt został przygotowany w ramach przedmiotu Projekt M-II jako aplikacja analityczna do demonstracji działania odwracalnych metod przekształcania obrazu cyfrowego. [file:1]
