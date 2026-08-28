# Problemi richiesti all'inizio

## Problema 3 — Restyle autentico della mappa + fix sprite Surf
- Ponti, strade, erba, interni casa e caverna al momento sono fatti si con tile veri della rom ma scelti e assemblati da me "a occhio". vorrei ricostruire quelli veri, hai la rom reversata in ../../pokefirered serve un modello che sappia leggere le immagini per capire quello che stai facendo. 
- Fix dello sprite di Surf a sinistra/destra (deve guardare nella direzione giusta, con il "blob" del mount visibile sotto il player).

---

## Direttive finali aggiunte dopo
- Guardare i progetti online per capire **come fanno a prendere gli asset** dal gioco (es. porymap/porytiles).
- **Niente contenuti protetti da copyright** nei file del progetto: niente stringhe tipo "pokefirered", niente path locali della mia macchina, niente dicitura tipo "authentic firered tileset" (es. lo avevo scritto in tile_render).

PER DOPO:
- **Decoupling degli offset:** tutti i file che contengono offset devono leggere da un **JSON con tutti gli offset per quella specifica ROM**, così in futuro potrò far funzionare il progetto con un'altra ROM cambiando solo quel file.