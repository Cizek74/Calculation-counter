import csv
import os
import re


class PrintingVolumeCalculator:
    """Calculator that extracts customer names from FILENAME to keep locations separate"""

    EXPECTED_COLUMNS = [
        'Model', 'Serial Number', 'Date Range',
        'A4/Letter-1sided-B&W (Report Interval)', 'A4/Letter-1sided-Color (Report Interval)',
        'A4/Letter-2sided-B&W (Report Interval)', 'A4/Letter-2sided-Color (Report Interval)',
        'A3/Ledger-1sided-B&W (Report Interval)', 'A3/Ledger-1sided-Color (Report Interval)',
        'A3/Ledger-2sided-B&W (Report Interval)', 'A3/Ledger-2sided-Color (Report Interval)',
        'A5-1sided-B&W (Report Interval)', 'A5-1sided-Color (Report Interval)',
        'A5-2sided-B&W (Report Interval)', 'A5-2sided-Color (Report Interval)',
        'A6-1sided-B&W (Report Interval)', 'A6-1sided-Color (Report Interval)',
        'A6-2sided-B&W (Report Interval)', 'A6-2sided-Color (Report Interval)',
        'B4/Legal-1sided-B&W (Report Interval)', 'B4/Legal-1sided-Color (Report Interval)',
        'B4/Legal-2sided-B&W (Report Interval)', 'B4/Legal-2sided-Color (Report Interval)',
        'B5-1sided-B&W (Report Interval)', 'B5-1sided-Color (Report Interval)',
        'B5-2sided-B&W (Report Interval)', 'B5-2sided-Color (Report Interval)',
        'Envelope-1sided-B&W (Report Interval)', 'Envelope-1sided-Color (Report Interval)',
        'Envelope-2sided-B&W (Report Interval)', 'Envelope-2sided-Color (Report Interval)',
        'Other-1sided-B&W (Report Interval)', 'Other-1sided-Color (Report Interval)',
        'Other-2sided-B&W (Report Interval)', 'Other-2sided-Color (Report Interval)',
    ]

    def __init__(self):
        # Your invoicing rules - ALL PAPER FORMATS
        self.page_multipliers = {
            'a4_simplex': 1, 'a4_duplex': 2,
            'a3_simplex': 2, 'a3_duplex': 4,
            'a5_simplex': 1, 'a5_duplex': 2,
            'a6_simplex': 1, 'a6_duplex': 2,
            'b4_simplex': 2, 'b4_duplex': 4,
            'b5_simplex': 1, 'b5_duplex': 2,
            'envelope_simplex': 1, 'envelope_duplex': 2,
            'other_simplex': 1, 'other_duplex': 2,
        }

    def load_csv_data(self, csv_file_path):
        """Load CSV data"""
        try:
            encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'iso-8859-1']
            for encoding in encodings:
                try:
                    with open(csv_file_path, 'r', encoding=encoding, newline='') as file:
                        reader = csv.DictReader(file)
                        return list(reader), None
                except UnicodeDecodeError:
                    continue
            return None, "Could not read file with any supported encoding"
        except Exception as e:
            return None, str(e)

    def validate_columns(self, csv_data, mapping=None):
        """Return list of expected columns missing from the CSV, considering mapping."""
        if not csv_data:
            return []
        headers = set(csv_data[0].keys())
        mapping = mapping or {}
        
        missing = []
        for col in self.EXPECTED_COLUMNS:
            mapped_col = mapping.get(col, col)
            if mapped_col not in headers:
                missing.append(col)
        return missing

    def _get_field_value(self, row, field_name, mapping):
        """Helper to get a field value using mapping if provided."""
        mapping = mapping or {}
        actual_field = mapping.get(field_name, field_name)
        return row.get(actual_field)

    def clean_numeric_value(self, value):
        """Convert value to integer"""
        if value is None or value == '':
            return 0
        try:
            # Handle possible string numbers with commas
            val_str = str(value).strip().replace(',', '.')
            return int(float(val_str))
        except (ValueError, TypeError):
            return 0

    def extract_customer_from_filename(self, filename):
        """Extract customer name from filename"""
        name = filename.replace('.csv', '').replace('.CSV', '')
        name = re.sub(r'_\d{8}$', '', name)
        name = re.sub(r'_\d{4}-\d{2}-\d{2}$', '', name)
        name = name.replace('-', ' ').replace('_', ' ')
        name = ' '.join(name.split())
        return name.strip()

    def calculate_billable_volumes(self, csv_data, filename, customer_name_override=None, mapping=None):
        """Calculate billable pages.

        Customer name priority:
          1. User override (from the editable input in the UI)
          2. 'Customer Name' column inside the CSV
          3. Name extracted from the filename
        """
        invoice_data = []
        filename_customer = self.extract_customer_from_filename(filename)
        forced_name = customer_name_override.strip() if customer_name_override and customer_name_override.strip() else None
        mapping = mapping or {}

        for row_index, row in enumerate(csv_data):
            try:
                csv_customer = self._get_field_value(row, 'Customer Name', mapping)
                if csv_customer:
                    csv_customer = str(csv_customer).strip()
                customer_name = forced_name or csv_customer or filename_customer

                printer_model = str(self._get_field_value(row, 'Model', mapping) or 'Unknown').strip()
                serial_number = str(self._get_field_value(row, 'Serial Number', mapping) or 'Unknown').strip()
                date_range = str(self._get_field_value(row, 'Date Range', mapping) or 'Unknown')

                # A4/Letter formats
                a4_bw_simplex = self.clean_numeric_value(self._get_field_value(row, 'A4/Letter-1sided-B&W (Report Interval)', mapping))
                a4_color_simplex = self.clean_numeric_value(self._get_field_value(row, 'A4/Letter-1sided-Color (Report Interval)', mapping))
                a4_bw_duplex = self.clean_numeric_value(self._get_field_value(row, 'A4/Letter-2sided-B&W (Report Interval)', mapping))
                a4_color_duplex = self.clean_numeric_value(self._get_field_value(row, 'A4/Letter-2sided-Color (Report Interval)', mapping))

                # A3/Ledger formats
                a3_bw_simplex = self.clean_numeric_value(self._get_field_value(row, 'A3/Ledger-1sided-B&W (Report Interval)', mapping))
                a3_color_simplex = self.clean_numeric_value(self._get_field_value(row, 'A3/Ledger-1sided-Color (Report Interval)', mapping))
                a3_bw_duplex = self.clean_numeric_value(self._get_field_value(row, 'A3/Ledger-2sided-B&W (Report Interval)', mapping))
                a3_color_duplex = self.clean_numeric_value(self._get_field_value(row, 'A3/Ledger-2sided-Color (Report Interval)', mapping))

                # A5 formats
                a5_bw_simplex = self.clean_numeric_value(self._get_field_value(row, 'A5-1sided-B&W (Report Interval)', mapping))
                a5_color_simplex = self.clean_numeric_value(self._get_field_value(row, 'A5-1sided-Color (Report Interval)', mapping))
                a5_bw_duplex = self.clean_numeric_value(self._get_field_value(row, 'A5-2sided-B&W (Report Interval)', mapping))
                a5_color_duplex = self.clean_numeric_value(self._get_field_value(row, 'A5-2sided-Color (Report Interval)', mapping))

                # A6 formats
                a6_bw_simplex = self.clean_numeric_value(self._get_field_value(row, 'A6-1sided-B&W (Report Interval)', mapping))
                a6_color_simplex = self.clean_numeric_value(self._get_field_value(row, 'A6-1sided-Color (Report Interval)', mapping))
                a6_bw_duplex = self.clean_numeric_value(self._get_field_value(row, 'A6-2sided-B&W (Report Interval)', mapping))
                a6_color_duplex = self.clean_numeric_value(self._get_field_value(row, 'A6-2sided-Color (Report Interval)', mapping))

                # B4/Legal formats
                b4_bw_simplex = self.clean_numeric_value(self._get_field_value(row, 'B4/Legal-1sided-B&W (Report Interval)', mapping))
                b4_color_simplex = self.clean_numeric_value(self._get_field_value(row, 'B4/Legal-1sided-Color (Report Interval)', mapping))
                b4_bw_duplex = self.clean_numeric_value(self._get_field_value(row, 'B4/Legal-2sided-B&W (Report Interval)', mapping))
                b4_color_duplex = self.clean_numeric_value(self._get_field_value(row, 'B4/Legal-2sided-Color (Report Interval)', mapping))

                # B5 formats
                b5_bw_simplex = self.clean_numeric_value(self._get_field_value(row, 'B5-1sided-B&W (Report Interval)', mapping))
                b5_color_simplex = self.clean_numeric_value(self._get_field_value(row, 'B5-1sided-Color (Report Interval)', mapping))
                b5_bw_duplex = self.clean_numeric_value(self._get_field_value(row, 'B5-2sided-B&W (Report Interval)', mapping))
                b5_color_duplex = self.clean_numeric_value(self._get_field_value(row, 'B5-2sided-Color (Report Interval)', mapping))

                # Envelope formats
                envelope_bw_simplex = self.clean_numeric_value(self._get_field_value(row, 'Envelope-1sided-B&W (Report Interval)', mapping))
                envelope_color_simplex = self.clean_numeric_value(self._get_field_value(row, 'Envelope-1sided-Color (Report Interval)', mapping))
                envelope_bw_duplex = self.clean_numeric_value(self._get_field_value(row, 'Envelope-2sided-B&W (Report Interval)', mapping))
                envelope_color_duplex = self.clean_numeric_value(self._get_field_value(row, 'Envelope-2sided-Color (Report Interval)', mapping))

                # Other formats
                other_bw_simplex = self.clean_numeric_value(self._get_field_value(row, 'Other-1sided-B&W (Report Interval)', mapping))
                other_color_simplex = self.clean_numeric_value(self._get_field_value(row, 'Other-1sided-Color (Report Interval)', mapping))
                other_bw_duplex = self.clean_numeric_value(self._get_field_value(row, 'Other-2sided-B&W (Report Interval)', mapping))
                other_color_duplex = self.clean_numeric_value(self._get_field_value(row, 'Other-2sided-Color (Report Interval)', mapping))

                # Calculate BILLABLE pages
                a4_bw_billable = (a4_bw_simplex * self.page_multipliers['a4_simplex'] +
                                 a4_bw_duplex * self.page_multipliers['a4_duplex'])
                a4_color_billable = (a4_color_simplex * self.page_multipliers['a4_simplex'] +
                                    a4_color_duplex * self.page_multipliers['a4_duplex'])

                a3_bw_billable = (a3_bw_simplex * self.page_multipliers['a3_simplex'] +
                                 a3_bw_duplex * self.page_multipliers['a3_duplex'])
                a3_color_billable = (a3_color_simplex * self.page_multipliers['a3_simplex'] +
                                    a3_color_duplex * self.page_multipliers['a3_duplex'])

                a5_bw_billable = (a5_bw_simplex * self.page_multipliers['a5_simplex'] +
                                 a5_bw_duplex * self.page_multipliers['a5_duplex'])
                a5_color_billable = (a5_color_simplex * self.page_multipliers['a5_simplex'] +
                                    a5_color_duplex * self.page_multipliers['a5_duplex'])

                a6_bw_billable = (a6_bw_simplex * self.page_multipliers['a6_simplex'] +
                                 a6_bw_duplex * self.page_multipliers['a6_duplex'])
                a6_color_billable = (a6_color_simplex * self.page_multipliers['a6_simplex'] +
                                    a6_color_duplex * self.page_multipliers['a6_duplex'])

                b4_bw_billable = (b4_bw_simplex * self.page_multipliers['b4_simplex'] +
                                 b4_bw_duplex * self.page_multipliers['b4_duplex'])
                b4_color_billable = (b4_color_simplex * self.page_multipliers['b4_simplex'] +
                                    b4_color_duplex * self.page_multipliers['b4_duplex'])

                b5_bw_billable = (b5_bw_simplex * self.page_multipliers['b5_simplex'] +
                                 b5_bw_duplex * self.page_multipliers['b5_duplex'])
                b5_color_billable = (b5_color_simplex * self.page_multipliers['b5_simplex'] +
                                    b5_color_duplex * self.page_multipliers['b5_duplex'])

                envelope_bw_billable = (envelope_bw_simplex * self.page_multipliers['envelope_simplex'] +
                                       envelope_bw_duplex * self.page_multipliers['envelope_duplex'])
                envelope_color_billable = (envelope_color_simplex * self.page_multipliers['envelope_simplex'] +
                                          envelope_color_duplex * self.page_multipliers['envelope_duplex'])

                other_bw_billable = (other_bw_simplex * self.page_multipliers['other_simplex'] +
                                    other_bw_duplex * self.page_multipliers['other_duplex'])
                other_color_billable = (other_color_simplex * self.page_multipliers['other_simplex'] +
                                       other_color_duplex * self.page_multipliers['other_duplex'])

                # Total billable pages
                total_bw_billable = (a4_bw_billable + a3_bw_billable + a5_bw_billable +
                                    a6_bw_billable + b4_bw_billable + b5_bw_billable +
                                    envelope_bw_billable + other_bw_billable)

                total_color_billable = (a4_color_billable + a3_color_billable + a5_color_billable +
                                       a6_color_billable + b4_color_billable + b5_color_billable +
                                       envelope_color_billable + other_color_billable)

                total_billable = total_bw_billable + total_color_billable

                invoice_record = {
                    'Customer': customer_name,
                    'Printer_Model': printer_model,
                    'Serial_Number': serial_number,
                    'Date_Range': date_range,
                    'Billable_BW_Pages': int(total_bw_billable),
                    'Billable_Color_Pages': int(total_color_billable),
                    'Total_Billable_Pages': int(total_billable),
                    'Source_File': filename
                }

                invoice_data.append(invoice_record)

            except Exception as e:
                print(f"Warning: Skipped row {row_index + 1} in {filename}: {str(e)}")
                continue

        return invoice_data
