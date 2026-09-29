document.addEventListener("DOMContentLoaded", function() {
    // On cible la div où la vidéo va s'afficher
    const qrReaderElement = document.getElementById("qr-reader");
    
    // On initialise le lecteur en ciblant notre div par son ID
    const html5QrCode = new Html5Qrcode("qr-reader");
    
    // Fonction appelée QUAND un QR code est scanné avec succès
    const onScanSuccess = (decodedText, decodedResult) => {
        // 1. On arrête la caméra pour figer l'image
        html5QrCode.stop().then(() => {
            console.log("Caméra arrêtée. Redirection vers :", decodedText);
            
            // 2. On redirige vers l'URL lue dans le QR Code
            // Si le QR code contient juste un ID (ex: "Billet-123"), il faut construire l'URL ici :
            // window.location.href = "/" + decodedText; 
            // Si le QR code contient l'URL complète (ex: "https://monsite.com/home/Billet-123/"), on fait juste :
            window.location.href = decodedText;
            
        }).catch((err) => {
            console.error("Erreur lors de l'arrêt de la caméra.", err);
        });
    };

    // Configuration du scanner
    const config = {
        fps: 10, // Images par seconde (10 est un bon équilibre performance/batterie)
        qrbox: { width: 250, height: 250 }, // Zone de focus au centre
        aspectRatio: 1.0 // Force un format carré pour correspondre à notre design
    };

    // On lance la caméra en demandant spécifiquement la caméra arrière (environment)
    html5QrCode.start({ facingMode: "environment" }, config, onScanSuccess)
    .catch((err) => {
        // En cas d'erreur (pas de caméra, ou permission refusée par l'utilisateur)
        const loadingDiv = document.getElementById('qr-loading');
        if (loadingDiv) {
            loadingDiv.innerHTML = `
                <i class="bi bi-camera-video-off text-danger" style="font-size: 3rem;"></i>
                <p class="mt-3 mb-0 fw-bold text-danger text-center">Caméra inaccessible<br><small>Vérifiez les permissions de votre navigateur</small></p>
            `;
        }
        console.error("Erreur de démarrage de la caméra :", err);
    });
});