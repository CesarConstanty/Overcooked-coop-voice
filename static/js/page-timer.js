/**
 * Page Timer Module
 * 
 * Module JavaScript réutilisable pour gérer les timers de page avec contraintes min/max.
 * Utilisé dans les pages d'instructions et de tutoriels.
 * 
 * Fonctionnalité :
 * - Timer minimum : empêche le clic sur le bouton "Next" jusqu'à expiration
 * - Timer maximum : redirige automatiquement vers goodbye.html
 * - Affichage du temps restant en anglais
 * - Interface non-intrusive
 * 
 * @author AI Assistant
 * @version 1.0
 */

class PageTimer {
    constructor(minSeconds, maxSeconds, nextButtonSelector = '.start-button') {
        this.minSeconds = minSeconds;
        this.maxSeconds = maxSeconds;
        this.nextButtonSelector = nextButtonSelector;
        this.currentTime = 0;
        this.timerInterval = null;
        this.timerDisplay = null;
        this.nextButton = null;
        
        this.init();
    }
    
    init() {
        // Créer l'affichage du timer
        this.createTimerDisplay();
        
        // Récupérer le bouton next
        this.nextButton = document.querySelector(this.nextButtonSelector);
        
        if (this.nextButton) {
            // Désactiver le bouton initialement
            this.disableNextButton();
            
            // Démarrer le timer
            this.startTimer();
        } else {
            console.warn('PageTimer: Next button not found with selector:', this.nextButtonSelector);
        }
    }
    
    createTimerDisplay() {
        // Créer un conteneur pour le timer
        this.timerDisplay = document.createElement('div');
        this.timerDisplay.id = 'page-timer-display';
        this.timerDisplay.style.cssText = `
            position: fixed;
            top: 24px;
            right: 24px;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.95) 100%);
            color: #e2e8f0;
            padding: 16px 20px;
            border-radius: 16px;
            border: 1px solid rgba(56, 189, 248, 0.3);
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Inter, Arial, sans-serif;
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.25), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            z-index: 1000;
            min-width: 280px;
            text-align: left;
            backdrop-filter: blur(8px);
            transition: all 0.3s ease-in-out;
        `;
        
        document.body.appendChild(this.timerDisplay);
        this.updateDisplay();
    }
    
    formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
    
    updateDisplay() {
        if (!this.timerDisplay) return;
        
        const minRemaining = Math.max(0, this.minSeconds - this.currentTime);
        const maxRemaining = Math.max(0, this.maxSeconds - this.currentTime);
        
        let statusText = '';
        let statusColor = '#e2e8f0';
        let statusIcon = '';
        let progressWidth = 0;
        
        if (minRemaining > 0) {
            statusText = `Please read carefully`;
            statusColor = '#f59e0b'; // Amber
            statusIcon = '📖';
            progressWidth = ((this.minSeconds - minRemaining) / this.minSeconds) * 100;
        } else {
            statusText = `You may continue`;
            statusColor = '#10b981'; // Emerald
            statusIcon = '✅';
            progressWidth = 100;
        }
        
        this.timerDisplay.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                <span style="font-size: 16px;">${statusIcon}</span>
                <div style="flex: 1;">
                    <div style="color: ${statusColor}; font-weight: 600; font-size: 15px; margin-bottom: 2px;">
                        ${statusText}
                    </div>
                    <div style="font-size: 12px; color: #94a3b8;">
                        ${minRemaining > 0 ? `Minimum time: ${this.formatTime(minRemaining)}` : 'Ready to proceed'}
                    </div>
                </div>
            </div>
            
            <div style="margin-bottom: 10px;">
                <div style="background: rgba(148, 163, 184, 0.2); height: 4px; border-radius: 2px; overflow: hidden;">
                    <div style="width: ${progressWidth}%; height: 100%; background: ${statusColor}; transition: width 0.3s ease;"></div>
                </div>
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #64748b;">
                <span>📋 Read instructions</span>
                <span>⏱️ Auto-redirect: ${this.formatTime(maxRemaining)}</span>
            </div>
        `;
    }
    
    disableNextButton() {
        if (!this.nextButton) return;
        
        // Stocker les styles originaux si pas déjà fait
        if (!this.nextButton.dataset.originalStyles) {
            this.nextButton.dataset.originalStyles = JSON.stringify({
                opacity: this.nextButton.style.opacity || '1',
                cursor: this.nextButton.style.cursor || 'pointer',
                pointerEvents: this.nextButton.style.pointerEvents || 'auto',
                filter: this.nextButton.style.filter || 'none'
            });
        }
        
        this.nextButton.style.opacity = '0.4';
        this.nextButton.style.cursor = 'not-allowed';
        this.nextButton.style.pointerEvents = 'none';
        this.nextButton.style.filter = 'grayscale(0.7)';
        
        // Ajouter un titre informatif
        this.nextButton.title = 'Please read the instructions carefully before proceeding';
        
        // Ajouter une classe pour le style CSS
        this.nextButton.classList.add('timer-disabled');
    }
    
    enableNextButton() {
        if (!this.nextButton) return;
        
        // Restaurer les styles originaux
        if (this.nextButton.dataset.originalStyles) {
            const originalStyles = JSON.parse(this.nextButton.dataset.originalStyles);
            this.nextButton.style.opacity = originalStyles.opacity;
            this.nextButton.style.cursor = originalStyles.cursor;
            this.nextButton.style.pointerEvents = originalStyles.pointerEvents;
            this.nextButton.style.filter = originalStyles.filter;
        } else {
            this.nextButton.style.opacity = '1';
            this.nextButton.style.cursor = 'pointer';
            this.nextButton.style.pointerEvents = 'auto';
            this.nextButton.style.filter = 'none';
        }
        
        // Retirer le titre et la classe
        this.nextButton.removeAttribute('title');
        this.nextButton.classList.remove('timer-disabled');
        
        // Ajouter un effet visuel discret pour attirer l'attention
        this.nextButton.style.animation = 'gentle-pulse 2s infinite';
        
        // Ajouter le CSS de l'animation si pas déjà présent
        if (!document.getElementById('gentle-pulse-animation')) {
            const style = document.createElement('style');
            style.id = 'gentle-pulse-animation';
            style.textContent = `
                @keyframes gentle-pulse {
                    0%, 100% { transform: scale(1); }
                    50% { transform: scale(1.02); }
                }
            `;
            document.head.appendChild(style);
        }
        
        // Arrêter l'animation après quelques cycles
        setTimeout(() => {
            if (this.nextButton) {
                this.nextButton.style.animation = '';
            }
        }, 6000);
    }
    
    startTimer() {
        this.timerInterval = setInterval(() => {
            this.currentTime++;
            this.updateDisplay();
            
            // Vérifier si le timer minimum est écoulé
            if (this.currentTime === this.minSeconds) {
                this.enableNextButton();
            }
            
            // Vérifier si le timer maximum est écoulé
            if (this.currentTime >= this.maxSeconds) {
                this.redirectToGoodbye();
            }
        }, 1000);
    }
    
    redirectToGoodbye() {
        // Arrêter le timer
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        
        // Afficher un message d'avertissement avant la redirection
        if (this.timerDisplay) {
            this.timerDisplay.innerHTML = `
                <div style="display: flex; align-items: center; gap: 12px; padding: 8px;">
                    <span style="font-size: 24px;">⏰</span>
                    <div>
                        <div style="color: #ef4444; font-weight: bold; font-size: 15px; margin-bottom: 4px;">
                            Time limit reached
                        </div>
                        <div style="color: #94a3b8; font-size: 13px;">
                            Redirecting to completion page...
                        </div>
                    </div>
                </div>
                <div style="background: rgba(239, 68, 68, 0.2); height: 4px; border-radius: 2px; margin-top: 8px; overflow: hidden;">
                    <div style="width: 100%; height: 100%; background: #ef4444; animation: countdown-bar 3s linear;"></div>
                </div>
            `;
            
            // Ajouter l'animation pour la barre de progression
            if (!document.getElementById('countdown-animation')) {
                const style = document.createElement('style');
                style.id = 'countdown-animation';
                style.textContent = `
                    @keyframes countdown-bar {
                        from { width: 100%; }
                        to { width: 0%; }
                    }
                `;
                document.head.appendChild(style);
            }
        }
        
        // Rediriger après un délai
        setTimeout(() => {
            window.location.href = '/goodbye';
        }, 3000);
    }
    
    // Méthode pour nettoyer les ressources
    destroy() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        
        if (this.timerDisplay && this.timerDisplay.parentNode) {
            this.timerDisplay.parentNode.removeChild(this.timerDisplay);
        }
    }
}

// Fonction utilitaire pour initialiser le timer depuis les templates
function initPageTimer(minSeconds, maxSeconds, nextButtonSelector) {
    // Attendre que le DOM soit chargé
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new PageTimer(minSeconds, maxSeconds, nextButtonSelector);
        });
    } else {
        new PageTimer(minSeconds, maxSeconds, nextButtonSelector);
    }
}

// Exposer les fonctions globalement
window.PageTimer = PageTimer;
window.initPageTimer = initPageTimer;