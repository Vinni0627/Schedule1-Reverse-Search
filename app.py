import streamlit as st
from reverse import load_items, find_item_sequence, BASE_PRICES, EFFECT_MULTIPLIERS, INGREDIENT_PRICES
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
Find the sequence of items needed to achieve your desired effects
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
    st.markdown("Select the effects you want to achieve:")
    selected_effects = st.multiselect(
        "Choose effects",
        sorted(list(all_effects)),
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
    
    # Add depth limit control
    st.header("Search Settings")
    min_depth = 1
    max_fib = 15
    depth_limit = st.slider(
        "Maximum step length",
        min_value=min_depth,
        max_value=max_fib,
        value=min_depth,
        help=f"Higher values may find better solutions but take longer to search. Next Fibonacci number: {max_fib}"
    )

# Main content
if selected_effects:
    st.subheader("Desired Effects")
    for effect in selected_effects:
        st.markdown(f"- {effect}")
    
    # Show warning for complex searches
    if len(selected_effects) >= 4:
        st.warning("⚠️ Searching for 4 or more effects may take up to 2 minutes. The search will automatically stop after 2 minutes.")
    elif len(selected_effects) >= 3:
        st.warning("⚠️ Searching for 3 effects may take up to 30 seconds. The search will automatically stop after 30 seconds.")
    
    if st.button("Find Recipe"):
        # Create progress elements
        progress_bar = st.progress(0)
        status_text = st.empty()
        depth_text = st.empty()
        states_text = st.empty()
        limit_text = st.empty()
        time_text = st.empty()
        
        # Define progress callback
        def update_progress(depth, states, max_depth, elapsed_time):
            # Update progress bar (using depth as a rough estimate)
            progress = min(depth / max_depth, 1.0)
            progress_bar.progress(progress)
            
            # Update status text
            status_text.text("Searching for solution...")
            depth_text.text(f"Current depth: {depth}")
            states_text.text(f"States explored: {states:,}")
            limit_text.text(f"Maximum depth: {max_depth}")
            time_text.text(f"Time elapsed: {elapsed_time:.1f}s")
        
        with st.spinner("Searching for the best sequence..."):
            optimize_for = "cost" if optimization_mode == "Cost (Cheapest Recipe)" else "profit"
            timeout = 120 if len(selected_effects) >= 4 else 30
            
            # Create a container for the search results
            result_container = st.empty()
            
            # Run the search
            sequence, final, cost, profit = find_item_sequence(
                selected_effects, 
                items_data, 
                optimize_for,
                progress_callback=update_progress,
                timeout=timeout,
                max_depth=depth_limit
            )

            # Clear progress elements
            progress_bar.empty()
            status_text.empty()
            depth_text.empty()
            states_text.empty()
            limit_text.empty()
            time_text.empty()

            # Display results in the container
            with result_container.container():
                if sequence:
                    st.success("Found a solution!")
                    
                    # Recipe details
                    st.subheader("Recipe Steps")
                    total_cost = 0
                    for i, item in enumerate(sequence, 1):
                        item_cost = INGREDIENT_PRICES[item]
                        total_cost += item_cost
                        st.markdown(f"{i}. **{item}** (${item_cost})")
                        # Show item details
                        with st.expander(f"Details for {item}"):
                            st.markdown(f"**Base Effect:** {items_data[item]['base_effect']}")
                            if items_data[item]['replacements']:
                                st.markdown("**Replacements:**")
                                for old_e, new_e in items_data[item]['replacements']:
                                    st.markdown(f"- {old_e} → {new_e}")
                    
                    # Cost and profit information
                    st.subheader("Cost Analysis")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Ingredient Cost", f"${total_cost}")
                    with col2:
                        final_price = BASE_PRICES[base_product] * (1 + sum(EFFECT_MULTIPLIERS.get(effect, 0) for effect in final))
                        st.metric("Final Product Price", f"${final_price:.2f}")
                        st.metric("Potential Profit", f"${final_price - total_cost:.2f}")
                    with col3:
                        st.metric("Final Product Price with 1.6x Rule", f"${int(final_price*1.6):.2f}")
                        st.metric("Potential Profit with 1.6x Rule", f"${int((final_price - total_cost)*1.6):.2f}")

                    # Final effects
                    st.subheader("Final Effects")
                    for effect in sorted(final):
                        multiplier = EFFECT_MULTIPLIERS.get(effect, 0)
                        st.markdown(f"- {effect} (Multiplier: {multiplier:.2f})")
                else:
                    st.error("No solution found within the time limit. Try increasing the maximum search depth or check if the desired effects are achievable.")
else:
    st.info("Please select at least one effect from the sidebar.")