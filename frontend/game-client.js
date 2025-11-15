// GameClient class for WebSocket connection and Canvas rendering with Stage-Based Flow

class GameClient {
    constructor(canvasElement) {
        this.canvas = canvasElement;
        this.ctx = canvasElement.getContext('2d');
        this.ws = null;
        this.gameState = null;
        this.gameId = null;
        this.cellSize = 30; // Grid cell size in pixels
        this.animationFrame = null;
        this.currentStage = 1;
        this.timeRemaining = 60;
    }

    async startGame(prompt1, prompt2) {
        try {
            // Request backend to start game
            const response = await fetch('http://localhost:8000/start_game', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt1, prompt2 })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            this.gameId = data.game_id;

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

    async updatePrompts(prompt1, prompt2) {
        if (!this.gameId) return;
        
        try {
            const response = await fetch(`http://localhost:8000/update_prompts/${this.gameId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt1, prompt2 })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Hide prompt update modal
            document.getElementById('promptUpdateModal').style.display = 'none';
        } catch (error) {
            console.error('Error updating prompts:', error);
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
            this.render();
            this.updateEvents(update.events || []);
            this.updateStageTimer(update.time_remaining);
        } else if (update.status === 'stage_ended') {
            this.showResults(update.results, update.stage);
        } else if (update.status === 'prompt_update_needed') {
            this.showPromptUpdateForm(update.current_traits);
        } else if (update.status === 'game_complete') {
            this.showFinalResults(update.final_results);
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
            timerEl.textContent = `Stage ${this.currentStage} - Time: ${timeRemaining}s`;
        }
    }

    showResults(results, stage) {
        const modal = document.getElementById('resultsModal');
        const content = document.getElementById('resultsContent');
        
        const p1 = results.player1;
        const p2 = results.player2;
        const winner = results.winner;
        
        content.innerHTML = `
            <h2>Stage ${stage} Results</h2>
            <div class="results-grid">
                <div class="player-results">
                    <h3>Player 1</h3>
                    <p><strong>Alive:</strong> ${p1.alive ? 'Yes' : 'No'}</p>
                    <p><strong>Energy:</strong> ${p1.energy}</p>
                    <p><strong>Age:</strong> ${p1.age}</p>
                    <p><strong>Stage:</strong> ${p1.stage}</p>
                    <p><strong>Color:</strong> ${p1.color}</p>
                    <p><strong>Speed:</strong> ${p1.speed}</p>
                </div>
                <div class="player-results">
                    <h3>Player 2</h3>
                    <p><strong>Alive:</strong> ${p2.alive ? 'Yes' : 'No'}</p>
                    <p><strong>Energy:</strong> ${p2.energy}</p>
                    <p><strong>Age:</strong> ${p2.age}</p>
                    <p><strong>Stage:</strong> ${p2.stage}</p>
                    <p><strong>Color:</strong> ${p2.color}</p>
                    <p><strong>Speed:</strong> ${p2.speed}</p>
                </div>
            </div>
            ${winner ? `<p class="winner">Winner: Player ${winner}!</p>` : '<p class="winner">Tie!</p>'}
        `;
        
        modal.style.display = 'block';
    }

    showPromptUpdateForm(currentTraits) {
        const modal = document.getElementById('promptUpdateModal');
        const prompt1Input = document.getElementById('promptUpdate1');
        const prompt2Input = document.getElementById('promptUpdate2');
        
        // Pre-fill with current traits as suggestions
        prompt1Input.value = `Evolved: ${currentTraits.traits1.color}, speed ${currentTraits.traits1.speed}, ${currentTraits.traits1.diet}`;
        prompt2Input.value = `Evolved: ${currentTraits.traits2.color}, speed ${currentTraits.traits2.speed}, ${currentTraits.traits2.diet}`;
        
        modal.style.display = 'block';
    }

    showFinalResults(results) {
        const modal = document.getElementById('resultsModal');
        const content = document.getElementById('resultsContent');
        
        const p1 = results.player1;
        const p2 = results.player2;
        const winner = results.winner;
        
        content.innerHTML = `
            <h2>Final Results - Game Complete!</h2>
            <div class="results-grid">
                <div class="player-results">
                    <h3>Player 1</h3>
                    <p><strong>Final Energy:</strong> ${p1.energy}</p>
                    <p><strong>Final Stage:</strong> ${p1.stage}</p>
                    <p><strong>Survived:</strong> ${p1.survival ? 'Yes' : 'No'}</p>
                </div>
                <div class="player-results">
                    <h3>Player 2</h3>
                    <p><strong>Final Energy:</strong> ${p2.energy}</p>
                    <p><strong>Final Stage:</strong> ${p2.stage}</p>
                    <p><strong>Survived:</strong> ${p2.survival ? 'Yes' : 'No'}</p>
                </div>
            </div>
            ${winner ? `<p class="winner">🏆 Winner: Player ${winner}!</p>` : '<p class="winner">Tie!</p>'}
            <button onclick="document.getElementById('resultsModal').style.display='none'">Close</button>
        `;
        
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
            this.gameState.world.resources.poison.forEach(p => this.drawPoison(p));
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

        const fillColor = colorMap[creature.color] || creature.color || '#2196F3';
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
        const energyPercent = creature.energy / 100;
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
        this.ctx.fillStyle = '#00AA00';
        this.ctx.fillRect(x - 5, y - 5, 10, 10);
    }

    drawPoison(poison) {
        const x = poison.x * this.cellSize + this.cellSize / 2;
        const y = poison.y * this.cellSize + this.cellSize / 2;
        this.ctx.fillStyle = '#FF0000';
        this.ctx.beginPath();
        this.ctx.arc(x, y, 6, 0, Math.PI * 2);
        this.ctx.fill();
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
}

// Initialize
let client;
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('gameCanvas');
    client = new GameClient(canvas);

    const startBtn = document.getElementById('startBtn');
    startBtn.onclick = () => {
        const prompt1 = document.getElementById('prompt1').value.trim();
        const prompt2 = document.getElementById('prompt2').value.trim();

        if (!prompt1 || !prompt2) {
            alert('Please enter prompts for both players!');
            return;
        }

        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';
        document.getElementById('eventsList').innerHTML = '';
        client.startGame(prompt1, prompt2).then(() => {
            startBtn.disabled = false;
            startBtn.textContent = 'Start Game';
        }).catch(error => {
            console.error('Error:', error);
            startBtn.disabled = false;
            startBtn.textContent = 'Start Game';
        });
    };

    // Handle prompt update form submission
    const updatePromptsBtn = document.getElementById('updatePromptsBtn');
    if (updatePromptsBtn) {
        updatePromptsBtn.onclick = () => {
            const prompt1 = document.getElementById('promptUpdate1').value.trim();
            const prompt2 = document.getElementById('promptUpdate2').value.trim();
            
            if (!prompt1 || !prompt2) {
                alert('Please enter evolution descriptions for both players!');
                return;
            }
            
            client.updatePrompts(prompt1, prompt2);
        };
    }
});
