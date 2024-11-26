import machine
from machine import Pin
import time
import neopixel
import random

W = 32
H = 8
RGB_DATA_PIN = 22

BRIGHTNESS = 0.05
MODE = "Off"
FRAME_DELAY = 10
USE_ONLY_STRONG_COLORS = True
DROP_STACK_COLORS = [(255, 0, 0), (0, 255, 0)]

STRONG_COLORS = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 255, 255),
    (255, 128, 0)
]

MODE_LIST = [
    "Off", 
    "Solid Color",
    "Solid Pattern",
    "Rainbow",
    "Single Color Chase",
    "Random All",
    "Random One", 
    "Raindrops", 
    "Twinkle", 
    "Fireflies", 
    "Drop and Stack",
    "Chase"
]

last_frame_time = 0
num_leds = W * H
sections = []
drop_stack_state = {"current_color_index": 0, "filled_rows": 0, "current_position": 0}

led_state = [(0, 0, 0) for _ in range(num_leds)]

selecting_sections = False
selected_section = 0
selection_changed = False
selected_pixel = 0

np = neopixel.NeoPixel(machine.Pin(RGB_DATA_PIN), num_leds)

buttons = {
    "b1": Pin(16, Pin.IN, Pin.PULL_UP),
    "b2": Pin(17, Pin.IN, Pin.PULL_UP),
    "b3": Pin(18, Pin.IN, Pin.PULL_UP),
    "b4": Pin(19, Pin.IN, Pin.PULL_UP)
}

leds = {
    "led1": Pin(20, Pin.OUT),
    "led2": Pin(21, Pin.OUT),
    "led3": Pin(26, Pin.OUT),
    "led4": Pin(27, Pin.OUT)
}
mode_index = 0

# Utility Functions
def apply_brightness(color):
    return tuple(int(c * BRIGHTNESS) for c in color)

def set_pixel(index, color):
    global led_state
    led_state[index] = color

def clear_frame():
    global led_state
    led_state = [(0, 0, 0) for _ in range(num_leds)]

def draw():
    for i, color in enumerate(led_state):
        np[i] = apply_brightness(color)
    np.write()

def add_section(start, end, mode="Off"):
    sections.append({
        "start": start,
        "end": end,
        "mode": mode,
        "frame_state": {
            "random_one": {"index": None},
            "twinkle": {"lights": [(0, 0, 0) for _ in range(end - start)]},
            "fireflies": {
                "lights": [{"color": (0, 0, 0), "phase": "off", "brightness": 0} for _ in range(end - start)],
                "active_indices": [],
            },
            "chase": {"index": 0},
            "rainbow": {"step": 0},
            "random_fade": {
                "target_colors": [random.choice(STRONG_COLORS) for _ in range(end - start)],
                "fade_steps": [0 for _ in range(end - start)],
            },
            "drop_stack": {
                "current_color_index": 0,
                "filled_rows": 0,
                "current_position": -1,
                "current_run_length": end - start,
            },
            "solid_color": (255, 255, 255),
            "solid_pattern": [(255, 0, 0), (255, 0, 0), (0, 255, 0), (0, 255, 0)],
        }
    })

def set_section_pixel(section, index, color):
    global led_state
    absolute_index = section["start"] + index
    if 0 <= absolute_index < num_leds:
        led_state[absolute_index] = color

def random_color():
    if USE_ONLY_STRONG_COLORS:
        return random.choice(STRONG_COLORS)
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

def wheel(pos):
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

def cycle_color(color):
    if color not in STRONG_COLORS:
        return STRONG_COLORS[0]
    strong_color_index = STRONG_COLORS.index(color)
    return STRONG_COLORS[(strong_color_index + 1) % len(STRONG_COLORS)]

# Frame Handlers
def frame_off():
    clear_frame()

def frame_fireflies_section(section):
    frame_state = section["frame_state"]["fireflies"]
    lights = frame_state["lights"]
    active_indices = frame_state["active_indices"]
    section_length = section["end"] - section["start"]

    for i in active_indices[:]:
        firefly = lights[i]
        if firefly["phase"] == "fade-in":
            firefly["brightness"] += 50
            if firefly["brightness"] >= 255:
                firefly["brightness"] = 255
                firefly["phase"] = "fade-out"
        elif firefly["phase"] == "fade-out":
            firefly["brightness"] -= 30
            if firefly["brightness"] <= 0:
                firefly["brightness"] = 0
                firefly["phase"] = "off"
                active_indices.remove(i)

        brightness = firefly["brightness"] / 255
        set_section_pixel(section, i, tuple(int(c * brightness) for c in firefly["color"]))

    max_active_fireflies = 3
    chance_new_firefly = 0.1

    if len(active_indices) < max_active_fireflies and random.random() < chance_new_firefly:
        new_index = random.randint(0, section_length - 1)
        if lights[new_index]["phase"] == "off":
            lights[new_index] = {
                "color": random_color(),
                "phase": "fade-in",
                "brightness": 0,
            }
            active_indices.append(new_index)

def frame_random_one_section(section):
    frame_state = section["frame_state"]["random_one"]
    section_length = section["end"] - section["start"]
    index = random.randint(0, section_length - 1)
    set_section_pixel(section, index, random_color())
    frame_state["index"] = index

def frame_twinkle_section(section):
    frame_state = section["frame_state"]["twinkle"]
    lights = frame_state["lights"]
    section_length = section["end"] - section["start"]

    index = random.randint(0, section_length - 1)
    lights[index] = random_color()

    for i in range(section_length):
        set_section_pixel(section, i, lights[i])
        lights[i] = tuple(max(c - 10, 0) for c in lights[i])

def frame_rainbow_section(section):
    frame_state = section["frame_state"]["rainbow"]
    step = frame_state["step"]
    section_length = section["end"] - section["start"]

    for i in range(section_length):
        pixel_index = (i * 256 // section_length) + step
        set_section_pixel(section, i, wheel(pixel_index & 255))
    frame_state["step"] = (step + 1) % 256

def frame_random_fade_section(section):
    frame_state = section["frame_state"]["random_fade"]
    target_colors = frame_state["target_colors"]
    fade_steps = frame_state["fade_steps"]
    section_length = section["end"] - section["start"]

    if all(led_state[section["start"] + i] == (0, 0, 0) for i in range(section_length)):
        for i in range(section_length):
            set_section_pixel(section, i, random_color())

    for _ in range(3):
        index = random.randint(0, section_length - 1)
        if fade_steps[index] == 0:
            target_colors[index] = random_color()
            fade_steps[index] = 20

    for i in range(section_length):
        if fade_steps[i] > 0:
            current_color = led_state[section["start"] + i]
            target_color = target_colors[i]
            fade_ratio = 1 - fade_steps[i] / 20

            new_color = tuple(
                int(current_color[j] + (target_color[j] - current_color[j]) * fade_ratio)
                for j in range(3)
            )
            set_section_pixel(section, i, new_color)

            fade_steps[i] -= 1
        else:
            set_section_pixel(section, i, target_colors[i])

def frame_drop_and_stack_section(section):
    state = section["frame_state"]["drop_stack"]
    section_length = section["end"] - section["start"]
    current_run_length = state.get("current_run_length", section_length)

    drop_color = DROP_STACK_COLORS[state["current_color_index"]]
    background_color = DROP_STACK_COLORS[state["current_color_index"] - 1] if state["current_color_index"] > 0 else DROP_STACK_COLORS[-1]

    current_position = state["current_position"]

    if current_position == -1:
        for i in range(section_length):
            set_section_pixel(section, i, background_color)
        state["current_position"] = section_length - 1
        state["current_run_length"] = section_length
        return

    if current_position < section_length - 1:
        set_section_pixel(section, current_position + 1, background_color)

    set_section_pixel(section, current_position, drop_color)

    if current_position == section_length - current_run_length:
        state["current_position"] = section_length - 1
        state["current_run_length"] -= 1

        if current_run_length == 1:
            state["current_color_index"] = (state["current_color_index"] + 1) % len(DROP_STACK_COLORS)
            state["current_position"] = -1
    else:
        state["current_position"] -= 1

def frame_solid_color_section(section):
    """Set the entire section to a solid color."""
    frame_state = section["frame_state"]
    color = frame_state.get("solid_color", (255, 255, 255))

    section_length = section["end"] - section["start"]
    for i in range(section_length):
        set_section_pixel(section, i, color)

def frame_solid_pattern_section(section):
    frame_state = section["frame_state"]
    pattern = frame_state.get("solid_pattern", [(255, 0, 0), (255, 0, 0), (0, 255, 0), (0, 255, 0)])

    section_length = section["end"] - section["start"]
    pattern_length = len(pattern)

    for i in range(section_length):
        set_section_pixel(section, i, pattern[i % pattern_length])

def frame_chase_section(section):
    frame_state = section["frame_state"]["chase"]
    section_length = section["end"] - section["start"]
    index = frame_state.get("index", 0)
    colors = STRONG_COLORS

    for i in range(section_length):
        set_section_pixel(section, i, (0, 0, 0))

    for i, color in enumerate(colors):
        pixel_index = (index + i) % section_length
        set_section_pixel(section, pixel_index, color)

    frame_state["index"] = (index + 1) % section_length

def frame_single_color_chase_section(section):
    frame_state = section["frame_state"]["chase"]
    section_length = section["end"] - section["start"]

    index = frame_state.get("index", 0)
    color_index = frame_state.get("color_index", 0)
    current_color = STRONG_COLORS[color_index]

    for i in range(section_length):
        set_section_pixel(section, i, (0, 0, 0))

    set_section_pixel(section, index, current_color)

    index = (index + 1) % section_length

    if index == 0:
        color_index = (color_index + 1) % len(STRONG_COLORS)

    frame_state["index"] = index
    frame_state["color_index"] = color_index

def frame_random_all_section(section):
    frame_state = section["frame_state"]
    section_length = section["end"] - section["start"]

    if "timer" not in frame_state:
        frame_state["timer"] = 0

    frame_state["timer"] += 1

    if frame_state["timer"] >= 200 // FRAME_DELAY:
        frame_state["timer"] = 0

        for i in range(section_length):
            set_section_pixel(section, i, random.choice(STRONG_COLORS))

# Drawing Functions
def apply_effects_to_sections():
    """Apply the current effect to each section."""
    for section in sections:
        mode = section["mode"]
        if mode == "Random Fade":
            frame_random_fade_section(section)
        elif mode == "Drop and Stack":
            frame_drop_and_stack_section(section)
        elif mode == "Fireflies":
            frame_fireflies_section(section)
        elif mode == "Random One":
            frame_random_one_section(section)
        elif mode == "Raindrops":
            frame_twinkle_section(section)
        elif mode == "Rainbow":
            frame_rainbow_section(section)
        elif mode == "Solid Color":
            frame_solid_color_section(section)
        elif mode == "Solid Pattern":
            frame_solid_pattern_section(section)
        elif mode == "Twinkle":
            frame_random_fade_section(section)
        elif mode == "Chase":
            frame_chase_section(section)
        elif mode == "Single Color Chase":
            frame_single_color_chase_section(section)
        elif mode == "Random All":
            frame_random_all_section(section)

def highlight_selected_section():
    """Highlight the currently selected section."""
    global selected_section
    for i, section in enumerate(sections):
        color = (0, 0, 0)
        if i == selected_section:
            color = (0, 0, 255)
        for j in range(section["start"], section["end"]):
            set_pixel(j, color)

# Input Handling
def handle_input():
    """Check button states and execute corresponding actions."""
    for name, button in buttons.items():
        if not button.value():
            leds[name.replace("b", "led")].value(1)
            button_actions[name]()
        else:
            leds[name.replace("b", "led")].value(0)

def cycle_mode(section):
    global sections
    current_mode = sections[section]["mode"]
    current_index = MODE_LIST.index(current_mode)
    new_index = (current_index + 1) % len(MODE_LIST)
    new_mode = MODE_LIST[new_index]
    sections[section]["mode"] = new_mode
    clear_frame()
    print("section "+ str(section) +" mode set to " + new_mode)

def cycle_section_selection():
    global selected_section, selection_changed
    selected_section = (selected_section + 1) % len(sections)
    selection_changed = True

def handle_b1():
    global selecting_sections
    selecting_sections = not selecting_sections
    clear_frame()
    time.sleep(0.25)

def handle_b2():
    if selecting_sections:
        cycle_section_selection()
    else:
        selected_section_mode = sections[selected_section]["mode"]
        if selected_section_mode == "Solid Color":
            sections[selected_section]["frame_state"]["solid_color"] = cycle_color(sections[selected_section]["frame_state"]["solid_color"])
        elif selected_section_mode == "Solid Pattern":
            current_pattern = sections[selected_section]["frame_state"]["solid_pattern"]
            new_pattern = [cycle_color(color) for color in current_pattern]
            sections[selected_section]["frame_state"]["solid_pattern"] = new_pattern
    time.sleep(0.25)

def handle_b3():
    if not selecting_sections:
        cycle_mode(selected_section)
    time.sleep(0.25)

def handle_b4():
    global selected_pixel, sections
    section_mode = sections[selected_section]["mode"]
    if section_mode == "Manual":
        selected_pixel = (selected_pixel + 1) % (sections[selected_section]["end"] - sections[selected_section]["start"])
    time.sleep(0.25)

button_actions = {
    "b1": handle_b1,
    "b2": handle_b2,
    "b3": handle_b3,
    "b4": handle_b4
}

frame_state = {
    "random_one": {"index": None},
    "twinkle": {"lights": [(0, 0, 0) for _ in range(num_leds)]},
    "fireflies": {
        "lights": [{"color": (0, 0, 0), "phase": "off", "brightness": 0} for _ in range(num_leds)],
        "active_indices": [],
    },
    "chase": {"index": 0},
    "rainbow": {"step": 0},
    "random_fade": {
        "target_colors": [random_color() for _ in range(num_leds)],
        "fade_steps": [0 for _ in range(num_leds)],
    }
}

# Main Loop
def main_loop():
    global MODE, last_frame_time, selection_changed
    while True:
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_frame_time) >= FRAME_DELAY:
            handle_input()

            if selecting_sections:
                if selection_changed:
                    selection_changed = False
                    clear_frame()
                    highlight_selected_section()
            else:
                apply_effects_to_sections()

            draw()
            last_frame_time = current_time

section_size = num_leds // 4
add_section(0, section_size, "Off")
add_section(section_size, section_size * 2, "Off")
add_section(section_size * 2, section_size * 3, "Off")
add_section(section_size * 3, num_leds, "Off")

main_loop()

# TODO: Store state info when modes are changed so we can resume after a power failure.
