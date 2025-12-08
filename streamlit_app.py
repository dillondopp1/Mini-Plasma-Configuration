import html
import io
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


# ----------------------------
# Data structures and helpers
# ----------------------------

@dataclass
class MachineConfig:
    name: str           # Label shown to you
    x_work_in: float    # Target working area in inches (X)
    y_work_in: float    # Target working area in inches (Y)


# Predefined machine configurations (nominal working areas)
MACHINE_CONFIGS: Dict[str, MachineConfig] = {
    "400 x 400 mm": MachineConfig("400 x 400 mm", x_work_in=15.75, y_work_in=15.75),
    "400 x 2 ft":   MachineConfig("400 x 2 ft",   x_work_in=15.75, y_work_in=24.0),
    "400 x 3 ft":   MachineConfig("400 x 3 ft",   x_work_in=15.75, y_work_in=36.0),
    "400 x 4 ft":   MachineConfig("400 x 4 ft",   x_work_in=15.75, y_work_in=48.0),
    "2 x 2 ft":     MachineConfig("2 x 2 ft",     x_work_in=24.0,  y_work_in=24.0),
    "2 x 3 ft":     MachineConfig("2 x 3 ft",     x_work_in=24.0,  y_work_in=36.0),
    "2 x 4 ft":     MachineConfig("2 x 4 ft",     x_work_in=24.0,  y_work_in=48.0),
    "3 x 3 ft":     MachineConfig("3 x 3 ft",     x_work_in=36.0,  y_work_in=36.0),
    "3 x 4 ft":     MachineConfig("3 x 4 ft",     x_work_in=36.0,  y_work_in=48.0),
    "4 x 4 ft":     MachineConfig("4 x 4 ft",     x_work_in=48.0,  y_work_in=48.0),
}

# Standard 2040 extrusion lengths and prices (mm -> per-piece price)
DEFAULT_2040_PRICES = {
    400: 6.75,
    600: 8.75,
    800: 12.50,
    1000: 12.50,
    1220: 15.00,
    1500: 19.75,
}

STANDARD_LENGTHS_MM = [400, 600, 800, 1000, 1220, 1500]

# Fixed costs
MISC_ELECTRONICS_COST = 30.0  # Fixed cost for misc electronics on every machine


def mm_to_in(mm: float) -> float:
    return mm / 25.4


def in_to_mm(inches: float) -> float:
    return inches * 25.4


def choose_standard_length(required_in: float) -> int:
    """
    Pick the smallest standard length (mm) that is >= the required inches.
    """
    required_mm = in_to_mm(required_in)
    for length_mm in STANDARD_LENGTHS_MM:
        if length_mm >= required_mm:
            return length_mm
    # If nothing fits (shouldn't happen with current sizes), use the largest
    return STANDARD_LENGTHS_MM[-1]


def round_ft(value_in: float) -> float:
    """
    Convert inches to feet and round to 2 decimals.
    """
    return round(value_in / 12.0, 2)


# Plasma units persistence
PLASMA_UNITS_FILE = "plasma_units.json"


def load_plasma_units() -> Dict[str, float]:
    """
    Load plasma units from JSON file.
    Returns empty dict if file doesn't exist.
    """
    if os.path.exists(PLASMA_UNITS_FILE):
        try:
            with open(PLASMA_UNITS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_plasma_units(plasma_units: Dict[str, float]) -> None:
    """
    Save plasma units to JSON file.
    """
    try:
        with open(PLASMA_UNITS_FILE, 'w') as f:
            json.dump(plasma_units, f, indent=2)
    except IOError:
        st.error("Failed to save plasma units to file.")


def generate_quote_pdf(
    customer_name: str,
    config_name: str,
    actual_x_ft: float,
    actual_y_ft: float,
    sell_price: float,
) -> bytes:
    """
    Generate a PDF quote with customer name, price, and specifications.
    Returns the PDF as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=30,
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=12,
        spaceBefore=12,
    )
    normal_style = styles['Normal']
    
    # Title
    story.append(Paragraph("QUOTE", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Customer and Date (escape XML special characters)
    escaped_customer_name = html.escape(customer_name)
    escaped_config_name = html.escape(config_name)
    story.append(Paragraph(f"<b>Customer:</b> {escaped_customer_name}", normal_style))
    story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}", normal_style))
    story.append(Paragraph(f"<b>Configuration:</b> {escaped_config_name}", normal_style))
    story.append(Paragraph(f"<b>Working Area:</b> {actual_x_ft:.2f} ft × {actual_y_ft:.2f} ft", normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Price
    story.append(Paragraph(f"<b><font size=18>Total Price: ${sell_price:,.2f}</font></b>", normal_style))
    story.append(Spacer(1, 0.4*inch))
    
    # Specifications
    story.append(Paragraph("SPECIFICATIONS", heading_style))
    story.append(Spacer(1, 0.1*inch))
    
    # Motion System
    story.append(Paragraph("<b>Motion System</b>", heading_style))
    motion_specs = [
        "Drive Type: Belt-driven X and Y axes",
        "Linear Motion: V-wheel system on aluminum V-slot extrusions",
        "Maximum Travel Speed: ~10,000 mm/min motion capability",
        "Motor Type: NEMA 17 stepper motors",
        "Microstepping: Up to 1/32 depending on controller configuration",
    ]
    for spec in motion_specs:
        story.append(Paragraph(f"• {spec}", normal_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Controller & Electronics
    story.append(Paragraph("<b>Controller & Electronics</b>", heading_style))
    controller_specs = [
        "Mainboard: 32-bit GRBL-based motion controller",
        "Firmware: Standard GRBL (configured for plasma torch on/off control)",
        "Supported Communication:",
        "  • USB connection to PC",
        "  • Wi-Fi (if included in your configuration)",
        "  • Offline job execution using MicroSD/TF card",
        "Power Input: 12V DC motion system supply",
        "Torch Control Output: Isolated relay output for plasma \"torch fire\" signal",
        "Safety Interlocks:",
        "  • Emergency stop button",
    ]
    for spec in controller_specs:
        story.append(Paragraph(f"• {spec}", normal_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Software Compatibility
    story.append(Paragraph("<b>Software Compatibility</b>", heading_style))
    software_specs = [
        "Compatible Control Software:",
        "  • LaserGRBL",
        "  • OpenBuilds CONTROL",
        "  • Universal G-Code Sender (UGS)",
        "  • Any GRBL-compatible sender",
        "G-Code Support: Standard GRBL G-code for 2-axis plasma cutting",
        "Design File Support: SVG, DXF, PNG/JPG (converted to paths), AI (via converters)",
    ]
    for spec in software_specs:
        story.append(Paragraph(f"• {spec}", normal_style))
    story.append(Spacer(1, 0.2*inch))
    
    # User Interface
    story.append(Paragraph("<b>User Interface</b>", heading_style))
    ui_specs = [
        "Touch Display (Optional): 3.5\" color LCD for offline control",
        "Offline Operation: Supported via MicroSD card",
    ]
    for spec in ui_specs:
        story.append(Paragraph(f"• {spec}", normal_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Structural System
    story.append(Paragraph("<b>Structural System</b>", heading_style))
    structural_specs = [
        "Frame Construction: Aluminum V-slot extrusion framework",
        "Gantry System: Reinforced aluminum crossbeam with adjustable carriage",
        "Torch Mounting: Custom fixed or adjustable plasma torch holder",
    ]
    for spec in structural_specs:
        story.append(Paragraph(f"• {spec}", normal_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Plasma System Integration
    story.append(Paragraph("<b>Plasma System Integration</b>", heading_style))
    plasma_specs = [
        "Torch Trigger: Dry-contact relay output compatible with most pilot-arc or blowback torch systems",
        "Signal Isolation: Relay isolator protects controller from arc interference",
        "Grounding Requirements: Dedicated ground recommended for plasma cutting",
        "Z-Axis Setup: Manual or fixed-height torch mount (motorized Z optional upgrade)",
    ]
    for spec in plasma_specs:
        story.append(Paragraph(f"• {spec}", normal_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def calculate_quote_for_config(
    config: MachineConfig,
    price_2020: float,
    price_2040_map: Dict[int, float],
    steel_price_per_ft: float,
    donor_cost: float,
    misc_addon_pct: float,
    base_profit: float,
    profit_per_sqft: float,
    plasma_unit_cost: float = 0.0,
) -> Dict:
    """
    Calculate the complete quote (cost, profit, sell_price) for a given configuration.
    Returns a dictionary with the results.
    """
    # Compute costs and parts
    extrusion_parts, steel_parts, extrusion_cost, steel_cost, actual_work = \
        calculate_extrusions_and_steel(
            config=config,
            price_2020=price_2020,
            price_2040_map=price_2040_map,
            steel_price_per_ft=steel_price_per_ft,
        )
    
    # Basic materials cost (extrusions + steel + donor kit + plasma unit + misc electronics)
    base_material_cost = extrusion_cost + steel_cost + donor_cost + plasma_unit_cost + MISC_ELECTRONICS_COST
    
    # Add misc % if any
    misc_cost = base_material_cost * (misc_addon_pct / 100.0)
    total_cost = base_material_cost + misc_cost
    
    # Calculate area and profit
    nominal_x_ft = config.x_work_in / 12.0
    nominal_y_ft = config.y_work_in / 12.0
    area_sqft = nominal_x_ft * nominal_y_ft
    
    base_profit_calc = base_profit + area_sqft * profit_per_sqft
    sell_price = total_cost + base_profit_calc
    
    # Round sell_price up to the nearest $10
    sell_price = math.ceil(sell_price / 10.0) * 10.0
    
    # Recalculate actual profit after rounding
    profit = sell_price - total_cost
    
    return {
        "config_name": config.name,
        "area_sqft": area_sqft,
        "total_cost": total_cost,
        "profit": profit,
        "sell_price": sell_price,
    }


# ----------------------------------------
# Core calculation logic for one machine
# ----------------------------------------

def calculate_extrusions_and_steel(
    config: MachineConfig,
    price_2020: float,
    price_2040_map: Dict[int, float],
    steel_price_per_ft: float,
) -> Tuple[
    List[Dict],
    List[Dict],
    float,
    float,
    Tuple[float, float]
]:
    """
    Given a machine configuration and pricing, compute:
      - extrusion parts list (2020 + gantry 2020/2040)
      - steel frame parts list
      - total extrusion cost
      - total steel cost
      - actual working area (X, Y) in inches, based on chosen extrusions
    """

    x_work = config.x_work_in
    y_work = config.y_work_in

    # Offsets (from your earlier logic)
    y_rail_offset = 6.0          # inches (extrusion Y)
    x_frame_offset_2020 = 3.5    # inches (extrusion X frame)
    gantry_offset = 5.25         # inches (gantry extrusion)
    x_frame_offset_steel = 5.25  # inches (steel X tube)
    y_frame_offset_steel = 6.0   # inches (steel Y tube)

    # ---------- Extrusions ----------
    # Required lengths in inches
    required_y_rail_in = y_work + y_rail_offset
    required_x_frame_in = x_work + x_frame_offset_2020
    required_gantry_in = x_work + gantry_offset

    # Choose standard extrusion lengths
    y_rail_length_mm = choose_standard_length(required_y_rail_in)
    x_frame_length_mm = choose_standard_length(required_x_frame_in)
    gantry_length_mm = choose_standard_length(required_gantry_in)

    y_rail_length_in = mm_to_in(y_rail_length_mm)
    x_frame_length_in = mm_to_in(x_frame_length_mm)
    gantry_length_in = mm_to_in(gantry_length_mm)

    # Decide if gantry is 2020 or 2040:
    # if required length < 29", 2020 is acceptable; otherwise 2040.
    gantry_profile = "2020" if required_gantry_in < 29.0 else "2040"

    extrusion_parts: List[Dict] = []

    # 2x Y-axis rails - always 2020
    extrusion_parts.append({
        "description": "Y-axis rail",
        "profile": "2020",
        "length_mm": y_rail_length_mm,
        "length_in": y_rail_length_in,
        "quantity": 2,
        "unit_price": price_2020,
        "line_total": price_2020 * 2,
    })

    # 2x X-axis frame rails - always 2020
    extrusion_parts.append({
        "description": "X-axis frame rail",
        "profile": "2020",
        "length_mm": x_frame_length_mm,
        "length_in": x_frame_length_in,
        "quantity": 2,
        "unit_price": price_2020,
        "line_total": price_2020 * 2,
    })

    # 1x Gantry beam
    if gantry_profile == "2020":
        gantry_unit_price = price_2020
    else:
        # 2040 – use the price map based on chosen length
        gantry_unit_price = price_2040_map.get(gantry_length_mm, 0.0)

    extrusion_parts.append({
        "description": "Gantry beam",
        "profile": gantry_profile,
        "length_mm": gantry_length_mm,
        "length_in": gantry_length_in,
        "quantity": 1,
        "unit_price": gantry_unit_price,
        "line_total": gantry_unit_price * 1,
    })

    total_extrusion_cost = sum(p["line_total"] for p in extrusion_parts)

    # ---------- Steel frame ----------
    # 2x X tubes, 2x Y tubes
    x_tube_length_in = x_work + x_frame_offset_steel
    y_tube_length_in = y_work + y_frame_offset_steel

    steel_parts: List[Dict] = []

    steel_parts.append({
        "description": "Steel tube X",
        "size": '1.5" x 1.5"',
        "length_in": x_tube_length_in,
        "length_ft": x_tube_length_in / 12.0,
        "quantity": 2,
    })

    steel_parts.append({
        "description": "Steel tube Y",
        "size": '1.5" x 1.5"',
        "length_in": y_tube_length_in,
        "length_ft": y_tube_length_in / 12.0,
        "quantity": 2,
    })

    total_steel_ft = sum(p["length_ft"] * p["quantity"] for p in steel_parts)
    total_steel_cost = total_steel_ft * steel_price_per_ft

    # ---------- Actual working area (based on chosen extrusions) ----------
    actual_x_work_in = gantry_length_in - gantry_offset
    actual_y_work_in = y_rail_length_in - y_rail_offset

    return extrusion_parts, steel_parts, total_extrusion_cost, total_steel_cost, (
        actual_x_work_in,
        actual_y_work_in,
    )


# -----------------
# Streamlit UI
# -----------------

def main():
    st.title("CNC Router / Plasma Quoting Tool")

    st.markdown(
        "Use this app to configure a machine size, tweak your costs, "
        "and generate a parts list, build cost, and customer quote.  \n"
        "Pricing is based on: **profit = base_profit + area_sqft * profit_per_sqft**."
    )

    # Sidebar: global settings
    st.sidebar.header("Global Settings")

    donor_cost = st.sidebar.number_input(
        "Donor Amazon CNC kit cost ($)",
        min_value=0.0,
        value=150.0,
        step=10.0,
    )

    steel_price_per_ft = st.sidebar.number_input(
        "Steel price per foot ($)",
        min_value=0.0,
        value=5.75,
        step=0.25,
    )

    price_2020 = st.sidebar.number_input(
        "2020 extrusion price per piece ($)",
        min_value=0.0,
        value=7.50,
        step=0.25,
    )

    st.sidebar.subheader("2040 Extrusion Prices (per piece)")
    price_2040_map = {}
    for length_mm in STANDARD_LENGTHS_MM:
        default_price = DEFAULT_2040_PRICES[length_mm]
        price_2040_map[length_mm] = st.sidebar.number_input(
            f"2040 @ {length_mm} mm ($)",
            min_value=0.0,
            value=float(default_price),
            step=0.25,
        )

    st.sidebar.subheader("Profit Settings (Area-based)")

    base_profit = st.sidebar.number_input(
        "Base profit per machine ($)",
        min_value=0.0,
        value=250.0,
        step=25.0,
        help="A fixed profit added to every build, regardless of size.",
    )

    profit_per_sqft = st.sidebar.number_input(
        "Profit per square foot of nominal area ($/ft²)",
        min_value=0.0,
        value=45.0,
        step=5.0,
        help="Additional profit for each square foot of nominal working area.",
    )

    misc_addon_pct = st.sidebar.number_input(
        "Extra misc % on materials (bolts, nuts, paint, etc.)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        help="Percentage of material cost added to cover miscellaneous items.",
    )

    # Plasma unit management
    st.sidebar.subheader("Plasma Unit Options")
    
    # Initialize session state for plasma units from file
    if "plasma_units" not in st.session_state:
        st.session_state.plasma_units = load_plasma_units()
    
    # Add new plasma unit
    with st.sidebar.expander("Add New Plasma Unit"):
        new_unit_name = st.text_input("Unit Name", key="new_unit_name")
        new_unit_cost = st.number_input(
            "Unit Cost ($)",
            min_value=0.0,
            value=0.0,
            step=10.0,
            key="new_unit_cost"
        )
        if st.button("Add Plasma Unit", key="add_plasma_unit"):
            if new_unit_name and new_unit_name.strip():
                st.session_state.plasma_units[new_unit_name.strip()] = new_unit_cost
                save_plasma_units(st.session_state.plasma_units)
                st.success(f"Added {new_unit_name.strip()} (${new_unit_cost:,.2f})")
                st.rerun()
    
    # Select plasma unit
    plasma_options = ["None"] + list(st.session_state.plasma_units.keys())
    selected_plasma = st.sidebar.selectbox(
        "Select Plasma Unit",
        options=plasma_options,
        help="Select a plasma unit to include in the quote. The cost will be added to both total cost and sale price."
    )
    
    plasma_unit_cost = 0.0
    plasma_unit_name = None
    if selected_plasma != "None":
        plasma_unit_cost = st.session_state.plasma_units[selected_plasma]
        plasma_unit_name = selected_plasma
        st.sidebar.info(f"Selected: {plasma_unit_name} (${plasma_unit_cost:,.2f})")
    
    # Option to delete plasma units
    if st.session_state.plasma_units:
        with st.sidebar.expander("Manage Plasma Units"):
            for unit_name, unit_cost in list(st.session_state.plasma_units.items()):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{unit_name}: ${unit_cost:,.2f}")
                with col2:
                    if st.button("Delete", key=f"delete_{unit_name}"):
                        del st.session_state.plasma_units[unit_name]
                        save_plasma_units(st.session_state.plasma_units)
                        st.rerun()

    # Main: machine selection
    st.header("Machine Configuration")

    config_name = st.selectbox(
        "Select machine size",
        list(MACHINE_CONFIGS.keys()),
    )
    config = MACHINE_CONFIGS[config_name]

    nominal_x_ft = config.x_work_in / 12.0
    nominal_y_ft = config.y_work_in / 12.0
    nominal_area_sqft = nominal_x_ft * nominal_y_ft

    st.write(
        f"**Nominal working area (target):** {nominal_x_ft:.2f} ft × {nominal_y_ft:.2f} ft "
        f"(Area: {nominal_area_sqft:.2f} ft²)"
    )

    # Customer name input for PDF quote
    customer_name = st.text_input("Customer Name (for PDF quote)", value="", key="customer_name")

    # Comparison button for all configurations
    if st.button("Compare All Configurations"):
        st.subheader("Price Comparison - All Configurations")
        comparison_note = (
            f"Using current pricing parameters: Base profit = ${base_profit:,.2f}, "
            f"Profit per sqft = ${profit_per_sqft:,.2f}"
        )
        if plasma_unit_cost > 0:
            comparison_note += f"  \n**Plasma unit included:** {plasma_unit_name} (${plasma_unit_cost:,.2f})"
        st.markdown(comparison_note)
        
        comparison_data = []
        for config_key, config in MACHINE_CONFIGS.items():
            quote = calculate_quote_for_config(
                config=config,
                price_2020=price_2020,
                price_2040_map=price_2040_map,
                steel_price_per_ft=steel_price_per_ft,
                donor_cost=donor_cost,
                misc_addon_pct=misc_addon_pct,
                base_profit=base_profit,
                profit_per_sqft=profit_per_sqft,
                plasma_unit_cost=plasma_unit_cost,
            )
            comparison_data.append({
                "Configuration": quote["config_name"],
                "Area (ft²)": round(quote["area_sqft"], 2),
                "Total Cost ($)": round(quote["total_cost"], 2),
                "Profit ($)": round(quote["profit"], 2),
                "Sale Price ($)": round(quote["sell_price"], 2),
            })
        
        # Sort by area for easier comparison
        comparison_data.sort(key=lambda x: x["Area (ft²)"])
        
        st.table(comparison_data)
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Lowest Price", f"${min(d['Sale Price ($)'] for d in comparison_data):,.0f}")
        with col2:
            st.metric("Highest Price", f"${max(d['Sale Price ($)'] for d in comparison_data):,.0f}")
        with col3:
            avg_price = sum(d['Sale Price ($)'] for d in comparison_data) / len(comparison_data)
            st.metric("Average Price", f"${avg_price:,.0f}")

    if st.button("Generate Quote"):
        # Compute costs and parts
        extrusion_parts, steel_parts, extrusion_cost, steel_cost, actual_work = \
            calculate_extrusions_and_steel(
                config=config,
                price_2020=price_2020,
                price_2040_map=price_2040_map,
                steel_price_per_ft=steel_price_per_ft,
            )

        actual_x_in, actual_y_in = actual_work
        actual_x_ft = round_ft(actual_x_in)
        actual_y_ft = round_ft(actual_y_in)

        # Basic materials cost (extrusions + steel + donor kit + plasma unit + misc electronics)
        base_material_cost = extrusion_cost + steel_cost + donor_cost + plasma_unit_cost + MISC_ELECTRONICS_COST

        # Add misc % if any
        misc_cost = base_material_cost * (misc_addon_pct / 100.0)
        total_cost = base_material_cost + misc_cost

        # ---------- Area-based pricing ----------
        # profit = base_profit + area_sqft * profit_per_sqft
        area_sqft = nominal_area_sqft
        base_profit_calc = base_profit + area_sqft * profit_per_sqft
        sell_price = total_cost + base_profit_calc
        
        # Round sell_price up to the nearest $10
        sell_price = math.ceil(sell_price / 10.0) * 10.0
        
        # Recalculate actual profit after rounding
        profit = sell_price - total_cost

        actual_margin_pct = (profit / sell_price * 100.0) if sell_price > 0 else 0.0

        # -------- Summary --------
        st.subheader("Summary")

        st.markdown(
            f"**Configuration:** {config.name}  \n"
            f"**Actual working area:** {actual_x_ft:.2f} ft × {actual_y_ft:.2f} ft  \n"
            f"**Nominal area used for pricing:** {area_sqft:.2f} ft²"
        )

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Extrusion cost ($)", f"{extrusion_cost:,.2f}")
            st.metric("Steel cost ($)", f"{steel_cost:,.2f}")
            st.metric("Donor kit cost ($)", f"{donor_cost:,.2f}")
            st.metric("Misc Electronics ($)", f"{MISC_ELECTRONICS_COST:,.2f}")
            if plasma_unit_cost > 0:
                st.metric(f"Plasma unit ({plasma_unit_name}) ($)", f"{plasma_unit_cost:,.2f}")
            st.metric("Misc add-on ($)", f"{misc_cost:,.2f}")
        with col2:
            st.metric("Total build cost ($)", f"{total_cost:,.2f}")
            st.metric("Sell price ($)", f"{sell_price:,.2f}")
            st.metric("Profit ($)", f"{profit:,.2f}")
            st.metric("Actual margin (%)", f"{actual_margin_pct:,.1f}%")

        # -------- Parts list: Extrusions --------
        st.subheader("Extrusion Parts List")

        ext_rows = []
        for part in extrusion_parts:
            ext_rows.append({
                "Description": part["description"],
                "Profile": part["profile"],
                "Length (mm)": part["length_mm"],
                "Length (in)": round(part["length_in"], 2),
                "Quantity": part["quantity"],
                "Unit price ($)": round(part["unit_price"], 2),
                "Line total ($)": round(part["line_total"], 2),
            })
        st.table(ext_rows)

        # -------- Parts list: Steel --------
        st.subheader("Steel Frame Parts List")

        steel_rows = []
        for part in steel_parts:
            steel_rows.append({
                "Description": part["description"],
                "Size": part["size"],
                "Length (in)": round(part["length_in"], 2),
                "Length (ft)": round(part["length_ft"], 3),
                "Quantity": part["quantity"],
            })
        st.table(steel_rows)

        st.markdown(
            f"**Total steel length:** "
            f"{sum(p['length_ft'] * p['quantity'] for p in steel_parts):.3f} ft  \n"
            f"**Steel cost (@ ${steel_price_per_ft:.2f}/ft):** ${steel_cost:,.2f}"
        )

        # -------- Donor kit --------
        st.subheader("Donor Kit / Other Major Components")

        donor_rows = [{
            "Item": "Amazon donor CNC kit (electronics, motors, wiring, plates, etc.)",
            "Cost ($)": round(donor_cost, 2),
        }, {
            "Item": "Misc Electronics",
            "Cost ($)": round(MISC_ELECTRONICS_COST, 2),
        }]
        if plasma_unit_cost > 0:
            donor_rows.append({
                "Item": f"Plasma unit: {plasma_unit_name}",
                "Cost ($)": round(plasma_unit_cost, 2),
            })
        st.table(donor_rows)

        st.info(
            "You can reuse some of the donor kit's original extrusions in reality, "
            "which will reduce your true cost and increase profit. "
            "This tool assumes you're buying the listed extrusions new for a conservative estimate."
        )

        # Store quote data for PDF generation
        st.session_state.quote_data = {
            "customer_name": customer_name if customer_name else "Customer",
            "config_name": config.name,
            "actual_x_ft": actual_x_ft,
            "actual_y_ft": actual_y_ft,
            "sell_price": sell_price,
        }

        # PDF Quote Generation
        st.subheader("Generate PDF Quote")
        if customer_name:
            pdf_bytes = generate_quote_pdf(
                customer_name=customer_name,
                config_name=config.name,
                actual_x_ft=actual_x_ft,
                actual_y_ft=actual_y_ft,
                sell_price=sell_price,
            )
            # Sanitize filename - remove or replace invalid characters
            safe_filename = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in customer_name)
            safe_filename = safe_filename.replace(' ', '_')
            st.download_button(
                label="Download PDF Quote",
                data=pdf_bytes,
                file_name=f"Quote_{safe_filename}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
            )
        else:
            st.info("Please enter a customer name above to generate a PDF quote.")


if __name__ == "__main__":
    main()
