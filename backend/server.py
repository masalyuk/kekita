"""FastAPI server for Evolution Game MVP - Stage-Based Flow."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
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
from game.stage_controller import StageController
from game.stage_results import StageResults
from game.stage_manager import StageManager

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
game_state = {}  # Store active games: {game_id: {simulation, decision_maker, stage_controller, current_stage, prompts, ...}}


class GameStartRequest(BaseModel):
    prompt1: str
    prompt2: str


class PromptUpdateRequest(BaseModel):
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


def apply_trait_evolution(creature, new_traits):
    """
    Apply evolved traits to creature (merge with existing).
    
    Args:
        creature: Creature object
        new_traits: Dict with new/evolved traits
    """
    # Merge traits (new traits override old ones)
    for key, value in new_traits.items():
        creature.traits[key] = value
    
    # Update creature properties
    if 'color' in new_traits:
        creature.color = new_traits['color']
    if 'speed' in new_traits:
        creature.speed = new_traits['speed']
    if 'diet' in new_traits:
        creature.diet = new_traits['diet']


@app.post("/start_game")
async def start_game(request: GameStartRequest):
    """Start a new game with 2 player prompts."""
    traits1 = PromptParser.parse(request.prompt1)
    traits2 = PromptParser.parse(request.prompt2)

    world = World(width=20, height=20)
    world.spawn_resources()

    # Spawn 1 creature per player (Stage 1)
    cell1 = Cell(creature_id=1, traits=traits1, x=5, y=5, player_id=1)
    cell2 = Cell(creature_id=2, traits=traits2, x=15, y=15, player_id=2)
    world.add_cell(cell1)
    world.add_cell(cell2)

    simulation = Simulation(world, llm_manager)
    decision_maker = HybridDecisionMaker(llm_manager, timeout=10.0)
    stage_controller = StageController(stage_duration=60)
    stage_controller.start_stage(1)

    game_id = str(uuid.uuid4())
    game_state[game_id] = {
        'simulation': simulation,
        'decision_maker': decision_maker,
        'stage_controller': stage_controller,
        'current_stage': 1,
        'original_prompts': {'prompt1': request.prompt1, 'prompt2': request.prompt2},
        'current_traits': {'traits1': traits1, 'traits2': traits2},
        'waiting_for_prompts': False
    }

    return {
        'game_id': game_id,
        'traits1': traits1,
        'traits2': traits2,
        'stage': 1
    }


@app.post("/update_prompts/{game_id}")
async def update_prompts(game_id: str, request: PromptUpdateRequest):
    """Update prompts for next stage (evolution descriptions)."""
    game = game_state.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if not game['waiting_for_prompts']:
        raise HTTPException(status_code=400, detail="Not waiting for prompt updates")
    
    # Parse new prompts (evolution descriptions)
    new_traits1 = PromptParser.parse(request.prompt1)
    new_traits2 = PromptParser.parse(request.prompt2)
    
    # Merge with existing traits
    merged_traits1 = {**game['current_traits']['traits1'], **new_traits1}
    merged_traits2 = {**game['current_traits']['traits2'], **new_traits2}
    
    # Apply to creatures
    world = game['simulation'].world
    for creature in world.cells:
        if creature.player_id == 1:
            apply_trait_evolution(creature, merged_traits1)
        elif creature.player_id == 2:
            apply_trait_evolution(creature, merged_traits2)
    
    # Update game state
    game['current_traits'] = {'traits1': merged_traits1, 'traits2': merged_traits2}
    game['waiting_for_prompts'] = False
    
    return {
        'status': 'updated',
        'traits1': merged_traits1,
        'traits2': merged_traits2
    }


async def run_stage(game, websocket):
    """Run a single stage until time expires."""
    stage_controller = game['stage_controller']
    simulation = game['simulation']
    decision_maker = game['decision_maker']
    
    # Reset world for new stage
    world = simulation.world
    world.turn = 0
    world.spawn_resources()
    
    # Send stage start message
    await websocket.send_json({
        'status': 'stage_started',
        'stage': stage_controller.current_stage,
        'time_remaining': stage_controller.stage_duration
    })
    
    # Run simulation until stage ends
    last_time_update = 0
    while not stage_controller.is_stage_ended():
        # Execute one simulation step
        step_result = await simulation.step(decision_maker)
        
        # Send update every simulation step (so frontend sees movement)
        stage_info = stage_controller.get_stage_info()
        current_time = int(stage_info['time_remaining'])
        
        await websocket.send_json({
            'status': 'update',
            'turn': step_result['turn'],
            'stage': stage_info['stage'],
            'time_remaining': stage_info['time_remaining'],
            'world': {
                'creatures': step_result['creatures'],
                'resources': step_result['resources']
            },
            'events': step_result['events'][-5:]  # Last 5 events
        })
        
        # Small delay between turns
        await asyncio.sleep(0.5)
    
    # Stage ended - calculate results
    results = StageResults.calculate(world, player1_id=1, player2_id=2)
    
    await websocket.send_json({
        'status': 'stage_ended',
        'stage': stage_controller.current_stage,
        'results': results
    })
    
    return results


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """WebSocket for real-time game updates with stage-based flow."""
    await websocket.accept()

    game = game_state.get(game_id)
    if not game:
        await websocket.close(code=4000, reason="Game not found")
        return

    try:
        stage_controller = game['stage_controller']
        
        # Run Stage 1
        await run_stage(game, websocket)
        game['waiting_for_prompts'] = True
        
        # Wait for prompt updates
        await websocket.send_json({
            'status': 'prompt_update_needed',
            'current_traits': game['current_traits']
        })
        
        # Wait for prompt update (frontend calls /update_prompts endpoint)
        # Poll for update completion (max 30 seconds wait)
        for _ in range(60):  # 60 * 0.5s = 30 seconds max wait
            await asyncio.sleep(0.5)
            if not game['waiting_for_prompts']:
                break
        
        # If still waiting, use current traits (no evolution)
        if game['waiting_for_prompts']:
            game['waiting_for_prompts'] = False
        
        # Advance to Stage 2
        if stage_controller.can_advance_to_next_stage():
            stage_controller.start_stage(2)
            game['current_stage'] = 2
            
            # Evolve creatures if criteria met
            StageManager.check_and_evolve_all(game['simulation'].world)
            
            await run_stage(game, websocket)
            game['waiting_for_prompts'] = True
            
            await websocket.send_json({
                'status': 'prompt_update_needed',
                'current_traits': game['current_traits']
            })
            
            # Wait for prompt update
            for _ in range(60):
                await asyncio.sleep(0.5)
                if not game['waiting_for_prompts']:
                    break
            
            if game['waiting_for_prompts']:
                game['waiting_for_prompts'] = False
        
        # Advance to Stage 3
        if stage_controller.can_advance_to_next_stage():
            stage_controller.start_stage(3)
            game['current_stage'] = 3
            
            # Evolve creatures if criteria met
            StageManager.check_and_evolve_all(game['simulation'].world)
            
            await run_stage(game, websocket)
        
        # Game complete
        final_results = StageResults.calculate(game['simulation'].world, player1_id=1, player2_id=2)
        await websocket.send_json({
            'status': 'game_complete',
            'final_results': final_results
        })

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for game {game_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.close(code=1000)
    finally:
        # Clean up game state
        if game_id in game_state:
            del game_state[game_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
