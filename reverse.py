import json
from collections import deque
import time
import concurrent.futures
from threading import Lock
from queue import Queue

# Pricing information
BASE_PRICES = {
    "OG Kush": 30,
    "Sour Diesel": 35,
    "Green Crack": 40,
    "Grandaddy Purple": 45, 
    "Poor Quality Meth": 60,
    "Meth": 80,
    "High-Quality Meth": 110,
    "Cocaine": 150
}

EFFECT_MULTIPLIERS = {
    "Anti-Gravity": 0.54,
    "Athletic": 0.32,
    "Balding": 0.30,
    "Bright-Eyed": 0.40,
    "Calming": 0.10,
    "Calorie-Dense": 0.28,
    "Cyclopean": 0.56,
    "Disorienting": 0.00,
    "Electrifying": 0.50,
    "Energizing": 0.22,
    "Euphoric": 0.18,
    "Explosive": 0.00,
    "Focused": 0.16,
    "Foggy": 0.36,
    "Gingeritis": 0.20,
    "Glowing": 0.48,
    "Jennerising": 0.42,
    "Laxative": 0.00,
    "Long Faced": 0.52,
    "Munchies": 0.12,
    "Paranoia": 0.00,
    "Refreshing": 0.14,
    "Schizophrenia": 0.00,
    "Sedating": 0.26,
    "Seizure-Inducing": 0.00,
    "Shrinking": 0.60,
    "Slippery": 0.34,
    "Smelly": 0.00,
    "Sneaky": 0.24,
    "Spicy": 0.38,
    "Thought-Provoking": 0.44,
    "Toxic": 0.00,
    "Tropic Thunder": 0.46,
    "Zombifying": 0.58
}

INGREDIENT_PRICES = {
    "Cuke": 2,
    "Banana": 2,
    "Paracetamol": 3,
    "Donut": 3,
    "Viagra": 4,
    "Mouth Wash": 4,
    "Flu Medicine": 5,
    "Gasoline": 5,
    "Energy Drink": 6,
    "Motor Oil": 6,
    "Mega Bean": 7,
    "Chili": 7,
    "Battery": 8,
    "Iodine": 8,
    "Addy": 9,
    "Horse Semen": 9
}

class SearchState:
    def __init__(self):
        self.best_solution = None
        self.best_value = float('inf')
        self.visited = set()
        self.lock = Lock()
        self.start_time = time.time()
        self.progress_queue = Queue()

def load_items(json_file):
    """
    Load the item data from a JSON file (with base_effect, replacements, etc.).
    """
    with open(json_file, "r") as f:
        data = json.load(f)
    return data

def apply_item(current_effects, item_name, items_data):
    """
    current_effects: a set of effect strings
    item_name: the name of the item to apply (must be a key in items_data)
    items_data: the dictionary loaded from the JSON

    Returns a new set of effects after applying the item.
    """
    new_effects = set(current_effects)

    # Add the item's base effect
    base_effect = items_data[item_name]["base_effect"]
    
    # Determine if the base effect was already present.
    base_already_present = base_effect in new_effects
    
    # Add the base effect (if not already there).
    new_effects.add(base_effect)

    # Apply the replacements.
    for old_e, new_e in items_data[item_name]["replacements"]:
        # If the base effect was just added and this replacement targets it, skip.
        if not base_already_present and old_e == base_effect:
            continue
        if old_e in new_effects:
            new_effects.remove(old_e)
            new_effects.add(new_e)

    return new_effects

def calculate_recipe_cost(sequence):
    """
    Calculate the total cost of a recipe sequence.
    """
    return sum(INGREDIENT_PRICES[item] for item in sequence)

def calculate_final_price(base_product, effects):
    """
    Calculate the final price of a product with given effects.
    """
    total_multiplier = sum(EFFECT_MULTIPLIERS.get(effect, 0) for effect in effects)
    return BASE_PRICES[base_product] * (1 + total_multiplier)

def find_item_sequence_thread(required_effects, items_data, optimize_for, start_state, min_depth, max_depth, timeout, allowed_ingredients=None):
    required_set = set(required_effects)
    queue = deque([(frozenset(), [], 0)])
    states_explored = 0
    current_depth = 0

    while queue:
        # Check timeout
        if time.time() - start_state.start_time > timeout:
            return

        current_effects_fset, path, cost = queue.popleft()
        current_effects = set(current_effects_fset)
        
        # Update progress
        if len(path) > current_depth:
            current_depth = len(path)
            start_state.progress_queue.put((
                current_depth,
                states_explored,
                max_depth,
                time.time() - start_state.start_time
            ))
        
        states_explored += 1
        if states_explored % 1000 == 0:
            start_state.progress_queue.put((
                current_depth,
                states_explored,
                max_depth,
                time.time() - start_state.start_time
            ))

        # Accept as solution if the required effects are met and we're at or above min_depth
        # (If no effects are selected, require that the recipe contains at least one item.)
        if required_set.issubset(current_effects) and (required_set or path) and len(path) >= min_depth:
            # Calculate profit for each base product.
            profits = {
                product: calculate_final_price(product, current_effects) - cost
                for product in BASE_PRICES
            }
            best_product = max(profits.items(), key=lambda x: x[1])[0]
            profit = profits[best_product]
            
            # Update best solution based on optimization criteria.
            with start_state.lock:
                if optimize_for == "cost" and cost < start_state.best_value:
                    start_state.best_solution = (path, current_effects, cost, profit)
                    start_state.best_value = cost
                elif optimize_for == "profit" and profit > start_state.best_value:
                    start_state.best_solution = (path, current_effects, cost, profit)
                    start_state.best_value = profit
            
            # In cost mode, prune further exploration since any extension will only increase cost.
            # For profit mode, we want to continue expanding to potentially reach a higher profit.
            if optimize_for == "cost":
                continue

        # Skip if we've exceeded max depth.
        if len(path) >= max_depth:
            continue

        # Otherwise, expand by applying each allowed item.
        for item_name in allowed_ingredients:
            next_effects = apply_item(current_effects, item_name, items_data)
            next_fset = frozenset(next_effects)
            
            with start_state.lock:
                if next_fset not in start_state.visited:
                    start_state.visited.add(next_fset)
                    next_cost = cost + INGREDIENT_PRICES[item_name]
                    queue.append((next_fset, path + [item_name], next_cost))

def find_item_sequence(required_effects, items_data, optimize_for="cost", progress_callback=None, timeout=30, min_depth=1, max_depth=None, allowed_ingredients=None):
    """
    Attempts to find a sequence of items that produces all 'required_effects'.
    Can optimize for cost (cheapest) or profit (most profitable).

    Args:
        required_effects: List of effects to achieve (if empty, any non-empty sequence is considered)
        items_data: Dictionary of item data
        optimize_for: "cost" or "profit"
        progress_callback: Function to call with progress updates (current_depth, states_explored, max_depth, elapsed_time)
        timeout: Maximum time in seconds to search for a solution
        min_depth: Minimum number of mixing steps required
        max_depth: Maximum depth to search
        allowed_ingredients: List of ingredient names to allow in the recipe. If None, all ingredients are allowed.

    Returns: (list_of_items_used, final_effects_set, cost, profit) or (None, None, None, None) if no solution.
    """

    # Create shared state
    search_state = SearchState()
    search_state.best_value = float('inf') if optimize_for == "cost" else float('-inf')
    
    # If no ingredients are specified, allow all ingredients
    if allowed_ingredients is None:
        allowed_ingredients = list(items_data.keys())

    # Determine number of threads based on available CPU cores
    num_threads = min(2, len(items_data))

    # Start threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for _ in range(num_threads):
            future = executor.submit(
                find_item_sequence_thread,
                required_effects,
                items_data,
                optimize_for,
                search_state,
                min_depth,
                max_depth,
                timeout,
                allowed_ingredients
            )
            futures.append(future)

        # Process progress updates
        while not all(f.done() for f in futures):
            try:
                progress = search_state.progress_queue.get(timeout=0.1)
                if progress_callback:
                    progress_callback(*progress)
            except:
                pass

        # Wait for threads to finish or timeout
        try:
            concurrent.futures.wait(futures, timeout=timeout)
        except concurrent.futures.TimeoutError:
            pass

    return search_state.best_solution if search_state.best_solution else (None, None, None, None)

def main():
    # Load items from the JSON file
    items_data = load_items("interactions.json")

    # Define the desired effects.
    # When empty, the search disregards effect requirements and optimizes solely for cost or profit.
    desired_effects = []  # Use an empty list to disregard effects requirement
    
    # Find the sequence of items needed (using a maximum step length of 15 here)
    sequence, final, cost, profit = find_item_sequence(desired_effects, items_data, optimize_for="cost", max_depth=15)

    if sequence:
        print("\nTo achieve the following effects:")
        if desired_effects:
            for effect in desired_effects:
                print(f"- {effect}")
        else:
            print("No specific effects required.")

        print("\nUse these items in order:")
        for i, item in enumerate(sequence, 1):
            print(f"{i}. {item} (${INGREDIENT_PRICES[item]})")
        
        print(f"\nTotal ingredient cost: ${cost}")
        print("\nThis will give you these final effects:")
        for effect in sorted(final):
            print(f"- {effect}")
        
        print("\nPotential profits with each base product:")
        for product in BASE_PRICES:
            final_price = calculate_final_price(product, final)
            print(f"- {product}: ${final_price} (Profit: ${final_price - cost})")
    else:
        print("\nCould not find a sequence of items that produces the desired outcome.")
        print("Try increasing the maximum mixing step length or check if the desired effects are achievable.")

if __name__ == "__main__":
    main()
