# Evolution Game MVP - Core Implementation

A prompt-based evolution game inspired by Spore, where players describe creatures using natural language. Each creature is powered by a small LLM (Qwen 0.5B) making real-time decisions through a hybrid AI system.

## Features

- **Prompt-Based Creation**: Describe creatures in natural language
- **Hybrid AI Decision-Making**: LLM + rule-based fallback for responsive gameplay
- **Real-Time Updates**: WebSocket communication between backend and frontend
- **2-Player Turn-Based**: Competitive gameplay with 1 creature per player
- **Canvas Rendering**: Visual representation of the cellular stage world

## Tech Stack

**Backend:**
- Python 3.8+
- FastAPI (WebSocket support)
- Ollama (local LLM inference)
- aiohttp (async HTTP client)

**Frontend:**
- Vanilla JavaScript
- HTML5 Canvas
- WebSocket API

## Prerequisites

1. **Python 3.8+** installed
2. **Ollama** installed and running
3. **Qwen 0.5B model** pulled in Ollama

## Setup Instructions

### 1. Install Ollama

Download and install Ollama from [ollama.ai](https://ollama.ai)

### 2. Pull the Model

```bash
ollama pull qwen2:0.5b
```

### 3. Start Ollama Server

```bash
ollama serve
```

The server should run on `http://localhost:11434` by default.

### 4. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 5. Start the Backend Server

```bash
cd backend
python server.py
```

The server will start on `http://localhost:8000`

### 6. Start the Frontend

Open a new terminal and serve the frontend:

```bash
cd frontend
python -m http.server 8080
```

Or use any simple HTTP server. Then open your browser to:
```
http://localhost:8080
```

## Game Flow

### Phase 1: Prompt Input

1. Player 1 enters a description like: "Small blue herbivores, move fast, travel in groups of 20, cautious"
2. Player 2 enters their creature description
3. Click "Start Game"

The system parses traits from the prompts:
- Color (blue, red, green, etc.)
- Speed (1-5 scale)
- Diet (herbivore, carnivore, omnivore)
- Population (number mentioned)
- Social behavior (group/solitary)

### Phase 2: Simulation (60 turns, ~30 seconds)

Each turn (~0.5 seconds):
1. Get creature state and world state
2. Hybrid decision function:
   - **Critical situations** (low energy, poison nearby) → instant rule-based
   - **Normal situations** → LLM call (Qwen 0.5B, ~0.15s)
   - **LLM timeout/error** → fallback to rule-based
3. Execute action (MOVE, EAT, FLEE, REPRODUCE)
4. Update world state
5. Send update to frontend via WebSocket

### Phase 3: Feedback

- Real-time visualization on canvas
- Event log showing creature actions
- Turn counter
- Game ends after 60 turns or when all creatures die

## Hybrid Decision-Making

The AI system has 3 layers:

1. **Rule-Based Layer (Instant)**: Simple if-then logic for critical situations
   - Energy < 20 → find food
   - Poison < 1 distance → flee
   - Enemy < 1 distance → flee

2. **LLM Layer (0.15-0.3s)**: Qwen 0.5B makes creative decisions
   - Compact prompts: "E:45 @(5,7)\nFOOD RIGHT d1\nAction?"
   - Responses parsed: "MOVE RIGHT", "EAT", "FLEE", "REPRODUCE"

3. **Fallback Layer**: If LLM times out or fails, use rule-based logic

## Project Structure

```
kekita/
├── backend/
│   ├── server.py                 # FastAPI server
│   ├── game/
│   │   ├── __init__.py
│   │   ├── cell.py               # Cell class
│   │   ├── world.py              # World class
│   │   ├── simulation.py         # Simulation orchestrator
│   │   ├── prompt_parser.py     # Parse prompts
│   │   ├── llm_manager.py        # Ollama integration
│   │   ├── llm_prompt_builder.py
│   │   ├── llm_response_parser.py
│   │   └── hybrid_decision_maker.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── game-client.js
│   └── package.json
└── README.md
```

## Performance

On RTX 3060 12GB:
- **LLM Inference**: ~0.15-0.2s per creature (Qwen 0.5B)
- **Rule-Based Fallback**: ~10ms (instant)
- **Turn Time**: 0.2-0.3s (includes network latency)
- **60 Turns**: ~18-30 seconds total
- **VRAM**: ~2GB for Qwen 0.5B + overhead

## Troubleshooting

**Ollama connection error:**
- Ensure Ollama is running: `ollama serve`
- Check model is pulled: `ollama list`
- Verify URL in `backend/game/llm_manager.py` matches your Ollama setup

**WebSocket connection failed:**
- Ensure backend is running on port 8000
- Check CORS settings if accessing from different origin
- Verify frontend URL in `game-client.js`

**Game not updating:**
- Check browser console for errors
- Verify WebSocket connection in Network tab
- Ensure backend server is running

## Next Steps (Future Enhancements)

- Add more evolution stages (Stage 2, Stage 3)
- Procedural sprite generation based on traits
- Advanced events (hunting, cooperation, territorial behavior)
- LLM memory for creatures (remember past events)
- Multiplayer support (more than 2 players)
- Export stats and evolution history

## License

MIT

