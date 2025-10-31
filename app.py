import pandas as pd
import streamlit as st

# --- 0. Configuration et Initialisation ---
st.set_page_config(layout="wide", page_title="Tableau de Données Complet") 

# --- Chemin d'accès du fichier ---
EXCEL_FILE_PATH = 'data/Liste des lots.xlsx' 
REF_COL = 'Référence annonce' 

# --- Fonction de Chargement des Données (Nettoyage Maximal et Cache) ---
@st.cache_data
def load_data(file_path):
    try:
        # Lire le fichier en forçant la colonne REF_COL en chaîne de caractères
        df = pd.read_excel(file_path, dtype={REF_COL: str})
        
        # Nettoyage des noms de colonnes
        df.columns = df.columns.str.strip() 
        
        # SÉCURISATION MAXIMALE DE LA COLONNE DE RÉFÉRENCE:
        if REF_COL in df.columns:
            df[REF_COL] = df[REF_COL].astype(str).str.strip()
            # Supprime tout '.0' ou partie décimale
            df[REF_COL] = df[REF_COL].apply(lambda x: x.split('.')[0] if isinstance(x, str) else str(x).split('.')[0])
            # Force le format 5 chiffres avec des zéros en tête
            df[REF_COL] = df[REF_COL].str.zfill(5) 
        
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"❌ Erreur critique lors du chargement: {e}"

# --- Chargement des données ---
data_df, error_message = load_data(EXCEL_FILE_PATH)

# --- 1. Affichage Principal ---
st.title("Liste Complète des Lots Immobiliers")
st.markdown("---")

if error_message:
    st.error(error_message)
elif data_df.empty:
    st.warning("Le DataFrame est vide. Vérifiez si votre fichier Excel contient des données.")
else:
    st.header(f"Tableau de Données (Total : {len(data_df)} lots)")
    st.info("Ce tableau interactif affiche toutes les colonnes et permet le tri et le filtrage.")
    
    # Affichage du tableau interactif
    st.dataframe(
        data_df, 
        use_container_width=True, 
        height=700 # Hauteur fixe pour une meilleure expérience
    )
    
    st.markdown("---")
    
    # Option d'exportation (utilité supplémentaire)
    @st.cache_data
    def convert_df_to_csv(df):
        # IMPORTANT : Utilise 'sep=;' pour la compatibilité avec Excel/français
        return df.to_csv(index=False, sep=';').encode('utf-8')

    csv = convert_df_to_csv(data_df)

    st.download_button(
        label="Télécharger les données en CSV",
        data=csv,
        file_name='Liste_Lots_Export.csv',
        mime='text/csv',
    )
