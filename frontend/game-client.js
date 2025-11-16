// GameClient class for WebSocket connection and Canvas rendering with Stage-Based Flow

// Polyfill for roundRect if not available
if (!CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function(x, y, width, height, radius) {
        this.beginPath();
        this.moveTo(x + radius, y);
        this.lineTo(x + width - radius, y);
        this.quadraticCurveTo(x + width, y, x + width, y + radius);
        this.lineTo(x + width, y + height - radius);
        this.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        this.lineTo(x + radius, y + height);
        this.quadraticCurveTo(x, y + height, x, y + height - radius);
        this.lineTo(x, y + radius);
        this.quadraticCurveTo(x, y, x + radius, y);
        this.closePath();
    };
}

class GameClient {
    constructor(canvasElement) {
        this.canvas = canvasElement;
        this.spriteCache = {}; // Cache for loaded sprites: {url: Image}
        this.pixelArtSpriteCache = {}; // Cache for generated pixel art sprites: {key: Image}
        this.foodSpriteCache = {}; // Cache for food sprites: {foodType: Image}
        this.ctx = canvasElement.getContext('2d');
        this.ws = null;
        this.gameState = null;
        this.gameId = null;
        this.cellSize = 30; // Grid cell size in pixels
        this.animationFrame = null;
        this.currentStage = 1;
        this.timeRemaining = 60;
        this.previewTimeouts = {}; // Store debounce timeouts
        this.confirmedPlayer = false; // Track confirmation state for initial game start
        this.attemptNumber = 1;
        this.maxAttempts = 3;
        
        // Mouse hover tracking
        this.hoveredElement = null;
        this.mouseX = 0;
        this.mouseY = 0;
        
        // Setup mouse event handlers
        this.setupMouseHandlers();
        
        // Preload food sprites
        this.preloadFoodSprites();
        
        // Render legend previews after DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.renderLegendPreviews());
        } else {
            // DOM already loaded
            setTimeout(() => this.renderLegendPreviews(), 100);
        }
    }
    
    renderLegendPreviews() {
        // Render creature preview
        const creatureCanvas = document.getElementById('legendCreature');
        if (creatureCanvas) {
            const ctx = creatureCanvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;
            ctx.fillStyle = '#667eea';
            // Draw simple pixel art creature (stage 1 style)
            const centerX = 12;
            const centerY = 12;
            const size = 8;
            for (let py = 0; py < size; py++) {
                for (let px = 0; px < size; px++) {
                    const dx = px - size/2;
                    const dy = py - size/2;
                    const dist = Math.sqrt(dx*dx + dy*dy);
                    if (dist < size/2 - 1) {
                        ctx.fillRect(centerX - size/2 + px, centerY - size/2 + py, 1, 1);
                    }
                }
            }
            // Draw energy bar
            ctx.fillStyle = '#2d3748';
            ctx.fillRect(6, 2, 12, 2);
            ctx.fillStyle = '#48bb78';
            ctx.fillRect(6, 2, 8, 2);
        }
        
        // Render predator preview
        const predatorCanvas = document.getElementById('legendPredator');
        if (predatorCanvas) {
            const ctx = predatorCanvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;
            ctx.fillStyle = '#c53030';
            const centerX = 12;
            const centerY = 12;
            const size = 8;
            for (let py = 0; py < size; py++) {
                for (let px = 0; px < size; px++) {
                    const dx = px - size/2;
                    const dy = py - size/2;
                    const dist = Math.sqrt(dx*dx + dy*dy);
                    if (dist < size/2 - 1) {
                        ctx.fillRect(centerX - size/2 + px, centerY - size/2 + py, 1, 1);
                    }
                }
            }
            // Draw skull icon
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(10, 8, 4, 4);
            ctx.fillStyle = '#c53030';
            ctx.fillRect(11, 9, 2, 2);
        }
        
        // Render food previews
        this.renderFoodPreview('legendApple', 'apple');
        this.renderFoodPreview('legendBanana', 'banana');
        this.renderFoodPreview('legendGrapes', 'grapes');
        this.renderFoodPreview('legendWater', 'water');
        this.renderFoodPreview('legendShelter', 'shelter');
        
        // Render disaster preview
        const disasterCanvas = document.getElementById('legendDisaster');
        if (disasterCanvas) {
            const ctx = disasterCanvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;
            ctx.fillStyle = '#8b4513';
            ctx.fillRect(2, 2, 20, 20);
            // Draw crack lines
            ctx.strokeStyle = '#654321';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(12, 12);
            ctx.lineTo(6, 6);
            ctx.moveTo(12, 12);
            ctx.lineTo(18, 18);
            ctx.stroke();
        }
        
        // Render territory preview
        const territoryCanvas = document.getElementById('legendTerritory');
        if (territoryCanvas) {
            const ctx = territoryCanvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;
            ctx.fillStyle = 'rgba(237, 137, 54, 0.15)';
            ctx.fillRect(2, 2, 20, 20);
            ctx.strokeStyle = 'rgba(237, 137, 54, 0.8)';
            ctx.lineWidth = 2;
            ctx.setLineDash([3, 3]);
            ctx.strokeRect(2, 2, 20, 20);
            ctx.setLineDash([]);
        }
    }
    
    renderFoodPreview(canvasId, foodType) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        ctx.imageSmoothingEnabled = false;
        
        // Try to use actual sprite first
        const sprite = this.loadFoodSprite(foodType);
        if (sprite && sprite.complete && sprite.naturalWidth > 0) {
            ctx.drawImage(sprite, 0, 0, 24, 24);
            return;
        }
        
        // Fallback to pixel art (same as drawFood)
        const centerX = 12;
        const centerY = 12;
        
        if (foodType === 'water') {
            const size = 8;
            ctx.fillStyle = '#38b2ac';
            ctx.fillRect(centerX - size, centerY - size, size * 2, size * 2);
            ctx.fillStyle = '#2c7a7b';
            for (let py = 0; py < 3; py++) {
                for (let px = 0; px < 3; px++) {
                    ctx.fillRect(centerX - size + 2 + px * 2, centerY - size + 2 + py * 2, 1, 1);
                }
            }
        } else if (foodType === 'shelter') {
            ctx.fillStyle = '#8b7355';
            ctx.beginPath();
            ctx.moveTo(centerX, centerY - 6);
            ctx.lineTo(centerX - 4, centerY + 3);
            ctx.lineTo(centerX + 4, centerY + 3);
            ctx.closePath();
            ctx.fill();
            ctx.strokeStyle = '#6b5d47';
            ctx.lineWidth = 1;
            ctx.stroke();
        } else if (foodType === 'apple') {
            const size = 6;
            for (let py = -size; py <= size; py++) {
                for (let px = -size; px <= size; px++) {
                    const dist = Math.sqrt(px*px + py*py);
                    if (dist < size - 1) {
                        ctx.fillStyle = '#ff6b6b';
                        ctx.fillRect(centerX + px, centerY + py, 1, 1);
                    } else if (dist < size) {
                        ctx.fillStyle = '#ee5a52';
                        ctx.fillRect(centerX + px, centerY + py, 1, 1);
                    }
                }
            }
            ctx.fillStyle = '#48bb78';
            ctx.fillRect(centerX - 1, centerY - 8, 2, 3);
        } else if (foodType === 'banana') {
            const width = 5;
            const height = 8;
            ctx.fillStyle = '#f6e05e';
            ctx.fillRect(centerX - width/2, centerY - height/2, width, height);
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(centerX - 1, centerY - 3, 1, 2);
            ctx.strokeStyle = '#ecc94b';
            ctx.lineWidth = 1;
            ctx.strokeRect(centerX - width/2, centerY - height/2, width, height);
        } else if (foodType === 'grapes') {
            const positions = [
                [centerX - 2, centerY - 2], [centerX, centerY - 3], [centerX + 2, centerY - 2],
                [centerX - 3, centerY + 1], [centerX, centerY], [centerX + 3, centerY + 1]
            ];
            positions.forEach(([px, py]) => {
                const grapeSize = 2;
                for (let gy = -grapeSize; gy <= grapeSize; gy++) {
                    for (let gx = -grapeSize; gx <= grapeSize; gx++) {
                        const dist = Math.sqrt(gx*gx + gy*gy);
                        if (dist < grapeSize) {
                            ctx.fillStyle = '#9f7aea';
                            ctx.fillRect(px + gx, py + gy, 1, 1);
                        }
                    }
                }
            });
        }
    }
    
    setupMouseHandlers() {
        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            this.mouseX = e.clientX - rect.left;
            this.mouseY = e.clientY - rect.top;
            this.detectHoveredElement();
            this.render(); // Re-render to show tooltip
        });
        
        this.canvas.addEventListener('mouseleave', () => {
            this.hoveredElement = null;
            this.render();
        });
    }
    
    detectHoveredElement() {
        if (!this.gameState || !this.gameState.world) {
            this.hoveredElement = null;
            return;
        }
        
        // Ensure mouse position is valid (within canvas bounds)
        if (this.mouseX < 0 || this.mouseY < 0 || 
            this.mouseX > this.canvas.width || this.mouseY > this.canvas.height) {
            this.hoveredElement = null;
            return;
        }
        
        const gridX = Math.floor(this.mouseX / this.cellSize);
        const gridY = Math.floor(this.mouseY / this.cellSize);
        const pixelX = gridX * this.cellSize + this.cellSize / 2;
        const pixelY = gridY * this.cellSize + this.cellSize / 2;
        
        // Check creatures first (they're on top)
        if (this.gameState.world.creatures) {
            for (const creature of this.gameState.world.creatures) {
                const cx = Math.round(creature.x * this.cellSize + this.cellSize / 2);
                const cy = Math.round(creature.y * this.cellSize + this.cellSize / 2);
                const dist = Math.sqrt((this.mouseX - cx) ** 2 + (this.mouseY - cy) ** 2);
                if (dist < 20) {
                    const isPredator = creature.player_id === null || creature.player_id === undefined;
                    this.hoveredElement = {
                        type: isPredator ? 'predator' : 'creature',
                        data: creature,
                        x: cx,
                        y: cy
                    };
                    return;
                }
            }
        }
        
        // Check food
        if (this.gameState.world.resources && this.gameState.world.resources.food) {
            for (const food of this.gameState.world.resources.food) {
                const fx = Math.round(food.x * this.cellSize + this.cellSize / 2);
                const fy = Math.round(food.y * this.cellSize + this.cellSize / 2);
                const dist = Math.sqrt((this.mouseX - fx) ** 2 + (this.mouseY - fy) ** 2);
                if (dist < 15) {
                    this.hoveredElement = {
                        type: 'food',
                        data: food,
                        x: fx,
                        y: fy
                    };
                    return;
                }
            }
        }
        
        // Check disasters
        if (this.gameState.world.disasters) {
            for (const disaster of this.gameState.world.disasters) {
                const dx = Math.round(disaster.x * this.cellSize + this.cellSize / 2);
                const dy = Math.round(disaster.y * this.cellSize + this.cellSize / 2);
                const radius = (disaster.radius || 3) * this.cellSize;
                const dist = Math.sqrt((this.mouseX - dx) ** 2 + (this.mouseY - dy) ** 2);
                if (dist < radius) {
                    this.hoveredElement = {
                        type: 'disaster',
                        data: disaster,
                        x: dx,
                        y: dy
                    };
                    return;
                }
            }
        }
        
        // Check biomes
        const env = this.gameState.environment || this.gameState.world?.environment;
        if (env?.biomes) {
            const biomeKey = `${gridX},${gridY}`;
            if (env.biomes[biomeKey]) {
                this.hoveredElement = {
                    type: 'biome',
                    data: { type: env.biomes[biomeKey] },
                    x: pixelX,
                    y: pixelY
                };
                return;
            }
        }
        
        // Check territories
        if (this.gameState.world.territories) {
            const regionSize = 5;
            const regionX = Math.floor(gridX / regionSize);
            const regionY = Math.floor(gridY / regionSize);
            const territoryKey = `${regionX},${regionY}`;
            if (this.gameState.world.territories[territoryKey]) {
                this.hoveredElement = {
                    type: 'territory',
                    data: { owner: this.gameState.world.territories[territoryKey] },
                    x: pixelX,
                    y: pixelY
                };
                return;
            }
        }
        
        this.hoveredElement = null;
    }

    async startGame(prompt) {
        try {
            // Reset confirmation state for new game
            this.confirmedPlayer = false;
            
            // Request backend to start game
            const response = await fetch('http://localhost:8000/start_game', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            this.gameId = data.game_id;
            
            // Initialize attempt tracking
            this.attemptNumber = 1;
            this.maxAttempts = 3;
            this.updateHearts(3);

            // Update status
            this.updateStatus('Game started! Connecting...');

            // Connect WebSocket
            this.ws = new WebSocket(`ws://localhost:8000/ws/${this.gameId}`);
            this.ws.onopen = () => {
                this.updateStatus('Game running...');
            };
            this.ws.onmessage = (event) => {
                const update = JSON.parse(event.data);
                this.onGameUpdate(update);
            };
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateStatus('Connection error!');
            };
            this.ws.onclose = () => {
                this.updateStatus('Game finished!');
                if (this.animationFrame) {
                    cancelAnimationFrame(this.animationFrame);
                }
            };
        } catch (error) {
            console.error('Error starting game:', error);
            this.updateStatus(`Error: ${error.message}`);
        }
    }

    async updatePrompts(prompt) {
        console.log('[updatePrompts] ===== Starting updatePrompts =====');
        console.log('[updatePrompts] gameId:', this.gameId);
        console.log('[updatePrompts] prompt:', prompt);
        console.log('[updatePrompts] WebSocket state:', this.ws ? {
            readyState: this.ws.readyState,
            url: this.ws.url,
            protocol: this.ws.protocol
        } : 'WebSocket is null');
        
        if (!this.gameId) {
            console.error('[updatePrompts] ✗ No gameId, returning early');
            return;
        }
        
        console.log('[updatePrompts] ✓ All checks passed, making API request');
        const url = `http://localhost:8000/update_prompts/${this.gameId}`;
        const payload = { prompt };
        console.log('[updatePrompts] Request URL:', url);
        console.log('[updatePrompts] Request payload:', payload);
        
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            console.log('[updatePrompts] Response received:', {
                status: response.status,
                statusText: response.statusText,
                ok: response.ok,
                headers: Object.fromEntries(response.headers.entries())
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[updatePrompts] ✗ HTTP error response:', {
                    status: response.status,
                    statusText: response.statusText,
                    body: errorText
                });
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const responseData = await response.json();
            console.log('[updatePrompts] ✓ Response data:', responseData);

            // Hide modal
            const resultsModal = document.getElementById('resultsModal');
            if (resultsModal) {
                resultsModal.style.display = 'none';
                console.log('[updatePrompts] ✓ Hidden resultsModal');
            }
            
            console.log('[updatePrompts] ===== updatePrompts completed successfully =====');
        } catch (error) {
            console.error('[updatePrompts] ✗ Error updating prompts:', error);
            console.error('[updatePrompts] Error details:', {
                name: error.name,
                message: error.message,
                stack: error.stack
            });
            alert(`Error updating prompts: ${error.message}`);
        }
    }

    onGameUpdate(update) {
        // Handle different status types
        if (update.status === 'stage_started') {
            this.currentStage = update.stage;
            this.timeRemaining = update.time_remaining;
            this.updateStatus(`Stage ${update.stage} started!`);
            this.updateStageTimer(update.time_remaining);
        } else if (update.status === 'update') {
            // Check if this is a new attempt (attempt number changed)
            const previousAttemptNumber = this.attemptNumber;
            this.gameState = update;
            this.currentStage = update.stage || this.currentStage;
            this.timeRemaining = update.time_remaining || this.timeRemaining;
            if (update.attempt_number) {
                this.attemptNumber = update.attempt_number;
            }
            if (update.max_attempts) {
                this.maxAttempts = update.max_attempts;
            }
            // Clear hovered element when a new attempt starts
            if (update.attempt_number && update.attempt_number !== previousAttemptNumber) {
                this.hoveredElement = null;
            }
            this.updateHearts(update.attempts_remaining || (this.maxAttempts - this.attemptNumber + 1));
            
            // Add environment and territories to game state if available
            if (update.environment) {
                this.gameState.environment = update.environment;
                if (!this.gameState.world) this.gameState.world = {};
                this.gameState.world.environment = update.environment;
            }
            if (update.territories) {
                if (!this.gameState.world) this.gameState.world = {};
                this.gameState.world.territories = update.territories;
            }
            if (update.disasters) {
                if (!this.gameState.world) this.gameState.world = {};
                this.gameState.world.disasters = update.disasters;
            }
            if (update.regions) {
                if (!this.gameState.world) this.gameState.world = {};
                this.gameState.world.regions = update.regions;
            }
            
            this.render();
            this.updateEvents(update.events || []);
            this.updateStageTimer(update.time_remaining);
            
            // Update scoring/achievements if available
            if (update.scoring) {
                this.updateScoring(update.scoring);
            }
        } else if (update.status === 'game_started') {
            // Clear hovered element when game starts (new attempt)
            this.hoveredElement = null;
            this.currentStage = update.stage;
            this.timeRemaining = update.time_remaining;
            if (update.attempt_number) {
                this.attemptNumber = update.attempt_number;
            }
            if (update.max_attempts) {
                this.maxAttempts = update.max_attempts;
            }
            this.updateHearts(update.attempts_remaining || (this.maxAttempts - this.attemptNumber + 1));
            this.updateStatus('Game started!');
            this.updateStageTimer(update.time_remaining);
        } else if (update.status === 'population_died') {
            // Population died - show prompt input modal
            this.attemptNumber = update.attempt_number || this.attemptNumber;
            this.maxAttempts = update.max_attempts || this.maxAttempts;
            this.updateHearts(update.attempts_remaining || (this.maxAttempts - this.attemptNumber));
            this.showPopulationDiedModal(update);
        } else if (update.status === 'game_complete') {
            this.attemptNumber = update.attempt_number || this.attemptNumber;
            this.maxAttempts = update.max_attempts || this.maxAttempts;
            this.updateHearts(0);
            this.showFinalResults(update.final_results, update.current_prompt, update.energy_events || []);
        } else if (update.status === 'finished') {
            this.updateStatus(`Game finished! Reason: ${update.reason}`);
            if (this.ws) {
                this.ws.close();
            }
            return;
        }
    }

    updateStatus(text) {
        const statusEl = document.getElementById('status');
        if (statusEl) {
            statusEl.textContent = text;
        }
    }

    updateStageTimer(timeRemaining) {
        const timerEl = document.getElementById('stageTimer');
        if (timerEl) {
            if (timeRemaining === null || timeRemaining === undefined) {
                timerEl.textContent = `Stage ${this.currentStage} - No time limit`;
            } else {
                timerEl.textContent = `Stage ${this.currentStage} - Time: ${timeRemaining}s`;
            }
        }
    }

    updateHearts(attemptsRemaining) {
        const heartsEl = document.getElementById('hearts');
        if (heartsEl) {
            const hearts = '❤️'.repeat(Math.max(0, attemptsRemaining));
            heartsEl.textContent = hearts || '💔';
        }
    }

    showPopulationDiedModal(update) {
        const modal = document.getElementById('resultsModal');
        const content = document.getElementById('resultsContent');
        const promptSection = document.getElementById('promptUpdateSection');
        
        if (!modal || !content) return;
        
        // Show death message
        const currentPrompt = update.current_prompt || 'N/A';
        const energyEvents = update.energy_events || [];
        
        // Format energy events list
        let energyEventsHtml = '';
        if (energyEvents.length > 0) {
            energyEventsHtml = `
                <div style="margin: 20px 0; padding: 16px; background: rgba(246, 224, 94, 0.15); border-radius: 12px; border-left: 4px solid #f6e05e;">
                    <p style="margin: 0 0 10px 0; font-weight: 700; color: #1a1a2e;">Energy Events (This Attempt):</p>
                    <ul style="margin: 0; padding-left: 20px; color: #1a1a2e;">
                        ${energyEvents.map(event => `<li style="margin: 5px 0; font-family: 'Inter', monospace; font-size: 13px;">${event}</li>`).join('')}
                    </ul>
                    <p style="margin: 10px 0 0 0; font-size: 12px; color: #1a1a2e; font-style: italic;">Use this information to update your prompt and improve survival strategies.</p>
                </div>
            `;
        } else {
            energyEventsHtml = `
                <div style="margin: 20px 0; padding: 16px; background: rgba(102, 126, 234, 0.05); border-radius: 12px; border-left: 4px solid rgba(102, 126, 234, 0.3);">
                    <p style="margin: 0; color: #1a1a2e; font-style: italic;">No energy events recorded this attempt.</p>
                </div>
            `;
        }
        
        content.innerHTML = `
            <h2 style="color: #1a1a2e; font-weight: 800; margin-top: 0;">Population Extinct!</h2>
            <p style="color: #f56565; font-size: 18px; font-weight: 700; margin: 10px 0;">All creatures have died.</p>
            <div style="margin: 20px 0; padding: 16px; background: rgba(102, 126, 234, 0.05); border-radius: 12px; border: 1px solid rgba(102, 126, 234, 0.15);">
                <p style="margin: 8px 0;"><strong style="color: #1a1a2e;">Attempt:</strong> <span style="color: #667eea; font-weight: 600;">${update.attempt_number || this.attemptNumber} / ${update.max_attempts || this.maxAttempts}</span></p>
                <p style="margin: 8px 0;"><strong style="color: #1a1a2e;">Attempts Remaining:</strong> <span style="color: #667eea; font-weight: 600;">${update.attempts_remaining || (this.maxAttempts - this.attemptNumber)}</span></p>
                <p style="margin: 8px 0;"><strong style="color: #1a1a2e;">Turn:</strong> <span style="color: #667eea; font-weight: 600;">${update.turn || 0}</span></p>
            </div>
            ${energyEventsHtml}
            <div style="margin: 20px 0; padding: 16px; background: rgba(102, 126, 234, 0.05); border-radius: 12px; border-left: 4px solid #667eea;">
                <p style="margin: 0 0 8px 0; font-weight: 700; color: #1a1a2e;">Current Prompt:</p>
                <p style="margin: 0; color: #1a1a2e; font-style: italic; word-wrap: break-word;">"${currentPrompt}"</p>
            </div>
            <p style="color: #1a1a2e; font-weight: 500;">Update your creatures' behavior to help them survive in the next attempt!</p>
        `;
        
        // Show prompt input section
        if (promptSection) {
            promptSection.style.display = 'block';
            const promptInput = document.getElementById('promptUpdateInput');
            if (promptInput) {
                promptInput.value = ''; // Clear previous input
            }
        }
        
        // Hide close button (user must submit prompt)
        const closeBtn = modal.querySelector('.close');
        if (closeBtn) {
            closeBtn.style.display = 'none';
        }
        
        modal.style.display = 'block';
    }

    showResults(results, stage) {
        const modal = document.getElementById('resultsModal');
        const content = document.getElementById('resultsContent');
        
        const player = results.player;
        const survived = results.survived;
        
        content.innerHTML = `
            <h2>Game Results</h2>
            <div class="player-results">
                <h3>Your Creature</h3>
                <p><strong>Alive:</strong> ${player.alive ? 'Yes' : 'No'}</p>
                <p><strong>Energy:</strong> ${player.energy}</p>
                <p><strong>Age:</strong> ${player.age}</p>
                <p><strong>Stage:</strong> ${player.stage}</p>
                <p><strong>Color:</strong> ${player.color}</p>
                <p><strong>Speed:</strong> ${player.speed}</p>
            </div>
            ${survived ? `<p class="winner">You survived!</p>` : '<p class="winner">Your creature did not survive.</p>'}
        `;
        
        modal.style.display = 'block';
    }


    showFinalResults(results, currentPrompt, energyEvents = []) {
        const modal = document.getElementById('resultsModal');
        const content = document.getElementById('resultsContent');
        const promptSection = document.getElementById('promptUpdateSection');
        const closeBtn = modal.querySelector('.close');
        
        const player = results.player;
        const survived = results.survived;
        const prompt = currentPrompt || 'N/A';
        
        // Format energy events list
        let energyEventsHtml = '';
        if (energyEvents && energyEvents.length > 0) {
            energyEventsHtml = `
                <div style="margin: 20px 0; padding: 16px; background: rgba(246, 224, 94, 0.15); border-radius: 12px; border-left: 4px solid #f6e05e;">
                    <p style="margin: 0 0 10px 0; font-weight: 700; color: #1a1a2e;">Energy Events (Final Attempt):</p>
                    <ul style="margin: 0; padding-left: 20px; color: #1a1a2e;">
                        ${energyEvents.map(event => `<li style="margin: 5px 0; font-family: 'Inter', monospace; font-size: 13px;">${event}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        content.innerHTML = `
            <h2 style="color: #1a1a2e; font-weight: 800; margin-top: 0;">Final Results - Game Complete!</h2>
            <div class="player-results">
                <h3>Your Creature</h3>
                <p style="margin: 8px 0;"><strong style="color: #1a1a2e;">Final Energy:</strong> <span style="color: #667eea; font-weight: 600;">${player.energy}</span></p>
                <p style="margin: 8px 0;"><strong style="color: #1a1a2e;">Final Stage:</strong> <span style="color: #667eea; font-weight: 600;">${player.stage}</span></p>
                <p style="margin: 8px 0;"><strong style="color: #1a1a2e;">Survived:</strong> <span style="color: ${survived ? '#48bb78' : '#f56565'}; font-weight: 600;">${survived ? 'Yes' : 'No'}</span></p>
                <p style="margin: 8px 0;"><strong style="color: #1a1a2e;">Age:</strong> <span style="color: #667eea; font-weight: 600;">${player.age}</span></p>
                <p style="margin: 8px 0;"><strong style="color: #1a1a2e;">Color:</strong> <span style="color: #667eea; font-weight: 600;">${player.color}</span></p>
                <p style="margin: 8px 0;"><strong style="color: #1a1a2e;">Speed:</strong> <span style="color: #667eea; font-weight: 600;">${player.speed}</span></p>
            </div>
            ${energyEventsHtml}
            <div style="margin: 20px 0; padding: 16px; background: rgba(102, 126, 234, 0.05); border-radius: 12px; border-left: 4px solid #667eea;">
                <p style="margin: 0 0 8px 0; font-weight: 700; color: #1a1a2e;">Final Prompt:</p>
                <p style="margin: 0; color: #1a1a2e; font-style: italic; word-wrap: break-word;">"${prompt}"</p>
            </div>
            ${survived ? `<p class="winner">🏆 You survived!</p>` : '<p class="winner">Your creature did not survive.</p>'}
            <button onclick="document.getElementById('resultsModal').style.display='none'" style="padding: 12px 24px; font-size: 14px; font-weight: 600; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 10px; cursor: pointer; margin-top: 20px; width: 100%; transition: all 0.3s ease; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);">Close</button>
        `;
        
        // Hide prompt input section for final results
        if (promptSection) {
            promptSection.style.display = 'none';
        }
        
        // Show close button
        if (closeBtn) {
            closeBtn.style.display = 'block';
        }
        
        modal.style.display = 'block';
    }

    render() {
        if (!this.gameState || !this.gameState.world) return;

        // Update hover detection to ensure tooltips work after game updates
        // This ensures tooltips continue to appear even after many game state updates
        this.detectHoveredElement();

        // Disable image smoothing for pixel-perfect rendering
        this.ctx.imageSmoothingEnabled = false;
        this.ctx.imageSmoothingQuality = 'low';

        // Clear canvas with solid background (day/night aware) - pixel art style
        const env = this.gameState.environment || this.gameState.world?.environment;
        const isDay = env?.is_day !== false; // Default to day
        // Use solid colors instead of gradients for pixel art
        this.ctx.fillStyle = isDay ? '#e8f0f8' : '#2a3441';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw biomes (before grid)
        if (env?.biomes) {
            this.drawBiomes(env.biomes);
        }

        // Draw grid
        this.drawGrid();

        // Draw natural disasters
        if (this.gameState.world.disasters) {
            this.gameState.world.disasters.forEach(disaster => this.drawDisaster(disaster));
        }

        // Draw territory markers
        if (this.gameState.world.territories) {
            this.drawTerritories(this.gameState.world.territories);
        }

        // Draw regional food density (background tint)
        if (this.gameState.world.regions) {
            this.drawRegionalDensity(this.gameState.world.regions);
        }

        // Draw resources
        if (this.gameState.world.resources) {
            this.gameState.world.resources.food.forEach(food => this.drawFood(food));
        }

        // Draw creatures
        if (this.gameState.world.creatures) {
            this.gameState.world.creatures.forEach(creature => this.drawCreature(creature));
        }

        // Draw weather effects
        const weather = env?.weather;
        if (weather) {
            this.drawWeather(weather);
        }

        // Draw UI
        this.drawUI(this.gameState.turn || 0);
        
        // Draw hover highlight and tooltip
        if (this.hoveredElement) {
            this.drawHoverHighlight(this.hoveredElement);
            this.drawTooltip(this.hoveredElement);
        }
    }
    
    drawHoverHighlight(element) {
        const { type, data, x, y } = element;
        
        this.ctx.save();
        this.ctx.imageSmoothingEnabled = false;
        
        // Draw a subtle highlight circle/square around the element
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 2;
        this.ctx.setLineDash([4, 4]);
        
        if (type === 'creature' || type === 'predator') {
            // Circle highlight for creatures
            this.ctx.beginPath();
            this.ctx.arc(x, y, 18, 0, Math.PI * 2);
            this.ctx.stroke();
        } else if (type === 'food') {
            // Square highlight for food
            this.ctx.strokeRect(x - 12, y - 12, 24, 24);
        } else if (type === 'disaster') {
            const radius = (data.radius || 3) * this.cellSize;
            this.ctx.strokeRect(x - radius, y - radius, radius * 2, radius * 2);
        } else if (type === 'biome' || type === 'territory') {
            // Grid cell highlight
            this.ctx.strokeRect(x - this.cellSize / 2, y - this.cellSize / 2, this.cellSize, this.cellSize);
        }
        
        this.ctx.setLineDash([]);
        this.ctx.restore();
    }
    
    drawTooltip(element) {
        const { type, data, x, y } = element;
        
        this.ctx.save();
        this.ctx.imageSmoothingEnabled = false;
        
        let tooltipText = '';
        let tooltipColor = '#ffffff';
        
        switch (type) {
            case 'creature':
                const isPlayer = data.player_id !== null && data.player_id !== undefined;
                tooltipText = isPlayer ? 'Your Creature' : 'Creature';
                tooltipColor = '#667eea';
                break;
            case 'predator':
                tooltipText = 'Predator (Danger!)';
                tooltipColor = '#c53030';
                break;
            case 'food':
                const foodType = data.type || 'food';
                const foodNames = {
                    'apple': 'Apple',
                    'banana': 'Banana',
                    'grapes': 'Grapes',
                    'water': 'Water Source',
                    'shelter': 'Shelter'
                };
                tooltipText = foodNames[foodType] || foodType.charAt(0).toUpperCase() + foodType.slice(1);
                tooltipColor = '#48bb78';
                break;
            case 'disaster':
                const disasterNames = {
                    'earthquake': 'Earthquake',
                    'flood': 'Flood'
                };
                tooltipText = disasterNames[data.type] || 'Disaster';
                tooltipColor = '#ed8936';
                break;
            case 'biome':
                const biomeNames = {
                    'forest': 'Forest',
                    'snow': 'Snow',
                    'desert': 'Desert',
                    'grassland': 'Grassland',
                    'tundra': 'Tundra'
                };
                tooltipText = biomeNames[data.type] || data.type;
                tooltipColor = '#9f7aea';
                break;
            case 'territory':
                tooltipText = 'Territory';
                tooltipColor = '#ed8936';
                break;
        }
        
        // Measure text
        this.ctx.font = 'bold 12px monospace';
        this.ctx.textAlign = 'center';
        const metrics = this.ctx.measureText(tooltipText);
        const textWidth = metrics.width;
        const padding = 8;
        const boxWidth = textWidth + padding * 2;
        const boxHeight = 24;
        
        // Calculate tooltip position (above element, but adjust if near edges)
        let tooltipX = x;
        let tooltipY = y - 35;
        
        // Adjust if tooltip would go off left edge
        if (tooltipX - boxWidth / 2 < 5) {
            tooltipX = boxWidth / 2 + 5;
        }
        // Adjust if tooltip would go off right edge
        if (tooltipX + boxWidth / 2 > this.canvas.width - 5) {
            tooltipX = this.canvas.width - boxWidth / 2 - 5;
        }
        
        // Adjust if tooltip would go off top edge (show below instead)
        const totalHeight = (type === 'creature' || type === 'predator') ? boxHeight + 22 : boxHeight;
        if (tooltipY - totalHeight < 40) {
            tooltipY = y + 35; // Show below instead
        }
        
        // Draw additional info for creatures (above main tooltip)
        if (type === 'creature' || type === 'predator') {
            const infoText = `Energy: ${Math.round(data.energy || 0)} | Stage: ${data.stage || 1}`;
            this.ctx.font = '10px monospace';
            const infoMetrics = this.ctx.measureText(infoText);
            const infoWidth = infoMetrics.width + padding * 2;
            const infoHeight = 20;
            
            // Adjust info box position if main tooltip is below
            let infoY = tooltipY - boxHeight - infoHeight - 2;
            if (tooltipY > y) {
                // Tooltip is below, so info should be above tooltip
                infoY = tooltipY + boxHeight + 2;
            }
            
            // Adjust info box X to match tooltip
            let infoX = tooltipX;
            if (infoX - infoWidth / 2 < 5) {
                infoX = infoWidth / 2 + 5;
            }
            if (infoX + infoWidth / 2 > this.canvas.width - 5) {
                infoX = this.canvas.width - infoWidth / 2 - 5;
            }
            
            this.ctx.fillStyle = '#1a1a2e';
            this.ctx.fillRect(
                Math.round(infoX - infoWidth / 2),
                Math.round(infoY),
                infoWidth,
                infoHeight
            );
            
            this.ctx.strokeStyle = tooltipColor;
            this.ctx.lineWidth = 1;
            this.ctx.strokeRect(
                Math.round(infoX - infoWidth / 2),
                Math.round(infoY),
                infoWidth,
                infoHeight
            );
            
            this.ctx.fillStyle = '#ffffff';
            this.ctx.fillText(infoText, infoX, infoY + infoHeight / 2);
        }
        
        // Draw tooltip background
        this.ctx.fillStyle = tooltipColor;
        this.ctx.fillRect(
            Math.round(tooltipX - boxWidth / 2),
            Math.round(tooltipY - boxHeight),
            boxWidth,
            boxHeight
        );
        
        // Draw border
        this.ctx.strokeStyle = '#1a1a2e';
        this.ctx.lineWidth = 2;
        this.ctx.strokeRect(
            Math.round(tooltipX - boxWidth / 2),
            Math.round(tooltipY - boxHeight),
            boxWidth,
            boxHeight
        );
        
        // Draw text
        this.ctx.fillStyle = '#ffffff';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(tooltipText, tooltipX, tooltipY - boxHeight / 2);
        
        this.ctx.restore();
    }

    drawBiomes(biomes) {
        // Draw biome tiles for each grid cell
        const cellSize = this.cellSize;
        this.ctx.save();
        this.ctx.imageSmoothingEnabled = false;
        
        // Biome color and pattern definitions
        const biomeStyles = {
            'forest': {
                baseColor: '#4a7c59',
                patternColor: '#3a5c47',
                lightColor: '#5a9c6a'
            },
            'snow': {
                baseColor: '#e8f0f8',
                patternColor: '#d0e0f0',
                lightColor: '#f0f8ff'
            },
            'desert': {
                baseColor: '#d4a574',
                patternColor: '#c49564',
                lightColor: '#e4b584'
            },
            'grassland': {
                baseColor: '#7cb342',
                patternColor: '#689f38',
                lightColor: '#8bc34a'
            },
            'tundra': {
                baseColor: '#b0bec5',
                patternColor: '#90a4ae',
                lightColor: '#cfd8dc'
            }
        };
        
        // Draw biome tiles
        for (const [key, biomeType] of Object.entries(biomes)) {
            const [x, y] = key.split(',').map(Number);
            const pixelX = Math.round(x * cellSize);
            const pixelY = Math.round(y * cellSize);
            
            const style = biomeStyles[biomeType] || biomeStyles['grassland'];
            
            // Fill cell with base color
            this.ctx.fillStyle = style.baseColor;
            this.ctx.fillRect(pixelX, pixelY, cellSize, cellSize);
            
            // Add pixel art pattern based on biome
            if (biomeType === 'forest') {
                // Tree-like pattern (vertical lines)
                for (let i = 0; i < 3; i++) {
                    const px = pixelX + 5 + i * 7;
                    this.ctx.fillStyle = style.patternColor;
                    this.ctx.fillRect(px, pixelY + 3, 2, cellSize - 6);
                    // Tree top (small circle)
                    for (let py = pixelY + 2; py < pixelY + 8; py++) {
                        for (let px2 = px - 1; px2 < px + 3; px2++) {
                            const dx = px2 - (px + 0.5);
                            const dy = py - (pixelY + 4);
                            if (dx*dx + dy*dy < 2) {
                                this.ctx.fillStyle = style.patternColor;
                                this.ctx.fillRect(px2, py, 1, 1);
                            }
                        }
                    }
                }
            } else if (biomeType === 'snow') {
                // Snowflake pattern (dots)
                const dots = [[5, 5], [12, 8], [20, 5], [8, 15], [17, 18]];
                this.ctx.fillStyle = style.patternColor;
                dots.forEach(([dx, dy]) => {
                    this.ctx.fillRect(pixelX + dx, pixelY + dy, 2, 2);
                });
            } else if (biomeType === 'desert') {
                // Sand dune pattern (curved lines)
                this.ctx.fillStyle = style.patternColor;
                for (let i = 0; i < 2; i++) {
                    const startX = pixelX + 3 + i * 12;
                    for (let y = 0; y < cellSize; y++) {
                        const offset = Math.sin((y / cellSize) * Math.PI) * 3;
                        this.ctx.fillRect(Math.round(startX + offset), pixelY + y, 1, 1);
                    }
                }
            } else if (biomeType === 'grassland') {
                // Grass blade pattern (small vertical lines)
                this.ctx.fillStyle = style.patternColor;
                for (let i = 0; i < 8; i++) {
                    const px = pixelX + 3 + (i % 4) * 7;
                    const py = pixelY + 5 + Math.floor(i / 4) * 10;
                    this.ctx.fillRect(px, py, 1, 4);
                    // Small blade curve
                    this.ctx.fillRect(px + 1, py + 1, 1, 1);
                }
            } else if (biomeType === 'tundra') {
                // Sparse pattern (few dots)
                this.ctx.fillStyle = style.patternColor;
                const sparseDots = [[8, 8], [18, 12], [12, 20]];
                sparseDots.forEach(([dx, dy]) => {
                    this.ctx.fillRect(pixelX + dx, pixelY + dy, 1, 1);
                });
            }
        }
        
        this.ctx.restore();
    }

    drawGrid() {
        const cellSize = this.cellSize;
        // Pixel-perfect grid lines (1px solid, no anti-aliasing)
        this.ctx.strokeStyle = 'rgba(102, 126, 234, 0.2)';
        this.ctx.lineWidth = 1;

        const gridWidth = Math.floor(this.canvas.width / cellSize);
        const gridHeight = Math.floor(this.canvas.height / cellSize);

        // Use integer coordinates for pixel-perfect alignment
        for (let i = 0; i <= gridWidth; i++) {
            const x = Math.round(i * cellSize);
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, this.canvas.height);
            this.ctx.stroke();
        }

        for (let i = 0; i <= gridHeight; i++) {
            const y = Math.round(i * cellSize);
            this.ctx.beginPath();
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(this.canvas.width, y);
            this.ctx.stroke();
        }
    }

    // Helper function to draw a pixel block
    drawPixelBlock(x, y, size, color) {
        this.ctx.fillStyle = color;
        this.ctx.fillRect(Math.round(x), Math.round(y), size, size);
    }

    // Generate placeholder pixel art sprite for creatures
    generatePixelArtSprite(creature) {
        const cacheKey = `${creature.color}_${creature.stage}_${creature.id || 'default'}`;
        
        // Check cache first
        if (this.pixelArtSpriteCache[cacheKey]) {
            return this.pixelArtSpriteCache[cacheKey];
        }

        // Create a 64x64 canvas for the sprite
        const spriteCanvas = document.createElement('canvas');
        spriteCanvas.width = 64;
        spriteCanvas.height = 64;
        const spriteCtx = spriteCanvas.getContext('2d');
        spriteCtx.imageSmoothingEnabled = false;

        // Color mapping
        const colorMap = {
            'blue': '#667eea',
            'red': '#f56565',
            'green': '#48bb78',
            'yellow': '#f6e05e',
            'purple': '#9f7aea',
            'orange': '#ed8936',
            'pink': '#ed64a6',
            'cyan': '#38b2ac',
            'brown': '#8b7355',
            'black': '#2d3748',
            'white': '#f0f0f0'
        };

        const creatureColor = creature.color ? String(creature.color).toLowerCase().trim() : 'blue';
        const fillColor = colorMap[creatureColor] || (creatureColor.startsWith('#') ? creatureColor : '#667eea');
        const darkColor = this.darkenColor(fillColor, 20);
        const lightColor = this.lightenColor(fillColor, 15);
        const stage = creature.stage || 1;

        // Draw pixel art based on stage
        if (stage === 1) {
            // Stage 1: Simple pixel creature (8x8 pixel blocks)
            const centerX = 32;
            const centerY = 32;
            const size = 16;
            
            // Main body (pixelated circle approximation)
            for (let py = 0; py < size; py++) {
                for (let px = 0; px < size; px++) {
                    const dx = px - size/2;
                    const dy = py - size/2;
                    const dist = Math.sqrt(dx*dx + dy*dy);
                    if (dist < size/2 - 1) {
                        spriteCtx.fillStyle = fillColor;
                        spriteCtx.fillRect(centerX - size/2 + px, centerY - size/2 + py, 1, 1);
                    } else if (dist < size/2) {
                        spriteCtx.fillStyle = darkColor;
                        spriteCtx.fillRect(centerX - size/2 + px, centerY - size/2 + py, 1, 1);
                    }
                }
            }
            // Add highlight
            spriteCtx.fillStyle = lightColor;
            spriteCtx.fillRect(centerX - 4, centerY - 4, 3, 3);
            
        } else if (stage === 2) {
            // Stage 2: Pixelated colony (multiple connected pixel blocks)
            const centerX = 32;
            const centerY = 32;
            const colonySize = creature.colony_size || 3;
            
            // Main body
            for (let py = 0; py < 20; py++) {
                for (let px = 0; px < 20; px++) {
                    const dx = px - 10;
                    const dy = py - 10;
                    const dist = Math.sqrt(dx*dx + dy*dy);
                    if (dist < 9) {
                        spriteCtx.fillStyle = fillColor;
                        spriteCtx.fillRect(centerX - 10 + px, centerY - 10 + py, 1, 1);
                    } else if (dist < 10) {
                        spriteCtx.fillStyle = darkColor;
                        spriteCtx.fillRect(centerX - 10 + px, centerY - 10 + py, 1, 1);
                    }
                }
            }
            
            // Add colony cells
            for (let i = 0; i < Math.min(colonySize, 5); i++) {
                const angle = (i * Math.PI * 2) / Math.min(colonySize, 5);
                const offsetX = Math.round(Math.cos(angle) * 12);
                const offsetY = Math.round(Math.sin(angle) * 12);
                const cellX = centerX + offsetX;
                const cellY = centerY + offsetY;
                
                // Draw small pixel cell
                for (let py = 0; py < 6; py++) {
                    for (let px = 0; px < 6; px++) {
                        const dx = px - 3;
                        const dy = py - 3;
                        if (dx*dx + dy*dy < 8) {
                            spriteCtx.fillStyle = fillColor;
                            spriteCtx.fillRect(cellX - 3 + px, cellY - 3 + py, 1, 1);
                        }
                    }
                }
            }
            
        } else if (stage === 3) {
            // Stage 3: Pixelated organism with pixel limbs/features
            const centerX = 32;
            const centerY = 32;
            const limbs = creature.parts?.limbs || 4;
            
            // Main body (larger)
            for (let py = 0; py < 24; py++) {
                for (let px = 0; px < 24; px++) {
                    const dx = px - 12;
                    const dy = py - 12;
                    const dist = Math.sqrt(dx*dx + dy*dy);
                    if (dist < 11) {
                        spriteCtx.fillStyle = fillColor;
                        spriteCtx.fillRect(centerX - 12 + px, centerY - 12 + py, 1, 1);
                    } else if (dist < 12) {
                        spriteCtx.fillStyle = darkColor;
                        spriteCtx.fillRect(centerX - 12 + px, centerY - 12 + py, 1, 1);
                    }
                }
            }
            
            // Add limbs
            for (let i = 0; i < limbs; i++) {
                const angle = (i * Math.PI * 2) / limbs;
                const startX = centerX + Math.round(Math.cos(angle) * 12);
                const startY = centerY + Math.round(Math.sin(angle) * 12);
                const endX = centerX + Math.round(Math.cos(angle) * 18);
                const endY = centerY + Math.round(Math.sin(angle) * 18);
                
                // Draw pixel limb (thick line)
                const steps = 8;
                for (let s = 0; s <= steps; s++) {
                    const px = Math.round(startX + (endX - startX) * s / steps);
                    const py = Math.round(startY + (endY - startY) * s / steps);
                    spriteCtx.fillStyle = darkColor;
                    spriteCtx.fillRect(px - 1, py - 1, 3, 3);
                }
            }
            
            // Add highlight
            spriteCtx.fillStyle = lightColor;
            spriteCtx.fillRect(centerX - 5, centerY - 5, 4, 4);
        }

        // Convert to Image and cache
        const img = new Image();
        img.src = spriteCanvas.toDataURL();
        // Mark as complete immediately since it's from canvas
        img.complete = true;
        img.naturalWidth = 64;
        img.naturalHeight = 64;
        this.pixelArtSpriteCache[cacheKey] = img;
        return img;
    }

    drawCreature(creature) {
        const x = Math.round(creature.x * this.cellSize + this.cellSize / 2);
        const y = Math.round(creature.y * this.cellSize + this.cellSize / 2);

        // Check if this is an NPC predator (player_id is null)
        const isPredator = creature.player_id === null || creature.player_id === undefined;

        // Try to use sprite if available
        if (creature.sprite_url && !isPredator) {
            const sprite = this.spriteCache[creature.sprite_url];
            if (sprite && sprite.complete && sprite.naturalWidth > 0) {
                // Sprite loaded successfully, draw it with pixel-perfect scaling
                const spriteSize = 32;
                
                this.ctx.save();
                this.ctx.imageSmoothingEnabled = false;
                
                // Draw sprite with pixel-perfect scaling (nearest-neighbor)
                this.ctx.drawImage(
                    sprite,
                    Math.round(x - spriteSize / 2),
                    Math.round(y - spriteSize / 2),
                    spriteSize,
                    spriteSize
                );
                this.ctx.restore();
                
                // Draw energy indicator on top
                this.drawEnergyBar(x, y, creature.energy);
                return;
            } else if (!sprite || (sprite && !sprite.complete)) {
                // Sprite not in cache or still loading, start loading it
                if (!sprite) {
                    const img = new Image();
                    img.crossOrigin = 'anonymous';
                    img.onload = () => {
                        console.log(`✓ Sprite loaded: ${creature.sprite_url}`);
                        this.spriteCache[creature.sprite_url] = img;
                        if (this.animationFrame) {
                            cancelAnimationFrame(this.animationFrame);
                        }
                        this.animationFrame = requestAnimationFrame(() => this.render());
                    };
                    img.onerror = (e) => {
                        console.warn(`✗ Failed to load sprite: ${creature.sprite_url}`, e);
                        this.spriteCache[creature.sprite_url] = null;
                    };
                    const fullUrl = `http://localhost:8000${creature.sprite_url}`;
                    console.log(`Loading sprite: ${fullUrl}`);
                    img.src = fullUrl;
                    this.spriteCache[creature.sprite_url] = img;
                }
            }
        }

        // Fallback: Generate pixel art sprite
        const pixelSprite = this.generatePixelArtSprite(creature);
        if (pixelSprite && pixelSprite.complete) {
            const spriteSize = 32;
            this.ctx.save();
            this.ctx.imageSmoothingEnabled = false;
            this.ctx.drawImage(
                pixelSprite,
                Math.round(x - spriteSize / 2),
                Math.round(y - spriteSize / 2),
                spriteSize,
                spriteSize
            );
            this.ctx.restore();
        } else {
            // If sprite not ready yet, draw simple pixel placeholder
            const colorMap = {
                'blue': '#667eea',
                'red': '#f56565',
                'green': '#48bb78',
                'yellow': '#f6e05e',
                'purple': '#9f7aea',
                'orange': '#ed8936',
                'pink': '#ed64a6',
                'cyan': '#38b2ac',
                'brown': '#8b7355',
                'black': '#2d3748',
                'white': '#f0f0f0'
            };

            const creatureColor = creature.color ? String(creature.color).toLowerCase().trim() : 'blue';
            const fillColor = isPredator ? '#c53030' : (colorMap[creatureColor] || (creatureColor.startsWith('#') ? creatureColor : '#667eea'));
            const darkColor = this.darkenColor(fillColor, 20);
            const stage = creature.stage || 1;
            
            // Draw simple pixel art creature
            const size = stage === 1 ? 12 : (stage === 2 ? 14 : 16);
            
            // Draw main body as pixel blocks
            for (let py = -size; py <= size; py++) {
                for (let px = -size; px <= size; px++) {
                    const dist = Math.sqrt(px*px + py*py);
                    if (dist < size - 1) {
                        this.ctx.fillStyle = fillColor;
                        this.drawPixelBlock(x + px, y + py, 1, fillColor);
                    } else if (dist < size) {
                        this.ctx.fillStyle = darkColor;
                        this.drawPixelBlock(x + px, y + py, 1, darkColor);
                    }
                }
            }
        }

        // Draw energy indicator
        this.drawEnergyBar(x, y, creature.energy);
        
        // Draw predator indicator (pixel art skull)
        if (isPredator) {
            this.ctx.save();
            this.ctx.fillStyle = '#c53030';
            // Draw simple pixel skull (5x5 block)
            for (let py = 0; py < 5; py++) {
                for (let px = 0; px < 5; px++) {
                    if ((px === 0 || px === 4) && py > 0 && py < 4) continue; // Eye holes
                    if (px === 2 && py === 2) continue; // Nose
                    this.drawPixelBlock(x - 2 + px, y - 25 + py, 1, '#c53030');
                }
            }
            this.ctx.restore();
        }
        
        // Draw combat indicator if creature just attacked (pixel border)
        if (creature.recent_action === 'attack') {
            this.ctx.save();
            this.ctx.strokeStyle = '#f56565';
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            // Draw pixelated square border
            const borderSize = 18;
            this.ctx.strokeRect(Math.round(x - borderSize), Math.round(y - borderSize), borderSize * 2, borderSize * 2);
            this.ctx.restore();
        }
        
        // Draw custom action indicators (pixel art icons)
        if (creature.custom_actions) {
            const actionIcons = {
                'signal': '📡',
                'claim': '🛡️',
                'cooperate': '🤝',
                'migrate': '🔄'
            };
            
            let iconY = y - 30;
            creature.custom_actions.forEach(action => {
                if (actionIcons[action]) {
                    this.ctx.save();
                    this.ctx.font = '12px monospace';
                    this.ctx.textAlign = 'center';
                    this.ctx.textBaseline = 'middle';
                    this.ctx.fillText(actionIcons[action], x + 20, iconY);
                    iconY += 15;
                    this.ctx.restore();
                }
            });
        }
    }
    
    lightenColor(color, percent) {
        const num = parseInt(color.replace("#",""), 16);
        const amt = Math.round(2.55 * percent);
        const R = Math.min(255, (num >> 16) + amt);
        const G = Math.min(255, ((num >> 8) & 0x00FF) + amt);
        const B = Math.min(255, (num & 0x0000FF) + amt);
        return "#" + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
    }
    
    darkenColor(color, percent) {
        const num = parseInt(color.replace("#",""), 16);
        const amt = Math.round(2.55 * percent);
        const R = Math.max(0, (num >> 16) - amt);
        const G = Math.max(0, ((num >> 8) & 0x00FF) - amt);
        const B = Math.max(0, (num & 0x0000FF) - amt);
        return "#" + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
    }

    drawEnergyBar(x, y, energy) {
        const energyPercent = Math.max(0, Math.min(1, energy / 100));
        const barWidth = 20;
        const barHeight = 4;
        const barX = Math.round(x - barWidth / 2);
        const barY = Math.round(y - 22);

        // Draw background (pixel art style - solid color, no rounded corners)
        this.ctx.fillStyle = '#2d3748';
        this.ctx.fillRect(barX, barY, barWidth, barHeight);

        // Draw energy bar (pixel art style - flat color, no gradient)
        const energyColor = energyPercent > 0.5 ? '#48bb78' : (energyPercent > 0.25 ? '#f6e05e' : '#f56565');
        this.ctx.fillStyle = energyColor;
        this.ctx.fillRect(barX, barY, Math.round(barWidth * energyPercent), barHeight);
        
        // Draw border (pixel art style - 1px solid)
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 1;
        this.ctx.strokeRect(barX, barY, barWidth, barHeight);
    }

    drawRegionalDensity(regions) {
        // Draw regional food density as background tint
        const regionSize = 5;
        const cellSize = this.cellSize;
        
        this.ctx.save();
        this.ctx.globalAlpha = 0.15;
        
        for (const [key, density] of Object.entries(regions)) {
            const [rx, ry] = key.split(',').map(Number);
            const startX = rx * regionSize * cellSize;
            const startY = ry * regionSize * cellSize;
            const width = regionSize * cellSize;
            const height = regionSize * cellSize;
            
            // Color based on density: low = red tint, high = green tint
            const intensity = (density - 0.3) / 1.2; // Normalize 0.3-1.5 to 0-1
            const r = Math.floor(255 * (1 - intensity));
            const g = Math.floor(255 * intensity);
            const b = 0;
            
            this.ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.2)`;
            this.ctx.fillRect(startX, startY, width, height);
        }
        
        this.ctx.restore();
    }

    drawDisaster(disaster) {
        const x = Math.round(disaster.x * this.cellSize + this.cellSize / 2);
        const y = Math.round(disaster.y * this.cellSize + this.cellSize / 2);
        const radius = (disaster.radius || 3) * this.cellSize;
        const disasterType = disaster.type;
        
        this.ctx.save();
        this.ctx.imageSmoothingEnabled = false;
        
        // Animated pulsing effect for disasters (pixel-based)
        const pulsePhase = Math.floor((Date.now() / 500) % 4); // 0-3 for pixel animation
        
        if (disasterType === 'earthquake') {
            // Earthquake - brown/orange pixel art
            const size = Math.round(radius);
            this.ctx.fillStyle = '#8b4513';
            this.ctx.fillRect(x - size, y - size, size * 2, size * 2);
            
            // Draw pixel crack lines
            this.ctx.strokeStyle = '#654321';
            this.ctx.lineWidth = 2;
            for (let i = 0; i < 4; i++) {
                const angle = (i * Math.PI * 2) / 4;
                const startX = Math.round(x + Math.cos(angle) * (size * 0.3));
                const startY = Math.round(y + Math.sin(angle) * (size * 0.3));
                const endX = Math.round(x + Math.cos(angle) * size);
                const endY = Math.round(y + Math.sin(angle) * size);
                this.ctx.beginPath();
                this.ctx.moveTo(startX, startY);
                this.ctx.lineTo(endX, endY);
                this.ctx.stroke();
            }
            
            // Draw pixel art earthquake symbol (cracked square)
            this.ctx.fillStyle = '#a0522d';
            this.ctx.fillRect(x - 4, y - 4, 8, 8);
            // Add crack through center
            this.ctx.strokeStyle = '#654321';
            this.ctx.lineWidth = 1;
            this.ctx.beginPath();
            this.ctx.moveTo(x - 2, y - 2);
            this.ctx.lineTo(x + 2, y + 2);
            this.ctx.stroke();
            
        } else if (disasterType === 'flood') {
            // Flood - blue pixel art with wave pattern
            const size = Math.round(radius);
            this.ctx.fillStyle = '#38b2ac';
            this.ctx.fillRect(x - size, y - size, size * 2, size * 2);
            
            // Draw pixel wave pattern
            this.ctx.strokeStyle = '#2c7a7b';
            this.ctx.lineWidth = 2;
            for (let i = 0; i < 3; i++) {
                const waveY = Math.round(y - size + (i * size / 2) + pulsePhase);
                this.ctx.beginPath();
                // Draw pixelated wave
                for (let j = 0; j <= size * 2; j += 2) {
                    const px = x - size + j;
                    const py = waveY + Math.sin((j / (size * 2)) * Math.PI * 2) * 2;
                    if (j === 0) {
                        this.ctx.moveTo(px, Math.round(py));
                    } else {
                        this.ctx.lineTo(px, Math.round(py));
                    }
                }
                this.ctx.stroke();
            }
            
            // Draw pixel art flood symbol (water drop)
            this.ctx.fillStyle = '#2c7a7b';
            for (let py = 0; py < 6; py++) {
                for (let px = 0; px < 6; px++) {
                    const dist = Math.sqrt((px - 3)*(px - 3) + (py - 3)*(py - 3));
                    if (dist < 2.5 && py < 4) {
                        this.drawPixelBlock(x - 3 + px, y - 3 + py, 1, '#2c7a7b');
                    }
                }
            }
        }
        
        // Draw duration indicator (pixel art style)
        if (disaster.duration && disaster.elapsed !== undefined) {
            const remaining = disaster.duration - disaster.elapsed;
            if (remaining > 0) {
                this.ctx.fillStyle = '#ffffff';
                this.ctx.font = 'bold 10px monospace';
                this.ctx.textAlign = 'center';
                this.ctx.textBaseline = 'top';
                this.ctx.fillText(`${remaining}`, x, y + radius + 5);
            }
        }
        
        this.ctx.restore();
    }

    drawTerritories(territories) {
        // Draw territory markers with color coding by owner
        const regionSize = 5;
        const cellSize = this.cellSize;
        
        this.ctx.save();
        this.ctx.globalAlpha = 0.3;
        
        // Color palette for different owners (cycling through colors)
        const territoryColors = [
            { border: 'rgba(237, 137, 54, 0.8)', fill: 'rgba(237, 137, 54, 0.15)' }, // Orange
            { border: 'rgba(245, 101, 101, 0.8)', fill: 'rgba(245, 101, 101, 0.15)' }, // Red
            { border: 'rgba(102, 126, 234, 0.8)', fill: 'rgba(102, 126, 234, 0.15)' }, // Blue
            { border: 'rgba(159, 122, 234, 0.8)', fill: 'rgba(159, 122, 234, 0.15)' }, // Purple
            { border: 'rgba(72, 187, 120, 0.8)', fill: 'rgba(72, 187, 120, 0.15)' }, // Green
        ];
        
        // Track which colors are assigned to which owners
        const ownerColorMap = {};
        let colorIndex = 0;
        
        for (const [key, ownerId] of Object.entries(territories)) {
            const [rx, ry] = key.split(',').map(Number);
            const startX = rx * regionSize * cellSize;
            const startY = ry * regionSize * cellSize;
            const width = regionSize * cellSize;
            const height = regionSize * cellSize;
            
            // Assign color to owner if not already assigned
            if (!ownerColorMap[ownerId]) {
                ownerColorMap[ownerId] = territoryColors[colorIndex % territoryColors.length];
                colorIndex++;
            }
            
            const colors = ownerColorMap[ownerId];
            
            // Draw territory border
            this.ctx.strokeStyle = colors.border;
            this.ctx.lineWidth = 3;
            this.ctx.setLineDash([5, 5]);
            this.ctx.strokeRect(startX, startY, width, height);
            
            // Draw claim marker (semi-transparent fill)
            this.ctx.fillStyle = colors.fill;
            this.ctx.fillRect(startX, startY, width, height);
            
            // Draw owner indicator (small circle at center)
            const centerX = startX + width / 2;
            const centerY = startY + height / 2;
            this.ctx.fillStyle = colors.border;
            this.ctx.beginPath();
            this.ctx.arc(centerX, centerY, 4, 0, Math.PI * 2);
            this.ctx.fill();
        }
        
        this.ctx.setLineDash([]);
        this.ctx.restore();
    }

    drawWeather(weather) {
        if (weather === 'storm' || weather === 'fog') {
            this.ctx.save();
            this.ctx.imageSmoothingEnabled = false;
            this.ctx.globalAlpha = 0.3;
            
            if (weather === 'storm') {
                // Draw pixel rain effect
                this.ctx.fillStyle = '#6496c8';
                for (let i = 0; i < 50; i++) {
                    const x = Math.round(Math.random() * this.canvas.width);
                    const y = Math.round(Math.random() * this.canvas.height);
                    // Draw pixel rain drops (1x3 pixels)
                    this.ctx.fillRect(x, y, 1, 3);
                }
            } else if (weather === 'fog') {
                // Draw pixel fog effect
                this.ctx.fillStyle = '#c8c8c8';
                for (let i = 0; i < 20; i++) {
                    const x = Math.round(Math.random() * this.canvas.width);
                    const y = Math.round(Math.random() * this.canvas.height);
                    const size = Math.round(30 + Math.random() * 40);
                    // Draw pixelated fog squares
                    this.ctx.fillRect(x, y, size, size);
                }
            }
            
            this.ctx.restore();
        }
    }

    preloadFoodSprites() {
        // Preload all food sprites
        const foodTypes = ['apple', 'banana', 'grapes', 'water', 'shelter'];
        foodTypes.forEach(foodType => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => {
                this.foodSpriteCache[foodType] = img;
                // Re-render legend when sprite loads
                this.renderLegendPreviews();
            };
            img.onerror = () => {
                console.warn(`Failed to load food sprite: ${foodType}`);
                this.foodSpriteCache[foodType] = null;
            };
            img.src = `http://localhost:8000/static/sprites/food/${foodType}.png`;
            this.foodSpriteCache[foodType] = img; // Store reference even if not loaded yet
        });
    }

    loadFoodSprite(foodType) {
        // Get sprite from cache or return null
        const sprite = this.foodSpriteCache[foodType];
        if (sprite && sprite.complete && sprite.naturalWidth > 0) {
            return sprite;
        }
        return null;
    }

    drawFood(food) {
        const x = Math.round(food.x * this.cellSize + this.cellSize / 2);
        const y = Math.round(food.y * this.cellSize + this.cellSize / 2);
        
        const foodType = food.type || 'apple';
        
        this.ctx.save();
        this.ctx.imageSmoothingEnabled = false;
        
        // Try to use sprite first
        const sprite = this.loadFoodSprite(foodType);
        if (sprite) {
            // Draw sprite with pixel-perfect scaling
            const spriteSize = 24;
            this.ctx.drawImage(
                sprite,
                Math.round(x - spriteSize / 2),
                Math.round(y - spriteSize / 2),
                spriteSize,
                spriteSize
            );
            this.ctx.restore();
            return;
        }
        
        // Fallback to geometric shapes if sprite not available
        if (foodType === 'water') {
            // Draw water source (pixel art - blue square with pixel pattern)
            const size = 10;
            this.ctx.fillStyle = '#38b2ac';
            this.ctx.fillRect(x - size, y - size, size * 2, size * 2);
            // Add pixel highlight
            this.ctx.fillStyle = '#2c7a7b';
            for (let py = 0; py < 3; py++) {
                for (let px = 0; px < 3; px++) {
                    this.drawPixelBlock(x - size + 2 + px * 2, y - size + 2 + py * 2, 1, '#2c7a7b');
                }
            }
        } else if (foodType === 'shelter') {
            // Draw shelter (pixel art triangle)
            this.ctx.fillStyle = '#8b7355';
            this.ctx.beginPath();
            this.ctx.moveTo(x, y - 8);
            this.ctx.lineTo(x - 6, y + 4);
            this.ctx.lineTo(x + 6, y + 4);
            this.ctx.closePath();
            this.ctx.fill();
            // Add pixel border
            this.ctx.strokeStyle = '#6b5d47';
            this.ctx.lineWidth = 1;
            this.ctx.stroke();
        } else if (foodType === 'apple') {
            // Apple (pixel art - red circle approximation)
            const size = 10;
            for (let py = -size; py <= size; py++) {
                for (let px = -size; px <= size; px++) {
                    const dist = Math.sqrt(px*px + py*py);
                    if (dist < size - 1) {
                        this.drawPixelBlock(x + px, y + py, 1, '#ff6b6b');
                    } else if (dist < size) {
                        this.drawPixelBlock(x + px, y + py, 1, '#ee5a52');
                    }
                }
            }
            // Stem
            this.ctx.fillStyle = '#48bb78';
            this.ctx.fillRect(x - 1, y - 12, 2, 4);
            // Highlight
            this.drawPixelBlock(x - 3, y - 3, 2, '#ffffff');
        } else if (foodType === 'banana') {
            // Banana (pixel art - yellow rectangle)
            const width = 8;
            const height = 12;
            this.ctx.fillStyle = '#f6e05e';
            this.ctx.fillRect(x - width/2, y - height/2, width, height);
            // Add pixel highlight
            this.ctx.fillStyle = '#ffffff';
            this.ctx.fillRect(x - 2, y - 4, 2, 3);
            // Border
            this.ctx.strokeStyle = '#ecc94b';
            this.ctx.lineWidth = 1;
            this.ctx.strokeRect(x - width/2, y - height/2, width, height);
        } else if (foodType === 'grapes') {
            // Grapes cluster (pixel art - purple circles)
            const positions = [
                [x - 4, y - 4], [x, y - 5], [x + 4, y - 4],
                [x - 5, y + 2], [x, y + 1], [x + 5, y + 2]
            ];
            positions.forEach(([px, py]) => {
                const grapeSize = 4;
                for (let gy = -grapeSize; gy <= grapeSize; gy++) {
                    for (let gx = -grapeSize; gx <= grapeSize; gx++) {
                        const dist = Math.sqrt(gx*gx + gy*gy);
                        if (dist < grapeSize) {
                            this.drawPixelBlock(px + gx, py + gy, 1, '#9f7aea');
                        }
                    }
                }
            });
        }
        
        this.ctx.restore();
    }

    drawUI(turn) {
        // Draw turn counter with pixel art styling
        this.ctx.save();
        this.ctx.imageSmoothingEnabled = false;
        
        // Background for text (pixel art - solid rectangle, no rounded corners)
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fillRect(8, 8, 100, 28);
        
        // Border (pixel art - 2px solid)
        this.ctx.strokeStyle = '#667eea';
        this.ctx.lineWidth = 2;
        this.ctx.strokeRect(8, 8, 100, 28);
        
        // Text (pixel art style - monospace font)
        this.ctx.fillStyle = '#1a1a2e';
        this.ctx.font = 'bold 14px monospace';
        this.ctx.textAlign = 'left';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(`Turn: ${turn}`, 18, 22);
        
        // Draw weather indicator (pixel art style)
        const weatherEnv = this.gameState.environment || this.gameState.world?.environment;
        if (weatherEnv?.weather) {
            const weather = weatherEnv.weather;
            const weatherIcons = {
                'clear': '☀️',
                'storm': '⛈️',
                'fog': '🌫️',
                'heat_wave': '🔥',
                'cold_snap': '❄️'
            };
            const icon = weatherIcons[weather] || '☀️';
            
            this.ctx.fillStyle = '#ffffff';
            this.ctx.fillRect(this.canvas.width - 50, 8, 42, 28);
            this.ctx.strokeStyle = '#667eea';
            this.ctx.lineWidth = 2;
            this.ctx.strokeRect(this.canvas.width - 50, 8, 42, 28);
            
            this.ctx.font = '20px monospace';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(icon, this.canvas.width - 29, 22);
        }
        
        // Draw day/night indicator (pixel art style)
        const dayNightEnv = this.gameState.environment || this.gameState.world?.environment;
        if (dayNightEnv) {
            const isDay = dayNightEnv.is_day !== false;
            const timeIcon = isDay ? '☀️' : '🌙';
            
            this.ctx.fillStyle = '#ffffff';
            this.ctx.fillRect(this.canvas.width - 100, 8, 42, 28);
            this.ctx.strokeStyle = '#667eea';
            this.ctx.lineWidth = 2;
            this.ctx.strokeRect(this.canvas.width - 100, 8, 42, 28);
            
            this.ctx.font = '18px monospace';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(timeIcon, this.canvas.width - 79, 22);
        }
        
        this.ctx.restore();
    }

    updateEvents(events) {
        const eventsList = document.getElementById('eventsList');
        if (!eventsList || events.length === 0) return;

        events.forEach(event => {
            const eventItem = document.createElement('div');
            eventItem.className = 'event-item';
            
            // Color code events by type
            let eventColor = '#667eea';
            if (event.includes('attacked') || event.includes('killed')) {
                eventColor = '#f56565';
            } else if (event.includes('reproduced')) {
                eventColor = '#48bb78';
            } else if (event.includes('claimed')) {
                eventColor = '#9f7aea';
            } else if (event.includes('cooperated') || event.includes('signaled')) {
                eventColor = '#38b2ac';
            } else if (event.includes('migrated')) {
                eventColor = '#ed8936';
            } else if (event.includes('EARTHQUAKE') || event.includes('FLOOD')) {
                eventColor = '#ed8936';
            } else if (event.includes('predator') || event.includes('Predator')) {
                eventColor = '#c53030';
            }
            
            eventItem.style.borderLeftColor = eventColor;
            eventItem.textContent = `[Turn ${this.gameState.turn}] ${event}`;
            eventsList.appendChild(eventItem);
        });

        while (eventsList.children.length > 20) {
            eventsList.removeChild(eventsList.firstChild);
        }

        const eventsDiv = document.getElementById('events');
        if (eventsDiv) {
            eventsDiv.scrollTop = eventsDiv.scrollHeight;
        }
    }

    updateScoring(scoring) {
        // Update scoring display if scoring panel exists
        const scoringEl = document.getElementById('scoringPanel');
        if (scoringEl && scoring.metrics) {
            const metrics = scoring.metrics;
            const achievements = scoring.unlocked_achievements || [];
            
            scoringEl.innerHTML = `
                <h4 style="margin-top: 0; color: #1a1a2e;">Stats</h4>
                <div style="font-size: 12px; color: #1a1a2e;">
                    <p>Energy Efficiency: ${metrics.energy_efficiency?.toFixed(2) || 0}</p>
                    <p>Reproductions: ${metrics.reproduction_count || 0}</p>
                    <p>Kills: ${metrics.combat_kills || 0}</p>
                    <p>Territories: ${metrics.territories_claimed || 0}</p>
                    <p>Cooperations: ${metrics.cooperation_events || 0}</p>
                </div>
                ${achievements.length > 0 ? `
                    <h4 style="margin-top: 15px; color: #1a1a2e;">Achievements</h4>
                    <div style="font-size: 11px; color: #48bb78;">
                        ${achievements.map(a => `🏆 ${a}`).join('<br>')}
                    </div>
                ` : ''}
            `;
        }
    }

    async previewTraits(prompt, playerId, isEvolution = false, generateSprite = false) {
        if (!prompt || prompt.trim().length === 0) {
            this.clearPreview(playerId, isEvolution);
            return Promise.reject(new Error('Empty prompt'));
        }

        try {
            console.log(`Previewing traits for Player ${playerId}:`, prompt);
            const response = await fetch('http://localhost:8000/parse_prompt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt, generate_sprite: generateSprite })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
            }

            const data = await response.json();
            console.log(`[Player ${playerId}] Received response:`, data);
            
            // Log debug info if available
            if (data.debug) {
                console.group(`[Player ${playerId}] Debug Info`);
                console.log('Method:', data.debug.method);
                console.log('LLM Available:', data.debug.llm_available);
                console.log('Timing:', data.debug.timing);
                if (data.debug.errors && data.debug.errors.length > 0) {
                    console.warn('Errors:', data.debug.errors);
                }
                if (data.debug.llm_response) {
                    console.log('LLM Response:', data.debug.llm_response);
                }
                if (data.debug.raw_traits) {
                    console.log('Raw Traits:', data.debug.raw_traits);
                }
                if (data.debug.validation_changes) {
                    console.log('Validation Changes:', data.debug.validation_changes);
                }
                console.groupEnd();
            }
            
            if (data.traits) {
                this.updatePreview(playerId, data.traits, data.sprite_url, isEvolution);
                return Promise.resolve();
            } else {
                throw new Error('No traits in response');
            }
        } catch (error) {
            console.error(`Error previewing traits for Player ${playerId}:`, error);
            this.showPreviewError(playerId, isEvolution);
            return Promise.reject(error);
        }
    }

    updatePreview(playerId, traits, spriteUrl, isEvolution = false) {
        const previewDiv = document.getElementById(isEvolution ? `previewUpdate${playerId}` : `preview${playerId}`);
        const traitsGrid = document.getElementById(isEvolution ? `traitsUpdate${playerId}` : `traits${playerId}`);
        const spriteContainer = document.getElementById(isEvolution ? `spriteUpdate${playerId}` : `sprite${playerId}`);
        
        if (!previewDiv || !traitsGrid) {
            console.error(`Preview elements not found for Player ${playerId}`);
            return;
        }

        console.log(`Updating preview for Player ${playerId} with traits:`, traits);
        previewDiv.classList.remove('loading');
        traitsGrid.innerHTML = '';

        const traitLabels = {
            'color': 'Color',
            'speed': 'Speed',
            'diet': 'Diet',
            'population': 'Population',
            'social': 'Social',
            'aggression': 'Aggression',
            'size': 'Size'
        };

        for (const [key, label] of Object.entries(traitLabels)) {
            const traitItem = document.createElement('div');
            traitItem.className = 'trait-item';
            const value = traits[key] !== undefined ? traits[key] : 'N/A';
            traitItem.innerHTML = `<span class="trait-label">${label}:</span> <span class="trait-value">${value}</span>`;
            traitsGrid.appendChild(traitItem);
        }

        // Display sprite image if available
        if (spriteContainer && spriteUrl) {
            const fullUrl = `http://localhost:8000${spriteUrl}`;
            spriteContainer.innerHTML = `<img src="${fullUrl}" alt="Creature sprite" class="preview-sprite" />`;
            spriteContainer.style.display = 'flex';
        } else if (spriteContainer) {
            spriteContainer.innerHTML = '';
            spriteContainer.style.display = 'none';
        }
    }

    clearPreview(playerId, isEvolution = false) {
        const previewDiv = document.getElementById(isEvolution ? `previewUpdate${playerId}` : `preview${playerId}`);
        const traitsGrid = document.getElementById(isEvolution ? `traitsUpdate${playerId}` : `traits${playerId}`);
        const spriteContainer = document.getElementById(isEvolution ? `spriteUpdate${playerId}` : `sprite${playerId}`);
        
        if (previewDiv) {
            previewDiv.classList.remove('loading');
        }
        if (traitsGrid) {
            traitsGrid.innerHTML = '<div style="color: #999; font-style: italic;">Enter a description to see traits...</div>';
        }
        if (spriteContainer) {
            spriteContainer.innerHTML = '';
            spriteContainer.style.display = 'none';
        }
    }

    showPreviewError(playerId, isEvolution = false) {
        const previewDiv = document.getElementById(isEvolution ? `previewUpdate${playerId}` : `preview${playerId}`);
        const traitsGrid = document.getElementById(isEvolution ? `traitsUpdate${playerId}` : `traits${playerId}`);
        const spriteContainer = document.getElementById(isEvolution ? `spriteUpdate${playerId}` : `sprite${playerId}`);
        
        if (previewDiv) {
            previewDiv.classList.remove('loading');
        }
        if (traitsGrid) {
            traitsGrid.innerHTML = '<div style="color: #F44336;">Error parsing traits. Using defaults.</div>';
        }
        if (spriteContainer) {
            spriteContainer.innerHTML = '';
            spriteContainer.style.display = 'none';
        }
    }

    showPreviewLoading(playerId, isEvolution = false) {
        const previewDiv = document.getElementById(isEvolution ? `previewUpdate${playerId}` : `preview${playerId}`);
        const traitsGrid = document.getElementById(isEvolution ? `traitsUpdate${playerId}` : `traits${playerId}`);
        
        if (previewDiv) {
            previewDiv.classList.add('loading');
        }
        if (traitsGrid) {
            traitsGrid.innerHTML = '<div>Parsing traits...</div>';
        }
    }

    checkAndUpdateStartButton() {
        const startBtn = document.getElementById('startBtn');
        if (startBtn) {
            startBtn.disabled = !this.confirmedPlayer;
        }
    }
}

// Initialize
let client;
document.addEventListener('DOMContentLoaded', () => {
    console.log('[DOMContentLoaded] ===== Page loaded, initializing =====');
    const canvas = document.getElementById('gameCanvas');
    console.log('[DOMContentLoaded] Canvas element:', canvas ? 'found' : 'not found');
    client = new GameClient(canvas);
    console.log('[DOMContentLoaded] GameClient created');

    // Set up input change handlers to re-enable confirm buttons
    const prompt1Input = document.getElementById('prompt1');
    if (prompt1Input) {
        prompt1Input.addEventListener('input', () => {
            const confirmBtn = document.getElementById('confirmBtn1');
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Confirm';
            }
            // Clear preview and reset confirmation state when text changes
            client.confirmedPlayer = false;
            client.clearPreview(1);
            client.checkAndUpdateStartButton();
        });
    }

    // Set up confirm button handler
    const confirmBtn1 = document.getElementById('confirmBtn1');
    if (confirmBtn1) {
        confirmBtn1.onclick = () => {
            const prompt = prompt1Input.value.trim();
            if (!prompt) {
                alert('Please enter a description first!');
                return;
            }
            confirmBtn1.disabled = true;
            confirmBtn1.textContent = 'Confirming...';
            client.showPreviewLoading(1);
            // Generate sprite only when user confirms (generateSprite = true)
            client.previewTraits(prompt, 1, false, true).then(() => {
                confirmBtn1.textContent = 'Confirmed';
                client.confirmedPlayer = true;
                client.checkAndUpdateStartButton();
            }).catch(() => {
                confirmBtn1.disabled = false;
                confirmBtn1.textContent = 'Confirm';
                client.confirmedPlayer = false;
                client.checkAndUpdateStartButton();
            });
        };
    }

    // Disable Start Game button initially
    const startBtn = document.getElementById('startBtn');
    if (startBtn) {
        startBtn.disabled = true;
        startBtn.onclick = () => {
            const prompt = document.getElementById('prompt1').value.trim();

            if (!prompt) {
                alert('Please enter a prompt!');
                return;
            }

            startBtn.disabled = true;
            startBtn.textContent = 'Starting...';
            document.getElementById('eventsList').innerHTML = '';
            client.startGame(prompt).then(() => {
                startBtn.disabled = false;
                startBtn.textContent = 'Start Game';
            }).catch(error => {
                console.error('Error:', error);
                startBtn.disabled = false;
                startBtn.textContent = 'Start Game';
            });
        };
    }

    // Set up prompt update submit button handler
    const submitPromptUpdateBtn = document.getElementById('submitPromptUpdateBtn');
    if (submitPromptUpdateBtn) {
        submitPromptUpdateBtn.onclick = async () => {
            const promptInput = document.getElementById('promptUpdateInput');
            if (!promptInput || !promptInput.value.trim()) {
                alert('Please enter a behavior update description!');
                return;
            }
            
            const prompt = promptInput.value.trim();
            submitPromptUpdateBtn.disabled = true;
            submitPromptUpdateBtn.textContent = 'Updating...';
            
            try {
                await client.updatePrompts(prompt);
                // Hide modal - game will continue automatically
                const modal = document.getElementById('resultsModal');
                const promptSection = document.getElementById('promptUpdateSection');
                const closeBtn = modal.querySelector('.close');
                
                // Clear hover state when modal closes (new attempt starting)
                if (client) {
                    client.hoveredElement = null;
                }
                
                if (modal) {
                    modal.style.display = 'none';
                }
                if (promptSection) {
                    promptSection.style.display = 'none';
                }
                if (closeBtn) {
                    closeBtn.style.display = 'block';
                }
                
                submitPromptUpdateBtn.disabled = false;
                submitPromptUpdateBtn.textContent = 'Update Behavior & Continue';
                promptInput.value = '';
            } catch (error) {
                console.error('Error updating prompt:', error);
                alert(`Error updating behavior: ${error.message}`);
                submitPromptUpdateBtn.disabled = false;
                submitPromptUpdateBtn.textContent = 'Update Behavior & Continue';
            }
        };
    }
});
