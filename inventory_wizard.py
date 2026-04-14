"""
Astro Inventory Wizard - Phase 1: Core Setup
MVP Inventory Management System for Baylor Astro Teams
"""

import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pandas as pd

# ============================================================================
# PAGE CONFIG MUST BE FIRST
# ============================================================================
st.set_page_config(
    page_title="Astro Inventory Wizard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CONFIGURATION - SUPABASE CREDENTIALS
# ============================================================================
# Credentials are loaded from .streamlit/secrets.toml
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# Initialize Supabase client
@st.cache_resource
def init_supabase() -> Client:
    """Initialize and cache Supabase client"""
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except TypeError:
        # Fallback for older supabase versions
        from supabase import Client as SupabaseClient
        return SupabaseClient(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def check_login():
    """Check if user is logged in, redirect to login if not"""
    if 'user' not in st.session_state or not st.session_state.user:
        login_page()
        st.stop()

def login_page():
    """Display login/welcome page"""
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("🚀 Astro Inventory Wizard")
        st.markdown("### Welcome to Baylor Astro Inventory Management")
        st.markdown("---")
        
        # Login form
        with st.form("login_form"):
            name = st.text_input("Enter your name to continue", placeholder="John Doe")
            submit = st.form_submit_button("Enter App", width="stretch", type="primary")
            
            if submit:
                if name and name.strip():
                    st.session_state.user = name.strip()
                    st.rerun()
                else:
                    st.error("Please enter your name to continue")

def logout():
    """Clear session and return to login"""
    st.session_state.user = None
    st.rerun()

# ============================================================================
# PREDEFINED OPTIONS
# ============================================================================

CATEGORIES = ['Rocket Materials', 'Consumables', 'Raw Material', 'Fittings/Tubing', 'Other']
TEAMS = ['Shared', 'Rocketry', 'Liquid Propulsion']
LOCATIONS = ['Lab Shelf A', 'Lab Shelf B', 'Storage Room', 'Fridge', 'Other (specify)']

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def get_all_items():
    """Fetch all inventory items"""
    try:
        response = supabase.table('items').select('*').order('name').execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching items: {str(e)}")
        return []

def get_item_by_id(item_id):
    """Fetch single item by ID"""
    try:
        response = supabase.table('items').select('*').eq('id', item_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        st.error(f"Error fetching item: {str(e)}")
        return None

def add_item(item_data):
    """Add new item to inventory"""
    try:
        # Add metadata
        item_data['created_by'] = st.session_state.user
        item_data['created_at'] = datetime.now().isoformat()
        item_data['updated_at'] = datetime.now().isoformat()
        
        response = supabase.table('items').insert(item_data).execute()
        
        # Log transaction
        log_transaction(
            item_id=response.data[0]['id'],
            transaction_type='addition',
            quantity=item_data['quantity'],
            reason=f"Initial inventory entry"
        )
        
        return True, "Item added successfully!"
    except Exception as e:
        return False, f"Error adding item: {str(e)}"

def update_item(item_id, item_data):
    """Update existing item"""
    try:
        item_data['updated_at'] = datetime.now().isoformat()
        response = supabase.table('items').update(item_data).eq('id', item_id).execute()
        return True, "Item updated successfully!"
    except Exception as e:
        return False, f"Error updating item: {str(e)}"

def delete_item(item_id):
    """Delete an item"""
    try:
        # Check if item exists in any BOMs first (will be relevant in Phase 2)
        # For now, just delete
        supabase.table('items').delete().eq('id', item_id).execute()
        return True, "Item deleted successfully!"
    except Exception as e:
        return False, f"Error deleting item: {str(e)}"

def check_duplicate_item(name, exclude_id=None):
    """Check if item with similar name already exists using fuzzy matching"""
    try:
        # Get all items
        response = supabase.table('items').select('id, name').execute()
        items = response.data
        
        # Normalize the input name
        normalized_input = name.strip().lower()
        
        for item in items:
            # Skip if checking against the same item (for edits)
            if exclude_id and item['id'] == exclude_id:
                continue
            
            normalized_existing = item['name'].strip().lower()
            
            # Check for exact match
            if normalized_input == normalized_existing:
                return True, item['name']
            
            # Check for very similar names (contains or is contained)
            if normalized_input in normalized_existing or normalized_existing in normalized_input:
                if len(normalized_input) > 3 and len(normalized_existing) > 3:  # Avoid false positives with short names
                    return True, item['name']
        
        return False, None
    except Exception as e:
        st.error(f"Error checking for duplicates: {str(e)}")
        return False, None

def log_transaction(item_id, transaction_type, quantity, reason=None):
    """Log a transaction"""
    try:
        transaction_data = {
            'item_id': item_id,
            'transaction_type': transaction_type,
            'quantity': quantity,
            'reason': reason,
            'performed_by': st.session_state.user,
            'timestamp': datetime.now().isoformat()
        }
        supabase.table('transactions').insert(transaction_data).execute()
    except Exception as e:
        st.error(f"Error logging transaction: {str(e)}")

def consume_item(item_id, quantity_to_consume, reason=None):
    """Consume item from inventory with validation"""
    try:
        # Get current item
        item = get_item_by_id(item_id)
        if not item:
            return False, "Item not found"
        
        # Validate quantity
        if quantity_to_consume <= 0:
            return False, "Quantity must be greater than 0"
        
        if quantity_to_consume > item['quantity']:
            return False, f"Cannot consume {quantity_to_consume} units. Only {item['quantity']} available."
        
        # Calculate new quantity
        new_quantity = item['quantity'] - quantity_to_consume
        
        # Update item
        supabase.table('items').update({
            'quantity': new_quantity,
            'updated_at': datetime.now().isoformat()
        }).eq('id', item_id).execute()
        
        # Log transaction
        log_transaction(
            item_id=item_id,
            transaction_type='deduction',
            quantity=-quantity_to_consume,
            reason=reason
        )
        
        return True, f"Successfully consumed {quantity_to_consume} units"
        
    except Exception as e:
        return False, f"Error consuming item: {str(e)}"

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_sidebar():
    """Render sidebar with navigation and user info"""
    with st.sidebar:
        st.title("🚀 Astro Inventory Wizard")
        st.markdown("---")
        
        # Initialize current page if not set
        if 'current_page' not in st.session_state:
            st.session_state.current_page = "Home"
        
        # Navigation - use session state to control the radio
        page_options = ["Home", "Inventory", "BOMs", "Orders", "Reports"]
        current_index = page_options.index(st.session_state.current_page) if st.session_state.current_page in page_options else 0
        
        selected_page = st.radio(
            "Navigation",
            page_options,
            index=current_index,
            label_visibility="collapsed",
            key="nav_radio"
        )
        
        # Update current page if user manually changed it
        if selected_page != st.session_state.current_page:
            st.session_state.current_page = selected_page
            # Clear any open modals/forms when manually navigating
            st.session_state.adding_item = False
            st.session_state.editing_item = None
            st.session_state.consuming_item = None
        
        page = st.session_state.current_page
        
        st.markdown("---")
        
        # User info at bottom
        st.markdown(f"**Logged in as:**  \n{st.session_state.user}")
        if st.button("Switch User", width="stretch"):
            logout()
        
        return page

def item_form(item=None, form_key="item_form"):
    """Render item add/edit form"""
    is_edit = item is not None
    
    # Prevent Enter key from submitting the form
    st.markdown("""
        <style>
        .stTextInput input, .stNumberInput input, .stSelectbox select {
            /* Prevent form submission on Enter */
        }
        </style>
    """, unsafe_allow_html=True)
    
    with st.form(form_key, enter_to_submit=False):
        st.subheader("Edit Item" if is_edit else "Add New Item")
        
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input(
                "Item Name *",
                value=item['name'] if is_edit else "",
                placeholder="e.g., M8 Bolt"
            )
            
            category = st.selectbox(
                "Category *",
                options=CATEGORIES,
                index=CATEGORIES.index(item['category']) if is_edit else 0
            )
            
            team = st.selectbox(
                "Team *",
                options=TEAMS,
                index=TEAMS.index(item['team']) if is_edit else 0
            )
            
            quantity = st.number_input(
                "Quantity *",
                min_value=0,
                value=item['quantity'] if is_edit else 0,
                step=1
            )
            
            location = st.selectbox(
                "Location *",
                options=LOCATIONS,
                index=LOCATIONS.index(item['location']) if is_edit and item['location'] in LOCATIONS else 0
            )
            
            # If "Other" selected or custom location, show text input
            if location == "Other (specify)" or (is_edit and item['location'] not in LOCATIONS):
                location = st.text_input(
                    "Specify Location *",
                    value=item['location'] if is_edit and item['location'] not in LOCATIONS else ""
                )
        
        with col2:
            supplier = st.text_input(
                "Supplier *",
                value=item['supplier'] if is_edit else "",
                placeholder="e.g., McMaster-Carr"
            )
            
            cost_per_unit = st.number_input(
                "Cost per Unit ($) *",
                min_value=0.0,
                value=float(item['cost_per_unit']) if is_edit else 0.0,
                step=0.01,
                format="%.2f"
            )
            
            min_stock_level = st.number_input(
                "Min Stock Level *",
                min_value=0,
                value=item['min_stock_level'] if is_edit else 0,
                step=1
            )
            
            reorder_quantity = st.number_input(
                "Reorder Quantity *",
                min_value=1,
                value=item['reorder_quantity'] if is_edit else 10,
                step=1
            )
            
            expiration_date = st.date_input(
                "Expiration Date (optional)",
                value=datetime.fromisoformat(item['expiration_date']).date() if is_edit and item.get('expiration_date') else None
            )
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            submit = st.form_submit_button(
                "Update Item" if is_edit else "Add Item",
                type="primary",
                width="stretch"
            )
        with col2:
            cancel = st.form_submit_button("Cancel", width="stretch")
        
        # Delete button only for edit mode (outside columns to be separate)
        if is_edit:
            st.markdown("---")
            col_del1, col_del2, col_del3 = st.columns([1, 1, 2])
            with col_del1:
                delete = st.form_submit_button("🗑️ Delete Item", width="stretch")
            if delete:
                # Show confirmation in session state
                st.session_state.confirm_delete_item = item['id']
                st.rerun()
        
        if cancel:
            if is_edit:
                st.session_state.editing_item = None
            else:
                st.session_state.adding_item = False
            st.rerun()
        
        if submit:
            # Validate required fields
            if not all([name, category, team, location, supplier]):
                st.error("Please fill in all required fields (marked with *)")
                return False
            
            if cost_per_unit < 0:
                st.error("Cost per unit must be non-negative")
                return False
            
            if quantity < 0:
                st.error("Quantity cannot be negative")
                return False
            
            # Check for duplicates (fuzzy matching)
            is_duplicate, existing_name = check_duplicate_item(name, exclude_id=item['id'] if is_edit else None)
            if is_duplicate:
                st.error(f"⚠️ An item with a similar name already exists: '{existing_name}'. Please use a different name or update the existing item.")
                return False
            
            # Prepare item data
            item_data = {
                'name': name.strip(),
                'category': category,
                'team': team,
                'quantity': quantity,
                'location': location.strip(),
                'supplier': supplier.strip(),
                'cost_per_unit': cost_per_unit,
                'min_stock_level': min_stock_level,
                'reorder_quantity': reorder_quantity,
                'expiration_date': expiration_date.isoformat() if expiration_date else None
            }
            
            # Add or update
            if is_edit:
                success, message = update_item(item['id'], item_data)
                if success:
                    st.success(message)
                    st.session_state.editing_item = None
                    st.rerun()
                else:
                    st.error(message)
            else:
                success, message = add_item(item_data)
                if success:
                    st.success(message)
                    st.session_state.adding_item = False
                    # Don't change page - stay on Inventory
                    st.rerun()
                else:
                    st.error(message)
            
            return success

def consume_modal(item):
    """Modal for consuming items"""
    st.subheader(f"Consume: {item['name']}")
    st.info(f"Current stock: **{item['quantity']}** units")
    
    # Initialize error state
    if 'consume_error' not in st.session_state:
        st.session_state.consume_error = None
    
    # Show error if exists
    if st.session_state.consume_error:
        st.error(st.session_state.consume_error)
    
    with st.form("consume_form", clear_on_submit=False):
        quantity_to_consume = st.number_input(
            "Quantity to consume *",
            min_value=1,
            value=1,
            step=1,
            help=f"Available: {item['quantity']} units"
        )
        
        reason = st.text_input(
            "Reason (optional)",
            placeholder="e.g., Test Flight #3"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Confirm", type="primary", width="stretch")
        with col2:
            cancel = st.form_submit_button("Cancel", width="stretch")
        
        if cancel:
            st.session_state.consuming_item = None
            st.session_state.consume_error = None
            st.rerun()
        
        if submit:
            # Clear previous errors
            st.session_state.consume_error = None
            
            # Validate before attempting to consume
            if quantity_to_consume <= 0:
                st.session_state.consume_error = "Quantity must be greater than 0"
                st.rerun()
            elif quantity_to_consume > item['quantity']:
                st.session_state.consume_error = f"Cannot consume {quantity_to_consume} units. Only {item['quantity']} available."
                st.rerun()
            else:
                # Attempt to consume
                success, message = consume_item(item['id'], quantity_to_consume, reason)
                if success:
                    # Check if now low stock
                    new_quantity = item['quantity'] - quantity_to_consume
                    if new_quantity < item['min_stock_level']:
                        st.success(message)
                        st.warning(f"⚠️ Item is now below minimum stock level ({item['min_stock_level']} units)")
                    else:
                        st.success(message)
                    
                    # Close modal on success
                    st.session_state.consuming_item = None
                    st.session_state.consume_error = None
                    st.rerun()
                else:
                    # Show error and keep modal open
                    st.session_state.consume_error = message
                    st.rerun()

# ============================================================================
# PAGES
# ============================================================================

def home_page():
    """Home dashboard page"""
    st.title("🏠 Dashboard")
    
    # Fetch all items for calculations
    items = get_all_items()
    
    if not items:
        st.info("No inventory items yet. Add your first item in the Inventory page!")
        return
    
    # Summary cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_value = sum(item['quantity'] * float(item['cost_per_unit']) for item in items)
        st.metric("Total Inventory Value", f"${total_value:,.2f}")
    
    with col2:
        low_stock_count = sum(1 for item in items if item['quantity'] < item['min_stock_level'])
        st.metric("Low Stock Items", low_stock_count)
    
    with col3:
        # This will be populated in Phase 3
        st.metric("Items on Order", 0)
    
    st.markdown("---")
    
    # Recent transactions
    st.subheader("Recent Activity")
    try:
        response = supabase.table('transactions').select('*, items(name)').order('timestamp', desc=True).limit(5).execute()
        
        if response.data:
            transactions_df = pd.DataFrame(response.data)
            transactions_df['item_name'] = transactions_df['items'].apply(lambda x: x['name'] if x else 'Unknown')
            transactions_df['timestamp'] = pd.to_datetime(transactions_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
            
            display_df = transactions_df[['timestamp', 'item_name', 'transaction_type', 'quantity', 'performed_by']]
            display_df.columns = ['Time', 'Item', 'Type', 'Quantity', 'User']
            
            st.dataframe(display_df, width="stretch", hide_index=True)
        else:
            st.info("No recent transactions")
    except Exception as e:
        st.error(f"Error loading transactions: {str(e)}")
    
    st.markdown("---")
    
    # Team summary
    st.subheader("Inventory by Team")
    col1, col2, col3 = st.columns(3)
    
    team_counts = {team: sum(1 for item in items if item['team'] == team) for team in TEAMS}
    
    with col1:
        st.metric("Shared", team_counts['Shared'])
    with col2:
        st.metric("Rocketry", team_counts['Rocketry'])
    with col3:
        st.metric("Liquid Propulsion", team_counts['Liquid Propulsion'])

def inventory_page():
    """Inventory management page"""
    st.title("📦 Inventory")
    
    # Ensure we stay on Inventory page
    st.session_state.current_page = "Inventory"
    
    # Check if we need to show delete confirmation
    if st.session_state.get('confirm_delete_item'):
        item_to_delete = get_item_by_id(st.session_state.confirm_delete_item)
        if item_to_delete:
            st.warning(f"⚠️ Are you sure you want to delete **{item_to_delete['name']}**?")
            st.markdown("This action cannot be undone. All transaction history for this item will be preserved.")
            
            col1, col2, col3 = st.columns([1, 1, 3])
            with col1:
                if st.button("Yes, Delete", type="primary", width="stretch"):
                    success, message = delete_item(item_to_delete['id'])
                    if success:
                        st.success(message)
                        st.session_state.confirm_delete_item = None
                        st.session_state.editing_item = None
                        st.rerun()
                    else:
                        st.error(message)
            with col2:
                if st.button("Cancel", width="stretch"):
                    st.session_state.confirm_delete_item = None
                    st.rerun()
            
            return  # Don't show the rest of the page during confirmation
    
    # Check if we're adding or editing an item
    if st.session_state.get('adding_item', False):
        item_form()
        return
    
    if st.session_state.get('editing_item'):
        item = get_item_by_id(st.session_state.editing_item)
        if item:
            item_form(item, form_key="edit_item_form")
        return
    
    if st.session_state.get('consuming_item'):
        item = get_item_by_id(st.session_state.consuming_item)
        if item:
            consume_modal(item)
        return
    
    # Filters
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    
    with col1:
        search_term = st.text_input("Search", placeholder="Search by name...", label_visibility="visible")
    
    with col2:
        filter_category = st.selectbox("Category", ["All"] + CATEGORIES, label_visibility="visible")
    
    with col3:
        filter_team = st.selectbox("Team", ["All"] + TEAMS, label_visibility="visible")
    
    with col4:
        st.markdown("&nbsp;", unsafe_allow_html=True)  # Empty label space to align with other filters
        filter_low_stock = st.checkbox("Low Stock Only")
    
    with col5:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacer to align button with inputs
        if st.button("➕ Add Item", type="primary", width="stretch"):
            st.session_state.adding_item = True
            st.rerun()
    
    st.markdown("---")
    
    # Fetch and filter items
    items = get_all_items()
    
    if search_term:
        items = [item for item in items if search_term.lower() in item['name'].lower()]
    
    if filter_category != "All":
        items = [item for item in items if item['category'] == filter_category]
    
    if filter_team != "All":
        items = [item for item in items if item['team'] == filter_team]
    
    if filter_low_stock:
        items = [item for item in items if item['quantity'] < item['min_stock_level']]
    
    # Display items
    if not items:
        st.info("No items found. Try adjusting your filters or add a new item.")
        return
    
    st.markdown(f"**{len(items)} items found**")
    
    # Create DataFrame for display
    df = pd.DataFrame(items)
    
    # Display items in a table-like format using columns
    for item in items:
        is_low_stock = item['quantity'] < item['min_stock_level']
        
        with st.container():
            col1, col2, col3, col4, col5, col6 = st.columns([3, 1.5, 1, 1, 1.5, 2])
            
            with col1:
                if is_low_stock:
                    st.markdown(f"**:red[{item['name']}]** ⚠️")
                else:
                    st.markdown(f"**{item['name']}**")
                st.caption(f"{item['category']} • {item['team']}")
            
            with col2:
                st.text(f"📍 {item['location']}")
            
            with col3:
                if is_low_stock:
                    st.markdown(f":red[**{item['quantity']}**]")
                else:
                    st.text(f"{item['quantity']}")
                st.caption(f"Min: {item['min_stock_level']}")
            
            with col4:
                st.text(f"${item['cost_per_unit']}")
            
            with col5:
                st.text(item['supplier'])
            
            with col6:
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    if st.button("✏️", key=f"edit_{item['id']}", help="Edit"):
                        st.session_state.editing_item = item['id']
                        st.rerun()
                with btn_col2:
                    if st.button("📉", key=f"consume_{item['id']}", help="Consume"):
                        st.session_state.consuming_item = item['id']
                        st.rerun()
                with btn_col3:
                    # Disabled button for Phase 3 feature
                    st.button("🛒", key=f"reorder_{item['id']}", help="Coming in Phase 3", disabled=True)
            
            st.markdown("---")

def boms_page():
    """BOMs page - placeholder for Phase 2"""
    st.title("📋 Bill of Materials")
    st.info("🚧 BOM features will be implemented in Phase 2")
    st.markdown("Coming soon:")
    st.markdown("- Create BOMs manually")
    st.markdown("- Upload BOMs from Excel")
    st.markdown("- Stock checking against BOMs")
    st.markdown("- Consume items from BOMs")

def orders_page():
    """Orders page - placeholder for Phase 3"""
    st.title("🛒 Orders")
    st.info("🚧 Order management features will be implemented in Phase 3")
    st.markdown("Coming soon:")
    st.markdown("- Order list grouped by supplier")
    st.markdown("- Purchase workflow")
    st.markdown("- Delivery tracking")
    st.markdown("- Automated reordering")

def reports_page():
    """Reports page - placeholder for Phase 3"""
    st.title("📊 Reports")
    st.info("🚧 Reporting features will be implemented in Phase 3")
    st.markdown("Coming soon:")
    st.markdown("- Transaction history")
    st.markdown("- Usage summaries")
    st.markdown("- Inventory exports")
    st.markdown("- BOM exports")

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application entry point"""
    
    # Check login status
    check_login()
    
    # Render sidebar and get selected page
    page = render_sidebar()
    
    # Store current page in session state
    st.session_state.page = page
    
    # Route to appropriate page
    if page == "Home":
        home_page()
    elif page == "Inventory":
        inventory_page()
    elif page == "BOMs":
        boms_page()
    elif page == "BOMs":
        boms_page()
    elif page == "Orders":
        orders_page()
    elif page == "Reports":
        reports_page()

if __name__ == "__main__":
    main()