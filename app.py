import streamlit as st
import streamlit_nested_layout

from reverse import load_items, find_item_sequence, BASE_PRICES, EFFECT_MULTIPLIERS, INGREDIENT_PRICES, apply_item
import time

# Set page config
st.set_page_config(
    page_title="Schedule 1 Reverse Recipe Search",
    page_icon="",
    layout="wide"
)

# Title and description
st.title("Schedule 1 Reverse Recipe Search")
st.markdown("""
Find the sequence of items needed to achieve your requirements.
""")

# Load items data
@st.cache_data
def load_items_data():
    return load_items("interactions.json")

items_data = load_items_data()

# Get all possible effects
all_effects = set()
for item_data in items_data.values():
    all_effects.add(item_data["base_effect"])
    for old_e, new_e in item_data["replacements"]:
        all_effects.add(old_e)
        all_effects.add(new_e)

# Sidebar with available effects and optimization options
with st.sidebar:
    st.header("Available Effects")
    st.markdown("Select the effects you want to achieve. Leave empty to disregard effect requirements:")
    selected_effects = st.multiselect(
        "Choose effects",
        sorted(list(all_effects)),
        default=[]
    )

    st.header("Available Ingredients")
    st.markdown("Select specific ingredients to use. Leave empty to allow all ingredients:")
    selected_ingredients = st.multiselect(
        "Choose ingredients",
        sorted(list(items_data.keys())),
        default=[]
    )

    st.header("Optimization")
    optimization_mode = st.radio(
        "Optimize for:",
        ["Cost (Cheapest Recipe)", "Profit (Most Profitable)"]
    )

    st.header("Base Product")
    base_product = st.selectbox(
        "Select base product for profit calculation:",
        list(BASE_PRICES.keys())
    )

    st.header("Search Settings")
    min_depth = 1
    max_depth = 15
    depth_range = st.slider(
        "Mixing step range",
        min_value=min_depth,
        max_value=max_depth,
        value=(min_depth, max_depth),
        help="Select the minimum and maximum number of mixing steps. Higher values may find better solutions but take longer to search."
    )
    min_steps, max_steps = depth_range

# Main content header
if selected_effects:
    st.subheader("Desired Effects")
    for effect in selected_effects:
        st.markdown(f"- {effect}")
else:
    st.info("No specific effects selected. The search will optimize based solely on cost or profit.")
    
if selected_ingredients:
    st.subheader("Selected Ingredients")
    for ingredient in selected_ingredients:
        st.markdown(f"- {ingredient}")
else:
    st.info("No specific ingredients selected. The search will allow all ingredients.")

if st.button("Find Recipe"):
    # Progress display
    progress_bar = st.progress(0)
    status_text = st.empty()
    depth_text = st.empty()
    states_text = st.empty()
    limit_text = st.empty()
    time_text = st.empty()

    def update_progress(depth, states, max_depth, elapsed_time):
        progress = min(depth / max_depth, 1.0)
        progress_bar.progress(progress)
        status_text.text("Searching for solution...")
        depth_text.text(f"Current mixing steps: {depth}")
        states_text.text(f"Recipes explored: {states:,}")
        limit_text.text(f"Maximum mixing steps: {max_depth}")
        time_text.text(f"Time elapsed: {elapsed_time:.1f}s")

    with st.spinner("Searching for the best sequence..."):
        optimize_for = "cost" if optimization_mode == "Cost (Cheapest Recipe)" else "profit"
        # Set timeout based on number of selected effects (if any)
        timeout = 600 if len(selected_effects) >= 8 else (300 if len(selected_effects) >= 6 else (120 if len(selected_effects) >= 4 else 30))
        result_container = st.empty()

        sequence, final, cost, profit = find_item_sequence(
            selected_effects,
            items_data,
            optimize_for,
            progress_callback=update_progress,
            timeout=timeout,
            min_depth=min_steps,
            max_depth=max_steps,
            allowed_ingredients=selected_ingredients if selected_ingredients else None
        )

        # Clear progress display
        progress_bar.empty()
        status_text.empty()
        depth_text.empty()
        states_text.empty()
        limit_text.empty()
        time_text.empty()

        # Display results
        with result_container.container():
            if sequence:
                st.success("Found a solution!")

                intermediate_effects = []
                current_effects = set()
                for item in sequence:
                    current_effects = apply_item(current_effects, item, items_data)
                    intermediate_effects.append(current_effects.copy())

                st.subheader("Recipe Steps")
                total_cost = 0
                for i, item in enumerate(sequence, 1):
                    item_cost = INGREDIENT_PRICES[item]
                    total_cost += item_cost
                    st.markdown(f"{i}. **{item}** (${item_cost})")

                    with st.expander(f"Details for {item}"):
                        current_step_effects = intermediate_effects[i - 1]
                        st.markdown("**Current Recipe Effects:**")
                        for effect in sorted(current_step_effects):
                            st.markdown(f"- {effect}")

                        st.markdown(f"**Base Effect:** {items_data[item]['base_effect']}")

                        if items_data[item]['replacements']:
                            with st.expander(f"**All {item} Effect Replacements:**"):
                                for old_e, new_e in items_data[item]['replacements']:
                                    st.markdown(f"- {old_e} → {new_e}")

                st.subheader("Cost Analysis")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Ingredient Cost", f"${total_cost}")
                with col2:
                    final_price = BASE_PRICES[base_product] * (1 + sum(EFFECT_MULTIPLIERS.get(effect, 0) for effect in final))
                    st.metric("Final Product Price", f"${int(final_price)}")
                    st.metric("Potential Profit", f"${int(final_price - total_cost)}")
                with col3:
                    st.metric("Final Product Price with 1.6x Rule", f"${int(final_price*1.6)}")
                    st.metric("Potential Profit with 1.6x Rule", f"${int(final_price*1.6) - total_cost}")

                st.subheader("Final Effects")
                for effect in sorted(final):
                    multiplier = EFFECT_MULTIPLIERS.get(effect, 0)
                    st.markdown(f"- {effect} (Multiplier: {multiplier:.2f})")
            else:
                st.error("No solution found within the time limit. Try increasing the maximum step length or check if the desired effects are achievable.")
