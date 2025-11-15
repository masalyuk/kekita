"""FastAPI server for Evolution Game MVP - Stage-Based Flow."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import uuid
import os

from game.llm_manager import LLMManager
from game.world import World
from game.cell import Cell
from game.simulation import Simulation
from game.prompt_parser import PromptParser
from game.hybrid_decision_maker import HybridDecisionMaker
from game.stage_controller import StageController
from game.stage_results import StageResults
from game.stage_manager import StageManager
from game.sprite_generator import SpriteGenerator

app = FastAPI()

# CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_manager = LLMManager()  # For game decisions (qwen2:0.5b)
llm_parser = LLMManager(model_name="qwen3:4b")  # For prompt parsing (larger model, higher temperature)
sprite_generator = SpriteGenerator()  # For generating creature sprites
game_state = {}  # Store active games: {game_id: {simulation, decision_maker, stage_controller, current_stage, prompts, ...}}

# Mount static files for sprite serving
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "sprites"), exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Test endpoint to verify static files are accessible
@app.get("/test_sprite/{creature_id}/{stage}")
async def test_sprite(creature_id: int, stage: int):
    """Test endpoint to check if sprite exists."""
    sprite_path = os.path.join(static_dir, "sprites", f"{creature_id}_{stage}.png")
    exists = os.path.exists(sprite_path)
    return {
        "sprite_path": sprite_path,
        "exists": exists,
        "url": f"/static/sprites/{creature_id}_{stage}.png",
        "full_url": f"http://localhost:8000/static/sprites/{creature_id}_{stage}.png"
    }


class GameStartRequest(BaseModel):
    prompt1: str
    prompt2: str


class PromptUpdateRequest(BaseModel):
    prompt1: str
    prompt2: str


class ParsePromptRequest(BaseModel):
    prompt: str


@app.on_event("startup")
async def startup():
    """Initialize LLM managers on startup."""
    await llm_manager.initialize()
    await llm_parser.initialize()
    print("LLM Manager initialized (game decisions)")
    print("LLM Parser initialized (prompt parsing)")


@app.on_event("shutdown")
async def shutdown():
    """Clean up on shutdown."""
    await llm_manager.close()
    await llm_parser.close()
    print("LLM Managers closed")


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
        # Ensure color is a lowercase string
        color = new_traits['color']
        creature.color = str(color).lower().strip() if color else 'blue'
    if 'speed' in new_traits:
        creature.speed = new_traits['speed']
    if 'diet' in new_traits:
        creature.diet = new_traits['diet']


@app.post("/start_game")
async def start_game(request: GameStartRequest):
    """Start a new game with 2 player prompts."""
    traits1 = await PromptParser.parse(request.prompt1, llm_manager=llm_manager)
    traits2 = await PromptParser.parse(request.prompt2, llm_manager=llm_manager)

    world = World(width=20, height=20)
    world.spawn_resources()

    # Spawn 1 creature per player (Stage 1)
    print(f"[start_game] Creating creatures with traits1: {traits1}, traits2: {traits2}")
    cell1 = Cell(creature_id=1, traits=traits1, x=5, y=5, player_id=1)
    cell2 = Cell(creature_id=2, traits=traits2, x=15, y=15, player_id=2)
    print(f"[start_game] Cell1 color: {cell1.color}, Cell2 color: {cell2.color}")
    
    # Generate sprites for both creatures (non-blocking, graceful fallback)
    print(f"[start_game] Generating sprites for creatures...")
    try:
        sprite1_url = await sprite_generator.get_or_generate_sprite(request.prompt1, 1, 1)
        if sprite1_url:
            cell1.sprite_url = sprite1_url
            print(f"[start_game] ✓ Sprite 1: {sprite1_url}")
        else:
            print(f"[start_game] ⚠ Sprite 1 generation failed, will use canvas drawing")
    except Exception as e:
        print(f"[start_game] ✗ Error generating sprite 1: {e}, will use canvas drawing")
    
    try:
        sprite2_url = await sprite_generator.get_or_generate_sprite(request.prompt2, 2, 1)
        if sprite2_url:
            cell2.sprite_url = sprite2_url
            print(f"[start_game] ✓ Sprite 2: {sprite2_url}")
        else:
            print(f"[start_game] ⚠ Sprite 2 generation failed, will use canvas drawing")
    except Exception as e:
        print(f"[start_game] ✗ Error generating sprite 2: {e}, will use canvas drawing")
    
    world.add_cell(cell1)
    world.add_cell(cell2)

    simulation = Simulation(world, llm_manager)
    decision_maker = HybridDecisionMaker(llm_manager, timeout=10.0)
    stage_controller = StageController(stage_duration=20)
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


@app.post("/parse_prompt")
async def parse_prompt(request: ParsePromptRequest):
    """Parse a single prompt and return extracted traits for preview."""
    import time
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"[parse_prompt] === PARSING PROMPT ===")
    print(f"[parse_prompt] Prompt: '{request.prompt}'")
    print(f"[parse_prompt] Prompt length: {len(request.prompt)} chars")
    
    debug_info = {
        'prompt': request.prompt,
        'method': None,
        'llm_available': llm_parser is not None and llm_parser.session is not None,
        'llm_model': None,
        'llm_response': None,
        'raw_traits': None,
        'validated_traits': None,
        'errors': [],
        'timing': {}
    }
    
    try:
        # Use LLM parser if available, otherwise use keyword parsing
        if llm_parser and llm_parser.session:
            print(f"[parse_prompt] ✓ LLM parser available (model: {llm_parser.model_name}), using LLM parsing")
            debug_info['method'] = 'llm'
            debug_info['llm_model'] = llm_parser.model_name
            llm_start = time.time()
            traits = await PromptParser.parse(request.prompt, llm_manager=llm_parser, debug_info=debug_info)
            debug_info['timing']['llm_parse'] = time.time() - llm_start
            print(f"[parse_prompt] ✓ LLM parsing completed in {debug_info['timing']['llm_parse']:.3f}s")
            print(f"[parse_prompt] Final traits: {traits}")
        else:
            # LLM not available, use keyword parsing
            print(f"[parse_prompt] ✗ LLM parser not available (session={llm_parser.session if llm_parser else None})")
            print(f"[parse_prompt] → Using keyword parsing")
            debug_info['method'] = 'keyword'
            keyword_start = time.time()
            traits = PromptParser._parse_keywords(request.prompt)
            debug_info['timing']['keyword_parse'] = time.time() - keyword_start
            debug_info['raw_traits'] = traits
            debug_info['validated_traits'] = traits
            print(f"[parse_prompt] ✓ Keyword parsing completed in {debug_info['timing']['keyword_parse']:.3f}s")
            print(f"[parse_prompt] Final traits: {traits}")
        
        debug_info['validated_traits'] = traits
        
        # Generate preview sprite (using temporary ID 0 for preview)
        sprite_url = None
        try:
            sprite_url = await sprite_generator.get_or_generate_sprite(request.prompt, 0, 1)
            if sprite_url:
                print(f"[parse_prompt] ✓ Preview sprite generated: {sprite_url}")
        except Exception as e:
            print(f"[parse_prompt] ✗ Sprite generation failed: {e}")
        
        total_time = time.time() - start_time
        debug_info['timing']['total'] = total_time
        print(f"[parse_prompt] Total time: {total_time:.3f}s")
        print(f"{'='*60}\n")
        
        return {
            'success': True,
            'traits': traits,
            'sprite_url': sprite_url,
            'debug': debug_info
        }
    except Exception as e:
        print(f"[parse_prompt] ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        debug_info['errors'].append(str(e))
        # Return fallback traits on error
        print(f"[parse_prompt] → Falling back to keyword parsing")
        fallback_start = time.time()
        traits = PromptParser._parse_keywords(request.prompt)
        debug_info['timing']['fallback_parse'] = time.time() - fallback_start
        debug_info['method'] = 'keyword_fallback'
        debug_info['raw_traits'] = traits
        debug_info['validated_traits'] = traits
        print(f"[parse_prompt] Fallback result: {traits}")
        total_time = time.time() - start_time
        debug_info['timing']['total'] = total_time
        print(f"{'='*60}\n")
        
        # Try to generate sprite even on error
        sprite_url = None
        try:
            sprite_url = await sprite_generator.get_or_generate_sprite(request.prompt, 0, 1)
        except Exception:
            pass
        
        return {
            'success': False,
            'traits': traits,
            'sprite_url': sprite_url,
            'error': str(e),
            'debug': debug_info
        }


@app.post("/update_prompts/{game_id}")
async def update_prompts(game_id: str, request: PromptUpdateRequest):
    """Update prompts for next stage (evolution descriptions)."""
    game = game_state.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if not game['waiting_for_prompts']:
        raise HTTPException(status_code=400, detail="Not waiting for prompt updates")
    
    # Use LLM-based merging to intelligently merge current traits with evolution descriptions
    # This preserves existing traits (like color) unless explicitly changed in the evolution description
    print(f"[update_prompts] Merging traits for Player 1 with evolution: '{request.prompt1[:50]}...'")
    print(f"[update_prompts] Current traits1: {game['current_traits']['traits1']}")
    merged_traits1 = await PromptParser.merge_traits(
        current_traits=game['current_traits']['traits1'],
        evolution_description=request.prompt1,
        llm_manager=llm_manager
    )
    print(f"[update_prompts] Merged traits1: {merged_traits1}")
    
    print(f"[update_prompts] Merging traits for Player 2 with evolution: '{request.prompt2[:50]}...'")
    print(f"[update_prompts] Current traits2: {game['current_traits']['traits2']}")
    merged_traits2 = await PromptParser.merge_traits(
        current_traits=game['current_traits']['traits2'],
        evolution_description=request.prompt2,
        llm_manager=llm_manager
    )
    print(f"[update_prompts] Merged traits2: {merged_traits2}")
    
    # Apply to creatures
    world = game['simulation'].world
    current_stage = game.get('current_stage', 1)
    
    # Regenerate sprites for evolved creatures
    # Combine original prompt with evolution description for better sprite generation
    for creature in world.cells:
        if creature.player_id == 1:
            apply_trait_evolution(creature, merged_traits1)
            print(f"[update_prompts] Applied merged traits1 to creature {creature.id}, color: {creature.color}")
            # Regenerate sprite with evolution description
            try:
                evolution_prompt = f"{game['original_prompts']['prompt1']}, evolved: {request.prompt1}"
                sprite_url = await sprite_generator.generate_sprite(evolution_prompt, creature.id, current_stage, force_regenerate=True)
                if sprite_url:
                    creature.sprite_url = sprite_url
                    print(f"[update_prompts] ✓ Regenerated sprite for creature {creature.id}: {sprite_url}")
                else:
                    print(f"[update_prompts] ⚠ Sprite regeneration failed for creature {creature.id}, keeping existing or using canvas")
            except Exception as e:
                print(f"[update_prompts] ✗ Error regenerating sprite for creature {creature.id}: {e}, keeping existing or using canvas")
        elif creature.player_id == 2:
            apply_trait_evolution(creature, merged_traits2)
            print(f"[update_prompts] Applied merged traits2 to creature {creature.id}, color: {creature.color}")
            # Regenerate sprite with evolution description
            try:
                evolution_prompt = f"{game['original_prompts']['prompt2']}, evolved: {request.prompt2}"
                sprite_url = await sprite_generator.generate_sprite(evolution_prompt, creature.id, current_stage, force_regenerate=True)
                if sprite_url:
                    creature.sprite_url = sprite_url
                    print(f"[update_prompts] ✓ Regenerated sprite for creature {creature.id}: {sprite_url}")
                else:
                    print(f"[update_prompts] ⚠ Sprite regeneration failed for creature {creature.id}, keeping existing or using canvas")
            except Exception as e:
                print(f"[update_prompts] ✗ Error regenerating sprite for creature {creature.id}: {e}, keeping existing or using canvas")
    
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
