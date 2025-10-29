# Sukiyaki - Japanese Vocabulary OCR & Anki Deck Generator

Sukiyaki is a desktop tool to extract Japanese vocabulary from images, fetch meanings and examples, and automatically generate Anki decks.

---

## Features

### OCR and Image Processing
- Recognizes Japanese text from images (`.png`, `.jpg`, `.jpeg`) using **Tesseract OCR**.
- Copies images to a temporary folder to avoid permission issues.
- Supports selecting multiple images at once.
- Drag & drop support for easy workflow.

<img width="896" height="694" alt="image" src="https://github.com/user-attachments/assets/aabc899f-42e2-4b08-8f8d-4ed481fcd3f6" />


---

### Tokenization and Analysis
- Extracts **key words**: nouns, verbs, and adjectives (`名詞`, `動詞`, `形容詞`).
- Uses **SudachiPy** for tokenization and reading analysis.
- Queries **Jisho API** for English meanings.
- Fetches usage examples from **Tatoeba**.

---

### Vocabulary Management
- Saves detected vocabulary in **SQLite** (`vocabulario.db`).
- Avoids duplicates and updates existing entries.
- Editable table interface to review and modify entries before saving.

**Sample Table:**
| Lemma | Reading | Meaning | Example JP | Example EN |
|-------|---------|---------|------------|------------|
| 食べる | たべる | to eat | ご飯を食べる | I eat rice |

---

### Anki Integration
- Automatically generates **Anki decks** from detected vocabulary.
- Each note includes: word, reading, meaning, and examples in Japanese and English.
- Saves the `.apkg` file in the `anki` folder of the project.

<img width="960" height="752" alt="image" src="https://github.com/user-attachments/assets/328e23fa-e5df-4b98-a49d-7730785d1dc4" />









