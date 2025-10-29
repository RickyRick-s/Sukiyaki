import os
import sys
import time
import sqlite3
import requests
from pathlib import Path
from PIL import Image
import pytesseract
import genanki
from sudachipy import tokenizer, dictionary

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QTextEdit, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QIcon, QPixmap




BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

OUTPUT_DIR = APP_DIR / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = OUTPUT_DIR / "vocabulario.db"
CAPTURAS_DIR = OUTPUT_DIR / "capturas"
CAPTURAS_DIR.mkdir(exist_ok=True)
ANKI_DIR = OUTPUT_DIR / "anki"
ANKI_DIR.mkdir(exist_ok=True)


if sys.platform == "darwin":
    
    if Path(BASE_DIR, "icons", "icono.icns").exists():
        ICON_PATH = str(Path(BASE_DIR) / "icons" / "icono.icns")
    elif Path(BASE_DIR, "icons", "icono.png").exists():
        ICON_PATH = str(Path(BASE_DIR) / "icons" / "icono.png")
    else:
        ICON_PATH = ""
elif sys.platform.startswith("win"):
    
    if Path(BASE_DIR, "icons", "icono.ico").exists():
        ICON_PATH = str(Path(BASE_DIR) / "icons" / "icono.ico")
    else:
        ICON_PATH = str(Path(BASE_DIR) / "icons" / "icono.png")
else:
    ICON_PATH = str(Path(BASE_DIR) / "icons" / "icono.png")

SUYAKI_ICON = str(Path(BASE_DIR) / "icons" / "sukiyaki.png")


important_pos = ['名詞', '動詞', '形容詞']

tokenizer_obj = dictionary.Dictionary().create()
mode = tokenizer.Tokenizer.SplitMode.A

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS palabras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma TEXT,
    reading TEXT,
    meaning TEXT,
    example_ja TEXT,
    example_en TEXT
)
''')
conn.commit()


cur.execute("PRAGMA table_info(palabras)")
cols = cur.fetchall()
lemmas_unique = any(c[1]=='lemma' and c[5]==1 for c in cols)
if not lemmas_unique:
    cur.execute('''
    CREATE TABLE IF NOT EXISTS palabras_tmp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lemma TEXT UNIQUE,
        reading TEXT,
        meaning TEXT,
        example_ja TEXT,
        example_en TEXT
    )
    ''')
    cur.execute('''
    INSERT OR IGNORE INTO palabras_tmp (lemma, reading, meaning, example_ja, example_en)
    SELECT lemma, reading, meaning, example_ja, example_en FROM palabras
    ''')
    cur.execute("DROP TABLE palabras")
    cur.execute("ALTER TABLE palabras_tmp RENAME TO palabras")
    conn.commit()


def show_custom_message(parent, text, title="すき焼き"):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)

    
    if ICON_PATH and Path(ICON_PATH).exists():
        msg.setWindowIcon(QIcon(ICON_PATH))

    
    if Path(SUYAKI_ICON).exists():
        icon = QPixmap(SUYAKI_ICON)
        msg.setIconPixmap(icon.scaled(80, 100))
    return msg.exec()


def query_jisho(word, retries=2, delay=2):
    url = f"https://jisho.org/api/v1/search/words?keyword={word}"
    for _ in range(retries + 1):
        try:
            r = requests.get(url, timeout=7)
            r.raise_for_status()
            return r.json().get("data", [])
        except Exception:
            time.sleep(delay)
    return []

def get_example_from_tatoeba(word, retries=2, delay=2):
    url = f"https://tatoeba.org/es/api_v0/search?from=jpn&to=eng&query={word}&orphans=no&unapproved=no&sort=random"
    for _ in range(retries + 1):
        try:
            r = requests.get(url, timeout=7)
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            if not results:
                return "", ""
            example_ja = results[0].get("text", "").strip()
            translations = results[0].get("translations", [])
            example_en = ""
            for group in translations:
                if isinstance(group, list):
                    for t in group:
                        if t.get("lang") == "eng":
                            example_en = t.get("text", "").strip()
                            break
                if example_en:
                    break
            return example_ja, example_en
        except Exception:
            time.sleep(delay)
    return "", ""


def process_text(text):
    vocab = {}
    tokens = tokenizer_obj.tokenize(text, mode)
    for t in tokens:
        lemma = t.dictionary_form()
        lectura = t.reading_form()
        pos = t.part_of_speech()[0]
        if pos not in important_pos or lemma in vocab:
            continue

        data = query_jisho(lemma)
        if data:
            entry = data[0]
            jp_word = entry["japanese"][0].get("word", lemma)
            jp_reading = entry["japanese"][0].get("reading", lectura)
            meanings = ", ".join(entry["senses"][0]["english_definitions"])
        else:
            jp_word = lemma
            jp_reading = lectura
            meanings = ""

        example_ja, example_en = get_example_from_tatoeba(lemma)
        vocab[lemma] = {
            "lemma": jp_word,
            "reading": jp_reading,
            "meaning": meanings,
            "example_ja": example_ja,
            "example_en": example_en
        }
    return list(vocab.values())

def process_image(img_path):
    try:
        text = pytesseract.image_to_string(Image.open(img_path), lang="jpn")
    except Exception:
        return "", []
    tokens = process_text(text)
    return text, tokens

def save_to_db(tokens_table, parent=None):
    for row in range(tokens_table.rowCount()):
        lemma = tokens_table.item(row, 0).text()
        reading = tokens_table.item(row, 1).text()
        meaning = tokens_table.item(row, 2).text()
        example_ja = tokens_table.item(row, 3).text()
        example_en = tokens_table.item(row, 4).text()

        try:
            cur.execute('''
                INSERT INTO palabras (lemma, reading, meaning, example_ja, example_en)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(lemma) DO UPDATE SET
                    reading=excluded.reading,
                    meaning=excluded.meaning,
                    example_ja=excluded.example_ja,
                    example_en=excluded.example_en
            ''', (lemma, reading, meaning, example_ja, example_en))
        except Exception as e:
            print(f"Error al insertar/actualizar {lemma}: {e}")
    conn.commit()
    
    msg = QMessageBox(parent)
    msg.setWindowTitle("すき焼き")
    msg.setText("Vocabulary successfully saved to the database.")
    
    if Path(SUYAKI_ICON).exists():
        icon = QPixmap(SUYAKI_ICON)
        msg.setIconPixmap(icon.scaled(80, 100))
    msg.exec()


def generate_anki_deck(db_conn):
    deck = genanki.Deck(2059400110, "Deck すき焼き")
    model = genanki.Model(
        1607392319,
        'Basic Japanese Model',
        fields=[
            {'name': 'Palabra'},
            {'name': 'Lectura'},
            {'name': 'Significado'},
            {'name': 'Ejemplo_JP'},
            {'name': 'Ejemplo_EN'}
        ],
        templates=[{
            'name': 'Card 1',
            'qfmt': '{{Palabra}}<br>({{Lectura}})',
            'afmt': '{{FrontSide}}<hr id="answer">{{Significado}}<br><br>{{Ejemplo_JP}}<br><i>{{Ejemplo_EN}}</i>'
        }]
    )
    cur = db_conn.cursor()
    cur.execute("SELECT lemma, reading, meaning, example_ja, example_en FROM palabras")
    for row in cur.fetchall():
        deck.add_note(genanki.Note(
            model=model,
            fields=[row[0], row[1], row[2], row[3] or "", row[4] or ""]
        ))
    filename = ANKI_DIR / "すき焼き.apkg"
    genanki.Package(deck).write_to_file(str(filename))
    return filename


class VocabApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("すき焼き")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(900, 700)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.layout = QVBoxLayout(main_widget)

        
        self.btn_select = QPushButton("Select an image")
        self.btn_research = QPushButton("Search Jisho")
        self.btn_save = QPushButton("Save")
        self.btn_anki = QPushButton("Generate Anki deck")
        for btn in [self.btn_select, self.btn_research, self.btn_save, self.btn_anki]:
            self.layout.addWidget(btn)

        self.btn_select.clicked.connect(self.select_images)
        self.btn_research.clicked.connect(self.research_text)
        self.btn_save.clicked.connect(lambda: save_to_db(self.vocab_table, self))
        self.btn_anki.clicked.connect(self.make_anki)

        
        self.ocr_text = QTextEdit()
        self.layout.addWidget(QLabel("Detected text:"))
        self.layout.addWidget(self.ocr_text)
        self.ocr_text.installEventFilter(self)
        self.zoom_factor = 1.0

        
        self.vocab_table = QTableWidget()
        self.vocab_table.setColumnCount(5)
        self.vocab_table.setHorizontalHeaderLabels(
            ["Lemma", "Reading", "Meaning", "Example JP", "Example EN"]
        )
        self.vocab_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.vocab_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.layout.addWidget(QLabel("Detected vocabulary:"))
        self.layout.addWidget(self.vocab_table)

    def eventFilter(self, obj, event):
        if obj == self.ocr_text:
            if event.type() == QEvent.Wheel and QApplication.keyboardModifiers() == Qt.ControlModifier:
                delta = event.angleDelta().y()
                if delta > 0:
                    self.ocr_text.zoomIn(1)
                else:
                    self.ocr_text.zoomOut(1)
                return True
        return super().eventFilter(obj, event)

    def add_tokens_to_table(self, tokens):
        existing = {self.vocab_table.item(r, 0).text() for r in range(self.vocab_table.rowCount()) if self.vocab_table.item(r,0)}
        for t in tokens:
            if t["lemma"] in existing:
                continue
            row = self.vocab_table.rowCount()
            self.vocab_table.insertRow(row)
            items = [QTableWidgetItem(t[k]) for k in ["lemma","reading","meaning","example_ja","example_en"]]
            for item in items:
                item.setTextAlignment(Qt.AlignCenter)
            for col, item in enumerate(items):
                self.vocab_table.setItem(row, col, item)

    def select_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select images", "", "Images (*.png *.jpg *.jpeg)")
        if not files:
            return
        self.ocr_text.clear()
        self.vocab_table.setRowCount(0)
        seen = set()
        for img_path in files:
            text, tokens = process_image(img_path)
            self.ocr_text.append(text + "\n")
            for t in tokens:
                if t["lemma"] in seen:
                    continue
                seen.add(t["lemma"])
                self.add_tokens_to_table([t])

    def research_text(self):
        text = self.ocr_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Warning", "No text to search.")
            return
        show_custom_message(self, "The chef is cooking, please be patient...")
        tokens = process_text(text)
        self.add_tokens_to_table(tokens)

    def make_anki(self):
        filename = generate_anki_deck(conn)
        show_custom_message(self, f"Anki deck generated: {filename}", "Deck generated")


if __name__ == "__main__":
    app = QApplication([])
  
    if ICON_PATH and Path(ICON_PATH).exists():
        app.setWindowIcon(QIcon(ICON_PATH))
    window = VocabApp()
    window.show()
    app.exec()
