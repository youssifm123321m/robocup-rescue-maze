# ============================================================
# RoboCup Rescue Maze – Decision Function (Checkpoints + Start/Pause)
# ============================================================

# Import 'deque' which is a highly efficient queue used for the BFS (shortest path) algorithm.
from collections import deque
# Import 'copy' so we can create exact clones (snapshots) of the robot's memory for checkpoints.
import copy 

# ============================================================
# SECTION 1 – Direction helpers
# ============================================================

# A list of the four possible directions the robot can move.
DIRECTIONS = ['N', 'E', 'S', 'W']

# Define a function to calculate the coordinates of the next cell.
def get_neighbor(cell, direction):
    """Return the (row, col) of the neighboring cell based on the direction."""
    row, col = cell
    if direction == 'N': return (row - 1, col)
    elif direction == 'S': return (row + 1, col)
    elif direction == 'E': return (row, col + 1)
    elif direction == 'W': return (row, col - 1) 
    return cell

# Define a function to get the exact opposite of a given direction.
def get_opposite(direction):
    opposites = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
    return opposites.get(direction)

# ============================================================
# SECTION 2 – BFS shortest path finder (Black Hole Protected)
# FIX #1: cell_data is now passed as a parameter instead of
#         secretly reading from _state inside the function.
# ============================================================

def bfs_shortest_path(internal_map, cell_data, start_cell, goal_cell):
    # Create a new empty queue to process cells one by one.
    frontier = deque()
    frontier.append((start_cell, []))
    visited_bfs = set()
    visited_bfs.add(start_cell)

    while frontier:
        current_cell, path_so_far = frontier.popleft()

        if current_cell == goal_cell:
            return path_so_far

        for direction in DIRECTIONS:
            wall_is_open = internal_map.get(current_cell, {}).get(direction, 0)

            if wall_is_open == 1:
                neighbor = get_neighbor(current_cell, direction)

                # FIX #1: Use the cell_data parameter, NOT _state directly.
                neighbor_data = cell_data.get(neighbor, {})
                
                if neighbor_data.get('black_hole', False):
                    continue 

                if neighbor not in visited_bfs:
                    visited_bfs.add(neighbor)
                    frontier.append((neighbor, path_so_far + [direction]))

    return []

# ============================================================
# SECTION 3 – Global state dictionary
# ============================================================

_state = {
    'current_cell': (0, 0),        
    'start_cell':   (0, 0),        
    'internal_map': {},            
    'visited': set(),              
    'dfs_stack': [],               
    'phase': 'exploring',          
    'return_path': [],             
    'cell_data': {},               
    'pending_direction': None,     
    'initialised': False,          
    'checkpoint_snapshot': None,        
    'last_saved_checkpoint_cell': None,
    # FIX #4: Store the absolute compass heading when a victim is spotted,
    # so kit dropping always faces the correct real-world direction.
    'victim_heading': None,
    # FIX #4: Store which side (L/R) the victim was seen from.
    'victim_side': None,
}

# ============================================================
# SECTION 4 – Update map
# ============================================================

def _update_map(cell, walls_list, victim, black_hole, blue_floor):
    _state['internal_map'][cell] = {
        'N': walls_list[0], 'S': walls_list[1],
        'E': walls_list[2], 'W': walls_list[3],
    }

    if cell not in _state['cell_data']:
        _state['cell_data'][cell] = {
            'victim': None,
            'black_hole': False,
            'blue': False,
            'blue_delay_done': False,
            'kits_dropped': False,
        }

    if victim is not None:
        _state['cell_data'][cell]['victim'] = victim
    if black_hole:
        _state['cell_data'][cell]['black_hole'] = True
    if blue_floor:
        _state['cell_data'][cell]['blue'] = True

# ============================================================
# SECTION 5 – Pick next DFS direction
# ============================================================

def _pick_dfs_direction():
    cell = _state['current_cell']
    
    if _state['cell_data'].get(cell, {}).get('black_hole', False):
        return None

    walls = _state['internal_map'].get(cell, {})

    for direction in DIRECTIONS:
        if walls.get(direction, 0) == 1:
            neighbor = get_neighbor(cell, direction)
            neighbor_data = _state['cell_data'].get(neighbor, {})
            if neighbor_data.get('black_hole', False):
                continue
            if neighbor not in _state['visited']:
                return direction
    return None

# ============================================================
# SECTION 6 – Main decision function 
# ============================================================

def decide(walls, executed, victim=None, victim_side=None, current_heading=0.0,
           black_hole=False, blue_floor=False, silver_floor=False,
           reset_to_checkpoint=False, play_signal=True):
    # NOTE: Two new parameters added:
    #   victim_side   – 'L' or 'R' from the camera (was passed separately before)
    #   current_heading – the MPU compass angle RIGHT NOW (from MPU.get_heading())
    #   These are used for FIX #4 (correct kit-drop direction).

    if not _state['initialised']:
        _state['current_cell'] = (0, 0)      
        _state['start_cell']   = (0, 0)      
        _state['visited'].add((0, 0))        
        _state['initialised']  = True        

    # ----------------------------------------------------------
    # FIX #4: Save victim heading the moment the victim is seen.
    # We record BOTH the compass heading AND the side right now,
    # before any movement happens. Mobility will use these later.
    # ----------------------------------------------------------
    if victim is not None and victim_side is not None:
        current_cell_check = _state['current_cell']
        cell_already_dropped = _state['cell_data'].get(current_cell_check, {}).get('kits_dropped', False)
        if not cell_already_dropped:
            # Save the exact compass heading and side at the moment of detection.
            _state['victim_heading'] = current_heading
            _state['victim_side']    = victim_side

    # ----------------------------------------------------------
    # MANUAL CHECKPOINT RESET LOGIC
    # ----------------------------------------------------------
    if reset_to_checkpoint:
        print("[CHECKPOINT] Reset triggered! Restoring memory...")
        
        dropped_kits_memory = {}
        for cell_key, data in _state['cell_data'].items():
            if data.get('kits_dropped', False):
                dropped_kits_memory[cell_key] = True

        if _state['checkpoint_snapshot'] is not None:
            snap = _state['checkpoint_snapshot']
            _state['current_cell'] = snap['current_cell']
            _state['start_cell']   = snap['start_cell']
            _state['internal_map'] = copy.deepcopy(snap['internal_map'])
            _state['visited']      = copy.deepcopy(snap['visited'])
            _state['dfs_stack']    = copy.deepcopy(snap['dfs_stack'])
            _state['phase']        = snap['phase']
            _state['return_path']  = copy.deepcopy(snap['return_path'])
            _state['cell_data']    = copy.deepcopy(snap['cell_data'])

            # FIX #9: Also restore the checkpoint lock so saving works correctly
            # after the reset.
            _state['last_saved_checkpoint_cell'] = snap.get('last_saved_checkpoint_cell', None)

        else:
            print("[CHECKPOINT] No silver floor found yet. Resetting to Start Zone (0,0).")
            reset_robot()
            _state['initialised']  = True
            
        for cell_key in dropped_kits_memory:
            if cell_key not in _state['cell_data']:
                _state['cell_data'][cell_key] = {
                    'victim': None, 'black_hole': False, 'blue': False, 
                    'blue_delay_done': False, 'kits_dropped': True
                }
            else:
                _state['cell_data'][cell_key]['kits_dropped'] = True
                
        _state['pending_direction'] = 'STOP'
        return 'STOP', False, None, None, None

    # ----------------------------------------------------------
    # PLAY / PAUSE LOGIC
    # ----------------------------------------------------------
    if not play_signal:
        return 'STOP', False, None, None, None

    # ----------------------------------------------------------
    # Safely Handle Movement & State Syncing
    # ----------------------------------------------------------
    if not executed and not reset_to_checkpoint:
        
        if black_hole and _state['pending_direction'] in DIRECTIONS:
            target_cell = get_neighbor(_state['current_cell'], _state['pending_direction'])
            print(f"\n[EMERGENCY] Black hole detected! Marking {target_cell} as danger!")
            
            if target_cell not in _state['cell_data']:
                _state['cell_data'][target_cell] = {
                    'victim': None, 'black_hole': True, 'blue': False, 
                    'blue_delay_done': False, 'kits_dropped': False
                }
            else:
                _state['cell_data'][target_cell]['black_hole'] = True
            
            black_hole = False
            _state['pending_direction'] = None
            
        elif _state['pending_direction'] not in [None, 'STOP', 'DONE']:
            return _state['pending_direction'], False, None, None, None
            
    elif not reset_to_checkpoint:
        if _state['pending_direction'] in DIRECTIONS:
            arrived_cell = get_neighbor(_state['current_cell'], _state['pending_direction'])
            
            if _state['phase'] == 'exploring':
                if arrived_cell not in _state['visited']:
                    # Brand new cell: push direction onto the breadcrumb stack.
                    _state['dfs_stack'].append(_state['pending_direction'])
                else:
                    # FIX #5: Only pop the stack if this move is the EXACT reverse of
                    # the last breadcrumb. Any other move into a visited cell (a loop)
                    # is ignored safely — the stack stays correct.
                    if (len(_state['dfs_stack']) > 0 and
                            _state['pending_direction'] == get_opposite(_state['dfs_stack'][-1])):
                        _state['dfs_stack'].pop()
                    # If it is NOT the reverse (robot took a loop), do nothing.
                    # The stack already reflects the real exploration path.
            
            elif _state['phase'] == 'returning':
                if len(_state['return_path']) > 0 and _state['pending_direction'] == _state['return_path'][0]:
                    _state['return_path'].pop(0)

            _state['current_cell'] = arrived_cell
            _state['visited'].add(arrived_cell)

            if arrived_cell in _state['cell_data']:
                # Only reset the blue delay if this is the FIRST visit (exploring phase).
                # During the return phase, do NOT reset it so we don't trigger the 5s wait again.
                if _state['phase'] == 'exploring':
                    _state['cell_data'][arrived_cell]['blue_delay_done'] = False

    # ----------------------------------------------------------
    # Phase: done
    # ----------------------------------------------------------
    if _state['phase'] == 'done':
        return 'DONE', False, None, None, None

    # ----------------------------------------------------------
    # Update map with fresh sensor readings
    # ----------------------------------------------------------
    current_cell = _state['current_cell']
    _update_map(current_cell, walls, victim, black_hole, blue_floor)
    cell_info = _state['cell_data'][current_cell]

    # ----------------------------------------------------------
    # CHECKPOINT (SILVER FLOOR) SAVE LOGIC
    # FIX #9: Also save 'last_saved_checkpoint_cell' inside the snapshot
    #         so it is correctly restored on reset.
    # ----------------------------------------------------------
    if silver_floor:
        if _state['last_saved_checkpoint_cell'] != current_cell:
            print(f"[CHECKPOINT] Silver floor at {current_cell}. Saving snapshot!")
            _state['checkpoint_snapshot'] = {
                'current_cell': _state['current_cell'],
                'start_cell':   _state['start_cell'],
                'internal_map': copy.deepcopy(_state['internal_map']),
                'visited':      copy.deepcopy(_state['visited']),
                'dfs_stack':    copy.deepcopy(_state['dfs_stack']),
                'phase':        _state['phase'],
                'return_path':  copy.deepcopy(_state['return_path']),
                'cell_data':    copy.deepcopy(_state['cell_data']),
                # FIX #9: Save the lock coordinate inside the snapshot too.
                'last_saved_checkpoint_cell': current_cell,
            }
            _state['last_saved_checkpoint_cell'] = current_cell
    else:
        _state['last_saved_checkpoint_cell'] = None

    # ----------------------------------------------------------
    # Calculate Victim Kits
    # ----------------------------------------------------------
    # Default: 0 kits (safe to pass to Mobility — avoids the None TypeError).
    kits_to_drop = 0

    # FIX #4: Read the saved heading and side (recorded when victim was first spotted).
    kit_heading = None
    kit_side    = None

    if cell_info['victim'] is not None and not cell_info['kits_dropped']:
        v_type = str(cell_info['victim']).upper()
        
        if v_type in ['H', 'RED', 'R']:
            kits_to_drop = 2
        elif v_type in ['S', 'YELLOW', 'Y']:
            kits_to_drop = 1
        elif v_type in ['U', 'GREEN', 'G']:
            kits_to_drop = 0
            
        # Only mark as done and extract heading if there are kits to drop.
        cell_info['kits_dropped'] = True
        # Pass the saved compass heading and side to Mobility.
        kit_heading = _state['victim_heading']
        kit_side    = _state['victim_side']
        # Clear the saved victim info now that we have consumed it.
        _state['victim_heading'] = None
        _state['victim_side']    = None

    # ----------------------------------------------------------
    # Safe Blue Floor Check
    # ----------------------------------------------------------
    blue_flag = False

    if blue_floor and not cell_info['blue_delay_done']:
        cell_info['blue_delay_done'] = True
        blue_flag = True 
        _state['pending_direction'] = 'STOP' 
        return 'STOP', True, kits_to_drop, kit_heading, kit_side

    # ----------------------------------------------------------
    # Returning Phase (BFS)
    # ----------------------------------------------------------
    if _state['phase'] == 'returning':
        if len(_state['return_path']) == 0:
            _state['phase'] = 'done'
            _state['pending_direction'] = 'DONE'
            return 'DONE', False, kits_to_drop, kit_heading, kit_side

        next_direction = _state['return_path'][0] 
        _state['pending_direction'] = next_direction 
        return next_direction, blue_flag, kits_to_drop, kit_heading, kit_side

    # ----------------------------------------------------------
    # Exploring Phase (DFS)
    # ----------------------------------------------------------
    next_direction = _pick_dfs_direction()

    if next_direction is not None:
        _state['pending_direction'] = next_direction
        return next_direction, blue_flag, kits_to_drop, kit_heading, kit_side

    if len(_state['dfs_stack']) == 0:
        # FIX #1: Pass _state['cell_data'] explicitly as a parameter.
        return_path = bfs_shortest_path(
            _state['internal_map'],
            _state['cell_data'],      # <-- FIX #1
            _state['current_cell'],
            _state['start_cell']
        )

        if len(return_path) == 0:
            _state['phase'] = 'done'
            _state['pending_direction'] = 'DONE'
            return 'DONE', blue_flag, kits_to_drop, kit_heading, kit_side

        _state['return_path'] = return_path
        _state['phase'] = 'returning'

        next_direction = _state['return_path'][0] 
        _state['pending_direction'] = next_direction
        return next_direction, blue_flag, kits_to_drop, kit_heading, kit_side

    arrival_direction   = _state['dfs_stack'][-1] 
    backtrack_direction = get_opposite(arrival_direction)
    _state['pending_direction'] = backtrack_direction
    return backtrack_direction, blue_flag, kits_to_drop, kit_heading, kit_side

# ============================================================
# Helpers
# ============================================================

def get_robot_state():
    return {
        'current_cell': _state['current_cell'], 'start_cell': _state['start_cell'],
        'phase': _state['phase'], 'visited': set(_state['visited']),
        'internal_map': dict(_state['internal_map']), 'cell_data': dict(_state['cell_data']),
        'dfs_stack': list(_state['dfs_stack']), 'return_path': list(_state['return_path']),
    }

def reset_robot():
    _state.update({
        'current_cell': (0, 0), 'start_cell': (0, 0), 'internal_map': {},
        'visited': set(), 'dfs_stack': [], 'phase': 'exploring',
        'return_path': [], 'cell_data': {}, 'pending_direction': None, 'initialised': False,
        'checkpoint_snapshot': None, 'last_saved_checkpoint_cell': None,
        'victim_heading': None, 'victim_side': None,
    })
