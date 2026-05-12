import keyboard
import time
import random
import os
import sys

# Config
WIDTH, HEIGHT = 60, 20
SPEED = 0.1  # seconds per step (lower = faster)

# ASCII Symbols
SNAKE_HEAD = 'O'
SNAKE_BODY = 'o'
FOOD_CHAR = '*'
EMPTY = ' '
HORZ = '-'
VERT = '|'
TOP_LEFT = '+'
TOP_RIGHT = '+'
BOTTOM_LEFT = '+'
BOTTOM_RIGHT = '+'


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def init_game():
    # Snake starts at center, length 3, moving right
    snake = [(WIDTH // 2, HEIGHT // 2),
             (WIDTH // 2 - 1, HEIGHT // 2),
             (WIDTH // 2 - 2, HEIGHT // 2)]
    direction = (1, 0)  # (dx, dy): right
    food = generate_food(snake)
    score = 0
    return snake, direction, food, score


def generate_food(snake):
    while True:
        x = random.randint(0, WIDTH - 1)
        y = random.randint(0, HEIGHT - 1)
        if (x, y) not in snake:
            return (x, y)


def draw(snake, food, score):
    # Build frame
    frame = [[EMPTY] * WIDTH for _ in range(HEIGHT)]
    
    # Draw snake
    for i, (x, y) in enumerate(snake):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            frame[y][x] = SNAKE_HEAD if i == 0 else SNAKE_BODY
    
    # Draw food
    fx, fy = food
    if 0 <= fx < WIDTH and 0 <= fy < HEIGHT:
        frame[fy][fx] = FOOD_CHAR
    
    # Print top border
    print(TOP_LEFT + HORZ * WIDTH + TOP_RIGHT)
    # Print rows
    for row in frame:
        print(VERT + ''.join(row) + VERT)
    # Print bottom border & score
    print(BOTTOM_LEFT + HORZ * WIDTH + BOTTOM_RIGHT)
    print(f'Score: {score} | Use Arrow Keys. Q=quit, SPACE=pause')


def update(snake, direction, food, score):
    head_x, head_y = snake[0]
    dx, dy = direction
    new_head = (head_x + dx, head_y + dy)
    
    # Wall collision
    x, y = new_head
    if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
        return None, None, food, score  # game over
    
    # Self collision
    if new_head in snake:
        return None, None, food, score  # game over
    
    # Move snake
    new_snake = [new_head] + snake
    
    # Check food
    if new_head == food:
        score += 10
        food = generate_food(new_snake)
    else:
        new_snake.pop()  # remove tail
    
    return new_snake, direction, food, score


def main():
    print("Terminal Snake Game -- Press any arrow key to start.")
    time.sleep(1.5)
    
    # Initial state
    snake, direction, food, score = init_game()
    paused = False
    
    # Key event handlers
    def on_up(e):
        nonlocal direction
        if not paused and direction != (0, 1):  # not down
            direction = (0, -1)
    
    def on_down(e):
        nonlocal direction
        if not paused and direction != (0, -1):  # not up
            direction = (0, 1)
    
    def on_left(e):
        nonlocal direction
        if not paused and direction != (1, 0):  # not right
            direction = (-1, 0)
    
    def on_right(e):
        nonlocal direction
        if not paused and direction != (-1, 0):  # not left
            direction = (1, 0)
    
    def on_quit(e):
        if e.name == 'q':
            sys.exit(0)
    
    def on_pause(e):
        nonlocal paused
        if e.name == 'space':
            paused = not paused
    
    keyboard.on_press_key('up', on_up)
    keyboard.on_press_key('down', on_down)
    keyboard.on_press_key('left', on_left)
    keyboard.on_press_key('right', on_right)
    keyboard.on_press(on_quit)
    keyboard.on_press_key('space', on_pause)
    
    try:
        while True:
            clear_screen()
            draw(snake, food, score)
            
            if not paused:
                snake, direction, food, score = update(snake, direction, food, score)
                if snake is None:
                    print('\nGAME OVER! Final Score:', score)
                    print('Press Q to exit.')
                    while True:
                        if keyboard.is_pressed('q'):
                            sys.exit(0)
                        time.sleep(0.1)
            
            time.sleep(SPEED)
    
    finally:
        keyboard.unhook_all()


if __name__ == '__main__':
    main()
