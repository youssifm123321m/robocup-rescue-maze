# ============================================================
# RoboCup Rescue Maze – Full Competition Simulation
# ============================================================
import pygame
import time
import random
from collections import deque
from pyamaze import maze

# ============================================================
# SETTINGS
# ============================================================

MAZE_ROWS    = 15
MAZE_COLS    = 15
LOOP_PERCENT = 50      # 50 = realistic competition maze (some loops)
STEP_DELAY   = 0.2    # seconds between each robot move

CELL_SIZE    = 20      # pixel size of each cell
WALL_WIDTH   = 1
MARGIN       = 40

# -- Competition tile probabilities (out of all non-special cells) --
BLACK_TILE_COUNT   = 2    # number of black (hole) tiles
SILVER_TILE_COUNT  = 1    # number of silver (checkpoint) tiles
BLUE_TILE_COUNT    = 1    # number of blue (puddle) tiles
RED_ZONE_COUNT     = 1    # number of red (danger zone entrance) tiles
VICTIM_COUNT       = 5    # number of victims placed on walls

BLUE_STOP_TIME     = 5.0  # seconds robot must stop on blue tile
VICTIM_BLINK_TIME  = 5.0  # seconds robot blinks after finding victim
BLINK_INTERVAL     = 0.5  # ON/OFF interval for blink

# -- Scoring --
SCORE_CHECKPOINT       =  10
SCORE_VICTIM_FOUND     =  20
SCORE_KIT_HARMED       =  20   # per kit delivered (2 kits for H/Red)
SCORE_KIT_STABLE       =  10   # per kit delivered (1 kit for S/Yellow)
SCORE_RAMP_NAVIGATE    =   5
SCORE_RETURN_TO_START  =  30
SCORE_BLACK_TILE       = -20   # penalty
SCORE_WRONG_VICTIM     = -10   # penalty
SCORE_LOP              =  -5   # penalty per Lack of Progress

MAX_KITS = 12

# ============================================================
# COLORS
# ============================================================

COLOR_BACKGROUND  = (245, 245, 240)
COLOR_WALL        = (40,  40,  40)
COLOR_VISITED     = (180, 220, 255)
COLOR_CURRENT     = (30,  120, 220)
COLOR_START       = (80,  200, 120)
COLOR_RETURN      = (100, 220, 180)
COLOR_TEXT        = (40,  40,  40)

# Special tile colors
COLOR_BLACK_TILE  = (20,  20,  20)
COLOR_SILVER_TILE = (192, 192, 192)
COLOR_BLUE_TILE   = (100, 149, 237)
COLOR_RED_ZONE    = (220,  60,  60)

# Victim colors
COLOR_VICTIM_H    = (255, 100,  50)   # Harmed  – orange-red
COLOR_VICTIM_S    = (255, 220,  50)   # Stable  – yellow
COLOR_VICTIM_U    = (80,  200, 120)   # Unharmed – green

# ============================================================
# SECTION 1 – Place special tiles randomly (avoiding start)
# ============================================================

def place_special_tiles(m, start_cell):
    """
    Randomly scatter special tiles across the maze.
    Returns dicts/sets of cell positions for each tile type.
    Rules:
      - No special tile at the start cell
      - Black tiles and victims are never adjacent to each other
        (RoboCup rule: victims not near black tiles)
    """

    all_cells = [(r, c) for r in range(1, m.rows + 1)
                         for c in range(1, m.cols + 1)]

    # Remove start cell from the pool
    available = [cell for cell in all_cells if cell != start_cell]
    random.shuffle(available)

    black_tiles  = set()
    silver_tiles = set()
    blue_tiles   = set()
    red_zones    = set()
    victims      = {}   # cell -> victim info dict

    def is_adjacent_to_black(cell):
        r, c = cell
        neighbors = [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]
        return any(n in black_tiles for n in neighbors)

    # Place black tiles first
    placed = 0
    for cell in available:
        if placed >= BLACK_TILE_COUNT:
            break
        black_tiles.add(cell)
        placed += 1

    # Remove black tiles and their neighbors from pool for other tiles
    safe_pool = [cell for cell in available
                 if cell not in black_tiles and not is_adjacent_to_black(cell)]
    random.shuffle(safe_pool)

    idx = 0

    # Silver tiles (checkpoints)
    for _ in range(SILVER_TILE_COUNT):
        if idx < len(safe_pool):
            silver_tiles.add(safe_pool[idx])
            idx += 1

    # Blue tiles (puddles)
    for _ in range(BLUE_TILE_COUNT):
        if idx < len(safe_pool):
            blue_tiles.add(safe_pool[idx])
            idx += 1

    # Red zone entrances
    for _ in range(RED_ZONE_COUNT):
        if idx < len(safe_pool):
            red_zones.add(safe_pool[idx])
            idx += 1

    # Victims – placed on walls, stored per cell
    # Victim types: H (Harmed), S (Stable), U (Unharmed)
    #               Red, Yellow, Green (colored)
    victim_types   = ['H', 'S', 'U', 'Red', 'Yellow', 'Green']
    victim_kits    = {'H': 2, 'S': 1, 'U': 0,
                      'Red': 2, 'Yellow': 1, 'Green': 0}

    for _ in range(VICTIM_COUNT):
        if idx < len(safe_pool):
            cell = safe_pool[idx]
            idx += 1
            vtype = random.choice(victim_types)
            victims[cell] = {
                'type':      vtype,
                'kits':      victim_kits[vtype],
                'found':     False,
                'reported':  False,
            }

    return black_tiles, silver_tiles, blue_tiles, red_zones, victims


# ============================================================
# SECTION 2 – Draw everything
# ============================================================

def draw_maze(screen, m, visited, current_cell,
              start_cell, mode, return_cells, font,
              black_tiles, silver_tiles, blue_tiles, red_zones,
              victims, checkpoint, score, kits_left, lop_count,
              blink_state, blink_cell):
    """
    Draw the full maze with all special tiles, robot, and HUD.
    """

    screen.fill(COLOR_BACKGROUND)

    for row in range(1, m.rows + 1):
        for col in range(1, m.cols + 1):

            cell = (row, col)
            x = MARGIN + (col - 1) * CELL_SIZE
            y = MARGIN + (row - 1) * CELL_SIZE

            # -- Choose fill color --
            if cell == current_cell:
                fill_color = COLOR_CURRENT

            elif cell in black_tiles:
                fill_color = COLOR_BLACK_TILE

            elif cell in silver_tiles:
                fill_color = COLOR_SILVER_TILE

            elif cell in blue_tiles:
                fill_color = COLOR_BLUE_TILE

            elif cell in red_zones:
                fill_color = COLOR_RED_ZONE

            elif cell in victims and not victims[cell]['found']:
                # Undetected victim – show faint color hint
                vtype = victims[cell]['type']
                if vtype in ('H', 'Red'):
                    fill_color = (255, 180, 160)
                elif vtype in ('S', 'Yellow'):
                    fill_color = (255, 240, 160)
                else:
                    fill_color = (180, 240, 180)

            elif cell == start_cell and cell != current_cell:
                fill_color = COLOR_START

            elif cell in return_cells:
                fill_color = COLOR_RETURN

            elif cell == checkpoint and cell != current_cell:
                # Last checkpoint – subtle highlight
                fill_color = (210, 210, 210)

            elif cell in visited:
                fill_color = COLOR_VISITED

            else:
                fill_color = COLOR_BACKGROUND

            pygame.draw.rect(screen, fill_color,
                             (x, y, CELL_SIZE, CELL_SIZE))

            # -- Draw victim label on wall if found --
            if cell in victims and victims[cell]['found']:
                vtype = victims[cell]['type']
                label = vtype[0] if vtype in ('Red','Yellow','Green') else vtype
                v_font = pygame.font.SysFont("Arial", max(10, CELL_SIZE // 3), bold=True)
                v_surf = v_font.render(label, True, (180, 0, 0))
                screen.blit(v_surf, (x + 2, y + 2))

            # -- Blinking LED effect when robot is identifying victim --
            if blink_cell == cell and blink_state:
                pygame.draw.rect(screen, (255, 255, 0),
                                 (x + CELL_SIZE//3, y + CELL_SIZE//3,
                                  CELL_SIZE//3, CELL_SIZE//3))

            # -- Draw walls --
            walls = m.maze_map[cell]

            if not walls['N']:
                pygame.draw.line(screen, COLOR_WALL,
                                 (x, y), (x + CELL_SIZE, y), WALL_WIDTH)
            if not walls['S']:
                pygame.draw.line(screen, COLOR_WALL,
                                 (x, y + CELL_SIZE),
                                 (x + CELL_SIZE, y + CELL_SIZE), WALL_WIDTH)
            if not walls['E']:
                pygame.draw.line(screen, COLOR_WALL,
                                 (x + CELL_SIZE, y),
                                 (x + CELL_SIZE, y + CELL_SIZE), WALL_WIDTH)
            if not walls['W']:
                pygame.draw.line(screen, COLOR_WALL,
                                 (x, y), (x, y + CELL_SIZE), WALL_WIDTH)

    # -- Draw robot circle --
    robot_row, robot_col = current_cell
    robot_x = MARGIN + (robot_col - 1) * CELL_SIZE + CELL_SIZE // 2
    robot_y = MARGIN + (robot_row - 1) * CELL_SIZE + CELL_SIZE // 2
    robot_radius = CELL_SIZE // 3

    pygame.draw.circle(screen, (255, 255, 255),
                       (robot_x, robot_y), robot_radius)
    pygame.draw.circle(screen, COLOR_WALL,
                       (robot_x, robot_y), robot_radius, 2)

    # -- HUD: status bar --
    hud_y = MARGIN + m.rows * CELL_SIZE + 8
    status_text = (f"Mode: {mode}   |   Cell: {current_cell}"
                   f"   |   Visited: {len(visited)}"
                   f"   |   LoP: {lop_count}")
    screen.blit(font.render(status_text, True, COLOR_TEXT),
                (MARGIN, hud_y))

    # -- HUD: score and kits --
    score_text = f"Score: {score}   |   Kits left: {kits_left} / {MAX_KITS}"
    screen.blit(font.render(score_text, True, (0, 100, 0)),
                (MARGIN, hud_y + 18))

    # -- Legend --
    legend_items = [
        (COLOR_START,        "Start"),
        (COLOR_CURRENT,      "Robot"),
        (COLOR_VISITED,      "Visited"),
        (COLOR_BLACK_TILE,   "Black (hole)"),
        (COLOR_SILVER_TILE,  "Silver (checkpoint)"),
        (COLOR_BLUE_TILE,    "Blue (puddle)"),
        (COLOR_RED_ZONE,     "Red (danger)"),
        ((255, 180, 160),    "Victim"),
        (COLOR_RETURN,       "Return path"),
    ]
    legend_x = MARGIN
    legend_y  = hud_y + 38

    for color, label in legend_items:
        pygame.draw.rect(screen, color,
                         (legend_x, legend_y, 12, 12))
        pygame.draw.rect(screen, COLOR_WALL,
                         (legend_x, legend_y, 12, 12), 1)
        surf = font.render(label, True, COLOR_TEXT)
        screen.blit(surf, (legend_x + 15, legend_y))
        legend_x += 15 + surf.get_width() + 12

    pygame.display.flip()


# ============================================================
# SECTION 3 – Helper functions
# ============================================================

def get_neighbor(cell, direction):
    row, col = cell
    if direction == 'N':   return (row - 1, col)
    elif direction == 'S': return (row + 1, col)
    elif direction == 'E': return (row, col + 1)
    elif direction == 'W': return (row, col - 1)

def get_opposite(direction):
    return {'N':'S','S':'N','E':'W','W':'E'}[direction]

def bfs_shortest_path(maze_map, start_cell, goal_cell):
    frontier    = deque([(start_cell, [])])
    visited_bfs = {start_cell}
    while frontier:
        current, path = frontier.popleft()
        if current == goal_cell:
            return path
        for direction in ['N','S','E','W']:
            if current in maze_map and maze_map[current][direction]:
                neighbor = get_neighbor(current, direction)
                if neighbor not in visited_bfs:
                    visited_bfs.add(neighbor)
                    frontier.append((neighbor, path + [direction]))
    return []


def handle_events():
    """Process pygame events. Returns False if window was closed."""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
    return True


def redraw_and_wait(screen, m, visited, current_cell, start_cell,
                    mode, return_cells, font,
                    black_tiles, silver_tiles, blue_tiles, red_zones,
                    victims, checkpoint, score, kits_left, lop_count,
                    blink_state, blink_cell, delay):
    """Draw one frame and sleep for delay seconds."""
    draw_maze(screen, m, visited, current_cell, start_cell,
              mode, return_cells, font,
              black_tiles, silver_tiles, blue_tiles, red_zones,
              victims, checkpoint, score, kits_left, lop_count,
              blink_state, blink_cell)
    steps = max(1, int(delay / 0.05))
    for _ in range(steps):
        time.sleep(0.05)
        if not handle_events():
            return False
    return True


# ============================================================
# SECTION 4 – Special tile handlers
# ============================================================

def handle_silver_tile(cell, visited_checkpoints, score):
    """
    Robot arrived on a silver checkpoint tile.
    Only score it the first time it is visited.
    Returns updated score and the new checkpoint position.
    """
    if cell not in visited_checkpoints:
        visited_checkpoints.add(cell)
        score += SCORE_CHECKPOINT
        print(f"  [CHECKPOINT] Reached checkpoint at {cell}. Score: {score}")
    return score, cell   # second return value = new checkpoint position


def handle_blue_tile(screen, m, visited, current_cell, start_cell,
                     mode, return_cells, font,
                     black_tiles, silver_tiles, blue_tiles, red_zones,
                     victims, checkpoint, score, kits_left, lop_count):
    """
    Robot is on a blue puddle tile → must stop for BLUE_STOP_TIME seconds.
    Draws a countdown on screen while waiting.
    Returns False if window was closed during the wait.
    """
    print(f"  [BLUE TILE] Puddle! Stopping for {BLUE_STOP_TIME}s at {current_cell}")

    start_time = time.time()
    while time.time() - start_time < BLUE_STOP_TIME:
        elapsed   = time.time() - start_time
        remaining = BLUE_STOP_TIME - elapsed

        # Draw the maze with a countdown message
        draw_maze(screen, m, visited, current_cell, start_cell,
                  f"BLUE TILE – waiting {remaining:.1f}s", return_cells, font,
                  black_tiles, silver_tiles, blue_tiles, red_zones,
                  victims, checkpoint, score, kits_left, lop_count,
                  False, None)

        time.sleep(0.1)
        if not handle_events():
            return False

    return True


def handle_victim(screen, m, visited, current_cell, start_cell,
                  mode, return_cells, font,
                  black_tiles, silver_tiles, blue_tiles, red_zones,
                  victims, checkpoint, score, kits_left, lop_count):
    """
    Robot detected a victim on the current cell wall.
    - Marks victim as found
    - Blinks LED for VICTIM_BLINK_TIME seconds (ON 0.5s / OFF 0.5s)
    - Delivers rescue kits
    - Adds score
    Returns (score, kits_left, window_still_open)
    """
    victim = victims[current_cell]

    if victim['found']:
        return score, kits_left, True   # already handled

    victim['found']    = True
    victim['reported'] = True

    score     += SCORE_VICTIM_FOUND
    kits_needed = victim['kits']
    kits_delivered = min(kits_needed, kits_left)
    kits_left -= kits_delivered

    # Score kits based on victim type
    if victim['type'] in ('H', 'Red'):
        score += kits_delivered * SCORE_KIT_HARMED
    elif victim['type'] in ('S', 'Yellow'):
        score += kits_delivered * SCORE_KIT_STABLE

    print(f"  [VICTIM] Found {victim['type']} victim at {current_cell}. "
          f"Delivered {kits_delivered} kits. Score: {score}")

    # Blink for VICTIM_BLINK_TIME seconds
    blink_start = time.time()
    blink_on    = True

    while time.time() - blink_start < VICTIM_BLINK_TIME:
        elapsed   = time.time() - blink_start
        remaining = VICTIM_BLINK_TIME - elapsed

        # Toggle blink state every BLINK_INTERVAL seconds
        blink_on = (int(elapsed / BLINK_INTERVAL) % 2 == 0)

        draw_maze(screen, m, visited, current_cell, start_cell,
                  f"VICTIM FOUND – blinking {remaining:.1f}s", return_cells, font,
                  black_tiles, silver_tiles, blue_tiles, red_zones,
                  victims, checkpoint, score, kits_left, lop_count,
                  blink_on, current_cell)

        time.sleep(0.05)
        if not handle_events():
            return score, kits_left, False

    return score, kits_left, True


def handle_lop(current_cell, checkpoint, dfs_stack,
               visited, score, lop_count):
    """
    Lack of Progress: robot is penalised and restarted
    from the last checkpoint.
    Clears the DFS stack so exploration restarts from checkpoint.
    Returns updated score, lop_count, new current_cell, cleared stack.
    """
    lop_count += 1
    score     += SCORE_LOP
    print(f"  [LoP #{lop_count}] Restarting from checkpoint {checkpoint}. "
          f"Score: {score}")

    # Teleport back to checkpoint (in real life: human carries robot)
    current_cell = checkpoint

    # Clear DFS stack – robot must re-explore from here
    dfs_stack.clear()

    return score, lop_count, current_cell, dfs_stack


# ============================================================
# SECTION 5 – Main simulation
# ============================================================

def run_simulation():

    # -- Build maze --
    print("Building maze...")
    m = maze(MAZE_ROWS, MAZE_COLS)
    m.CreateMaze(loopPercent=LOOP_PERCENT)
    print("Maze ready.")

    # -- Place special tiles --
    start_cell = (1, 1)
    (black_tiles, silver_tiles,
     blue_tiles, red_zones, victims) = place_special_tiles(m, start_cell)

    print(f"Black tiles   : {sorted(black_tiles)}")
    print(f"Silver tiles  : {sorted(silver_tiles)}")
    print(f"Blue tiles    : {sorted(blue_tiles)}")
    print(f"Red zones     : {sorted(red_zones)}")
    print(f"Victims       : {list(victims.keys())}")

    # -- pygame setup --
    pygame.init()

    window_width  = MAZE_COLS * CELL_SIZE + 2 * MARGIN
    window_height = MAZE_ROWS * CELL_SIZE + 2 * MARGIN + 90

    screen = pygame.display.set_mode((window_width, window_height))
    pygame.display.set_caption("RoboCup Rescue Maze – Competition Simulation")
    font = pygame.font.SysFont("Arial", 13)

    # -- Robot state --
    current_cell       = start_cell
    checkpoint         = start_cell   # last reached checkpoint
    visited            = set()
    visited.add(current_cell)
    visited_checkpoints = set()

    dfs_stack  = []
    return_cells = set()
    mode       = "exploring"
    running    = True

    # -- Scoring state --
    score      = 0
    kits_left  = MAX_KITS
    lop_count  = 0

    print(f"\n=== Simulation Started at {start_cell} ===\n")

    # --------------------------------------------------------
    # Main DFS loop
    # --------------------------------------------------------
    while running:

        if not handle_events():
            running = False
            break

        # -- Check the tile the robot just landed on --

        # BLACK TILE → Lack of Progress
        if current_cell in black_tiles:
            print(f"  [BLACK TILE] Robot fell into hole at {current_cell}!")
            score += SCORE_BLACK_TILE
            score, lop_count, current_cell, dfs_stack = handle_lop(
                current_cell, checkpoint, dfs_stack, visited, score, lop_count)
            running = redraw_and_wait(
                screen, m, visited, current_cell, start_cell,
                "LoP – black tile", return_cells, font,
                black_tiles, silver_tiles, blue_tiles, red_zones,
                victims, checkpoint, score, kits_left, lop_count,
                False, None, STEP_DELAY)
            continue

        # SILVER TILE → checkpoint
        if current_cell in silver_tiles:
            score, checkpoint = handle_silver_tile(
                current_cell, visited_checkpoints, score)

        # BLUE TILE → stop for 5 seconds
        if current_cell in blue_tiles:
            running = handle_blue_tile(
                screen, m, visited, current_cell, start_cell,
                mode, return_cells, font,
                black_tiles, silver_tiles, blue_tiles, red_zones,
                victims, checkpoint, score, kits_left, lop_count)
            if not running:
                break

        # VICTIM → blink and deliver kits
        if current_cell in victims and not victims[current_cell]['found']:
            score, kits_left, running = handle_victim(
                screen, m, visited, current_cell, start_cell,
                mode, return_cells, font,
                black_tiles, silver_tiles, blue_tiles, red_zones,
                victims, checkpoint, score, kits_left, lop_count)
            if not running:
                break

        # RED ZONE → just print a warning (robot chooses to enter)
        if current_cell in red_zones:
            print(f"  [RED ZONE] Entering dangerous zone at {current_cell}!")

        # -- Read walls --
        walls = m.maze_map[current_cell]

        # -- Find unvisited open neighbors (skip black tiles) --
        unvisited = []
        for direction in ['N', 'E', 'S', 'W']:
            if walls[direction]:
                neighbor = get_neighbor(current_cell, direction)
                if neighbor not in visited and neighbor not in black_tiles:
                    unvisited.append(direction)

        # -- DFS decision --
        if unvisited:
            chosen    = unvisited[0]
            next_cell = get_neighbor(current_cell, chosen)

            dfs_stack.append(chosen)
            current_cell = next_cell
            visited.add(current_cell)
            mode = "exploring"

            print(f"At {current_cell} | going {chosen}")

        else:
            # Backtrack
            if not dfs_stack:
                print("\n=== Exploration complete! ===")
                mode = "done"
                draw_maze(screen, m, visited, current_cell, start_cell,
                          mode, return_cells, font,
                          black_tiles, silver_tiles, blue_tiles, red_zones,
                          victims, checkpoint, score, kits_left, lop_count,
                          False, None)
                pygame.display.flip()
                time.sleep(1.0)
                break

            arrival_dir   = dfs_stack.pop()
            back_dir      = get_opposite(arrival_dir)
            current_cell  = get_neighbor(current_cell, back_dir)
            mode          = "backtracking"

            print(f"  Backtracking {back_dir} to {current_cell}")

        running = redraw_and_wait(
            screen, m, visited, current_cell, start_cell,
            mode, return_cells, font,
            black_tiles, silver_tiles, blue_tiles, red_zones,
            victims, checkpoint, score, kits_left, lop_count,
            False, None, STEP_DELAY)

    # --------------------------------------------------------
    # BFS return to start
    # --------------------------------------------------------
    if running and mode in ("done", "backtracking", "exploring"):

        print(f"\n=== Returning to start via BFS shortest path ===")

        return_path  = bfs_shortest_path(m.maze_map, current_cell, start_cell)
        return_cells = set()

        temp = current_cell
        for d in return_path:
            temp = get_neighbor(temp, d)
            return_cells.add(temp)

        mode = "returning"

        for direction in return_path:
            if not handle_events():
                running = False
                break

            current_cell = get_neighbor(current_cell, direction)
            print(f"  Returning: {direction} → {current_cell}")

            running = redraw_and_wait(
                screen, m, visited, current_cell, start_cell,
                mode, return_cells, font,
                black_tiles, silver_tiles, blue_tiles, red_zones,
                victims, checkpoint, score, kits_left, lop_count,
                False, None, STEP_DELAY)

        if current_cell == start_cell:
            score += SCORE_RETURN_TO_START
            print(f"  [EXIT BONUS] Returned to start! +{SCORE_RETURN_TO_START} points.")

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------
    found_victims = [c for c in victims if victims[c]['found']]

    print("\n========================================")
    print("           MISSION COMPLETE             ")
    print("========================================")
    print(f"  Final score      : {score}")
    print(f"  Cells explored   : {len(visited)}")
    print(f"  Victims found    : {len(found_victims)} / {VICTIM_COUNT}")
    print(f"  Kits used        : {MAX_KITS - kits_left} / {MAX_KITS}")
    print(f"  Lack of Progress : {lop_count}")
    print("========================================")

    if running:
        mode = "mission complete"
        draw_maze(screen, m, visited, current_cell, start_cell,
                  mode, return_cells, font,
                  black_tiles, silver_tiles, blue_tiles, red_zones,
                  victims, checkpoint, score, kits_left, lop_count,
                  False, None)

        done_font = pygame.font.SysFont("Arial", 20, bold=True)
        msg  = done_font.render(
            f"Mission Complete!  Final Score: {score}  –  Close to exit",
            True, (30, 30, 30))
        msg_x = (window_width  - msg.get_width())  // 2
        msg_y = (window_height - msg.get_height()) // 2
        screen.blit(msg, (msg_x, msg_y))
        pygame.display.flip()

        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    waiting = False

    pygame.quit()
    print("Window closed.")


if __name__ == '__main__':
    run_simulation()