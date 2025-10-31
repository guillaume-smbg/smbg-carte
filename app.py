<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Carte Interactive Immo - SMBG</title>
    <!-- Chargement de Tailwind CSS pour le style -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Chargement de la librairie Leaflet pour la carte OSM -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
    <!-- Configuration de la police Inter -->
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            overflow: hidden; /* Empêche tout défilement */
        }
    </style>
</head>
<body class="bg-gray-50">

    <!-- Conteneur principal - Prend toute la fenêtre, non défilant -->
    <div id="app" class="flex h-screen overflow-hidden">

        <!-- 1. Panneau Gauche (Filtres/Navigation) - Largeur fixe 275px -->
        <div id="left-panel" class="w-[275px] flex-shrink-0 bg-blue-900 text-white shadow-2xl p-6 overflow-y-auto">
            <h1 class="text-3xl font-bold mb-6 text-yellow-500 border-b-4 border-yellow-600 pb-2">
                Carte SMBG Immo
            </h1>
            <p class="text-sm opacity-80 mb-6">
                Panneau de navigation et de filtres (à développer).
            </p>
            
            <div id="filter-controls" class="space-y-4">
                <div class="bg-blue-800 p-3 rounded-lg">
                    <h2 class="font-semibold text-lg mb-2 text-yellow-300">Statistiques</h2>
                    <p class="text-sm">Total Annonces : <span id="total-count" class="font-bold">0</span></p>
                    <p class="text-sm">Annonces sur Carte : <span id="visible-count" class="font-bold">0</span></p>
                </div>

                <!-- Simuler un contrôle de filtre -->
                <div class="bg-blue-800 p-3 rounded-lg">
                    <h2 class="font-semibold text-lg mb-2 text-yellow-300">Typologie</h2>
                    <select id="typo-filter" class="w-full p-2 rounded-md bg-blue-700 text-white focus:ring-yellow-500 focus:border-yellow-500 transition">
                        <option value="all">Toutes les typologies</option>
                    </select>
                </div>

                <!-- Bouton de Reset -->
                <button onclick="resetMapAndSelection()" class="w-full py-3 bg-yellow-500 hover:bg-yellow-600 text-blue-900 font-bold rounded-xl transition duration-300 shadow-md">
                    Réinitialiser la carte
                </button>
            </div>
        </div>

        <!-- 2. Conteneur principal pour la carte et le panneau droit -->
        <div class="relative flex-grow">
            <!-- La carte prend tout l'espace restant -->
            <div id="map-container" class="h-full w-full"></div>

            <!-- 3. Panneau Droit (Détails) - Volet rétractable 275px -->
            <!-- Positionné absolument à droite, caché par défaut (translate-x-full) -->
            <div id="right-panel" class="absolute top-0 right-0 w-[275px] h-full bg-white shadow-2xl transform translate-x-full transition-transform duration-500 ease-in-out z-50 p-6 overflow-y-auto">
                
                <!-- Bouton de fermeture -->
                <button onclick="closeDetailPanel()" class="absolute top-4 right-4 p-2 bg-gray-200 hover:bg-gray-300 rounded-full transition">
                    <svg class="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
                
                <h2 class="text-2xl font-bold mb-4 text-blue-900">
                    <span id="detail-ref" class="text-yellow-600"></span>
                </h2>

                <div id="detail-content" class="space-y-4">
                    <!-- Les détails du lot seront injectés ici -->
                </div>

                <!-- Bouton Google Maps -->
                <a id="google-maps-btn" target="_blank" class="mt-8 block w-full text-center py-3 bg-red-600 hover:bg-red-700 text-white font-bold rounded-xl transition duration-300 shadow-lg">
                    Voir sur Google Maps
                </a>
                
                <!-- Bouton de Contact -->
                <button class="mt-3 block w-full text-center py-3 border border-blue-900 text-blue-900 hover:bg-blue-50 font-bold rounded-xl transition duration-300">
                    Contacter l'équipe
                </button>
            </div>
        </div>
        
        <!-- Conteneur pour la boîte de message personnalisée (à la place d'alert) -->
        <div id="message-box" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100] hidden">
            <div class="bg-white p-6 rounded-xl shadow-2xl max-w-sm w-full">
                <h3 id="message-title" class="text-xl font-bold mb-3 text-red-600"></h3>
                <p id="message-text" class="text-gray-700 mb-4"></p>
                <button onclick="document.getElementById('message-box').classList.add('hidden')" class="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition">Fermer</button>
            </div>
        </div>
    </div>

    <!-- Script principal -->
    <script>
        // CORRECTION: Utilisation du nom exact du fichier et encodage pour l'URL
        const DATA_FILE_PATH = 'Liste des lots.xlsx - Tableau recherche.csv';
        // Colonnes essentielles pour la carte et les détails
        const REQUIRED_COLUMNS = [
            'Référence annonce', 'Latitude', 'Longitude', 'Ville', 'Adresse', 
            'Surface GLA', 'Loyer annuel', 'Typologie', 'Lien Google Maps'
        ];
        
        let map;
        let dataMarkers = []; // Pour stocker les marqueurs Leaflet
        let originalData = []; // Pour stocker les données après parsing
        let filteredData = []; // Pour stocker les données filtrées
        let selectedMarker = null; // Marqueur actuellement sélectionné
        let currentFilter = 'all'; // Filtre de typologie actuel

        // Initialisation de la carte (Leaflet)
        function initMap() {
            // Centre la carte sur la France par défaut
            map = L.map('map-container', {
                zoomControl: false // Contrôle le zoom dans le panneau droit si besoin
            }).setView([46.603354, 1.888334], 6); // Coordonnées et zoom initial

            // Ajout du calque OpenStreetMap
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                minZoom: 4,
                maxZoom: 18
            }).addTo(map);

            // Ajout d'un contrôle de zoom simple
            L.control.zoom({ position: 'topleft' }).addTo(map);
        }

        // Fonction utilitaire pour lire le CSV (adaptée à l'environnement Immersive)
        async function loadData() {
            try {
                // Utilise la fonction d'accès aux fichiers du conteneur
                // CORRECTION: Encodage du chemin du fichier
                const encodedPath = encodeURIComponent(DATA_FILE_PATH);
                const response = await fetch(encodedPath); 
                
                if (!response.ok) throw new Error(`Erreur de chargement: ${response.statusText} (${response.status})`);
                
                const csvText = await response.text();
                // Simule un parser CSV simple
                const rows = csvText.trim().split('\n').filter(row => row.trim() !== ''); // Filtrer les lignes vides
                
                if (rows.length === 0) {
                    throw new Error("Le fichier CSV est vide.");
                }

                // Détecter le séparateur
                let separator = ',';
                if (rows.length > 0 && rows[0].includes(';')) {
                    separator = ';';
                }

                const header = rows[0].split(separator).map(h => h.trim().replace(/"/g, ''));
                
                const data = [];
                for (let i = 1; i < rows.length; i++) {
                    const values = rows[i].split(separator);
                    // Si le nombre de colonnes ne correspond pas ou la ligne est vide, on passe
                    if (values.length !== header.length || values.every(v => v.trim() === '')) continue;

                    const row = {};
                    header.forEach((col, index) => {
                        row[col] = values[index] ? values[index].trim().replace(/"/g, '') : '';
                    });
                    
                    // Vérification des colonnes essentielles et conversion de types
                    if (row['Latitude'] && row['Longitude']) {
                        // Remplacer la virgule par un point pour la décimale si nécessaire
                        let latStr = row.Latitude.replace(',', '.');
                        let lonStr = row.Longitude.replace(',', '.');
                        
                        row.Latitude = parseFloat(latStr);
                        row.Longitude = parseFloat(lonStr);
                        row['Référence annonce'] = row['Référence annonce'] || 'N/A';
                        
                        // Assurez-vous que les données sont valides
                        if (!isNaN(row.Latitude) && !isNaN(row.Longitude)) {
                            data.push(row);
                        }
                    }
                }
                
                originalData = data;
                document.getElementById('total-count').textContent = originalData.length;
                
                // Peupler le filtre de typologie
                populateTypologyFilter(originalData);
                
                // Afficher les données initiales
                applyFilterAndRenderMap();
                
                if (originalData.length === 0) {
                    showMessageBox("Avertissement Données", "Aucune donnée de lot valide n'a pu être chargée (vérifiez les colonnes 'Latitude' et 'Longitude').");
                }
                
            } catch (error) {
                console.error("Erreur critique lors du chargement des données:", error);
                // Utiliser une boîte de message à la place d'alert()
                showMessageBox("Erreur de chargement", `Impossible de charger ou d'analyser le fichier de données. Détail: ${error.message}. Consultez la console pour les détails.`);
            }
        }

        // Boîte de message personnalisée (remplace alert())
        function showMessageBox(title, message) {
            let msgBox = document.getElementById('message-box');
            
            // Mise à jour du contenu
            document.getElementById('message-title').textContent = title;
            document.getElementById('message-text').textContent = message;
            msgBox.classList.remove('hidden');
        }


        // Peuple le menu déroulant de typologie
        function populateTypologyFilter(data) {
            const select = document.getElementById('typo-filter');
            const typos = [...new Set(data.map(d => d.Typologie).filter(t => t && t.trim() !== 'N/A' && t.trim() !== ''))].sort();
            
            // Nettoyer les options existantes sauf 'all'
            select.querySelectorAll('option:not([value="all"])').forEach(opt => opt.remove());

            typos.forEach(typo => {
                const option = document.createElement('option');
                option.value = typo;
                option.textContent = typo;
                select.appendChild(option);
            });
            
            select.onchange = (e) => {
                currentFilter = e.target.value;
                applyFilterAndRenderMap();
            };
        }

        // Applique les filtres et met à jour la carte
        function applyFilterAndRenderMap() {
            // Filtrage
            filteredData = originalData.filter(d => {
                return currentFilter === 'all' || d.Typologie === currentFilter;
            });
            
            // Mise à jour du compteur
            document.getElementById('visible-count').textContent = filteredData.length;
            
            // Mise à jour de la carte
            renderMarkers(filteredData);
            
            // Ferme le panneau si le marqueur sélectionné n'est plus visible
            if (selectedMarker && !filteredData.find(d => d['Référence annonce'] === selectedMarker.ref)) {
                closeDetailPanel();
            }
        }

        // Fonction de rendu des marqueurs sur la carte
        function renderMarkers(data) {
            // 1. Supprimer tous les anciens marqueurs
            dataMarkers.forEach(marker => map.removeLayer(marker));
            dataMarkers = [];

            // 2. Créer et ajouter les nouveaux marqueurs
            data.forEach(lot => {
                // Utilisation d'un DivIcon personnalisé pour un meilleur contrôle du style
                const refCourt = (lot['Référence annonce'] || '').replace(/^0+/, '');
                
                // Mettre le marqueur en jaune s'il est actuellement sélectionné
                const isSelected = selectedMarker && selectedMarker.ref === lot['Référence annonce'];
                const markerClass = isSelected 
                    ? 'bg-yellow-500 selected-marker-active' 
                    : 'bg-blue-900';

                const customIconHtml = `<div id="marker-${lot['Référence annonce']}" class="custom-marker ${markerClass} text-white font-bold rounded-full w-8 h-8 flex items-center justify-center text-xs shadow-md border-2 border-yellow-500 hover:scale-110 transition duration-150 cursor-pointer" data-ref="${lot['Référence annonce']}">
                                            ${refCourt}
                                        </div>`;

                const customIcon = L.divIcon({
                    className: 'leaflet-data-marker-container',
                    html: customIconHtml,
                    iconSize: [32, 32],
                    iconAnchor: [16, 16]
                });

                const marker = L.marker([lot.Latitude, lot.Longitude], { icon: customIcon });
                
                // Ajouter la référence à l'objet marqueur pour la retrouver facilement
                marker.ref = lot['Référence annonce']; 
                
                marker.on('click', (e) => onMarkerClick(e, lot));
                marker.addTo(map);
                dataMarkers.push(marker);
            });
            
            // Si des données sont affichées, assure un centrage sur la France si le zoom est trop faible
            if (data.length > 0 && map.getZoom() < 5) {
                map.setView([46.603354, 1.888334], 6);
            }
        }

        // Gestion du clic sur un marqueur
        function onMarkerClick(e, lotData) {
            // Réinitialiser la classe du marqueur précédemment sélectionné
            if (selectedMarker) {
                const prevMarkerElement = document.getElementById(`marker-${selectedMarker.ref}`);
                if (prevMarkerElement) {
                    prevMarkerElement.classList.remove('selected-marker-active');
                    prevMarkerElement.classList.remove('bg-yellow-500');
                    prevMarkerElement.classList.add('bg-blue-900');
                }
            }

            // Mettre à jour le marqueur sélectionné
            selectedMarker = e.target;
            
            // Appliquer la classe de sélection au nouveau marqueur
            const newMarkerElement = document.getElementById(`marker-${lotData['Référence annonce']}`);
            if (newMarkerElement) {
                newMarkerElement.classList.add('selected-marker-active');
                newMarkerElement.classList.remove('bg-blue-900');
                newMarkerElement.classList.add('bg-yellow-500');
            }
            
            // Ouvrir le panneau de détails
            openDetailPanel(lotData);
        }

        // Ouvre le volet de détails à droite et le peuple
        function openDetailPanel(lot) {
            const panel = document.getElementById('right-panel');
            const detailContent = document.getElementById('detail-content');

            // 1. Mise à jour de l'en-tête et du bouton Maps
            document.getElementById('detail-ref').textContent = `Réf. ${lot['Référence annonce']}`;
            document.getElementById('google-maps-btn').href = lot['Lien Google Maps'] || '#';
            
            const hasLink = !!lot['Lien Google Maps'];
            const mapBtn = document.getElementById('google-maps-btn');
            
            if (!hasLink) {
                mapBtn.textContent = "Lien Maps non disponible";
                mapBtn.classList.remove('hover:bg-red-700');
                mapBtn.classList.remove('bg-red-600');
                mapBtn.classList.add('opacity-50', 'cursor-not-allowed', 'bg-gray-400');
            } else {
                 mapBtn.textContent = "Voir sur Google Maps";
                 mapBtn.classList.add('hover:bg-red-700', 'bg-red-600');
                 mapBtn.classList.remove('opacity-50', 'cursor-not-allowed', 'bg-gray-400');
            }

            // 2. Construction du contenu des détails
            detailContent.innerHTML = `
                <div class="p-3 bg-gray-100 rounded-lg">
                    <p class="font-semibold text-lg text-blue-800">${lot.Ville} (${lot['N° Département'] || 'N/A'})</p>
                    <p class="text-sm text-gray-600">${lot.Adresse}</p>
                </div>

                ${createDetailRow("Typologie", lot.Typologie)}
                ${createDetailRow("Surface GLA", formatNumber(lot['Surface GLA']) + ' m²')}
                ${createDetailRow("Loyer Annuel", formatCurrency(lot['Loyer annuel']))}
                ${createDetailRow("Loyer €/m²", formatNumber(lot['Loyer €/m²']) + ' €/m²')}
                ${createDetailRow("Région", lot.Région)}
                ${createDetailRow("Département", lot.Département)}
                
                <div class="mt-4 p-3 bg-yellow-50 rounded-lg border-l-4 border-yellow-500">
                    <p class="font-semibold text-sm text-gray-700">Commentaires :</p>
                    <p class="text-xs text-gray-600">${lot.Commentaires || 'Aucun commentaire disponible.'}</p>
                </div>
            `;

            // 3. Affichage du panneau
            panel.classList.remove('translate-x-full');
            
            // S'assurer que le marqueur est visible (centrage de la carte)
            if (selectedMarker) {
                 map.setView(selectedMarker.getLatLng(), map.getZoom() > 10 ? map.getZoom() : 13);
            }
        }

        // Fonction utilitaire pour créer une ligne de détail stylisée
        function createDetailRow(label, value) {
            // S'assurer que les valeurs vides affichent N/A
            const displayValue = (value && value.trim() !== '') ? value : 'N/A';
            return `
                <div class="flex justify-between items-center border-b border-gray-100 py-2">
                    <span class="text-sm font-medium text-gray-500">${label}</span>
                    <span class="text-base font-semibold text-blue-900">${displayValue}</span>
                </div>
            `;
        }

        // Fonction utilitaire pour fermer le volet de détails
        function closeDetailPanel() {
            const panel = document.getElementById('right-panel');
            panel.classList.add('translate-x-full');

            // Réinitialiser la classe du marqueur (s'il y en a un de sélectionné)
            if (selectedMarker) {
                const prevMarkerElement = document.getElementById(`marker-${selectedMarker.ref}`);
                if (prevMarkerElement) {
                    prevMarkerElement.classList.remove('selected-marker-active');
                    prevMarkerElement.classList.remove('bg-yellow-500');
                    prevMarkerElement.classList.add('bg-blue-900');
                }
                selectedMarker = null;
            }
        }
        
        // Fonction utilitaire pour formater les devises (Euro)
        function formatCurrency(value) {
            // Nettoyer et convertir
            const strValue = String(value).trim().replace(',', '.');
            const num = parseFloat(strValue.replace(/[^0-9.]/g, ''));
            
            if (isNaN(num) || num === 0) return 'N/A';
            
            // Formattage en Euro sans décimales
            return num.toLocaleString('fr-FR', { 
                style: 'currency', 
                currency: 'EUR', 
                minimumFractionDigits: 0, 
                maximumFractionDigits: 0 
            });
        }
        
        // Fonction utilitaire pour formater les nombres avec des espaces
        function formatNumber(value) {
             // Nettoyer et convertir
            const strValue = String(value).trim().replace(',', '.');
            const num = parseFloat(strValue.replace(/[^0-9.]/g, ''));

             if (isNaN(num) || num === 0) return 'N/A';
             
             return num.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        }

        // Fonction pour réinitialiser la carte et la sélection
        function resetMapAndSelection() {
            closeDetailPanel();
            // Réinitialiser les filtres
            currentFilter = 'all';
            document.getElementById('typo-filter').value = 'all';
            applyFilterAndRenderMap();
            // Recentrer sur la France
            map.setView([46.603354, 1.888334], 6);
        }

        // Initialisation de l'application au chargement complet de la fenêtre
        window.onload = function() {
            initMap();
            loadData();
        };

    </script>
</body>
</html>
