// GameClient class for WebSocket connection and Canvas rendering with Stage-Based Flow

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
                <div style="margin: 20px 0; padding: 15px; background: #fff3cd; border-radius: 4px; border-left: 4px solid #ffc107;">
                    <p style="margin: 0 0 10px 0; font-weight: bold; color: #856404;">Energy Events (This Attempt):</p>
                    <ul style="margin: 0; padding-left: 20px; color: #333;">
                        ${energyEvents.map(event => `<li style="margin: 5px 0; font-family: monospace;">${event}</li>`).join('')}
                    </ul>
                    <p style="margin: 10px 0 0 0; font-size: 12px; color: #666; font-style: italic;">Use this information to update your prompt and improve survival strategies.</p>
                </div>
            `;
        } else {
            energyEventsHtml = `
                <div style="margin: 20px 0; padding: 15px; background: #f5f5f5; border-radius: 4px; border-left: 4px solid #999;">
                    <p style="margin: 0; color: #666; font-style: italic;">No energy events recorded this attempt.</p>
                </div>
            `;
        }
        
        content.innerHTML = `
            <h2>Population Extinct!</h2>
            <p style="color: #F44336; font-size: 18px; font-weight: bold;">All creatures have died.</p>
            <div style="margin: 20px 0;">
                <p><strong>Attempt:</strong> ${update.attempt_number || this.attemptNumber} / ${update.max_attempts || this.maxAttempts}</p>
                <p><strong>Attempts Remaining:</strong> ${update.attempts_remaining || (this.maxAttempts - this.attemptNumber)}</p>
                <p><strong>Turn:</strong> ${update.turn || 0}</p>
            </div>
            ${energyEventsHtml}
            <div style="margin: 20px 0; padding: 15px; background: #f5f5f5; border-radius: 4px; border-left: 4px solid #2196F3;">
                <p style="margin: 0 0 8px 0; font-weight: bold; color: #555;">Current Prompt:</p>
                <p style="margin: 0; color: #333; font-style: italic; word-wrap: break-word;">"${currentPrompt}"</p>
            </div>
            <p style="color: #666;">Update your creatures' behavior to help them survive in the next attempt!</p>
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
                <div style="margin: 20px 0; padding: 15px; background: #fff3cd; border-radius: 4px; border-left: 4px solid #ffc107;">
                    <p style="margin: 0 0 10px 0; font-weight: bold; color: #856404;">Energy Events (Final Attempt):</p>
                    <ul style="margin: 0; padding-left: 20px; color: #333;">
                        ${energyEvents.map(event => `<li style="margin: 5px 0; font-family: monospace;">${event}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        content.innerHTML = `
            <h2>Final Results - Game Complete!</h2>
            <div class="player-results">
                <h3>Your Creature</h3>
                <p><strong>Final Energy:</strong> ${player.energy}</p>
                <p><strong>Final Stage:</strong> ${player.stage}</p>
                <p><strong>Survived:</strong> ${survived ? 'Yes' : 'No'}</p>
                <p><strong>Age:</strong> ${player.age}</p>
                <p><strong>Color:</strong> ${player.color}</p>
                <p><strong>Speed:</strong> ${player.speed}</p>
            </div>
            ${energyEventsHtml}
            <div style="margin: 20px 0; padding: 15px; background: #f5f5f5; border-radius: 4px; border-left: 4px solid #2196F3;">
                <p style="margin: 0 0 8px 0; font-weight: bold; color: #555;">Final Prompt:</p>
                <p style="margin: 0; color: #333; font-style: italic; word-wrap: break-word;">"${prompt}"</p>
            </div>
            ${survived ? `<p class="winner">🏆 You survived!</p>` : '<p class="winner">Your creature did not survive.</p>'}
            <button onclick="document.getElementById('resultsModal').style.display='none'">Close</button>
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

        // Clear canvas
        this.ctx.fillStyle = '#E8E8E8';
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
        this.ctx.strokeStyle = '#CCCCCC';
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
                // Sprite loaded successfully, draw it
                const spriteSize = 32; // Size to draw sprite on canvas
                this.ctx.drawImage(
                    sprite,
                    x - spriteSize / 2,
                    y - spriteSize / 2,
                    spriteSize,
                    spriteSize
                );
                
                // Draw energy indicator on top
                this.drawEnergyBar(x, y, creature.energy);
                return;
            } else if (!sprite || (sprite && !sprite.complete)) {
                // Sprite not in cache or still loading, start loading it
                if (!sprite) {
                    const img = new Image();
                    img.crossOrigin = 'anonymous'; // Allow CORS if needed
                    img.onload = () => {
                        console.log(`✓ Sprite loaded: ${creature.sprite_url}`);
                        this.spriteCache[creature.sprite_url] = img;
                        // Trigger redraw
                        if (this.animationFrame) {
                            cancelAnimationFrame(this.animationFrame);
                        }
                        this.animationFrame = requestAnimationFrame(() => this.render());
                    };
                    img.onerror = (e) => {
                        console.warn(`✗ Failed to load sprite: ${creature.sprite_url}`, e);
                        // Mark as failed to avoid retrying
                        this.spriteCache[creature.sprite_url] = null;
                    };
                    const fullUrl = `http://localhost:8000${creature.sprite_url}`;
                    console.log(`Loading sprite: ${fullUrl}`);
                    img.src = fullUrl;
                    this.spriteCache[creature.sprite_url] = img; // Store reference while loading
                }
            }
            // If sprite is loading or failed, fall through to canvas drawing
        } else {
            // Debug: log when sprite_url is missing
            if (creature.id === 1 || creature.id === 2) {
                console.log(`Creature ${creature.id} has no sprite_url, using canvas drawing`);
            }
        }

        // Fallback to canvas drawing (original implementation)
        const colorMap = {
            'blue': '#2196F3',
            'red': '#F44336',
            'green': '#4CAF50',
            'yellow': '#FFEB3B',
            'purple': '#9C27B0',
            'orange': '#FF9800',
            'pink': '#E91E63',
            'cyan': '#00BCD4',
            'brown': '#795548',
            'black': '#212121',
            'white': '#FFFFFF'
        };

        // Normalize color to lowercase string for matching
        const creatureColor = creature.color ? String(creature.color).toLowerCase().trim() : null;
        
        // Debug logging (can be removed later)
        if (!creatureColor || !colorMap[creatureColor]) {
            console.warn(`Creature ${creature.id} has invalid or missing color:`, creature.color, '-> using default blue');
        }
        
        // Get color from map, or use creatureColor if it's already a hex code, or default to blue
        const fillColor = colorMap[creatureColor] || (creatureColor && creatureColor.startsWith('#') ? creatureColor : '#2196F3');
        const stage = creature.stage || 1;
        
        this.ctx.fillStyle = fillColor;
        this.ctx.beginPath();
        
        // Different shapes for different stages
        if (stage === 1) {
            this.ctx.arc(x, y, 10, 0, Math.PI * 2);
        } else if (stage === 2) {
            const colonySize = creature.colony_size || 1;
            const radius = 12 + (colonySize * 2);
            this.ctx.arc(x, y, radius, 0, Math.PI * 2);
            for (let i = 0; i < Math.min(colonySize, 5); i++) {
                const angle = (i * Math.PI * 2) / Math.min(colonySize, 5);
                const offsetX = Math.cos(angle) * (radius * 0.6);
                const offsetY = Math.sin(angle) * (radius * 0.6);
                this.ctx.beginPath();
                this.ctx.arc(x + offsetX, y + offsetY, 4, 0, Math.PI * 2);
                this.ctx.fill();
            }
        } else if (stage === 3) {
            const limbs = creature.parts?.limbs || 4;
            const radius = 15;
            this.ctx.arc(x, y, radius, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.strokeStyle = fillColor;
            this.ctx.lineWidth = 2;
            for (let i = 0; i < limbs; i++) {
                const angle = (i * Math.PI * 2) / limbs;
                const startX = x + Math.cos(angle) * radius;
                const startY = y + Math.sin(angle) * radius;
                const endX = x + Math.cos(angle) * (radius + 8);
                const endY = y + Math.sin(angle) * (radius + 8);
                this.ctx.beginPath();
                this.ctx.moveTo(startX, startY);
                this.ctx.lineTo(endX, endY);
                this.ctx.stroke();
            }
        }
        
        this.ctx.fill();
        this.ctx.strokeStyle = '#333';
        this.ctx.lineWidth = stage === 3 ? 2 : 1;
        this.ctx.stroke();

        // Draw energy indicator
        this.drawEnergyBar(x, y, creature.energy);
    }

    drawEnergyBar(x, y, energy) {
        const energyPercent = energy / 100;
        const barWidth = 16;
        const barHeight = 3;
        const barX = x - barWidth / 2;
        const barY = y - 18;

        this.ctx.fillStyle = '#333';
        this.ctx.fillRect(barX, barY, barWidth, barHeight);
        this.ctx.fillStyle = energyPercent > 0.5 ? '#4CAF50' : (energyPercent > 0.25 ? '#FFC107' : '#F44336');
        this.ctx.fillRect(barX, barY, barWidth * energyPercent, barHeight);
    }

    drawFood(food) {
        const x = food.x * this.cellSize + this.cellSize / 2;
        const y = food.y * this.cellSize + this.cellSize / 2;
        
        // Get food type, default to apple if not specified
        const foodType = food.type || 'apple';
        
        // Save context state
        this.ctx.save();
        
        // Draw colored shapes based on food type (more reliable than emojis)
        this.ctx.fillStyle = foodType === 'apple' ? '#FF4444' : 
                             (foodType === 'banana' ? '#FFEB3B' : '#9C27B0');
        
        if (foodType === 'apple') {
            // Red circle for apple
            this.ctx.beginPath();
            this.ctx.arc(x, y, 10, 0, Math.PI * 2);
            this.ctx.fill();
            // Add a small green stem
            this.ctx.fillStyle = '#4CAF50';
            this.ctx.fillRect(x - 2, y - 12, 4, 4);
        } else if (foodType === 'banana') {
            // Yellow curved shape for banana
            this.ctx.beginPath();
            this.ctx.ellipse(x, y, 8, 12, -0.3, 0, Math.PI * 2);
            this.ctx.fill();
        } else if (foodType === 'grapes') {
            // Purple circles for grapes
            this.ctx.fillStyle = '#9C27B0';
            for (let i = 0; i < 3; i++) {
                for (let j = 0; j < 2; j++) {
                    this.ctx.beginPath();
                    this.ctx.arc(x - 6 + i * 6, y - 4 + j * 8, 4, 0, Math.PI * 2);
                    this.ctx.fill();
                }
            }
        }
        
        // Restore context state
        this.ctx.restore();
    }

    drawUI(turn) {
        this.ctx.fillStyle = 'black';
        this.ctx.font = '14px sans-serif';
        this.ctx.textAlign = 'left';
        this.ctx.fillText(`Turn: ${turn}`, 10, 20);
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
