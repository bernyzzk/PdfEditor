# PdfEditor

Application locale Windows et macOS en Python, inspirée des éditeurs PDF desktop modernes.

![Icône PdfEditor](assets/pdfeditor-512.png)

## Télécharger

[Télécharger la dernière version Windows de PdfEditor](https://github.com/bernyzzk/PdfEditor/releases/latest)

La version macOS est fournie sous forme de fichier DMG dans les releases GitHub.

## Fonctions disponibles

- ouverture et rendu PDF local haute définition avec miniatures et cache ;
- navigation, sélection de page et zoom ;
- ajout de texte ;
- modification d'un bloc texte existant par double-clic ;
- détection de la police, de la taille et de la couleur du texte sélectionné ;
- analyse et affichage des zones texte, image et graphique en mode sélection ;
- sélection, déplacement, redimensionnement à huit poignées et suppression des objets ;
- copier-coller de texte, d'image ou de sélection graphique ;
- inspecteur de mise en page pour régler précisément position, largeur et hauteur ;
- ajout et remplacement d'images ;
- ajout de liens web par zone ;
- dessin libre et surlignage compatibles PDF ;
- insertion d'une signature PNG/JPG ;
- tampons prédéfinis ou personnalisés avec texte, date automatique et logo transparent ;
- rotation, suppression et réorganisation des pages par glisser-déposer ;
- fusion de plusieurs PDF et extraction de la page actuelle ;
- recherche de texte ;
- redaction manuelle par gomme ou automatique par terme ;
- OCR local français/anglais des pages scannées ;
- déplacement et redimensionnement d'objets texte ou image en mode sélection ;
- rotation de l'objet sélectionné ;
- bibliothèque de modèles de signature avec réglage de l'opacité ;
- réutilisation de la police embarquée lors de la modification quand elle est extractible ;
- annulation/rétablissement sur 20 opérations ;
- export d'un nouveau PDF sans envoi réseau.

## Installation et lancement

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

## Générer l'application Windows

```powershell
.\build_windows.ps1
```

L'exécutable autonome est créé dans `dist\PdfEditor 0.6.0\PdfEditor.exe`.

Pour générer l'installateur Windows :

```powershell
.\build_installer.ps1
```

L'installateur est créé dans `dist\installer\PdfEditor-Setup-0.6.0.exe`.

## Générer l'application macOS

Sur un Mac :

```bash
bash build_macos.sh
```

Le disque d'installation est créé dans `dist/PdfEditor-0.7.0-macOS.dmg`.

## Signature Windows

L'éditeur Windows est `Zouzouko Bernard`. Pour supprimer l'avertissement
« éditeur inconnu », la construction accepte un certificat Authenticode reconnu :

```powershell
$env:PDFEDITOR_CERTIFICATE="C:\certificats\zouzouko-bernard.pfx"
$env:PDFEDITOR_CERTIFICATE_PASSWORD="mot-de-passe"
.\build_installer.ps1
```

Microsoft SmartScreen peut conserver un avertissement de réputation pendant les
premiers téléchargements, même avec un certificat standard. Un certificat EV réduit
généralement ce délai.

## Utilisation

1. Ouvrir un PDF avec `Ctrl+O`.
2. Choisir `Texte`, `Crayon`, `Surligner` ou `Signature`.
3. Avec l'outil texte, cliquer sur la page, saisir directement puis valider avec
   `Ctrl+Entrée`.
4. Avec la main de sélection, cliquer un objet, le déplacer ou utiliser ses huit poignées.
5. Double-cliquer un texte pour le modifier directement sur la page.
6. Utiliser `Ctrl+C` et `Ctrl+V` pour dupliquer un objet.
7. Utiliser la gomme pour effacer définitivement l'objet sous le pointeur.
8. Réorganiser les pages en faisant glisser les miniatures.
9. Exporter avec `Ctrl+S`.

## Limites de cette première version

La modification de texte supprime le bloc sélectionné puis réinsère le nouveau contenu
avec la police embarquée extraite du PDF, ou sa meilleure correspondance Windows.
Les PDF contenant des effets graphiques, des polices non extractibles ou des paragraphes composés caractère par
caractère restent limités par le moteur PyMuPDF.

## Licence du moteur

PyMuPDF est proposé sous licence AGPL ou licence commerciale Artifex. Avant de
distribuer une version propriétaire de l'application, il faut acquérir la licence
adaptée ou remplacer le moteur dans `pdf_editor/model.py`.
