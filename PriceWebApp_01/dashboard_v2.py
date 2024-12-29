import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, ColumnsAutoSizeMode

import pandas as pd
import calculations_v2 as calc

try:
    st.set_page_config(layout="wide")
except:
    pass

# st.header("Pricing Session")

# Sidebar Tabs for Input Parameters
st.sidebar.title("Input Parameters")
tabs = st.sidebar.tabs(["General", "Currency", "Overheads", "Sales Rates", "Others"])

with tabs[0]:
    uploaded_file = st.file_uploader("Upload Input File (Excel)", type=["xlsx"])
    ## Choose Update Method 
    options = ["Original Price", "New Gross", "Price Diff"]
    selected_option = st.selectbox("Choose the Pricing Method:", options)
    up_butt = st.sidebar.button("Update Table") # Update table
    show_extras = st.sidebar.checkbox("Extras", value=False)    # Sidebar toggle buttons to show/hide columns
    show_freez = st.sidebar.checkbox("Freez Part No & Desc", value=False)

with tabs[1]:
    nima = st.number_input("Dollar NIMA (IRR):", value=680000)
    custom = st.number_input("Dollar Custom (IRR):", value=300000)
    euro_to_currency = {
        "USD": st.number_input("Euro to USD", value=1.10, step=0.01, format="%.2f"),
        "AED": st.number_input("Euro to AED", value=4.054, step=0.001, format="%.3f"),
        "EUR": 1.0,
    }
    ExpDuties = st.number_input("Custom Export Duties Percentage (%)", value=2.5)

with tabs[2]:
    OLDlaborRate = st.number_input("Labor Rate (IRR):", value=2300000)
    OverHead_Rates = {
        "MOH": st.number_input("MOH (%)", value=1.2),
        "LAB": st.number_input("LAB (IRR)", value=282000),
        "LABSU1": st.number_input("LABSU1 (%)", value=27.8),
        "LABSU2": st.number_input("LABSU2 (%)", value=22.9),
    }

with tabs[3]:
    vat = st.number_input("Value Added Tax (%)", value=10)
    RepCom = st.number_input("Representative Commission (%)", value=5)
    Sales_Percent = {
        "End_User_DOM_All": st.number_input("End-User DOM All Luminaires (%)", value=1.22, format="%.3f"),
        "End_User_DOM_Explosion": st.number_input("End-User DOM Explosion Proof (%)", value=1.175, format="%.3f"),
        "End_User_Turkey": st.number_input("End-User Turkey (%)", value=3.85, format="%.3f"),
        "End_User_Iraq_Armenia_Afghan": st.number_input("End-User Iraq Armenia Afghanistan (%)", value=1.4, format="%.2f"),
        "Electrical_All": st.number_input("Electrical All Luminaires (%)", value=0.895, format="%.3f"),
        "Electrical_Explosion": st.number_input("Electrical Explosion Proof (%)", value=0.925, format="%.3f"),
        "Wholesales": st.number_input("Wholesales (%)", value=0.94, format="%.3f"),
    }

with tabs[4]:
    DomesticRM = st.number_input("Domestic Raw Material Increase (%)", value=0)
    CommonPartPriceCriteria = st.number_input("Price Criteria for Rounding Common Parts (IRR):", value=900000)
    CommonPartCoeff = st.number_input("Coefficient for Common Parts Price:", value=0.55, format="%.2f")

# Getting the data as cache
@st.cache_data
def getdata(uploaded_file):
    # Input DataFrame
    Cost, Al_profile, Imp_RM, MH, BOM, Shemsh, DOM_short, DOM_ALL, Compare = calc.input_df(uploaded_file)
    return Cost, Al_profile, Imp_RM, MH, BOM, Shemsh, DOM_short, DOM_ALL, Compare

# Calculation of Finish Cost
def FinishCostUp(Al_profile, Imp_RM, BOM, MH, Shemsh, Cost, DOM_ALL, euro_to_currency, nima, custom, ExpDuties, DomesticRM, OverHead_Rates, OLDlaborRate):

    Al_profile, Imp_RM = calc.process_AlprofIMPRM(Al_profile, Imp_RM, euro_to_currency, nima, custom, ExpDuties)
    BOM, MH = calc.process_bom(Al_profile, Imp_RM, Shemsh, Cost, BOM, MH, DomesticRM) # BOM MH Update
    DOM_ALL = calc.process_DOM_ALL(BOM, MH, DOM_ALL, OverHead_Rates, OLDlaborRate) # Collecting all and Finish Cost calculation

    return DOM_ALL

# Update prices
def UpdatePricing(DOM_ALL, DOM_short, Compare, RepCom, vat, CommonPartPriceCriteria, CommonPartCoeff, Sales_Percent):

    # Call to Update DOM_short and DOM_ALL with Mani algorithm
    DOM_short, DOM_ALL = calc.UpdateBasePrice(DOM_ALL, DOM_short, selected_option, Compare, RepCom, vat, CommonPartPriceCriteria, CommonPartCoeff)

    # Call to Calculate Other Users Prices in Dom-all
    DOM_ALL = calc.Calc_Side_Prices(DOM_ALL, Sales_Percent, Compare, price_type='End-User Price Including VAT (IRR)')
    DOM_ALL = calc.Calc_Side_Prices(DOM_ALL, Sales_Percent, Compare, price_type='Electrical Shops (IRR)')
    DOM_ALL = calc.Calc_Side_Prices(DOM_ALL, Sales_Percent, Compare, price_type='Wholesales Price Including VAT (IRR)')

    # DOM_Short Update
    DOM_short = calc.Calc_Side_Prices(DOM_short, Sales_Percent, Compare, price_type='End-User Price Including VAT (IRR)')
    DOM_short = calc.Calc_Side_Prices(DOM_short, Sales_Percent, Compare, price_type='Electrical Shops (IRR)')
    DOM_short = calc.Calc_Side_Prices(DOM_short, Sales_Percent, Compare, price_type='Wholesales Price Including VAT (IRR)')

    return DOM_ALL, DOM_short

if uploaded_file:
    # Input data
    
    Cost, Al_profile, Imp_RM, MH, BOM, Shemsh, DOM_short, DOM_ALL, Compare = getdata(uploaded_file) # Cache

    # Using session state to update price and save changes
    if 'data' not in st.session_state:
        st.session_state.data = DOM_short

    if 'All' not in st.session_state:
        st.session_state.All = DOM_ALL

    st.session_state.All = FinishCostUp(Al_profile, Imp_RM, BOM, MH, Shemsh, Cost, st.session_state.All, euro_to_currency, nima, custom, ExpDuties, DomesticRM, OverHead_Rates, OLDlaborRate)

    # Display DataFrames
    # Using AgGrid for better tables
    tabs = st.tabs(["DOM_Short","DOM_All", "test"])

    # Configure AG Grid
    gb = GridOptionsBuilder.from_dataframe(st.session_state.data)
    gb2 = GridOptionsBuilder.from_dataframe(st.session_state.All)

    gb.configure_default_column(filter=True)
    gb.configure_column("Original Price (IRR)", editable=True)
    gb.configure_column("New_Gross", editable=True)
    
    # Percentage Cols
    # Configure multiple columns with a formatter
    columns_to_format = ["Old_Gross", "New_Gross", "Base Price Change (%)"]
    for col in columns_to_format:
        if selected_option == "Original Price":
            gb.configure_column(
            col,
            type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
            # valueFormatter="x",
            valueFormatter="Math.abs(x).toFixed(2)",  # Set decimal places to 2 "x.toFixed(2)" for positive and Negetive only
            editable=False,
            )
            gb2.configure_column(
                col,
                type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                # valueFormatter="x",
                valueFormatter="Math.abs(x).toFixed(2)",
            )
        if selected_option == "New Gross":
            if col == "New_Gross":
                gb.configure_column(
                    col,
                    type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                    # valueFormatter="x",
                    valueFormatter="Math.abs(x).toFixed(2)",  # Set decimal places to 2 "x.toFixed(2)" for positive and Negetive only
                    editable=True,
                )
                gb2.configure_column(
                    col,
                    type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                    # valueFormatter="x",
                    valueFormatter="Math.abs(x).toFixed(2)",
                )
            else:
                gb.configure_column(
                    col,
                    type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                    # valueFormatter="x",
                    valueFormatter="Math.abs(x).toFixed(2)",  # Set decimal places to 2 "x.toFixed(2)" for positive and Negetive only
                    editable=False,
                    )
                gb2.configure_column(
                        col,
                        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                        # valueFormatter="x",
                        valueFormatter="Math.abs(x).toFixed(2)",
                    )
        if selected_option == "Price Diff":
            if col == "Base Price Change (%)":
                gb.configure_column(
                    col,
                    type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                    # valueFormatter="x",
                    valueFormatter="Math.abs(x).toFixed(2)",  # Set decimal places to 2 "x.toFixed(2)" for positive and Negetive only
                    editable=True,
                )
                gb2.configure_column(
                    col,
                    type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                    # valueFormatter="x",
                    valueFormatter="Math.abs(x).toFixed(2)",
                )
            else:
                    gb.configure_column(
                    col,
                    type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                    # valueFormatter="x",
                    valueFormatter="Math.abs(x).toFixed(2)",  # Set decimal places to 2 "x.toFixed(2)" for positive and Negetive only
                    editable=False,
                    )
                    gb2.configure_column(
                        col,
                        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                        # valueFormatter="x",
                        valueFormatter="Math.abs(x).toFixed(2)",
                    )
        # Formatting Price Columns
    # Columns that need formatting
    gb.configure_column(
        "Rough Price",
        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
        valueFormatter='Intl.NumberFormat("en-IR").format(x)',  # Format with commas
    )
    Pricecolumns_to_format = ["Old Finished Cost With Comp.", "Finished Cost", " Old Base Prices (IRR)", "Base Price Including VAT (IRR)", \
                               "Wholesales Price Including VAT (IRR)", "Electrical Shops (IRR)", "End-User Price Including VAT (IRR)"]
    for col in Pricecolumns_to_format:
        gb.configure_column(
            col,
            type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
            valueFormatter='Intl.NumberFormat("en-IR").format(x)',  # Format with commas
        )
        gb2.configure_column(
            col,
            type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
            valueFormatter='Intl.NumberFormat("en-IR").format(x)',  # Format with commas
        )

    # Configure SideBar to hide or show extras
    extraCols = ["كد كاتالوگ نهايي", "نوع عرضه", "تاريخ اجرا", "توضيحات", "Base Part", "Depr.", "Machin", "Man_Hour", "Labor Cost", "Super Base Part", \
                  "Coefficient", "Material Cost", "Raw Material Cost", "MOH", "LAB", "Overhead Cost"]
    
    for col in extraCols:
        gb.configure_column(col, hide=not show_extras)
        gb2.configure_column(col, hide=not show_extras)

    # Pinned Columns for easy understanding
    # pinnedCols = ["Price List Type", "Part No.", "Part Description", "Product Family", "Model"]
    pinnedCols = ["Part No.", "Part Description"]
    for col in pinnedCols:
        gb.configure_column(col, pinned=show_freez)
        gb2.configure_column(col, pinned=show_freez)

    # Fixing the problem of showing invalid number in some cases
    gb.configure_column("Part No.", valueFormatter="value ? value.toString() : ''")
    gb.configure_column("Super Base Part", valueFormatter="value ? value.toString() : ''")
    gb.configure_column("Base Price Including VAT (IRR)", editable=False)
    gb.configure_grid_options(enableRangeSelection=True)
    grid_options = gb.build()

    # Fixing the problem of showing invalid number in some cases
    gb2.configure_default_column(autoWidth=True, filter=True)
    gb2.configure_column("Part No.", valueFormatter="value ? value.toString() : ''")
    gb2.configure_column("Base Part", valueFormatter="value ? value.toString() : ''")
    gb2.configure_grid_options(enableRangeSelection=True)
    grid_options2 = gb2.build()





    with tabs[0]:
        grid_return = AgGrid(
            st.session_state.data,
            height=800,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.VALUE_CHANGED,
            theme='alpine',
            style={'font-size': '20px'},
            columns_auto_size_mode=ColumnsAutoSizeMode.FIT_ALL_COLUMNS_TO_VIEW,
        )

    with tabs[1]:
        grid_DOM_ALL = AgGrid(
            st.session_state.All,
            height=800,
            gridOptions=grid_options2,
            update_mode=GridUpdateMode.VALUE_CHANGED,
            theme='alpine',
            style={'font-size': '20px'},
            columns_auto_size_mode=ColumnsAutoSizeMode.FIT_ALL_COLUMNS_TO_VIEW,
        )

    with tabs[2]:
        st.write(grid_DOM_ALL.data)

    # Button to modify the dataframe
    if up_butt:
        updated_data = pd.DataFrame(grid_return.data)
        update_all = pd.DataFrame(grid_DOM_ALL.data)
        
        st.session_state.All, st.session_state.data = UpdatePricing(update_all, updated_data, Compare, RepCom, vat, CommonPartPriceCriteria, CommonPartCoeff, Sales_Percent)