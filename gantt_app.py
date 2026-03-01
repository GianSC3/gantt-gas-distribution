import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Industrial Gas Distribution – Gantt", layout="wide")
st.title("🏭 Industrial Gas Distribution – Delivery Gantt Chart")
st.markdown("Upload the **Trips Report CSV** from the simulation model to visualize the delivery schedule.")

# ── File uploader ─────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader("📂 Upload Trips Report (CSV)", type=["csv"])

if uploaded_file is None:
    st.info("Please upload a CSV file to get started.")
    st.stop()

# ── Load & parse CSV ──────────────────────────────────────────────────────────
try:
    raw = uploaded_file.read().decode("utf-8")
    lines = raw.splitlines()
    parsed = []
    for line in lines:
        line = line.rstrip(",")
        if line.strip() == "":
            continue
        parsed.append(line)
    content = "\n".join(parsed)
    df = pd.read_csv(
        io.StringIO(content),
        header=0,
        names=["Route","Truck","Customer","Amount","PlannedDelivery",
               "DeliveryGap","LevelBefore","LevelAfter",
               "TripStart","ArrivalCustomer","EndOfRoute"],
        usecols=range(11)
    )
except Exception as e:
    st.error(f"Error reading file: {e}")
    st.stop()

# ── Clean data ────────────────────────────────────────────────────────────────
df["Customer"]        = df["Customer"].astype(str).str.strip()
df["Truck"]           = pd.to_numeric(df["Truck"],           errors="coerce")
df["Amount"]          = pd.to_numeric(df["Amount"],          errors="coerce")
df["TripStart"]       = pd.to_numeric(df["TripStart"],       errors="coerce")
df["ArrivalCustomer"] = pd.to_numeric(df["ArrivalCustomer"], errors="coerce")
df["EndOfRoute"]      = pd.to_numeric(df["EndOfRoute"],      errors="coerce")
df = df.dropna(subset=["Truck","TripStart"])

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Filters")
all_trucks = sorted(df["Truck"].dropna().unique().astype(int).tolist())
sel_trucks = st.sidebar.multiselect("Trucks to display", all_trucks, default=all_trucks)

total_hours = int(df["EndOfRoute"].max() or 720)

st.sidebar.markdown("---")
st.sidebar.markdown("**Initial view window**")
view_end = st.sidebar.number_input(
    "Show first N hours on load", 
    min_value=24, max_value=total_hours, value=200, step=24
)

df_f = df[df["Truck"].isin(sel_trucks)].copy()

# ── Color palette ─────────────────────────────────────────────────────────────
PALETTE_DELIVERY = [
    "#1565C0","#C62828","#2E7D32","#E65100","#6A1B9A",
    "#00838F","#AD1457","#558B2F","#4E342E","#37474F",
]
PALETTE_RETURN = [
    "#90CAF9","#EF9A9A","#A5D6A7","#FFCC80","#CE93D8",
    "#80DEEA","#F48FB1","#C5E1A5","#BCAAA4","#B0BEC5",
]

truck_color_delivery = {t: PALETTE_DELIVERY[i % len(PALETTE_DELIVERY)] for i, t in enumerate(all_trucks)}
truck_color_return   = {t: PALETTE_RETURN[i   % len(PALETTE_RETURN)]   for i, t in enumerate(all_trucks)}

# ── Y-axis order: Plant first, then Customers 1-14 ────────────────────────────
customers_in_data = df_f["Customer"].unique().tolist()
numeric_customers = sorted(
    [c for c in customers_in_data if c.lower() != "plant"],
    key=lambda x: int(x) if x.isdigit() else 999
)
y_labels = ["Plant"] + [f"Customer {c}" for c in numeric_customers]
y_index  = {label: i for i, label in enumerate(y_labels)}

def get_y_label(customer_val):
    v = str(customer_val).strip()
    if v.lower() == "plant":
        return "Plant"
    return f"Customer {v}"

# ── Build figure ──────────────────────────────────────────────────────────────
fig = go.Figure()

# ── Color constants (defined here so grid lines can use them) ─────────────────
FONT_COLOR  = "#1a1a1a"      # near-black for all labels
GRID_COLOR  = "#d0d0d0"
PLOT_BG     = "#fafafa"

# One invisible trace per truck for the legend
for truck in all_trucks:
    if truck in sel_trucks:
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(size=12, color=truck_color_delivery[truck], symbol="square"),
            name=f"Truck {truck}",
            showlegend=True
        ))

# ── Manual grid lines (drawn BEFORE bars so bars appear on top) ───────────────

# Vertical lines every 24 h (X axis grid)
for h in range(0, total_hours + 1, 24):
    fig.add_shape(
        type="line",
        x0=h, x1=h,
        y0=-0.5, y1=len(y_labels) - 0.5,
        line=dict(color=GRID_COLOR, width=1),
        layer="below",               # ← BELOW everything, including bars
    )

# Horizontal lines between rows (Y axis grid)
for y_pos in range(len(y_labels)):
    fig.add_shape(
        type="line",
        x0=0, x1=total_hours,
        y0=y_pos + 0.5, y1=y_pos + 0.5,
        line=dict(color=GRID_COLOR, width=1),
        layer="below",               # ← BELOW everything, including bars
    )

# ── Draw bars ─────────────────────────────────────────────────────────────────
for _, row in df_f.iterrows():
    truck    = int(row["Truck"])
    customer = str(row["Customer"]).strip()
    is_plant = customer.lower() == "plant"
    y_label  = get_y_label(customer)

    t_start = row["TripStart"]
    t_end   = row["ArrivalCustomer"] if not is_plant else row["EndOfRoute"]

    if pd.isna(t_start) or pd.isna(t_end):
        continue
    if t_start >= t_end:
        continue

    # Enforce x >= 0
    t_start = max(t_start, 0)
    t_end   = max(t_end,   0)

    bar_color = truck_color_return[truck] if is_plant else truck_color_delivery[truck]

    label_text = ""
    if not is_plant and pd.notna(row["Amount"]):
        label_text = f"{row['Amount']:.2f}"

    hover = (
        f"<b>Truck {truck}</b><br>"
        f"{'Plant (return)' if is_plant else f'Customer {customer}'}<br>"
        f"Start: {t_start:.2f} h<br>"
        f"End: {t_end:.2f} h<br>"
        f"Duration: {t_end - t_start:.2f} h"
        + (f"<br>Amount delivered: {row['Amount']:.2f}" if not is_plant else "")
    )

    y_pos = y_index[y_label]

    # Bar rectangle – drawn BELOW annotations (layer="below")
    fig.add_shape(
        type="rect",
        x0=t_start, x1=t_end,
        y0=y_pos - 0.38, y1=y_pos + 0.38,
        fillcolor=bar_color,
        line=dict(color="white", width=1),
        layer="below"       # ← grid lines go on top of this but below annotations
    )

    # Amount label inside bar (above grid lines)
    if label_text:
        fig.add_annotation(
            x=(t_start + t_end) / 2,
            y=y_pos,
            text=label_text,
            showarrow=False,
            font=dict(color="white", size=10, family="Arial Black"),
            xanchor="center",
            yanchor="middle",
            bgcolor="rgba(0,0,0,0)",   # transparent bg so bar colour shows
            borderpad=0,
        )

    # Invisible scatter for hover tooltip
    fig.add_trace(go.Scatter(
        x=[(t_start + t_end) / 2],
        y=[y_pos],
        mode="markers",
        marker=dict(size=0, opacity=0),
        hovertext=hover,
        hoverinfo="text",
        showlegend=False
    ))


fig.update_layout(
    title=dict(
        text="Delivery Schedule – Gantt Chart",
        font=dict(size=20, color=FONT_COLOR, family="Arial"),
        x=0.0,
    ),
    xaxis=dict(
        title=dict(text="Time (hours)", font=dict(size=14, color=FONT_COLOR)),
        range=[0, view_end],            # ← Initial window set by sidebar
        minallowed=0,                   # ← Hard block: cannot scroll past 0
        maxallowed=total_hours,         # ← Hard block: cannot scroll past total
        rangeslider=dict(
            visible=True,
            thickness=0.05,
            bgcolor="#e8f0fe",
        ),
        showgrid=False,
        gridcolor=GRID_COLOR,
        gridwidth=1,
        dtick=24,
        tickfont=dict(size=11, color=FONT_COLOR),
        fixedrange=False,
        layer="above traces",           # ← Grid lines render ABOVE bar shapes
    ),
    yaxis=dict(
        tickvals=list(y_index.values()),
        ticktext=list(y_index.keys()),
        autorange="reversed",
        showgrid=False,
        gridcolor=GRID_COLOR,
        gridwidth=1,
        tickfont=dict(size=12, color=FONT_COLOR),
        layer="above traces",           # ← Grid lines render ABOVE bar shapes
        fixedrange=True,                # ← Y axis doesn't zoom (only X does)
    ),
    height=max(500, 52 * len(y_labels) + 180),
    plot_bgcolor=PLOT_BG,
    paper_bgcolor="white",
    legend=dict(
        title=dict(text="Trucks", font=dict(color=FONT_COLOR, size=13)),
        orientation="v",
        x=1.01, y=1,
        font=dict(color=FONT_COLOR, size=12),
    ),
    margin=dict(l=140, r=160, t=80, b=80),
    hovermode="closest",
    # ── Default interaction mode = PAN ───────────────────────────────────────
    dragmode="pan",
    modebar=dict(
        orientation="v",
        bgcolor="rgba(255,255,255,0.85)",
        color="#444444",
        activecolor="#1565C0",
    ),
)

# ── Modebar buttons: Pan first, then zoom tools ───────────────────────────────
config = dict(
    scrollZoom=True,            # scroll wheel zooms on X axis
    displayModeBar=True,
    modeBarButtonsToRemove=[
        "select2d", "lasso2d", "autoScale2d", "resetScale2d"
    ],
    modeBarButtonsToAdd=[],
    displaylogo=False,
    toImageButtonOptions=dict(
        format="png", filename="gantt_chart", scale=2
    ),
)

st.plotly_chart(fig, use_container_width=True, config=config)

# ── Raw data table ────────────────────────────────────────────────────────────
with st.expander("📋 View raw data table"):
    st.dataframe(df_f.reset_index(drop=True), use_container_width=True)

# ── Summary KPIs ──────────────────────────────────────────────────────────────
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)
deliveries = df_f[df_f["Customer"].str.lower() != "plant"]
col1.metric("Total Deliveries",        len(deliveries))
col2.metric("Trucks Active",           len(sel_trucks))
col3.metric("Unique Customers",        deliveries["Customer"].nunique())
col4.metric("Total Amount Delivered",  f"{deliveries['Amount'].sum():.2f}")