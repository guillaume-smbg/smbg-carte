# SMBG Carte — Starter

Ce répertoire contient les fichiers de démarrage pour l'application SMBG Carte.

## Étapes rapides

1. **Créer les comptes** : GitHub → Streamlit Cloud → Supabase → Cloudflare R2.
2. **Supabase** : dans l'onglet **SQL**, exécute `supabase_schema.sql`. Crée un bucket **attachments** (privé).
3. **Cloudflare R2** : crée un bucket **smbg-photos** (public) et envoie 1–2 dossiers d'annonces de test.
4. **Excel** : utilise `data/Excel_template_SMBG.xlsx` comme base. Héberge ce fichier (GitHub raw ou Supabase Storage public).
5. **Secrets Streamlit** : renseigne `SUPABASE_URL`, `SUPABASE_KEY`, `EXCEL_URL`, `R2_BASE_URL`.
6. **Déploiement** : pousse ce dossier sur GitHub, puis lance l'app via Streamlit Cloud (New app).

## Fichiers
- `requirements.txt` — dépendances Python.
- `schema.yaml` — mapping des colonnes et règles d'affichage (volet droit, techniques, filtres).
- `supabase_schema.sql` — tables Supabase (contacts, events, approvals, etc.).
- `app.py` — squelette d'application Streamlit (à compléter si besoin).
- `data/Excel_template_SMBG.xlsx` — modèle Excel à remplir.
- `assets/` — place ici Logo Bleu, Slogan Bleu, et la police Futura (.ttf/.otf).
- `.streamlit/` — dossier de config local (facultatif).

## Remarques
- Les colonnes **G→AF** s'affichent dans le volet droit, **H** est un **bouton 'Cliquer ici'** pour Google Maps.
- Les colonnes techniques **AG→AM** ne s'affichent pas (sauf **Référence annonce** en cartouche) :
  - AG: Latitude, AH: Longitude, AI: Géocodage statut, AJ: Géocodage date, AK: Référence annonce,
    AL: Photos annonce (URLs `|`), AM: Actif (oui/non).
- Les valeurs `"/"`, `"-"`, vide sont masquées côté rendu.
- Mode **client** : colonnes loyers **N/O/P** remplacées par **'Demander le loyer'** ; Mode **interne** : loyers visibles.
- Filtres **Région/Département** dynamiques basés uniquement sur les valeurs présentes dans l'Excel.

> Généré le 2025-10-13 15:34
