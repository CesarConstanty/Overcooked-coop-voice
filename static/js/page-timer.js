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
        // Récupérer le bouton next
        this.nextButton = document.querySelector(this.nextButtonSelector);
        
        if (this.nextButton) {
            // Créer l'affichage du timer minimum au-dessus du bouton
            this.createMinTimerDisplay();
            
            // Créer l'affichage du timer maximum SEULEMENT si maxSeconds > 0
            if (this.maxSeconds > 0) {
                this.createMaxTimerDisplay();
            }
            
            // Désactiver le bouton initialement
            this.disableNextButton();
            
            // Démarrer le timer
            this.startTimer();
        } else {
            console.warn('PageTimer: Next button not found with selector:', this.nextButtonSelector);
        }
    }
    
    createMinTimerDisplay() {
        // Créer un conteneur pour le timer minimum au-dessus du bouton
        this.minTimerDisplay = document.createElement('div');
        this.minTimerDisplay.id = 'min-timer-display';
        this.minTimerDisplay.style.cssText = `
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.95) 100%);
            color: #e2e8f0;
            padding: 12px 16px;
            border-radius: 12px;
            border: 1px solid rgba(56, 189, 248, 0.3);
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Inter, Arial, sans-serif;
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 4px 12px -2px rgba(0, 0, 0, 0.15);
            margin-bottom: 16px;
            text-align: center;
            backdrop-filter: blur(8px);
            transition: all 0.3s ease-in-out;
        `;
        
        // Insérer le timer au-dessus du bouton
        this.nextButton.parentNode.insertBefore(this.minTimerDisplay, this.nextButton);
    }
    
    createMaxTimerDisplay() {
        // Créer un conteneur pour le timer maximum (discret, en haut à droite)
        this.maxTimerDisplay = document.createElement('div');
        this.maxTimerDisplay.id = 'max-timer-display';
        this.maxTimerDisplay.style.cssText = `
            position: fixed;
            top: 16px;
            right: 16px;
            background: rgba(15, 23, 42, 0.7);
            color: rgba(226, 232, 240, 0.8);
            padding: 8px 12px;
            border-radius: 8px;
            border: 1px solid rgba(56, 189, 248, 0.15);
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Inter, Arial, sans-serif;
            font-size: 12px;
            font-weight: 400;
            box-shadow: 0 2px 8px -2px rgba(0, 0, 0, 0.1);
            z-index: 1000;
            backdrop-filter: blur(4px);
            transition: opacity 0.3s ease-in-out;
            opacity: 0.6;
        `;
        
        // Effet hover pour plus de visibilité si nécessaire
        this.maxTimerDisplay.addEventListener('mouseenter', () => {
            this.maxTimerDisplay.style.opacity = '0.9';
        });
        
        this.maxTimerDisplay.addEventListener('mouseleave', () => {
            this.maxTimerDisplay.style.opacity = '0.6';
        });
        
        document.body.appendChild(this.maxTimerDisplay);
    }
    
    formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
    
    updateDisplay() {
        this.updateMinTimer();
        this.updateMaxTimer();
    }
    
    updateMinTimer() {
        if (!this.minTimerDisplay) return;
        
        const minRemaining = Math.max(0, this.minSeconds - this.currentTime);
        
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
        
        this.minTimerDisplay.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 8px;">
                <span style="font-size: 16px;">${statusIcon}</span>
                <div style="color: ${statusColor}; font-weight: 600; font-size: 15px;">
                    ${statusText}
                </div>
            </div>
            
            ${minRemaining > 0 ? `
                <div style="margin-bottom: 8px;">
                    <div style="font-size: 12px; color: #94a3b8; margin-bottom: 4px; text-align: center;">
                        Minimum reading time: ${this.formatTime(minRemaining)}
                    </div>
                    <div style="background: rgba(148, 163, 184, 0.2); height: 4px; border-radius: 2px; overflow: hidden;">
                        <div style="width: ${progressWidth}%; height: 100%; background: ${statusColor}; transition: width 0.3s ease;"></div>
                    </div>
                </div>
            ` : ''}
        `;
        
        // Masquer progressivement quand le timer minimum est fini
        if (minRemaining === 0) {
            setTimeout(() => {
                if (this.minTimerDisplay && minRemaining === 0) {
                    this.minTimerDisplay.style.opacity = '0.7';
                    this.minTimerDisplay.style.transform = 'scale(0.95)';
                }
            }, 2000);
        }
    }
    
    updateMaxTimer() {
        // Ne rien faire si maxSeconds est 0 (pas de limite de temps)
        if (!this.maxTimerDisplay || this.maxSeconds <= 0) return;
        
        const maxRemaining = Math.max(0, this.maxSeconds - this.currentTime);
        
        this.maxTimerDisplay.innerHTML = `
            <div style="display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 12px;">⏱️</span>
                <span style="font-size: 11px;">Auto-redirect: ${this.formatTime(maxRemaining)}</span>
            </div>
        `;
        
        // Rendre plus visible quand il reste peu de temps
        if (maxRemaining <= 60) {
            this.maxTimerDisplay.style.opacity = '0.9';
            this.maxTimerDisplay.style.background = 'rgba(239, 68, 68, 0.8)';
            this.maxTimerDisplay.style.color = '#fff';
        } else if (maxRemaining <= 120) {
            this.maxTimerDisplay.style.opacity = '0.8';
            this.maxTimerDisplay.style.background = 'rgba(245, 158, 11, 0.8)';
            this.maxTimerDisplay.style.color = '#fff';
        }
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
        this.updateDisplay();
        this.timerInterval = setInterval(() => {
            this.currentTime++;
            this.updateDisplay();
            
            // Vérifier si le timer minimum est écoulé
            if (this.currentTime === this.minSeconds) {
                this.enableNextButton();
            }
            
            // Vérifier si le timer maximum est écoulé (seulement si maxSeconds > 0)
            if (this.maxSeconds > 0 && this.currentTime >= this.maxSeconds) {
                this.redirectToGoodbye();
            }
        }, 1000);
    }
    
    redirectToGoodbye() {
        // Arrêter le timer
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        
        // Afficher un message d'avertissement dans le timer maximum
        if (this.maxTimerDisplay) {
            this.maxTimerDisplay.style.opacity = '1';
            this.maxTimerDisplay.style.background = 'rgba(239, 68, 68, 0.95)';
            this.maxTimerDisplay.style.color = '#fff';
            this.maxTimerDisplay.style.padding = '12px 16px';
            this.maxTimerDisplay.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 16px;">⏰</span>
                    <div>
                        <div style="font-weight: bold; font-size: 13px;">Time limit reached</div>
                        <div style="font-size: 11px; opacity: 0.9;">Redirecting in 3s...</div>
                    </div>
                </div>
            `;
        }
        
        // Masquer le timer minimum pour éviter la confusion
        if (this.minTimerDisplay) {
            this.minTimerDisplay.style.opacity = '0.3';
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
        
        if (this.minTimerDisplay && this.minTimerDisplay.parentNode) {
            this.minTimerDisplay.parentNode.removeChild(this.minTimerDisplay);
        }
        
        if (this.maxTimerDisplay && this.maxTimerDisplay.parentNode) {
            this.maxTimerDisplay.parentNode.removeChild(this.maxTimerDisplay);
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