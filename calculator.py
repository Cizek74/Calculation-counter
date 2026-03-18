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

    def validate_columns(self, csv_data):
        """Return list of expected columns missing from the CSV."""
        if not csv_data:
            return []
        headers = set(csv_data[0].keys())
        return [col for col in self.EXPECTED_COLUMNS if col not in headers]

    def clean_numeric_value(self, value):
        """Convert value to integer"""
        if value is None or value == '':
            return 0
        try:
            return int(float(str(value).strip()))
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

    def calculate_billable_volumes(self, csv_data, filename, customer_name_override=None):
        """Calculate billable pages.

        Customer name priority:
          1. User override (from the editable input in the UI)
          2. 'Customer Name' column inside the CSV
          3. Name extracted from the filename
        """
        invoice_data = []
        filename_customer = self.extract_customer_from_filename(filename)
        forced_name = customer_name_override.strip() if customer_name_override and customer_name_override.strip() else None

        for row_index, row in enumerate(csv_data):
            try:
                csv_customer = row.get('Customer Name', '').strip()
                customer_name = forced_name or csv_customer or filename_customer

                printer_model = row.get('Model', 'Unknown').strip()
                serial_number = row.get('Serial Number', 'Unknown').strip()
                date_range = row.get('Date Range', 'Unknown')

                # A4/Letter formats
                a4_bw_simplex = self.clean_numeric_value(row.get('A4/Letter-1sided-B&W (Report Interval)'))
                a4_color_simplex = self.clean_numeric_value(row.get('A4/Letter-1sided-Color (Report Interval)'))
                a4_bw_duplex = self.clean_numeric_value(row.get('A4/Letter-2sided-B&W (Report Interval)'))
                a4_color_duplex = self.clean_numeric_value(row.get('A4/Letter-2sided-Color (Report Interval)'))

                # A3/Ledger formats
                a3_bw_simplex = self.clean_numeric_value(row.get('A3/Ledger-1sided-B&W (Report Interval)'))
                a3_color_simplex = self.clean_numeric_value(row.get('A3/Ledger-1sided-Color (Report Interval)'))
                a3_bw_duplex = self.clean_numeric_value(row.get('A3/Ledger-2sided-B&W (Report Interval)'))
                a3_color_duplex = self.clean_numeric_value(row.get('A3/Ledger-2sided-Color (Report Interval)'))

                # A5 formats
                a5_bw_simplex = self.clean_numeric_value(row.get('A5-1sided-B&W (Report Interval)'))
                a5_color_simplex = self.clean_numeric_value(row.get('A5-1sided-Color (Report Interval)'))
                a5_bw_duplex = self.clean_numeric_value(row.get('A5-2sided-B&W (Report Interval)'))
                a5_color_duplex = self.clean_numeric_value(row.get('A5-2sided-Color (Report Interval)'))

                # A6 formats
                a6_bw_simplex = self.clean_numeric_value(row.get('A6-1sided-B&W (Report Interval)'))
                a6_color_simplex = self.clean_numeric_value(row.get('A6-1sided-Color (Report Interval)'))
                a6_bw_duplex = self.clean_numeric_value(row.get('A6-2sided-B&W (Report Interval)'))
                a6_color_duplex = self.clean_numeric_value(row.get('A6-2sided-Color (Report Interval)'))

                # B4/Legal formats
                b4_bw_simplex = self.clean_numeric_value(row.get('B4/Legal-1sided-B&W (Report Interval)'))
                b4_color_simplex = self.clean_numeric_value(row.get('B4/Legal-1sided-Color (Report Interval)'))
                b4_bw_duplex = self.clean_numeric_value(row.get('B4/Legal-2sided-B&W (Report Interval)'))
                b4_color_duplex = self.clean_numeric_value(row.get('B4/Legal-2sided-Color (Report Interval)'))

                # B5 formats
                b5_bw_simplex = self.clean_numeric_value(row.get('B5-1sided-B&W (Report Interval)'))
                b5_color_simplex = self.clean_numeric_value(row.get('B5-1sided-Color (Report Interval)'))
                b5_bw_duplex = self.clean_numeric_value(row.get('B5-2sided-B&W (Report Interval)'))
                b5_color_duplex = self.clean_numeric_value(row.get('B5-2sided-Color (Report Interval)'))

                # Envelope formats
                envelope_bw_simplex = self.clean_numeric_value(row.get('Envelope-1sided-B&W (Report Interval)'))
                envelope_color_simplex = self.clean_numeric_value(row.get('Envelope-1sided-Color (Report Interval)'))
                envelope_bw_duplex = self.clean_numeric_value(row.get('Envelope-2sided-B&W (Report Interval)'))
                envelope_color_duplex = self.clean_numeric_value(row.get('Envelope-2sided-Color (Report Interval)'))

                # Other formats
                other_bw_simplex = self.clean_numeric_value(row.get('Other-1sided-B&W (Report Interval)'))
                other_color_simplex = self.clean_numeric_value(row.get('Other-1sided-Color (Report Interval)'))
                other_bw_duplex = self.clean_numeric_value(row.get('Other-2sided-B&W (Report Interval)'))
                other_color_duplex = self.clean_numeric_value(row.get('Other-2sided-Color (Report Interval)'))

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
