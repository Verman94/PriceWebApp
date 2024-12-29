import numpy as np
import pandas as pd
import streamlit as st

########################################################################################
def custom_round(value):
    steps = [(200, 10), (1000, 50), (5000, 100), (20000, 500), (100000, 1000)]
    for threshold, step in steps:
        if value < threshold:
            return np.ceil(value / step) * step
    return np.ceil(value / 5000) * 5000

#########################################################################################
# Test rounding function 
def test_round(value):

    """Rounds a number to a specific logic IRR:
        - Round to the nearest 50_000 if it is greater than 10,000,000
        - otherwise round to the nearest 10_000
    """
    if value >= 300_000:
        return np.ceil(value/10000)*10000
    return np.ceil(value/5000)*5000

##########################################################################################
def input_df(uploaded_file):
    """
    Reads and extracts data from the uploaded file.
    Returns a dictionary of dataframes for further processing.
    """
    
    if uploaded_file:
        # Define expected sheet names
        expected_sheets = {
            "Cost Centers": "Cost",
            "Aluminium Profile": "Al_profile",
            "IMP": "Imp_RM",
            "MH": "MH",
            "BOM": "BOM",
            "Shemsh": "Shemsh",
            "Dom-Short": "DOM_short",
            "Dom-All": "DOM_ALL",
            "Compare": "Adj"
        }

        # Dictionary to hold dataframes
        dataframes = {}
        
        try:
            # Read the uploaded file
            available_sheets = pd.ExcelFile(uploaded_file).sheet_names

            # Loop through expected sheets and load data
            for sheet_name, variable_name in expected_sheets.items():
                if sheet_name in available_sheets:
                    dataframes[variable_name] = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                else:
                    st.warning(f"Warning: Sheet '{sheet_name}' is missing in the uploaded file.")

            # Extract individual dataframes for further use
            Cost = dataframes.get("Cost")
            Al_profile = dataframes.get("Al_profile")
            Imp_RM = dataframes.get("Imp_RM")
            MH = dataframes.get("MH")
            BOM = dataframes.get("BOM")
            Shemsh = dataframes.get("Shemsh")
            DOM_short = dataframes.get("DOM_short")
            DOM_ALL = dataframes.get("DOM_ALL")
            Compare = dataframes.get("Adj")


        except Exception as e:
            st.error(f"An error occurred: {e}")
    else:
        st.info("Please upload an Excel file to proceed.")
    return Cost, Al_profile, Imp_RM, MH, BOM, Shemsh, DOM_short, DOM_ALL, Compare

##########################################################################################
def process_AlprofIMPRM(Al_profile, Imp_RM, euro_to_currency, nima, custom, ExpDuties):
    """
    Process Aluminium Profile and Imported Raw Material.
    """
    ##########
    # Perform calculations for Aluminium Profiles Imported Raw Material
    baseFees = Al_profile.columns[Al_profile.columns.str.contains("پايه", case=False, na=False)]
    Al_profile["Total"] = Al_profile[baseFees].mul(Al_profile["وزن"], axis=0).sum(axis=1)
    
    # Example: Currency Conversion
    currency_to_euro = {key: 1 / value for key, value in euro_to_currency.items()}
    Imp_RM["Euro Cost"] = Imp_RM["Cost"] * Imp_RM["Currency"].map(currency_to_euro)
 
    # Determine Euro Cost for Megalit and VSG then find IRR
    # Commission Megalite and VS.G from Euro price
    Imp_RM["MEG Cost"] = Imp_RM["MEG Commission Percentage"] * Imp_RM["Euro Cost"] +  Imp_RM["Euro Cost"]
    Imp_RM["VS.G Cost"] = Imp_RM["VS.G Commission Percentage"] * Imp_RM["MEG Cost"] +  Imp_RM["MEG Cost"]

    # Convert Vsg cost to IRR without Customs
    Imp_RM["IRR Cost"] =  Imp_RM["VS.G Cost"] * euro_to_currency['USD'] * nima

    # Custom duties and export
    Imp_RM["Domestic Custom Duties"] =  Imp_RM["VS.G Cost"] * euro_to_currency['USD'] * Imp_RM["Tariff Percentage"] * custom
    Imp_RM["Export Custom Duties"] =  Imp_RM["VS.G Cost"] * euro_to_currency['USD'] * ExpDuties / 100 * custom

    # IRR Cost with Customs
    Imp_RM["Domestic Cost"] = Imp_RM["Domestic Custom Duties"] + Imp_RM["IRR Cost"]

    # Apply rounding for IRR Cost with Customs
    Imp_RM["Final Domestic Cost"] = Imp_RM["Domestic Cost"].apply(custom_round)

    return Al_profile, Imp_RM

################################################################################################
def process_bom(Al_profile, Imp_RM, Shemsh, Cost, BOM, MH, DomesticRM):
    """
    Process BOM and Man Hour file.
    """
    # Example: BOM Calculation
    # Example merge: Ensure column names in the source dataframes match
    BOM = BOM.merge(Al_profile[['Part No', 'Total']], how='left', left_on='PART NO', right_on='Part No', suffixes=('', '_aluminium'))
    BOM = BOM.merge(Imp_RM[['Part No', 'Final Domestic Cost']], how='left', left_on='PART NO', right_on='Part No', suffixes=('', '_imp'))
    BOM = BOM.merge(Shemsh[['Part No', 'Est Mtr Cost']], how='left', left_on='PART NO', right_on='Part No', suffixes=('', '_shemsh'))

    BOM['Material Cost'] = BOM['Total'].fillna(0) + BOM['Final Domestic Cost'].fillna(0) + BOM['Est Mtr Cost'].fillna(0)
    DropCols = ['Part No', 'Part No_aluminium', 'Part No_imp', 'Part No_shemsh', 'Total', 'Final Domestic Cost', 'Est Mtr Cost']
    BOM.drop(columns=DropCols, inplace=True, errors='ignore')
    BOM['ESTIMATED MATERIAL COST'] = BOM['ESTIMATED MATERIAL COST'] * (1 + DomesticRM / 100.0)
    BOM['Material Cost'] = BOM['Material Cost'].where(BOM['Material Cost'] != 0, BOM['ESTIMATED MATERIAL COST'])

    BOM['Total Component Cost'] = BOM['Material Cost'] * BOM['CUMM QTY PER ASSEMBLY']

    # Calculate Labor Cost and Man Hour
    dropCols = ['Cost Center Description']
    MH = pd.merge(MH, Cost, on='Cost Center', how='left').drop(columns=dropCols)

    MH["Man_Hour"] = ((1 / MH["RUN FACTOR"]) + (MH[" SETUP TIME"]/MH["STD LOT SIZE"])) * MH["QTY"] * MH["CREW SIZE"]
    # MH["Labor Cost -OLD"] = MH["Man_Hour"] * OLDlaborRate
    # MH['Labor Cost -NEW'] = MH['Man_Hour'] * MH['Est Labor Cost']
    # MH['Diff'] = MH['Labor Cost -NEW'] - MH["Labor Cost -OLD"]
    return BOM, MH

################################################################################################
def process_DOM_ALL(BOM, MH, DOM_ALL, OverHead_Rates, OLDlaborRate):
    """
    Mapping the Calculated Material Cost From BOM and and Labor Cost from MH to Dom ALL and calculate Finish cost
        - Material Cost
        - Labor Cost
        - OverHead Cost
    """
    ## DOM_ALL
    grp = MH.groupby('PART_NO')['Man_Hour'].sum().reset_index()
    DOM_ALL['Man_Hour'] = DOM_ALL['Part No.'].map(grp.set_index('PART_NO')['Man_Hour'])

    ###########
    Exceptions = ['31BB802000', '31BB803000', '31BB804000', '31BB805000']
    DOM_ALL.loc[DOM_ALL['Part No.'].isin(Exceptions) , 'Man_Hour'] = 0.1
    DOM_ALL['Man_Hour'] = DOM_ALL['Man_Hour'].fillna(0)
    ###########
    Galaxy = ['31CS009006', '31CS009007']
    DOM_ALL.loc[DOM_ALL['Part No.'].isin(Galaxy) , 'Man_Hour'] = DOM_ALL.loc[1213 , 'Man_Hour']
    ##########

    DOM_ALL['Labor Cost'] = DOM_ALL['Man_Hour'] * OLDlaborRate
    DOM_ALL.drop(columns=['TOP LEVEL PART NO', 'Total Component Cost'], inplace=True, errors='ignore')  

    grp2 = BOM.groupby('TOP LEVEL PART NO')['Total Component Cost'].sum().reset_index()
    DOM_ALL = DOM_ALL.merge(grp2, how='left', left_on='Part No.', right_on='TOP LEVEL PART NO')
    DOM_ALL['Material Cost'] = DOM_ALL['Total Component Cost']  # Raw Material plus semi-finished
    DOM_ALL.drop(columns=['TOP LEVEL PART NO', 'Total Component Cost'], inplace=True, errors='ignore')   

    filtered_bom = BOM[BOM['TEMPLATE ID'] == 'RM']
    grp3 = filtered_bom.groupby('TOP LEVEL PART NO')['Total Component Cost'].sum().reset_index()
    DOM_ALL = DOM_ALL.merge(grp3, how='left', left_on='Part No.', right_on='TOP LEVEL PART NO')
    DOM_ALL['Raw Material Cost'] = DOM_ALL['Total Component Cost']
    DOM_ALL.drop(columns=['TOP LEVEL PART NO', 'Total Component Cost'], inplace=True, errors='ignore')   
    DOM_ALL['MOH'] = DOM_ALL['Raw Material Cost'] * OverHead_Rates['MOH'] / 100

    # MOH for Explosion Proof and Fanal barchasb set to zero
    # make type of part no column as string for searching effectivly
    Copy_DOM_ALL = DOM_ALL.copy()
    Copy_DOM_ALL['Part No.'] = Copy_DOM_ALL['Part No.'].astype(str)
    Copy_DOM_ALL.loc[Copy_DOM_ALL['Part No.'].str.startswith('34'), 'MOH'] = 0
    # Fanal Barchasb changes
    Copy_DOM_ALL.loc[Copy_DOM_ALL['Part No.']=='3129814000', 'MOH'] = 0
    DOM_ALL['MOH'] = Copy_DOM_ALL['MOH']
    #####################################

    DOM_ALL['LAB'] = DOM_ALL['Man_Hour'] * OverHead_Rates['LAB'] + OverHead_Rates['LABSU2'] * OverHead_Rates['LAB'] * DOM_ALL['Man_Hour'] / 100 + \
        DOM_ALL['Labor Cost'] * OverHead_Rates['LABSU1'] / 100
    DOM_ALL['Overhead Cost'] = DOM_ALL['Depr.'] + DOM_ALL['Machin'] + DOM_ALL['LAB'] + DOM_ALL['MOH']
    DOM_ALL['Finished Cost'] = DOM_ALL['Material Cost'] + DOM_ALL['Overhead Cost'] + DOM_ALL['Labor Cost']

    # Return processed DataFrames
    return DOM_ALL

########################################################################################################
def compare(Compare, DOM_ALL, price_type):

    ## Compare Adjustments
    # Diff component part 1 price with component part 2 price plus the increase or decreased price
    Compare['Diff Component Part 2 and 1'] = Compare['Component Part 1'].map(DOM_ALL.set_index('Part No.')[price_type]) - \
        Compare['Component Part 2'].map(DOM_ALL.set_index('Part No.')[price_type])
    

    # Compare['Increase or Decrease Price'] =  0
    # Compare['Diff Component Part 2 and 1'] = Compare['Component Part 1'].map(DOM_ALL.set_index('Part No.')[price_type]) - \
    #     Compare['Component Part 2'].map(DOM_ALL.set_index('Part No.')[price_type]) \
    #      - Compare['Component Part 2'].map(Compare.set_index('Component Part 1')['Increase or Decrease Price'])


    Compare['Diff Super Component Part 2 and 1'] = Compare['Super Component 1'].map(Compare.set_index('Component Part 1')['Diff Component Part 2 and 1'])

    Compare['Increase or Decrease Price'] =  Compare['Diff Super Component Part 2 and 1'] - Compare['Diff Component Part 2 and 1']
    
    # Pricing After Compare Adjustments
    DOM_ALL[price_type] += DOM_ALL['Part No.'].map(Compare.set_index('Component Part 1')['Increase or Decrease Price']).fillna(0)
    # Common Parts
    cond1 = (DOM_ALL['Price List Type']=="Common Parts")
    cond4 = (DOM_ALL[price_type] <= DOM_ALL[" Old Base Prices (IRR)"])
    DOM_ALL.loc[cond1 & cond4, price_type] = DOM_ALL[" Old Base Prices (IRR)"]

    return DOM_ALL

########################################################################################################
def UpdateBasePrice(DOM_ALL, DOM_short, method, Compare, RepCom, VAT, CommonPartPriceCriteria, CommonPartCoeff):
    """
    Calculation of short list products price with Mani Algorithm then perform adjustments 
    based on compare method and finnaly updating the DOM_ALL dataFrame.
    """
    ## DOM Short
    DOM_short['Finished Cost'] = DOM_short['Part No.'].map(DOM_ALL.set_index('Part No.')['Finished Cost'])
    DOM_short[' Old Base Prices (IRR)'] = DOM_short['Part No.'].map(DOM_ALL.set_index('Part No.')[' Old Base Prices (IRR)'])
    DOM_short['Old Finished Cost With Comp.'] = DOM_short['Part No.'].map(DOM_ALL.set_index('Part No.')['Old Finished Cost With Comp.'])

    # Calculating Old Gross
    NoVATOLDPrice = (1-(RepCom/100)) * DOM_short[' Old Base Prices (IRR)'] / (1 + VAT / 100)
    DOM_short['Old_Gross'] = (NoVATOLDPrice - DOM_short['Old Finished Cost With Comp.'] ) / (NoVATOLDPrice) * 100
    # DOM_short['Old_Gross'] = round(DOM_short['Old_Gross'], 2)

    # Create a mapping from 'Part No.' to 'Old Base Prices (IRR)'
    price_map = DOM_short.set_index('Part No.')[' Old Base Prices (IRR)']

    # Use the 'Super Base Part' to map the corresponding 'Old Base Prices (IRR)' from the price_map 
    # OLD Base price for the super base parts
    DOM_short['Matching Price'] = DOM_short['Super Base Part'].map(price_map)

    # Calculate the 'Coefficient' in a vectorized manner
    DOM_short['Coefficient'] = (DOM_short[' Old Base Prices (IRR)'] / DOM_short['Matching Price']) * 100
    DOM_short.drop(columns='Matching Price', inplace=True, errors='ignore')

    if (method == 'Original Price'):
        # Original Price is the new base price for super base parts
        Original_price_map = DOM_short.set_index('Part No.')['Original Price (IRR)']
        mapped = pd.to_numeric(DOM_short['Super Base Part'].map(Original_price_map), errors='coerce')
        DOM_short['Rough Price'] = mapped * DOM_short['Coefficient'] / 100
        #DOM_short['Rough Price'] = DOM_short['Rough Price'].astype(int)    

        # New Gross Calculation
        NoVATRoughPrice = (DOM_short['Rough Price'] / (1 + VAT / 100))
        DOM_short['New_Gross'] = ((1-(RepCom/100)) * NoVATRoughPrice - DOM_short['Finished Cost'] ) / (NoVATRoughPrice) * 100

        # Updating Dom_short base price Including VAT (IRR)
        DOM_short["Base Price Including VAT (IRR)"] = DOM_short['Finished Cost'] * (1 + VAT / 100) / (((100 - RepCom)- DOM_short['New_Gross'])/100)
        # Rounding will get the results closer tosource but by changing original price we will be under valuing by a 10000 irr supposably.
        # DOM_short["Base Price Including VAT (IRR)"] = np.ceil(round(DOM_short["Base Price Including VAT (IRR)"] / 10000)) * 10000
        DOM_short["Base Price Including VAT (IRR)"] = np.ceil(DOM_short["Base Price Including VAT (IRR)"] / 10000) * 10000
        DOM_short["Base Price Change (%)"] = (DOM_short["Base Price Including VAT (IRR)"] - DOM_short[' Old Base Prices (IRR)']) /  DOM_short[' Old Base Prices (IRR)'] * 100

    elif (method == 'New Gross'):
        DOM_short["Base Price Including VAT (IRR)"] = DOM_short['Finished Cost'] * (1 + VAT / 100) / (((100 - RepCom)- DOM_short['New_Gross'])/100)
        DOM_short["Base Price Including VAT (IRR)"] = np.ceil(DOM_short["Base Price Including VAT (IRR)"] / 10000) * 10000
        DOM_short["Base Price Change (%)"] = (DOM_short["Base Price Including VAT (IRR)"] - DOM_short[' Old Base Prices (IRR)']) /  DOM_short[' Old Base Prices (IRR)'] * 100

    elif (method == "Price Diff"):
        DOM_short["Base Price Including VAT (IRR)"] = (1 + DOM_short["Base Price Change (%)"] / 100) * DOM_short[' Old Base Prices (IRR)']
        DOM_short["Base Price Including VAT (IRR)"] = np.ceil(DOM_short["Base Price Including VAT (IRR)"] / 10000) * 10000
        # New Gross Calculation
        NoVATRoughPrice = (DOM_short["Base Price Including VAT (IRR)"] / (1 + VAT / 100))
        DOM_short['New_Gross'] = ((1-(RepCom/100)) * NoVATRoughPrice - DOM_short['Finished Cost'] ) / (NoVATRoughPrice) * 100
        # Updating Original Price
        DOM_short['Orig'] = DOM_short["Base Price Including VAT (IRR)"] / (DOM_short['Coefficient'] / 100)
        # Update Original Price (IRR) only where Coefficient is 100
        DOM_short.loc[DOM_short['Coefficient'] == 100, 'Original Price (IRR)'] = DOM_short['Orig']

        # Drop the 'Orig' column after the update
        DOM_short.drop(columns='Orig', inplace=True, errors='ignore')


    ## Set Prices For all products based on the short list pricing algorithm in DOM_ALL
    DOM_ALL["Base Price Including VAT (IRR)"] = DOM_ALL['Part No.'].map(DOM_short.set_index('Part No.')['Base Price Including VAT (IRR)']).fillna(0) \
    + DOM_ALL['Base Part'].map(DOM_short.set_index('Part No.')['Base Price Including VAT (IRR)']).fillna(0)

    ## Common Parts Fix Rounding
    cond1 = (DOM_ALL['Price List Type']=="Common Parts")
    cond2 = (DOM_ALL['Finished Cost'] < CommonPartPriceCriteria)
    cond3 = (DOM_ALL['Finished Cost'] > CommonPartPriceCriteria)

    DOM_ALL.loc[cond1 & cond3, 'Base Price Including VAT (IRR)'] = np.ceil(DOM_ALL['Finished Cost'] / CommonPartCoeff / 100000) * 100000
    DOM_ALL.loc[cond1 & cond2, 'Base Price Including VAT (IRR)'] = np.ceil(DOM_ALL['Finished Cost'] / CommonPartCoeff / 5000) * 5000

    DOM_ALL["Base Price Including VAT (IRR)"] = DOM_ALL["Base Price Including VAT (IRR)"].astype(int)

    ## Compare Function Call to Adjust prices
    DOM_ALL = compare(Compare, DOM_ALL, price_type='Base Price Including VAT (IRR)')

    # New & Old Gross in DOM ALL
    NoVATOLDPriceAll = (1-(RepCom/100)) * DOM_ALL[' Old Base Prices (IRR)'] / (1 + VAT / 100)
    DOM_ALL['Old_Gross'] = (NoVATOLDPriceAll - DOM_ALL['Old Finished Cost With Comp.'] ) / (NoVATOLDPriceAll) * 100
    #DOM_ALL['Old_Gross'] = round(DOM_ALL['Old_Gross'], 2)


    NoVATNewPriceAll = (DOM_ALL["Base Price Including VAT (IRR)"] / (1 + VAT / 100))
    DOM_ALL['New_Gross'] = ((1-(RepCom/100)) * NoVATNewPriceAll - DOM_ALL['Finished Cost'] ) / (NoVATNewPriceAll) * 100
    #DOM_ALL['New_Gross'] = round(DOM_ALL['New_Gross'], 2)

    # Price Change
    DOM_ALL["Base Price Change (%)"] = (DOM_ALL["Base Price Including VAT (IRR)"] - DOM_ALL[' Old Base Prices (IRR)']) /  DOM_ALL[' Old Base Prices (IRR)'] * 100
    #DOM_ALL["Base Price Change (%)"] = round(DOM_ALL["Base Price Change (%)"], 1)

    return DOM_short, DOM_ALL

########################################################################################################
def Calc_Side_Prices(DOM_ALL, Sales_Percent, Compare, price_type):
    
    cond = (DOM_ALL['Model']== 'ضد انفجار')

    if (price_type=='End-User Price Including VAT (IRR)'):
    
        old_price_type = 'Base Price Including VAT (IRR)'
        DOM_ALL[price_type] = DOM_ALL[old_price_type] * Sales_Percent["End_User_DOM_All"]
        DOM_ALL.loc[cond, price_type] = DOM_ALL[old_price_type] * Sales_Percent["End_User_DOM_Explosion"]
 
    elif (price_type=='Electrical Shops (IRR)'):
        old_price_type = 'End-User Price Including VAT (IRR)'
        DOM_ALL[price_type] = DOM_ALL[old_price_type] * Sales_Percent["Electrical_All"]
        DOM_ALL.loc[cond, price_type] = DOM_ALL[old_price_type] * Sales_Percent["Electrical_Explosion"]

    elif(price_type=='Wholesales Price Including VAT (IRR)'):
        old_price_type = 'End-User Price Including VAT (IRR)'
        DOM_ALL[price_type] = DOM_ALL[old_price_type] * Sales_Percent["Wholesales"]
    
    
    # Rounding and adjustments of the price
    DOM_ALL[price_type] = DOM_ALL[price_type].apply(test_round)
    DOM_ALL = compare(Compare, DOM_ALL, price_type)
    

    return DOM_ALL