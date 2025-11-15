"""FastAPI server for Evolution Game MVP."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import uuid

from game.llm_manager import LLMManager
from game.world import World
from game.cell import Cell
from game.simulation import Simulation
from game.prompt_parser import PromptParser
from game.hybrid_decision_maker import HybridDecisionMaker

app = FastAPI()

# CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_manager = LLMManager()
game_state = {}  # Store active games: {game_id: {simulation, decision_maker, turn, ...}}


class GameStartRequest(BaseModel):
    prompt1: str
    prompt2: str


@app.on_event("startup")
async def startup():
    """Initialize LLM manager on startup."""
    await llm_manager.initialize()
    print("LLM Manager initialized")


@app.on_event("shutdown")
async def shutdown():
    """Clean up on shutdown."""
    await llm_manager.close()
    print("LLM Manager closed")


@app.post("/start_game")
async def start_game(request: GameStartRequest):
    """Start a new game with 2 player prompts."""
    traits1 = PromptParser.parse(request.prompt1)
    traits2 = PromptParser.parse(request.prompt2)

    world = World(width=20, height=20)
    world.spawn_resources()

    # Spawn creatures for both players
    cell1 = Cell(creature_id=1, traits=traits1, x=5, y=5)
    cell2 = Cell(creature_id=2, traits=traits2, x=15, y=15)
    world.add_cell(cell1)
    world.add_cell(cell2)

    simulation = Simulation(world, llm_manager)
    decision_maker = HybridDecisionMaker(llm_manager)

    game_id = str(uuid.uuid4())
    game_state[game_id] = {
        'simulation': simulation,
        'decision_maker': decision_maker,
        'turn': 0,
        'max_turns': 60
    }

    return {
        'game_id': game_id,
        'traits1': traits1,
        'traits2': traits2
    }


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """WebSocket for real-time game updates."""
    await websocket.accept()

    game = game_state.get(game_id)
    if not game:
        await websocket.close(code=4000, reason="Game not found")
        return

    try:
        while game['turn'] < game['max_turns']:
            # Get current world state
            world_state = {
                'creatures': [c.to_dict() for c in game['simulation'].world.cells if c.alive],
                'resources': {
                    'food': game['simulation'].world.food,
                    'poison': game['simulation'].world.poison,
                }
            }

            # Execute one simulation step
            step_result = await game['simulation'].step(game['decision_maker'])
            game['turn'] = step_result['turn']

            # Send state to frontend
            await websocket.send_json({
                'turn': game['turn'],
                'world': {
                    'creatures': step_result['creatures'],
                    'resources': step_result['resources']
                },
                'events': step_result['events'][-5:]  # Last 5 events
            })

            # Check if game should end (no alive creatures)
            if len(step_result['creatures']) == 0:
                await websocket.send_json({'status': 'finished', 'reason': 'no_creatures'})
                break

            # Delay between turns (adjustable)
            await asyncio.sleep(0.5)

        # Game finished normally
        if game['turn'] >= game['max_turns']:
            await websocket.send_json({'status': 'finished', 'reason': 'max_turns'})

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for game {game_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close(code=1000)
    finally:
        # Clean up game state
        if game_id in game_state:
            del game_state[game_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

