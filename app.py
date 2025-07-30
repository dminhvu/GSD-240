import io
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="GSD-240: A2Z Flashing")
st.title("GSD-240: A2Z Flashing")


def process_file(file):
    # Read incoming file
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    elif file.name.lower().endswith((".xls", ".xlsx")):
        df = pd.read_excel(file)
    else:
        st.error("Unsupported file format. Please upload a CSV or Excel file.")
        return None

    if df.empty:
        st.error("The uploaded file is empty.")
        return None

    # Check for required columns (flexible matching)
    required_cols = {
        "customer": None,
        "order_number": None,
        "reference": None,
        "date": None,
        "amount": None,
    }

    # Find columns by matching common variations
    for col in df.columns:
        col_lower = col.lower().strip()
        if "customer" == col_lower:
            required_cols["customer"] = col
        elif "order nbr." == col_lower:
            required_cols["order_number"] = col
        elif "reference nbr." == col_lower:
            required_cols["reference"] = col
        elif "date" == col_lower:
            required_cols["date"] = col
        elif "amount" == col_lower:
            required_cols["amount"] = col

    # Check if all required columns are found
    missing_cols = [k for k, v in required_cols.items() if v is None]
    if missing_cols:
        st.error(f"Could not find the following required columns: {missing_cols}")
        st.write(
            "Please ensure your file contains columns for: Customer, Order Number, Reference, Date, and Amount"
        )
        return None

    # Create output DataFrame with required columns
    output = pd.DataFrame()

    # 1. Rename "Customer" column to "Debtor Reference" and move to Column A
    output["Debtor Reference"] = df[required_cols["customer"]]

    # 2. Add Transaction Type column into Column B (will be populated based on amount)
    # We'll populate this after processing the amount

    # 3. Create Document Number Column in Column C
    # Concatenate("O_", Order Number Column, "_", Reference Column)
    def create_document_number(row):
        order_num = (
            str(row[required_cols["order_number"]])
            if pd.notna(row[required_cols["order_number"]])
            else ""
        )
        reference = (
            str(row[required_cols["reference"]])
            if pd.notna(row[required_cols["reference"]])
            else ""
        )
        return f"O_{order_num}_{reference}"

    output["Document Number"] = df.apply(create_document_number, axis=1)

    # 4. Date -> Document Date in Column D, "DD/MM/YYYY" format
    def format_date(val):
        if pd.isna(val) or str(val).strip() == "":
            return ""

        # Try common date formats
        for fmt in (
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%d-%b-%Y",
            "%d %b %Y",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        ):
            try:
                return datetime.strptime(str(val), fmt).strftime("%d/%m/%Y")
            except:
                continue

        try:
            # Fallback to pandas
            parsed_date = pd.to_datetime(val, dayfirst=True, errors="coerce")
            if pd.notna(parsed_date):
                return parsed_date.strftime("%d/%m/%Y")
        except:
            pass

        return str(val)  # Return original if can't parse

    output["Document Date"] = df[required_cols["date"]].apply(format_date)

    # 5. Amount -> Document Balance in Column E, number format with 2 decimals
    def format_amount(val):
        try:
            # Clean the value by removing common currency symbols and formatting
            clean_val = (
                str(val)
                .replace("$", "")
                .replace(",", "")
                .replace("£", "")
                .replace("€", "")
                .strip()
            )
            if clean_val == "" or clean_val.lower() == "nan":
                return "0.00"
            return f"{float(clean_val):.2f}"
        except:
            return "0.00"

    output["Document Balance"] = df[required_cols["amount"]].apply(format_amount)

    # 2. Populate Transaction Type column based on amount (INV for positive, CRD for negative)
    def determine_transaction_type(balance_str):
        try:
            balance_val = float(balance_str)
            return "INV" if balance_val >= 0 else "CRD"
        except:
            return "INV"  # default

    output["Transaction Type"] = output["Document Balance"].apply(
        determine_transaction_type
    )

    # Filter out rows where essential data is missing
    output = output[
        (output["Debtor Reference"].notna())
        & (output["Debtor Reference"].astype(str).str.strip() != "")
        & (output["Document Number"].notna())
        & (output["Document Number"].astype(str).str.strip() != "")
    ].reset_index(drop=True)

    # 6. Reorder columns
    output = output[
        [
            "Debtor Reference",
            "Transaction Type",
            "Document Number",
            "Document Date",
            "Document Balance",
        ]
    ]

    return output


def get_csv_download_link(df):
    csv = df.to_csv(index=False)
    return io.BytesIO(csv.encode())


st.write("Upload your Excel or CSV file for A2Z Flashing processing:")

uploaded_file = st.file_uploader("Choose a file", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    processed_df = process_file(uploaded_file)
    if processed_df is not None:
        st.write("Processed Data:")
        st.dataframe(processed_df)

        csv_buffer = get_csv_download_link(processed_df)
        st.download_button(
            label="Download Processed File",
            data=csv_buffer,
            file_name="a2z_flashing_processed.csv",
            mime="text/csv",
        )
    else:
        st.error(
            "Failed to process the file. Please check the file format and content."
        )
