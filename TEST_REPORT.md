# Rapport de validation fonctionnelle

Version testée : PdfEditor 0.4.0

La suite automatisée couvre les parcours suivants :

- ouverture et rendu PDF ;
- ajout et modification directe du texte ;
- détection et réutilisation d'une police Calibri embarquée ;
- sélection, déplacement et redimensionnement de texte ;
- ajout, remplacement, déplacement et redimensionnement d'image ;
- rendu haute définition, cache de rendu et cache d'analyse des objets ;
- affichage des zones modifiables, huit poignées et inspecteur de mise en page ;
- copier-coller de texte et d'image ;
- dessin, surlignage, lien, gomme et redaction ;
- rotation, suppression, réorganisation, fusion et extraction de pages ;
- annulation, rétablissement et export PDF ;
- OCR local d'une page scannée générée pour le test ;
- conversion puis réouverture de fichiers Word, Excel et PowerPoint ;
- utilisation de l'éditeur de texte directement sur le canevas.

Résultat automatisé : **6 scénarios réussis sur 6**.

Le test réel Clockify confirme également le déplacement/redimensionnement du titre,
la copie d'une image, son collage à un nouvel emplacement et la réouverture du PDF
exporté. Cent lectures successives des objets mis en cache prennent environ 0,0003 s.

Le test de non-régression des polices modifie un texte Arial sous-ensemble avec
des caractères français et le symbole euro, puis le déplace, l'exporte et le
réouvre. Le rendu final ne contient plus de carrés.

Le PDF Clockify fourni a également été utilisé comme test réel. Sa page était tournée
à 90 degrés tout en conservant des coordonnées d'objets non tournées. L'application
normalise maintenant automatiquement ce type de page. Le titre, les chiffres du
tableau, le total et le logo ont été modifiés ou déplacés, exportés puis vérifiés
visuellement.

Une passe complémentaire a ouvert et rendu 8 PDF réels présents dans le dossier
Téléchargements. Chaque fichier a été rendu, ses objets ont été détectés, puis un bloc
texte a été réécrit dans une copie exportée et réouverte avec succès : **8 sur 8**.

Commande de validation :

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest -q
```

Limite technique restante : un PDF n'est pas un document Word. Les objets complexes
composés de glyphes individuels, masques, transparences ou polices non extractibles
peuvent nécessiter un moteur PDF commercial spécialisé pour une fidélité parfaite.
