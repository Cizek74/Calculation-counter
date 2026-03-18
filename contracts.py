import csv
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta


class ContractManager:
    """Manage printer contracts"""

    def __init__(self, contracts_file):
        self.contracts_file = contracts_file
        self.contracts = {}
        self.load_contracts()

    def parse_date(self, date_str):
        """Parse date from multiple formats"""
        if not date_str or date_str.strip() == '':
            return None

        date_str = date_str.strip()

        # Try multiple date formats
        formats = [
            '%d/%m/%y',      # 1/9/25 (day/month/2-digit year)
            '%d/%m/%Y',      # 1/9/2025 (day/month/4-digit year)
            '%d-%m-%y',      # 1-9-25
            '%d-%m-%Y',      # 1-9-2025
            '%Y-%m-%d',      # 2025-09-01 (ISO format)
            '%m/%d/%y',      # 9/1/25 (US format)
            '%m/%d/%Y',      # 9/1/2025 (US format)
        ]

        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # Convert to standard format YYYY-MM-DD
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue

        # If no format worked, return original
        print(f"[WARN] Could not parse date '{date_str}'")
        return date_str

    def load_contracts(self):
        """Load contracts from CSV file"""
        self.contracts = {}

        if not os.path.exists(self.contracts_file):
            print(f"[WARN] {self.contracts_file} not found. Contract tracking disabled.")
            return

        try:
            with open(self.contracts_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    serial = row.get('Serial_Number', '').strip()
                    if serial:
                        # Parse dates to standard format
                        start_date = self.parse_date(row.get('Start_Date', ''))
                        end_date = self.parse_date(row.get('End_Date', ''))

                        self.contracts[serial] = {
                            'contract_name': row.get('Contract_Name', 'N/A'),
                            'customer_location': row.get('Customer_Location', 'N/A'),
                            'contract_type': row.get('Contract_Type', 'N/A'),
                            'start_date': start_date,
                            'end_date': end_date,
                            'monthly_fixed_cost': float(row.get('Monthly_Fixed_Cost', 0) or 0),
                            'bw_cost_per_page': float(row.get('BW_Cost_Per_Page', 0) or 0),
                            'color_cost_per_page': float(row.get('Color_Cost_Per_Page', 0) or 0),
                            'minimum_monthly_volume': int(row.get('Minimum_Monthly_Volume', 0) or 0),
                            'status': row.get('Status', 'Unknown'),
                            'notes': row.get('Notes', '')
                        }
            print(f"[OK] Loaded {len(self.contracts)} contracts from {self.contracts_file}")
        except Exception as e:
            print(f"[ERROR] Error loading contracts: {str(e)}")

    def get_contract(self, serial_number):
        """Get contract info for a printer"""
        return self.contracts.get(serial_number)

    def calculate_months_remaining(self, end_date_str):
        """Calculate only COMPLETE full months remaining (excluding current partial month)"""
        if not end_date_str:
            return None

        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            today = datetime.now()

            if end_date < today:
                return 0  # Expired

            # Start counting from the 1st of NEXT month (skip current partial month)
            next_month_start = (today.replace(day=1) + relativedelta(months=1))

            # If contract ends before next month starts
            if end_date < next_month_start:
                return 0

            # Calculate from next month to end date
            delta = relativedelta(end_date, next_month_start)

            # Add 1 to include the ending month (e.g., October 2030)
            remaining_months = delta.years * 12 + delta.months + 1

            return max(0, remaining_months)
        except Exception as e:
            print(f"[WARN] Error calculating months for date '{end_date_str}': {str(e)}")
            return None

    def get_contract_status_color(self, months_remaining):
        """Get color code based on months remaining"""
        if months_remaining is None:
            return 'gray'
        elif months_remaining <= 0:
            return 'red'
        elif months_remaining <= 3:
            return 'orange'
        elif months_remaining <= 6:
            return 'yellow'
        else:
            return 'green'

    def calculate_monthly_cost(self, contract, bw_pages, color_pages):
        """Calculate total monthly cost for a printer"""
        if not contract:
            return None

        fixed_cost = contract['monthly_fixed_cost']
        page_cost = (bw_pages * contract['bw_cost_per_page'] +
                     color_pages * contract['color_cost_per_page'])

        total_cost = fixed_cost + page_cost

        return {
            'fixed_cost': fixed_cost,
            'page_cost': page_cost,
            'total_cost': total_cost,
            'bw_pages': bw_pages,
            'color_pages': color_pages
        }

    def get_all_contracts(self):
        """Return all contracts as a list of dicts with computed fields."""
        result = []
        for serial, c in self.contracts.items():
            months = self.calculate_months_remaining(c.get('end_date', ''))
            color  = self.get_contract_status_color(months)
            result.append({
                'serial':                serial,
                'contract_name':         c.get('contract_name', ''),
                'customer_location':     c.get('customer_location', ''),
                'contract_type':         c.get('contract_type', ''),
                'start_date':            c.get('start_date', ''),
                'end_date':              c.get('end_date', ''),
                'monthly_fixed_cost':    c.get('monthly_fixed_cost', 0),
                'bw_cost_per_page':      c.get('bw_cost_per_page', 0),
                'color_cost_per_page':   c.get('color_cost_per_page', 0),
                'minimum_monthly_volume': c.get('minimum_monthly_volume', 0),
                'status':                c.get('status', 'Active'),
                'notes':                 c.get('notes', ''),
                'months_remaining':      months,
                'status_color':          color,
            })
        result.sort(key=lambda x: x['contract_name'].lower())
        return result

    def add_contract(self, data):
        """Add a new contract. Raises ValueError on validation failure."""
        serial = data.get('serial', '').strip()
        if not serial:
            raise ValueError('Sériové číslo je povinné')
        if serial in self.contracts:
            raise ValueError(f'Smlouva pro sériové číslo {serial} již existuje')
        self.contracts[serial] = self._build_row(data)
        self.save_to_csv()

    def update_contract(self, serial, data):
        """Update existing contract. Raises KeyError if serial not found."""
        if serial not in self.contracts:
            raise KeyError(f'Smlouva {serial} nenalezena')
        new_serial = data.get('serial', serial).strip()
        if new_serial != serial:
            if new_serial in self.contracts:
                raise ValueError(f'Sériové číslo {new_serial} již existuje')
            del self.contracts[serial]
            self.contracts[new_serial] = self._build_row(data)
        else:
            self.contracts[serial] = self._build_row(data)
        self.save_to_csv()

    def delete_contract(self, serial):
        """Delete contract by serial. Raises KeyError if not found."""
        if serial not in self.contracts:
            raise KeyError(f'Smlouva {serial} nenalezena')
        del self.contracts[serial]
        self.save_to_csv()

    def reload(self):
        """Re-read contracts from disk."""
        self.load_contracts()

    def _build_row(self, data):
        return {
            'contract_name':          data.get('contract_name', ''),
            'customer_location':      data.get('customer_location', ''),
            'contract_type':          data.get('contract_type', ''),
            'start_date':             self.parse_date(data.get('start_date', '')) or '',
            'end_date':               self.parse_date(data.get('end_date', '')) or '',
            'monthly_fixed_cost':     float(data.get('monthly_fixed_cost', 0) or 0),
            'bw_cost_per_page':       float(data.get('bw_cost_per_page', 0) or 0),
            'color_cost_per_page':    float(data.get('color_cost_per_page', 0) or 0),
            'minimum_monthly_volume': int(data.get('minimum_monthly_volume', 0) or 0),
            'status':                 data.get('status', 'Active'),
            'notes':                  data.get('notes', ''),
        }

    def save_to_csv(self):
        """Write current contracts dict back to the CSV file."""
        fieldnames = [
            'Serial_Number', 'Contract_Name', 'Customer_Location', 'Contract_Type',
            'Start_Date', 'End_Date', 'Monthly_Fixed_Cost', 'BW_Cost_Per_Page',
            'Color_Cost_Per_Page', 'Minimum_Monthly_Volume', 'Status', 'Notes'
        ]
        with open(self.contracts_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for serial, row in self.contracts.items():
                writer.writerow({
                    'Serial_Number':          serial,
                    'Contract_Name':          row.get('contract_name', ''),
                    'Customer_Location':      row.get('customer_location', ''),
                    'Contract_Type':          row.get('contract_type', ''),
                    'Start_Date':             row.get('start_date', ''),
                    'End_Date':               row.get('end_date', ''),
                    'Monthly_Fixed_Cost':     row.get('monthly_fixed_cost', 0),
                    'BW_Cost_Per_Page':       row.get('bw_cost_per_page', 0),
                    'Color_Cost_Per_Page':    row.get('color_cost_per_page', 0),
                    'Minimum_Monthly_Volume': row.get('minimum_monthly_volume', 0),
                    'Status':                 row.get('status', ''),
                    'Notes':                  row.get('notes', ''),
                })
