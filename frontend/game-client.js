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
            this.gameState = update;
            this.currentStage = update.stage || this.currentStage;
            this.timeRemaining = update.time_remaining || this.timeRemaining;
            if (update.attempt_number) {
                this.attemptNumber = update.attempt_number;
            }
            if (update.max_attempts) {
                this.maxAttempts = update.max_attempts;
            }
            this.updateHearts(update.attempts_remaining || (this.maxAttempts - this.attemptNumber + 1));
            this.render();
            this.updateEvents(update.events || []);
            this.updateStageTimer(update.time_remaining);
        } else if (update.status === 'game_started') {
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

        // Clear canvas with gradient background
        const gradient = this.ctx.createLinearGradient(0, 0, this.canvas.width, this.canvas.height);
        gradient.addColorStop(0, '#f5f7fa');
        gradient.addColorStop(1, '#c3cfe2');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw grid
        this.drawGrid();

        // Draw resources
        if (this.gameState.world.resources) {
            this.gameState.world.resources.food.forEach(food => this.drawFood(food));
        }

        // Draw creatures
        if (this.gameState.world.creatures) {
            this.gameState.world.creatures.forEach(creature => this.drawCreature(creature));
        }

        // Draw UI
        this.drawUI(this.gameState.turn || 0);
    }

    drawGrid() {
        const cellSize = this.cellSize;
        this.ctx.strokeStyle = 'rgba(102, 126, 234, 0.15)';
        this.ctx.lineWidth = 0.5;

        const gridWidth = Math.floor(this.canvas.width / cellSize);
        const gridHeight = Math.floor(this.canvas.height / cellSize);

        for (let i = 0; i <= gridWidth; i++) {
            this.ctx.beginPath();
            this.ctx.moveTo(i * cellSize, 0);
            this.ctx.lineTo(i * cellSize, this.canvas.height);
            this.ctx.stroke();
        }

        for (let i = 0; i <= gridHeight; i++) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, i * cellSize);
            this.ctx.lineTo(this.canvas.width, i * cellSize);
            this.ctx.stroke();
        }
    }

    drawCreature(creature) {
        const x = creature.x * this.cellSize + this.cellSize / 2;
        const y = creature.y * this.cellSize + this.cellSize / 2;

        // Try to use sprite if available
        if (creature.sprite_url) {
            const sprite = this.spriteCache[creature.sprite_url];
            if (sprite && sprite.complete && sprite.naturalWidth > 0) {
                // Sprite loaded successfully, draw it with shadow
                const spriteSize = 32;
                
                // Draw shadow
                this.ctx.save();
                this.ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
                this.ctx.shadowBlur = 8;
                this.ctx.shadowOffsetX = 2;
                this.ctx.shadowOffsetY = 2;
                
                this.ctx.drawImage(
                    sprite,
                    x - spriteSize / 2,
                    y - spriteSize / 2,
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

        // Fallback to canvas drawing with modern styling
        const colorMap = {
            'blue': '#667eea',
            'red': '#f56565',
            'green': '#48bb78',
            'yellow': '#f6e05e',
            'purple': '#9f7aea',
            'orange': '#ed8936',
            'pink': '#ed64a6',
            'cyan': '#38b2ac',
            'brown': '#a0aec0',
            'black': '#2d3748',
            'white': '#ffffff'
        };

        const creatureColor = creature.color ? String(creature.color).toLowerCase().trim() : null;
        const fillColor = colorMap[creatureColor] || (creatureColor && creatureColor.startsWith('#') ? creatureColor : '#667eea');
        const stage = creature.stage || 1;
        
        // Create gradient for creature
        const gradient = this.ctx.createRadialGradient(x - 3, y - 3, 0, x, y, 20);
        gradient.addColorStop(0, this.lightenColor(fillColor, 20));
        gradient.addColorStop(1, fillColor);
        
        this.ctx.save();
        
        // Draw shadow
        this.ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
        this.ctx.shadowBlur = 8;
        this.ctx.shadowOffsetX = 2;
        this.ctx.shadowOffsetY = 2;
        
        this.ctx.fillStyle = gradient;
        this.ctx.beginPath();
        
        // Different shapes for different stages
        if (stage === 1) {
            this.ctx.arc(x, y, 12, 0, Math.PI * 2);
        } else if (stage === 2) {
            const colonySize = creature.colony_size || 1;
            const radius = 14 + (colonySize * 2);
            this.ctx.arc(x, y, radius, 0, Math.PI * 2);
            for (let i = 0; i < Math.min(colonySize, 5); i++) {
                const angle = (i * Math.PI * 2) / Math.min(colonySize, 5);
                const offsetX = Math.cos(angle) * (radius * 0.6);
                const offsetY = Math.sin(angle) * (radius * 0.6);
                this.ctx.beginPath();
                this.ctx.arc(x + offsetX, y + offsetY, 5, 0, Math.PI * 2);
                this.ctx.fill();
            }
        } else if (stage === 3) {
            const limbs = creature.parts?.limbs || 4;
            const radius = 16;
            this.ctx.arc(x, y, radius, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.strokeStyle = this.lightenColor(fillColor, 10);
            this.ctx.lineWidth = 2.5;
            for (let i = 0; i < limbs; i++) {
                const angle = (i * Math.PI * 2) / limbs;
                const startX = x + Math.cos(angle) * radius;
                const startY = y + Math.sin(angle) * radius;
                const endX = x + Math.cos(angle) * (radius + 10);
                const endY = y + Math.sin(angle) * (radius + 10);
                this.ctx.beginPath();
                this.ctx.moveTo(startX, startY);
                this.ctx.lineTo(endX, endY);
                this.ctx.stroke();
            }
        }
        
        this.ctx.fill();
        
        // Draw border
        this.ctx.shadowBlur = 0;
        this.ctx.strokeStyle = this.darkenColor(fillColor, 15);
        this.ctx.lineWidth = stage === 3 ? 2.5 : 1.5;
        this.ctx.stroke();
        
        this.ctx.restore();

        // Draw energy indicator
        this.drawEnergyBar(x, y, creature.energy);
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
        const barX = x - barWidth / 2;
        const barY = y - 22;
        const borderRadius = 2;

        // Draw background
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
        this.ctx.beginPath();
        this.ctx.roundRect(barX, barY, barWidth, barHeight, borderRadius);
        this.ctx.fill();

        // Draw energy bar with gradient
        const energyColor = energyPercent > 0.5 ? '#48bb78' : (energyPercent > 0.25 ? '#f6e05e' : '#f56565');
        const gradient = this.ctx.createLinearGradient(barX, barY, barX + barWidth * energyPercent, barY);
        gradient.addColorStop(0, this.lightenColor(energyColor, 15));
        gradient.addColorStop(1, energyColor);
        
        this.ctx.fillStyle = gradient;
        this.ctx.beginPath();
        this.ctx.roundRect(barX, barY, barWidth * energyPercent, barHeight, borderRadius);
        this.ctx.fill();
        
        // Draw border
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        this.ctx.lineWidth = 0.5;
        this.ctx.beginPath();
        this.ctx.roundRect(barX, barY, barWidth, barHeight, borderRadius);
        this.ctx.stroke();
    }

    drawFood(food) {
        const x = food.x * this.cellSize + this.cellSize / 2;
        const y = food.y * this.cellSize + this.cellSize / 2;
        
        const foodType = food.type || 'apple';
        
        this.ctx.save();
        
        // Draw shadow
        this.ctx.shadowColor = 'rgba(0, 0, 0, 0.2)';
        this.ctx.shadowBlur = 4;
        this.ctx.shadowOffsetX = 1;
        this.ctx.shadowOffsetY = 1;
        
        if (foodType === 'apple') {
            // Apple with gradient
            const appleGradient = this.ctx.createRadialGradient(x - 2, y - 2, 0, x, y, 12);
            appleGradient.addColorStop(0, '#ff6b6b');
            appleGradient.addColorStop(1, '#ee5a52');
            this.ctx.fillStyle = appleGradient;
            this.ctx.beginPath();
            this.ctx.arc(x, y, 11, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Stem
            this.ctx.shadowBlur = 0;
            this.ctx.fillStyle = '#48bb78';
            this.ctx.fillRect(x - 2, y - 13, 4, 5);
            
            // Highlight
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
            this.ctx.beginPath();
            this.ctx.arc(x - 3, y - 3, 4, 0, Math.PI * 2);
            this.ctx.fill();
        } else if (foodType === 'banana') {
            // Banana with gradient
            const bananaGradient = this.ctx.createLinearGradient(x - 8, y - 12, x + 8, y + 12);
            bananaGradient.addColorStop(0, '#f6e05e');
            bananaGradient.addColorStop(1, '#ecc94b');
            this.ctx.fillStyle = bananaGradient;
            this.ctx.beginPath();
            this.ctx.ellipse(x, y, 9, 13, -0.3, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Highlight
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
            this.ctx.beginPath();
            this.ctx.ellipse(x - 2, y - 4, 3, 5, -0.3, 0, Math.PI * 2);
            this.ctx.fill();
        } else if (foodType === 'grapes') {
            // Grapes cluster
            this.ctx.fillStyle = '#9f7aea';
            const positions = [
                [x - 5, y - 5], [x, y - 6], [x + 5, y - 5],
                [x - 6, y + 2], [x, y + 1], [x + 6, y + 2]
            ];
            positions.forEach(([px, py], i) => {
                const grapeGradient = this.ctx.createRadialGradient(px - 1, py - 1, 0, px, py, 5);
                grapeGradient.addColorStop(0, '#b794f4');
                grapeGradient.addColorStop(1, '#9f7aea');
                this.ctx.fillStyle = grapeGradient;
                this.ctx.beginPath();
                this.ctx.arc(px, py, 5, 0, Math.PI * 2);
                this.ctx.fill();
            });
        }
        
        this.ctx.restore();
    }

    drawUI(turn) {
        // Draw turn counter with modern styling
        this.ctx.save();
        
        // Background for text
        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        this.ctx.beginPath();
        this.ctx.roundRect(8, 8, 100, 28, 8);
        this.ctx.fill();
        
        // Border
        this.ctx.strokeStyle = 'rgba(102, 126, 234, 0.3)';
        this.ctx.lineWidth = 1.5;
        this.ctx.beginPath();
        this.ctx.roundRect(8, 8, 100, 28, 8);
        this.ctx.stroke();
        
        // Text with shadow
        this.ctx.shadowColor = 'rgba(0, 0, 0, 0.2)';
        this.ctx.shadowBlur = 2;
        this.ctx.shadowOffsetX = 1;
        this.ctx.shadowOffsetY = 1;
        this.ctx.fillStyle = '#1a1a2e';
        this.ctx.font = 'bold 14px Inter, sans-serif';
        this.ctx.textAlign = 'left';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(`Turn: ${turn}`, 18, 22);
        
        this.ctx.restore();
    }

    updateEvents(events) {
        const eventsList = document.getElementById('eventsList');
        if (!eventsList || events.length === 0) return;

        events.forEach(event => {
            const eventItem = document.createElement('div');
            eventItem.className = 'event-item';
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

    async previewTraits(prompt, playerId, isEvolution = false) {
        if (!prompt || prompt.trim().length === 0) {
            this.clearPreview(playerId, isEvolution);
            return Promise.reject(new Error('Empty prompt'));
        }

        try {
            console.log(`Previewing traits for Player ${playerId}:`, prompt);
            const response = await fetch('http://localhost:8000/parse_prompt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt })
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
            client.previewTraits(prompt, 1).then(() => {
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
