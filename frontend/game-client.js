// GameClient class for WebSocket connection and Canvas rendering

class GameClient {
    constructor(canvasElement) {
        this.canvas = canvasElement;
        this.ctx = canvasElement.getContext('2d');
        this.ws = null;
        this.gameState = null;
        this.cellSize = 30; // Grid cell size in pixels
        this.animationFrame = null;
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
            const gameId = data.game_id;

            // Update status
            document.getElementById('status').textContent = `Game started! Connecting...`;

            // Connect WebSocket
            this.ws = new WebSocket(`ws://localhost:8000/ws/${gameId}`);
            this.ws.onopen = () => {
                document.getElementById('status').textContent = 'Game running...';
            };
            this.ws.onmessage = (event) => {
                const update = JSON.parse(event.data);
                this.onGameUpdate(update);
            };
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                document.getElementById('status').textContent = 'Connection error!';
            };
            this.ws.onclose = () => {
                document.getElementById('status').textContent = 'Game finished!';
                if (this.animationFrame) {
                    cancelAnimationFrame(this.animationFrame);
                }
            };
        } catch (error) {
            console.error('Error starting game:', error);
            document.getElementById('status').textContent = `Error: ${error.message}`;
        }
    }

    onGameUpdate(update) {
        if (update.status === 'finished') {
            document.getElementById('status').textContent = `Game finished! Reason: ${update.reason}`;
            if (this.ws) {
                this.ws.close();
            }
            return;
        }

        this.gameState = update;
        this.render();
        this.updateEvents(update.events || []);
    }

    render() {
        if (!this.gameState) return;

        // Clear canvas
        this.ctx.fillStyle = '#E8E8E8';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw grid
        this.drawGrid();

        // Draw resources
        if (this.gameState.world && this.gameState.world.resources) {
            this.gameState.world.resources.food.forEach(food => this.drawFood(food));
            this.gameState.world.resources.poison.forEach(p => this.drawPoison(p));
        }

        // Draw creatures
        if (this.gameState.world && this.gameState.world.creatures) {
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
            // Stage 1: Simple circle
            this.ctx.arc(x, y, 10, 0, Math.PI * 2);
        } else if (stage === 2) {
            // Stage 2: Larger circle with multiple smaller circles (colony)
            const colonySize = creature.colony_size || 1;
            const radius = 12 + (colonySize * 2);
            this.ctx.arc(x, y, radius, 0, Math.PI * 2);
            // Draw smaller circles around for colony members
            for (let i = 0; i < Math.min(colonySize, 5); i++) {
                const angle = (i * Math.PI * 2) / Math.min(colonySize, 5);
                const offsetX = Math.cos(angle) * (radius * 0.6);
                const offsetY = Math.sin(angle) * (radius * 0.6);
                this.ctx.beginPath();
                this.ctx.arc(x + offsetX, y + offsetY, 4, 0, Math.PI * 2);
                this.ctx.fill();
            }
        } else if (stage === 3) {
            // Stage 3: Complex shape (polygon with parts)
            const limbs = creature.parts?.limbs || 4;
            const radius = 15;
            // Draw main body (larger circle)
            this.ctx.arc(x, y, radius, 0, Math.PI * 2);
            this.ctx.fill();
            // Draw limbs as lines
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

        // Draw border
        this.ctx.strokeStyle = '#333';
        this.ctx.lineWidth = stage === 3 ? 2 : 1;
        this.ctx.stroke();

        // Draw energy indicator
        const energyPercent = creature.energy / 100;
        const barWidth = 16;
        const barHeight = 3;
        const barX = x - barWidth / 2;
        const barY = y - 18;

        // Background
        this.ctx.fillStyle = '#333';
        this.ctx.fillRect(barX, barY, barWidth, barHeight);

        // Energy bar
        this.ctx.fillStyle = energyPercent > 0.5 ? '#4CAF50' : (energyPercent > 0.25 ? '#FFC107' : '#F44336');
        this.ctx.fillRect(barX, barY, barWidth * energyPercent, barHeight);

        // Draw creature ID
        this.ctx.fillStyle = '#000';
        this.ctx.font = '10px sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(creature.id, x, y + 4);
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
        // Draw turn counter on canvas (optional, also shown in status)
        this.ctx.fillStyle = 'black';
        this.ctx.font = '14px sans-serif';
        this.ctx.textAlign = 'left';
        this.ctx.fillText(`Turn: ${turn}`, 10, 20);
    }

    updateEvents(events) {
        const eventsList = document.getElementById('eventsList');
        if (events.length === 0) return;

        events.forEach(event => {
            const eventItem = document.createElement('div');
            eventItem.className = 'event-item';
            eventItem.textContent = `[Turn ${this.gameState.turn}] ${event}`;
            eventsList.appendChild(eventItem);
        });

        // Keep only last 20 events
        while (eventsList.children.length > 20) {
            eventsList.removeChild(eventsList.firstChild);
        }

        // Auto-scroll to bottom
        const eventsDiv = document.getElementById('events');
        eventsDiv.scrollTop = eventsDiv.scrollHeight;
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('gameCanvas');
    const client = new GameClient(canvas);

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
});

