"""FastAPI server for Evolution Game MVP - Single Player, Single Stage."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import uuid
import os
from pathlib import Path

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
total_attempts_global = 0  # Track total attempts across all games for evolution

# Mount static files for sprite serving
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "sprites"), exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Test endpoint to verify static files are accessible
@app.get("/test_sprite/{prompt_hash}/{stage}")
async def test_sprite(prompt_hash: str, stage: int):
    """Test endpoint to check if sprite exists."""
    sprite_path = os.path.join(static_dir, "sprites", f"{prompt_hash}_{stage}.png")
    exists = os.path.exists(sprite_path)
    return {
        "sprite_path": sprite_path,
        "exists": exists,
        "url": f"/static/sprites/{prompt_hash}_{stage}.png",
        "full_url": f"http://localhost:8000/static/sprites/{prompt_hash}_{stage}.png"
    }


class GameStartRequest(BaseModel):
    prompt: str


class PromptUpdateRequest(BaseModel):
    prompt: str


class ParsePromptRequest(BaseModel):
    prompt: str
    generate_sprite: bool = False  # Only generate sprite when user confirms


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


def cleanup_user_sprites():
    """Remove game sprite files before starting a new game.
    Since we now use prompt hash, we remove all sprites (they will be regenerated if needed).
    Preview sprites will be regenerated on demand."""
    sprite_dir = Path(static_dir) / "sprites"
    if not sprite_dir.exists():
        return
    
    removed_count = 0
    for sprite_file in sprite_dir.glob("*.png"):
        try:
            # Remove all sprite files (they will be regenerated if needed)
            # Old format: {creature_id}_{stage}.png
            # New format: {prompt_hash}_{stage}.png
            sprite_file.unlink()
            removed_count += 1
        except Exception as e:
            print(f"[cleanup_user_sprites] Failed to remove {sprite_file}: {e}")
    
    if removed_count > 0:
        print(f"[cleanup_user_sprites] Removed {removed_count} sprite file(s)")


def get_stage_from_attempts(total_attempts):
    """
    Determine evolution stage based on total attempts.
    
    Args:
        total_attempts: Total number of attempts across all games
        
    Returns:
        Stage number (1, 2, or 3)
    """
    if total_attempts < 1000:
        return 1  # Stage 1: Cell
    elif total_attempts < 2000:
        return 2  # Stage 2: Multicellular
    else:
        return 3  # Stage 3: Organism


def get_llm_model_for_stage(stage):
    """
    Get LLM model name based on stage (more powerful models for higher stages).
    
    Args:
        stage: Evolution stage (1, 2, or 3)
        
    Returns:
        Model name string
    """
    if stage == 1:
        return "qwen2:0.5b"  # Basic model for stage 1
    elif stage == 2:
        return "qwen2:1.5b"  # Medium model for stage 2 (or fallback to 0.5b if not available)
    else:
        return "qwen3:4b"  # Powerful model for stage 3


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
    """Start a new game with single player prompt."""
    # Don't clean up sprites - they should persist from confirm
    # cleanup_user_sprites()  # Removed: sprites should persist from confirm
    
    traits = await PromptParser.parse(request.prompt, llm_manager=llm_manager)

    world = World(width=20, height=20)
    world.spawn_resources(num_food=50)  # Increased initial food amount
    # Add special resources (water, shelter)
    world.resource_manager.add_special_resources(num_water=3, num_shelter=2)

    # Store food_type_config in game state to persist across attempts
    food_type_config = world.food_type_config.copy()
    print(f"[start_game] Stored food_type_config for persistence across attempts")

    # Try to reuse sprite that was already generated on confirm
    # If it doesn't exist, the game will use canvas drawing (sprite should already exist from confirm)
    sprite_url = None
    try:
        sprite_url = await sprite_generator.get_or_generate_sprite(request.prompt, 1, 1, force_regenerate=False)
        if sprite_url:
            print(f"[start_game] ✓ Using sprite from confirm: {sprite_url}")
        else:
            print(f"[start_game] ⚠ Sprite not found (should have been generated on confirm), creatures will use canvas drawing")
    except Exception as e:
        print(f"[start_game] ✗ Error loading sprite: {e}, creatures will use canvas drawing")
    
    # Spawn {num_creatures} creatures (Stage 1) at random positions
    import random
    num_creatures = 2
    print(f"[start_game] Creating {num_creatures} creatures with traits: {traits}")
    creature_id = 1
    for _ in range(num_creatures):
        # Find a random position that's not occupied
        x = random.randint(0, world.width - 1)
        y = random.randint(0, world.height - 1)
        # Avoid spawning on existing cells or food
        while (any(c.x == x and c.y == y for c in world.cells) or
               any(f['x'] == x and f['y'] == y for f in world.food)):
            x = random.randint(0, world.width - 1)
            y = random.randint(0, world.height - 1)
        
        cell = Cell(creature_id=creature_id, traits=traits, x=x, y=y, player_id=1)
        print(f"[start_game] Creature {creature_id} at ({x}, {y}), color: {cell.color}")
        
        # Assign same sprite URL to all creatures from same prompt
        if sprite_url:
            cell.sprite_url = sprite_url
            print(f"[start_game] ✓ Assigned sprite to creature {creature_id}: {sprite_url}")
        
        world.add_cell(cell)
        creature_id += 1

    simulation = Simulation(world, llm_manager)
    decision_maker = HybridDecisionMaker(llm_manager, timeout=10.0)
    stage_controller = StageController(stage_duration=20)
    stage_controller.start_stage(1)

    # Determine stage based on total attempts
    global total_attempts_global
    current_stage = get_stage_from_attempts(total_attempts_global)
    
    # Get appropriate LLM model for this stage
    stage_model = get_llm_model_for_stage(current_stage)
    
    # Create LLM manager for this stage (use existing if same model, otherwise create new)
    stage_llm_manager = llm_manager
    if stage_model != "qwen2:0.5b":
        # For now, use existing manager (will need to handle model switching later)
        print(f"[start_game] Stage {current_stage} would use model {stage_model}, but using default for now")
    
    # Update creatures to correct stage
    for cell in world.cells:
        cell.stage = current_stage
    
    game_id = str(uuid.uuid4())
    game_state[game_id] = {
        'simulation': simulation,
        'decision_maker': decision_maker,
        'stage_controller': stage_controller,
        'current_stage': current_stage,
        'prompt_history': [request.prompt],
        'current_traits': traits,
        'waiting_for_prompts': False,
        'attempt_number': 1,
        'max_attempts': 3,
        'waiting_for_prompt': False,
        'food_type_config': food_type_config,  # Store food config to persist across attempts
        'total_attempts': total_attempts_global  # Track total attempts
    }

    return {
        'game_id': game_id,
        'traits': traits,
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
        
        # Generate sprite only if explicitly requested (when user confirms)
        # Only generate if sprite doesn't already exist (to avoid regeneration)
        sprite_url = None
        if request.generate_sprite:
            try:
                # Check if sprite already exists first
                prompt_hash = sprite_generator._get_prompt_hash(request.prompt, 1)
                if sprite_generator._sprite_exists(prompt_hash, 1):
                    sprite_url = sprite_generator._get_sprite_url(prompt_hash, 1)
                    print(f"[parse_prompt] ✓ Sprite already exists, reusing: {sprite_url}")
                else:
                    # Only generate if sprite doesn't exist
                    sprite_url = await sprite_generator.get_or_generate_sprite(request.prompt, 0, 1, force_regenerate=False)
                    if sprite_url:
                        print(f"[parse_prompt] ✓ Sprite generated on confirm: {sprite_url}")
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
        
        # Try to generate sprite even on error (only if requested)
        sprite_url = None
        if request.generate_sprite:
            try:
                # Check if sprite already exists first
                prompt_hash = sprite_generator._get_prompt_hash(request.prompt, 1)
                if sprite_generator._sprite_exists(prompt_hash, 1):
                    sprite_url = sprite_generator._get_sprite_url(prompt_hash, 1)
                else:
                    sprite_url = await sprite_generator.get_or_generate_sprite(request.prompt, 0, 1, force_regenerate=False)
            except Exception:
                pass
        
        return {
            'success': False,
            'traits': traits,
            'sprite_url': sprite_url,
            'error': str(e),
            'debug': debug_info
        }


async def _process_evolution_background(game, world, request, current_stage):
    """Background task to process evolution (trait merging, application, sprite regeneration) without blocking."""
    try:
        # Use LLM-based merging to intelligently merge current traits with evolution descriptions
        print(f"[update_prompts] [Background] Merging traits with evolution: '{request.prompt[:50]}...'")
        print(f"[update_prompts] [Background] Current traits: {game['current_traits']}")
        merged_traits = await PromptParser.merge_traits(
            current_traits=game['current_traits'],
            evolution_description=request.prompt,
            llm_manager=llm_manager
        )
        print(f"[update_prompts] [Background] Merged traits: {merged_traits}")
        
        # Append new evolution description to prompt history
        game['prompt_history'].append(request.prompt)
        
        # Apply to creature
        for creature in world.cells:
            if creature.alive:
                apply_trait_evolution(creature, merged_traits)
                print(f"[update_prompts] [Background] Applied merged traits to creature {creature.id}, color: {creature.color}")
                break
        
        # Update game state
        game['current_traits'] = merged_traits
        
        # Regenerate sprite for all evolved creatures (same prompt = same sprite)
        evolution_prompt = ", ".join(game['prompt_history'])
        sprite_url = None
        try:
            # Generate sprite once for all creatures with same evolution prompt
            sprite_url = await sprite_generator.generate_sprite(evolution_prompt, 0, current_stage, force_regenerate=True)
            if sprite_url:
                print(f"[update_prompts] [Background] ✓ Regenerated sprite for evolution: {sprite_url}")
                # Assign same sprite URL to all alive creatures
                for creature in world.cells:
                    if creature.alive:
                        creature.sprite_url = sprite_url
                        print(f"[update_prompts] [Background] ✓ Assigned sprite to creature {creature.id}")
            else:
                print(f"[update_prompts] [Background] ⚠ Sprite regeneration failed, keeping existing or using canvas")
        except Exception as e:
            print(f"[update_prompts] [Background] ✗ Error regenerating sprite: {e}, keeping existing or using canvas")
    except Exception as e:
        print(f"[update_prompts] [Background] ✗ Error in background evolution processing: {e}")
        import traceback
        traceback.print_exc()


async def _restart_attempt(game, world, request, current_stage):
    """Restart attempt after population death: reset creatures, apply new traits, keep world state."""
    try:
        print(f"[restart_attempt] Restarting attempt {game['attempt_number'] + 1}")
        
        # Ensure world uses the stored food_type_config (persist across attempts)
        if 'food_type_config' in game:
            world.food_type_config = game['food_type_config'].copy()
            print(f"[restart_attempt] Restored food_type_config from game state (persisting across attempts)")
        
        # Reset energy events tracker for new attempt
        if hasattr(world, 'reset_energy_events'):
            world.reset_energy_events()
        
        # Merge traits with new prompt
        merged_traits = await PromptParser.merge_traits(
            current_traits=game['current_traits'],
            evolution_description=request.prompt,
            llm_manager=llm_manager
        )
        print(f"[restart_attempt] Merged traits: {merged_traits}")
        
        # Append new prompt to history
        game['prompt_history'].append(request.prompt)
        game['current_traits'] = merged_traits
        
        # Reset all creatures to alive state and apply new traits
        import random
        for creature in world.cells:
            # Reset creature to alive
            creature.alive = True
            creature.energy = 50  # Reset energy to starting value
            
            # Apply updated traits
            apply_trait_evolution(creature, merged_traits)
            
            # Reset age (optional - could keep age for continuity)
            # creature.age = 0
        
        # Reuse sprite from original confirm (don't regenerate on restart)
        # Use the original prompt from confirm, not the evolution prompt
        original_prompt = game['prompt_history'][0] if game.get('prompt_history') else request.prompt
        sprite_url = None
        try:
            # Check if sprite exists for original prompt (from confirm)
            prompt_hash = sprite_generator._get_prompt_hash(original_prompt, current_stage)
            if sprite_generator._sprite_exists(prompt_hash, current_stage):
                sprite_url = sprite_generator._get_sprite_url(prompt_hash, current_stage)
                print(f"[restart_attempt] ✓ Reusing sprite from confirm: {sprite_url}")
            else:
                # Only generate if sprite doesn't exist (shouldn't happen if confirm worked)
                sprite_url = await sprite_generator.get_or_generate_sprite(
                    original_prompt, 0, current_stage, force_regenerate=False
                )
                if sprite_url:
                    print(f"[restart_attempt] ✓ Generated sprite (was missing): {sprite_url}")
            
            # Assign sprite to all creatures
            if sprite_url:
                for creature in world.cells:
                    creature.sprite_url = sprite_url
        except Exception as e:
            print(f"[restart_attempt] ✗ Error loading sprite: {e}")
        
        # Increment attempt number (before clearing flag so WebSocket loop can check)
        game['attempt_number'] += 1
        
        # Update global attempt counter
        global total_attempts_global
        total_attempts_global += 1
        game['total_attempts'] = total_attempts_global
        
        # Check if stage should change based on total attempts
        new_stage = get_stage_from_attempts(total_attempts_global)
        if new_stage != game.get('current_stage', 1):
            game['current_stage'] = new_stage
            # Update all creatures to new stage
            for creature in world.cells:
                creature.stage = new_stage
            print(f"[restart_attempt] Stage evolved to {new_stage} (total attempts: {total_attempts_global})")
        
        print(f"[restart_attempt] ✓ Attempt restarted. New attempt number: {game['attempt_number']}, Total attempts: {total_attempts_global}")
        
        # Clear waiting flag to resume simulation
        game['waiting_for_prompt'] = False
        
    except Exception as e:
        print(f"[restart_attempt] ✗ Error restarting attempt: {e}")
        import traceback
        traceback.print_exc()
        game['waiting_for_prompt'] = False  # Clear flag even on error


@app.post("/update_prompts/{game_id}")
async def update_prompts(game_id: str, request: PromptUpdateRequest):
    """Update prompt (evolution description). Restarts attempt if population died."""
    game = game_state.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Get world and stage info
    world = game['simulation'].world
    current_stage = game.get('current_stage', 1)
    
    # Check if we're restarting an attempt after population death
    if game.get('waiting_for_prompt', False):
        # Restart attempt with new traits
        print(f"[update_prompts] Restarting attempt after population death")
        await _restart_attempt(game, world, request, current_stage)
        return {
            'status': 'attempt_restarted',
            'attempt_number': game['attempt_number'],
            'max_attempts': game['max_attempts'],
            'traits': game['current_traits']
        }
    else:
        # Normal evolution update (during gameplay)
        print(f"[update_prompts] Normal evolution update")
        asyncio.create_task(_process_evolution_background(game, world, request, current_stage))
        return {
            'status': 'updated',
            'traits': game['current_traits']
        }


async def regenerate_sprites_for_evolved_creatures(game, evolved_creatures, new_stage):
    """
    Regenerate sprites for creatures that just evolved.
    
    Args:
        game: Game state dict
        evolved_creatures: List of newly evolved creatures
        new_stage: The new stage number (2 or 3)
    """
    if not evolved_creatures:
        return
    
    world = game['simulation'].world
    prompt_history = game['prompt_history']
    
    # Combine all prompts from history for full context
    evolution_prompt = ", ".join(prompt_history)
    
    # Generate sprite once for all evolved creatures with same prompt+stage
    sprite_url = None
    try:
        print(f"[regenerate_sprites] Regenerating sprite for evolution to stage {new_stage}")
        sprite_url = await sprite_generator.generate_sprite(
            evolution_prompt, 
            0,  # creature_id not used for file naming
            new_stage, 
            force_regenerate=True
        )
        if sprite_url:
            print(f"[regenerate_sprites] ✓ Regenerated sprite: {sprite_url}")
            # Assign same sprite URL to all evolved creatures
            for creature in evolved_creatures:
                creature.sprite_url = sprite_url
                print(f"[regenerate_sprites] ✓ Assigned sprite to creature {creature.id}")
        else:
            print(f"[regenerate_sprites] ⚠ Sprite regeneration failed, keeping existing or using canvas")
    except Exception as e:
        print(f"[regenerate_sprites] ✗ Error regenerating sprite: {e}, keeping existing or using canvas")


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """WebSocket for real-time game updates with single continuous simulation."""
    await websocket.accept()

    game = game_state.get(game_id)
    if not game:
        await websocket.close(code=4000, reason="Game not found")
        return

    try:
        stage_controller = game['stage_controller']
        simulation = game['simulation']
        decision_maker = game['decision_maker']
        
        # Send game start message
        await websocket.send_json({
            'status': 'game_started',
            'stage': 1,
            'attempt_number': game['attempt_number'],
            'max_attempts': game['max_attempts'],
            'attempts_remaining': game['max_attempts'] - game['attempt_number'] + 1
        })
        
        # Run continuous simulation until population dies or game ends
        while True:
            # Check if waiting for prompt update
            if game.get('waiting_for_prompt', False):
                # Wait for prompt update (will be handled by restart_attempt endpoint)
                await asyncio.sleep(0.1)
                continue
            
            # Execute one simulation step
            step_result = await simulation.step(decision_maker)
            
            # Regenerate sprites for any creatures that evolved during this step
            evolved_creatures = step_result.get('evolved_creatures', [])
            if evolved_creatures:
                current_stage = stage_controller.current_stage
                await regenerate_sprites_for_evolved_creatures(game, evolved_creatures, current_stage)
            
            # Check if population is extinct
            if simulation.is_population_extinct():
                # Print current prompt for reference
                current_prompt = ", ".join(game['prompt_history']) if game.get('prompt_history') else "N/A"
                print(f"\n{'='*60}")
                print(f"[POPULATION EXTINCT] Current user prompt:")
                print(f"{current_prompt}")
                print(f"{'='*60}\n")
                
                # Population died - check if attempts remain
                if game['attempt_number'] < game['max_attempts']:
                    # More attempts available - pause and wait for prompt
                    game['waiting_for_prompt'] = True
                    # Get energy events from world
                    energy_events = []
                    if hasattr(simulation.world, 'get_energy_events_list'):
                        energy_events = simulation.world.get_energy_events_list()
                    await websocket.send_json({
                        'status': 'population_died',
                        'attempt_number': game['attempt_number'],
                        'max_attempts': game['max_attempts'],
                        'attempts_remaining': game['max_attempts'] - game['attempt_number'],
                        'turn': step_result['turn'],
                        'current_prompt': current_prompt,
                        'energy_events': energy_events
                    })
                    # Wait for prompt update (will restart attempt)
                    while game.get('waiting_for_prompt', False):
                        await asyncio.sleep(0.1)
                    # Continue to next iteration (attempt will be restarted)
                    continue
                else:
                    # No attempts remaining - game over
                    final_results = StageResults.calculate(game['simulation'].world, player_id=1)
                    # Get energy events from world
                    energy_events = []
                    if hasattr(simulation.world, 'get_energy_events_list'):
                        energy_events = simulation.world.get_energy_events_list()
                    await websocket.send_json({
                        'status': 'game_complete',
                        'final_results': final_results,
                        'attempt_number': game['attempt_number'],
                        'max_attempts': game['max_attempts'],
                        'current_prompt': current_prompt,
                        'energy_events': energy_events
                    })
                    break
            
            # Send update every simulation step (so frontend sees movement)
            stage_info = stage_controller.get_stage_info()
            
            await websocket.send_json({
                'status': 'update',
                'turn': step_result['turn'],
                'stage': stage_info['stage'],
                'time_remaining': stage_info['time_remaining'],
                'attempt_number': game['attempt_number'],
                'max_attempts': game['max_attempts'],
                'attempts_remaining': game['max_attempts'] - game['attempt_number'] + 1,
                'world': {
                    'creatures': step_result['creatures'],
                    'resources': step_result['resources']
                },
                'events': step_result['events'][-5:],  # Last 5 events
                'environment': step_result.get('environment'),
                'territories': step_result.get('territories', {}),
                'regions': step_result.get('regions', {}),
                'scoring': step_result.get('scoring')
            })
            
            # Small delay between turns
            await asyncio.sleep(0.5)

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
