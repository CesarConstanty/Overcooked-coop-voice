/**
 * Tutorial Timer Module
 * 
 * Module JavaScript spécifique pour les timers des pages de tutoriel.
 * Contrairement au module page-timer.js, celui-ci est optimisé pour rester
 * visible en permanence même lors des changements d'état du tutoriel.
 * 
 * @author AI Assistant
 * @version 1.0
 */

class TutorialTimer {
    constructor(maxSeconds, onTimeout) {
        this.maxSeconds = maxSeconds;
        this.onTimeout = onTimeout || (() => { window.location.href = '/goodbye'; });
        this.currentTime = 0;
        this.timerInterval = null;
        this.timerDisplay = null;
        
        this.init();
    }
    
    init() {
        this.createTimerDisplay();
        this.startTimer();
        this.startVisibilityWatcher();
    }
    
    createTimerDisplay() {
        // Créer l'élément timer
        this.timerDisplay = document.createElement('div');
        this.timerDisplay.id = 'tutorial-timer-display';
        this.timerDisplay.className = 'tutorial-timer';
        
        // Styles avec position fixe et z-index élevé
        this.timerDisplay.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            z-index: 9999;
            background-color: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 5px;
            font-family: Arial, sans-serif;
            font-size: 14px;
            font-weight: bold;
            display: block;
            visibility: visible;
            opacity: 1;
            pointer-events: none;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        `;
        
        // Ajouter au body
        document.body.appendChild(this.timerDisplay);
        
        // Mise à jour initiale
        this.updateDisplay();
    }
    
    formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
    
    updateDisplay() {
        if (!this.timerDisplay) return;
        
        const remaining = Math.max(0, this.maxSeconds - this.currentTime);
        
        if (remaining <= 0) {
            this.timerDisplay.innerHTML = `
                <div style="color: #ff6b6b;">
                    ⏰ Time's up!
                </div>
            `;
        } else {
            // Changer la couleur selon le temps restant
            let color = 'white';
            if (remaining <= 60) {
                color = '#ff6b6b'; // Rouge pour la dernière minute
            } else if (remaining <= 300) {
                color = '#ffa500'; // Orange pour les 5 dernières minutes
            }
            
            this.timerDisplay.innerHTML = `
                <div style="color: ${color};">
                    ⏱️ ${this.formatTime(remaining)}
                </div>
            `;
        }
    }
    
    startTimer() {
        this.timerInterval = setInterval(() => {
            this.currentTime++;
            this.updateDisplay();
            
            if (this.currentTime >= this.maxSeconds) {
                this.handleTimeout();
            }
        }, 1000);
    }
    
    handleTimeout() {
        // Arrêter le timer
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        
        // Afficher un message final
        if (this.timerDisplay) {
            this.timerDisplay.style.backgroundColor = 'rgba(239, 68, 68, 0.95)';
            this.timerDisplay.innerHTML = `
                <div style="color: white; text-align: center;">
                    <div style="font-weight: bold;">⏰ Time limit reached</div>
                    <div style="font-size: 12px; margin-top: 2px;">Redirecting...</div>
                </div>
            `;
        }
        
        // Rediriger après 2 secondes
        setTimeout(() => {
            this.onTimeout();
        }, 2000);
    }
    
    startVisibilityWatcher() {
        // Vérifier et corriger la visibilité du timer toutes les 500ms
        this.visibilityInterval = setInterval(() => {
            this.ensureVisibility();
        }, 500);
    }
    
    ensureVisibility() {
        if (!this.timerDisplay) return;
        
        // Forcer les styles pour s'assurer que le timer reste visible
        const element = this.timerDisplay;
        
        // Vérifier si l'élément existe toujours dans le DOM
        if (!document.body.contains(element)) {
            // Recréer l'élément s'il a été supprimé
            document.body.appendChild(element);
        }
        
        // Forcer les styles critiques
        element.style.position = 'fixed';
        element.style.top = '10px';
        element.style.right = '10px';
        element.style.zIndex = '9999';
        element.style.display = 'block';
        element.style.visibility = 'visible';
        element.style.opacity = '1';
        
        // S'assurer que les styles de base sont préservés
        if (!element.style.backgroundColor) {
            element.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        }
        if (!element.style.color) {
            element.style.color = 'white';
        }
        if (!element.style.padding) {
            element.style.padding = '8px 12px';
        }
        if (!element.style.borderRadius) {
            element.style.borderRadius = '5px';
        }
        if (!element.style.fontFamily) {
            element.style.fontFamily = 'Arial, sans-serif';
        }
        if (!element.style.fontSize) {
            element.style.fontSize = '14px';
        }
        if (!element.style.fontWeight) {
            element.style.fontWeight = 'bold';
        }
    }
    
    start() {
        // Méthode pour démarrer le timer (alias)
        if (!this.timerInterval) {
            this.startTimer();
        }
    }
    
    destroy() {
        // Nettoyer les ressources
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        
        if (this.visibilityInterval) {
            clearInterval(this.visibilityInterval);
        }
        
        if (this.timerDisplay && this.timerDisplay.parentNode) {
            this.timerDisplay.parentNode.removeChild(this.timerDisplay);
        }
    }
}

// Exposer globalement
window.TutorialTimer = TutorialTimer;