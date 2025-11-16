# Evolution Game MVP - Core Implementation

A prompt-based evolution game inspired by Spore, where players describe creatures using natural language. Each creature is powered by a small LLM (Qwen 0.5B) making real-time decisions through a hybrid AI system. The game features a 3-stage evolution system where creatures evolve through cellular, multicellular, and complex organism stages.

## Features

- **Prompt-Based Creation**: Describe creatures in natural language with real-time trait preview
- **3-Stage Evolution System**: Progress through Stage 1 (Cellular) → Stage 2 (Multicellular) → Stage 3 (Complex Organism)
- **Procedural Sprite Generation**: Automatic pixel art sprite generation via Sana API based on creature descriptions
- **Prompt Evolution**: Merge and evolve creature traits between stages with natural language descriptions
- **Hybrid AI Decision-Making**: LLM + rule-based fallback for responsive gameplay
- **Dual LLM System**: Qwen 0.5B for game decisions, Qwen 3:4B for intelligent prompt parsing
- **Real-Time Updates**: WebSocket communication between backend and frontend
- **2-Player Competitive**: Competitive gameplay with 1 creature per player
- **Canvas Rendering**: Visual representation with sprite-based or canvas-drawn creatures

## Tech Stack

**Backend:**
- Python 3.8+
- FastAPI (WebSocket support, static file serving)
- Ollama (local LLM inference)
- aiohttp (async HTTP client)
- gradio_client (Sana API integration for sprite generation)
- Pillow (image processing for placeholder sprites)

**Frontend:**
- Vanilla JavaScript
- Phaser.js 3.80.1 (game rendering framework)
- WebSocket API

**External Services:**
- Sana API (sprite generation via Gradio client)

## Prerequisites

1. **Python 3.8+** installed
2. **Ollama** installed and running
3. **Qwen models** pulled in Ollama:
   - `qwen2:0.5b` for game decision-making
   - `qwen3:4b` for prompt parsing and trait extraction

## Setup Instructions

### 1. Install Ollama

Download and install Ollama from [ollama.ai](https://ollama.ai)

### 2. Pull the Models

```bash
ollama pull qwen2:0.5b
ollama pull qwen3:4b
```

Note: `qwen2:0.5b` is used for real-time game decisions, while `qwen3:4b` is used for parsing player prompts into structured traits.

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

### Phase 1: Prompt Input & Preview

1. Player 1 enters a description like: "Small blue herbivores, move fast, travel in groups of 20, cautious"
2. Player 2 enters their creature description
3. Traits are automatically parsed and previewed in real-time (via `/parse_prompt` endpoint)
4. Sprites are generated for each creature based on their descriptions
5. Click "Start Game" to begin

The system parses traits from the prompts using Qwen 3:4B:
- Color (blue, red, green, etc.)
- Speed (1-5 scale)
- Diet (herbivore, carnivore, omnivore)
- Population (number mentioned)
- Social behavior (group/solitary)

### Phase 2: Stage 1 - Cellular Stage (20 seconds)

Each turn (~0.5 seconds):
1. Get creature state and world state
2. Hybrid decision function:
   - **Critical situations** (low energy, poison nearby) → instant rule-based
   - **Normal situations** → LLM call (Qwen 0.5B, ~0.15s)
   - **LLM timeout/error** → fallback to rule-based
3. Execute action (MOVE, EAT, FLEE, REPRODUCE)
4. Update world state
5. Send update to frontend via WebSocket

Stage ends after 20 seconds. Results are calculated and displayed.

### Phase 3: Evolution Input (Between Stages)

After Stage 1 ends:
1. Players are prompted to describe how their creatures have evolved
2. Evolution descriptions are merged with existing traits using LLM-based merging
3. New sprites are generated to reflect the evolved creatures
4. Traits are updated: "Now they have sharp claws, faster movement, and better defense"

The system intelligently merges evolution descriptions with current traits, preserving unchanged attributes while applying new ones.

### Phase 4: Stage 2 - Multicellular Stage (20 seconds)

- Creatures may evolve to multicellular forms if criteria are met
- Simulation continues with evolved creatures
- Same hybrid decision-making system
- Stage ends after 20 seconds

### Phase 5: Evolution Input (Between Stages)

Players provide another evolution description for Stage 3.

### Phase 6: Stage 3 - Complex Organism Stage (20 seconds)

- Final evolution stage
- Creatures may evolve to complex organisms if criteria are met
- Final simulation phase
- Stage ends after 20 seconds

### Phase 7: Final Results

- Final statistics calculated across all stages
- Winner determined based on survival, energy, and performance
- Complete game history available

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

## API Endpoints

### REST Endpoints

- **`POST /start_game`**: Start a new game with two player prompts
  - Request: `{ "prompt1": "...", "prompt2": "..." }`
  - Response: `{ "game_id": "...", "traits1": {...}, "traits2": {...}, "stage": 1 }`

- **`POST /parse_prompt`**: Parse a prompt and preview traits before starting
  - Request: `{ "prompt": "..." }`
  - Response: `{ "success": true, "traits": {...}, "sprite_url": "/static/sprites/0_1.png", "debug": {...} }`
  - Used for real-time trait preview in the frontend

- **`POST /update_prompts/{game_id}`**: Update creature prompts for evolution between stages
  - Request: `{ "prompt1": "evolution description...", "prompt2": "evolution description..." }`
  - Response: `{ "status": "updated", "traits1": {...}, "traits2": {...} }`
  - Merges evolution descriptions with existing traits and regenerates sprites

- **`GET /test_sprite/{creature_id}/{stage}`**: Test endpoint to check if sprite exists

### WebSocket Endpoint

- **`WS /ws/{game_id}`**: Real-time game updates
  - Sends: `{ "status": "update", "turn": N, "stage": 1-3, "time_remaining": N, "world": {...}, "events": [...] }`
  - Status types: `stage_started`, `update`, `stage_ended`, `prompt_update_needed`, `game_complete`

## Project Structure

```
kekita/
├── backend/
│   ├── server.py                 # FastAPI server with WebSocket and REST endpoints
│   ├── game/
│   │   ├── __init__.py
│   │   ├── cell.py               # Cell class (Stage 1)
│   │   ├── creature.py           # Base Creature abstract class
│   │   ├── multicellular.py      # Multicellular class (Stage 2)
│   │   ├── organism.py           # Organism class (Stage 3)
│   │   ├── world.py              # World class
│   │   ├── simulation.py         # Simulation orchestrator
│   │   ├── prompt_parser.py      # Parse prompts with LLM/keyword fallback
│   │   ├── llm_manager.py        # Ollama integration
│   │   ├── llm_prompt_builder.py
│   │   ├── llm_response_parser.py
│   │   ├── hybrid_decision_maker.py
│   │   ├── stage_controller.py   # Stage timing and progression
│   │   ├── stage_manager.py       # Evolution stage management
│   │   ├── stage_results.py      # Stage result calculation
│   │   ├── sprite_generator.py   # Sprite generation via Sana API
│   │   └── creature_memory.py    # Creature memory system
│   ├── static/
│   │   └── sprites/              # Generated sprite storage
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── game-client.js
│   └── package.json
└── README.md
```

## Performance

On RTX 3060 12GB:
- **LLM Inference (Game Decisions)**: ~0.15-0.2s per creature (Qwen 0.5B)
- **LLM Inference (Prompt Parsing)**: ~0.5-1s per prompt (Qwen 3:4B, async)
- **Rule-Based Fallback**: ~10ms (instant)
- **Turn Time**: 0.2-0.3s (includes network latency)
- **Stage Duration**: 20 seconds per stage
- **Total Game Time**: ~60 seconds (3 stages × 20s) + evolution input time
- **Sprite Generation**: Async, non-blocking (uses external Sana API, ~5-15s per sprite)
- **VRAM**: ~2GB for Qwen 0.5B + ~4GB for Qwen 3:4B + overhead

## Troubleshooting

**Ollama connection error:**
- Ensure Ollama is running: `ollama serve`
- Check models are pulled: `ollama list` (should show `qwen2:0.5b` and `qwen3:4b`)
- Verify URL in `backend/game/llm_manager.py` matches your Ollama setup (default: `http://localhost:11434`)

**Prompt parsing issues:**
- If LLM parsing fails, the system automatically falls back to keyword-based parsing
- Check console logs for parsing errors
- Ensure `qwen3:4b` model is available for better parsing accuracy
- Verify Ollama is accessible and models are loaded

**Sprite generation issues:**
- Sprites are generated asynchronously and non-blocking
- If Sana API is unavailable, placeholder sprites are created using Pillow
- If both fail, creatures fall back to canvas drawing
- Check `backend/static/sprites/` directory for generated sprites
- Verify `gradio_client` is installed: `pip install gradio_client`
- Sprite generation errors are logged but don't stop gameplay

**WebSocket connection failed:**
- Ensure backend is running on port 8000
- Check CORS settings if accessing from different origin
- Verify frontend URL in `game-client.js`
- Check browser console for WebSocket errors

**Game not updating:**
- Check browser console for errors
- Verify WebSocket connection in Network tab
- Ensure backend server is running
- Check that game_id matches between `/start_game` response and WebSocket connection

**Stage progression issues:**
- Verify stage controller is working (check server logs)
- Ensure prompts are updated between stages via `/update_prompts/{game_id}`
- Check that evolution descriptions are being merged correctly

## Next Steps (Future Enhancements)

- Advanced events (hunting, cooperation, territorial behavior)
- Enhanced LLM memory for creatures (remember past events across stages)
- Multiplayer support (more than 2 players)
- Export stats and evolution history
- Custom stage durations
- More sophisticated evolution criteria
- Visual evolution tree/history

## License

MIT

