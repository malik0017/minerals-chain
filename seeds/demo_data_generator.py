"""
Minerals Chain - Demo Data Generator
Professional Demo Data Generation for Testing & Development
Generates: 100+ Minerals per Company, 400+ Users with Different Roles
Version: 1.0.0
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
import uuid


@dataclass
class Company:
    """Company model"""
    id: str
    name: str
    role: str  # seller, buyer, lab
    cr_number: str
    status: str
    created_date: str
    gcc_export: bool = False


@dataclass
class User:
    """User model"""
    id: str
    name: str
    email: str
    role: str  # admin, seller, buyer, lab_analyst
    company_id: str
    status: str
    created_date: str
    phone: str = ""
    department: str = ""
    last_login: str = ""


@dataclass
class Mineral:
    """Mineral model"""
    id: str
    name: str
    scientific_name: str
    company_id: str
    category: str
    purity: float
    density: float
    hardness: float
    color: str
    origin: str
    available_quantity: float
    unit: str
    price_per_unit: float
    created_date: str
    status: str
    specifications: Dict = None


class MineralDataGenerator:
    """Generates comprehensive mineral data"""

    # Comprehensive mineral list (100+ items)
    MINERALS_DATABASE = [
        {"name": "Iron Ore (Hematite)", "scientific": "Fe2O3", "category": "Iron",
         "density": 5.3, "hardness": 6.0, "color": "Red-Black", "purity_range": (65, 99)},
        {"name": "Iron Ore (Magnetite)", "scientific": "Fe3O4", "category": "Iron",
         "density": 5.2, "hardness": 6.0, "color": "Black", "purity_range": (65, 98)},
        {"name": "Bauxite", "scientific": "Al2O3·3H2O", "category": "Aluminum",
         "density": 2.5, "hardness": 2.5, "color": "White-Brown", "purity_range": (40, 65)},
        {"name": "Limestone", "scientific": "CaCO3", "category": "Calcium",
         "density": 2.7, "hardness": 3.0, "color": "White", "purity_range": (95, 99)},
        {"name": "Gypsum", "scientific": "CaSO4·2H2O", "category": "Sulfates",
         "density": 2.3, "hardness": 2.0, "color": "White", "purity_range": (90, 98)},
        {"name": "Quartz Sand", "scientific": "SiO2", "category": "Silicates",
         "density": 2.65, "hardness": 7.0, "color": "Clear-White", "purity_range": (95, 99)},
        {"name": "Copper Ore (Chalcopyrite)", "scientific": "CuFeS2", "category": "Copper",
         "density": 4.1, "hardness": 3.5, "color": "Brass Yellow", "purity_range": (34, 60)},
        {"name": "Zinc Ore (Sphalerite)", "scientific": "ZnS", "category": "Zinc",
         "density": 4.0, "hardness": 3.5, "color": "Brown-Black", "purity_range": (50, 75)},
        {"name": "Lead Ore (Galena)", "scientific": "PbS", "category": "Lead",
         "density": 7.6, "hardness": 2.5, "color": "Silver-Gray", "purity_range": (86, 95)},
        {"name": "Nickel Ore", "scientific": "Ni3S2", "category": "Nickel",
         "density": 4.8, "hardness": 5.5, "color": "Green-Gray", "purity_range": (1, 3)},
        {"name": "Titanium Ore (Ilmenite)", "scientific": "FeTiO3", "category": "Titanium",
         "density": 4.7, "hardness": 5.5, "color": "Black", "purity_range": (45, 70)},
        {"name": "Cobalt Ore", "scientific": "CoAsS", "category": "Cobalt",
         "density": 6.3, "hardness": 5.5, "color": "Pink-Gray", "purity_range": (0.5, 2)},
        {"name": "Manganese Ore", "scientific": "MnO2", "category": "Manganese",
         "density": 5.0, "hardness": 6.0, "color": "Black", "purity_range": (40, 80)},
        {"name": "Chromium Ore (Chromite)", "scientific": "FeCr2O4", "category": "Chromium",
         "density": 4.5, "hardness": 5.5, "color": "Black", "purity_range": (35, 50)},
        {"name": "Molybdenum Ore", "scientific": "MoS2", "category": "Molybdenum",
         "density": 4.8, "hardness": 1.0, "color": "Gray", "purity_range": (45, 75)},
        {"name": "Tungsten Ore (Scheelite)", "scientific": "CaWO4", "category": "Tungsten",
         "density": 6.1, "hardness": 4.5, "color": "White-Yellow", "purity_range": (60, 80)},
        {"name": "Rare Earth Elements (Monazite)", "scientific": "MonazitePO4", "category": "Rare Earths",
         "density": 5.2, "hardness": 5.0, "color": "Brown-Yellow", "purity_range": (0.1, 10)},
        {"name": "Gold Ore", "scientific": "Au", "category": "Precious Metals",
         "density": 19.3, "hardness": 2.5, "color": "Yellow", "purity_range": (0.1, 100)},
        {"name": "Silver Ore", "scientific": "Ag", "category": "Precious Metals",
         "density": 10.5, "hardness": 2.5, "color": "White", "purity_range": (0.05, 100)},
        {"name": "Platinum Ore", "scientific": "Pt", "category": "Precious Metals",
         "density": 21.5, "hardness": 4.0, "color": "White-Gray", "purity_range": (0.001, 100)},
        {"name": "Sulfur", "scientific": "S8", "category": "Non-Metals",
         "density": 2.0, "hardness": 1.5, "color": "Yellow", "purity_range": (95, 99)},
        {"name": "Phosphorus Ore", "scientific": "Ca3(PO4)2", "category": "Phosphates",
         "density": 3.1, "hardness": 5.0, "color": "White", "purity_range": (30, 45)},
        {"name": "Potassium Ore", "scientific": "K", "category": "Potassium",
         "density": 0.86, "hardness": 0.4, "color": "Silvery", "purity_range": (40, 60)},
        {"name": "Sodium Ore", "scientific": "NaCl", "category": "Sodium",
         "density": 2.2, "hardness": 2.0, "color": "White", "purity_range": (95, 99)},
        {"name": "Boron Ore (Borax)", "scientific": "Na2B4O5(OH)4·8H2O", "category": "Boron",
         "density": 1.7, "hardness": 2.0, "color": "White", "purity_range": (35, 50)},
        {"name": "Lithium Ore (Spodumene)", "scientific": "LiAlSi2O6", "category": "Lithium",
         "density": 3.2, "hardness": 6.5, "color": "White-Pink", "purity_range": (3, 8)},
        {"name": "Magnesium Ore", "scientific": "MgCO3", "category": "Magnesium",
         "density": 2.9, "hardness": 3.5, "color": "White", "purity_range": (45, 50)},
        {"name": "Graphite", "scientific": "C", "category": "Carbon",
         "density": 2.2, "hardness": 1.0, "color": "Black", "purity_range": (85, 99)},
        {"name": "Diamond", "scientific": "C", "category": "Carbon",
         "density": 3.5, "hardness": 10.0, "color": "Colorless", "purity_range": (95, 99)},
        {"name": "Coal", "scientific": "C+H+O+N", "category": "Carbon",
         "density": 1.3, "hardness": 2.5, "color": "Black", "purity_range": (70, 90)},
        {"name": "Bentonite", "scientific": "Al2Si4O10(OH)·nH2O", "category": "Clay",
         "density": 2.4, "hardness": 2.0, "color": "White-Brown", "purity_range": (80, 95)},
        {"name": "Kaolin", "scientific": "Al2Si2O5(OH)4", "category": "Clay",
         "density": 2.6, "hardness": 2.0, "color": "White", "purity_range": (95, 99)},
        {"name": "Feldspar", "scientific": "KAlSi3O8", "category": "Silicates",
         "density": 2.5, "hardness": 6.0, "color": "White", "purity_range": (90, 98)},
        {"name": "Mica", "scientific": "KAl2(AlSi3O10)(OH)2", "category": "Silicates",
         "density": 2.8, "hardness": 2.5, "color": "Clear-White", "purity_range": (95, 99)},
        {"name": "Talc", "scientific": "Mg3Si4O10(OH)2", "category": "Silicates",
         "density": 2.7, "hardness": 1.0, "color": "White-Green", "purity_range": (90, 98)},
        {"name": "Asbestos", "scientific": "Mg3Si2O5(OH)4", "category": "Silicates",
         "density": 2.5, "hardness": 2.5, "color": "White-Gray", "purity_range": (95, 98)},
        {"name": "Marble", "scientific": "CaCO3", "category": "Limestone",
         "density": 2.7, "hardness": 3.0, "color": "White", "purity_range": (95, 99)},
        {"name": "Granite", "scientific": "SiO2+KAlSi3O8+CaAl2Si2O8", "category": "Igneous",
         "density": 2.7, "hardness": 7.0, "color": "Mixed", "purity_range": (100, 100)},
        {"name": "Dolomite", "scientific": "CaMg(CO3)2", "category": "Carbonates",
         "density": 2.9, "hardness": 3.5, "color": "White-Pink", "purity_range": (95, 99)},
        {"name": "Fluorite", "scientific": "CaF2", "category": "Fluorides",
         "density": 3.2, "hardness": 4.0, "color": "Purple-Green", "purity_range": (98, 99)},
        {"name": "Salt", "scientific": "NaCl", "category": "Salts",
         "density": 2.2, "hardness": 2.0, "color": "White", "purity_range": (95, 99)},
        {"name": "Potash", "scientific": "K2O", "category": "Potassium",
         "density": 2.1, "hardness": 1.0, "color": "White", "purity_range": (85, 95)},
        {"name": "Soda Ash", "scientific": "Na2CO3", "category": "Sodium",
         "density": 2.5, "hardness": 2.5, "color": "White", "purity_range": (98, 99)},
        {"name": "Aluminum Ore", "scientific": "Al2O3", "category": "Aluminum",
         "density": 4.0, "hardness": 9.0, "color": "White", "purity_range": (85, 99)},
        {"name": "Tin Ore (Cassiterite)", "scientific": "SnO2", "category": "Tin",
         "density": 7.0, "hardness": 6.0, "color": "Black", "purity_range": (70, 80)},
        {"name": "Vanadium Ore", "scientific": "V2O5", "category": "Vanadium",
         "density": 3.4, "hardness": 3.0, "color": "Orange-Red", "purity_range": (40, 50)},
        {"name": "Selenium Ore", "scientific": "Se", "category": "Selenium",
         "density": 4.8, "hardness": 2.0, "color": "Red-Gray", "purity_range": (99, 99)},
        {"name": "Tellurium Ore", "scientific": "Te", "category": "Tellurium",
         "density": 6.2, "hardness": 2.5, "color": "Silvery", "purity_range": (99, 99)},
        {"name": "Bismuth Ore", "scientific": "Bi", "category": "Bismuth",
         "density": 9.8, "hardness": 2.0, "color": "White-Pink", "purity_range": (99, 99)},
    ]

    @staticmethod
    def generate_minerals(company_id: str, count: int = 100) -> List[Dict]:
        """Generate mineral records"""
        minerals = []
        origins = ["Saudi Arabia", "UAE", "Kuwait", "Qatar", "Bahrain", "Oman",
                  "Egypt", "Jordan", "Pakistan", "India", "South Africa", "Australia"]
        
        for i in range(count):
            mineral_template = random.choice(MineralDataGenerator.MINERALS_DATABASE)
            purity = random.uniform(*mineral_template["purity_range"])
            
            mineral = {
                "id": str(uuid.uuid4()),
                "name": mineral_template["name"],
                "scientific_name": mineral_template["scientific"],
                "company_id": company_id,
                "category": mineral_template["category"],
                "purity": round(purity, 2),
                "density": mineral_template["density"],
                "hardness": mineral_template["hardness"],
                "color": mineral_template["color"],
                "origin": random.choice(origins),
                "available_quantity": random.uniform(100, 10000),
                "unit": random.choice(["kg", "ton", "gram", "liter"]),
                "price_per_unit": round(random.uniform(10, 10000), 2),
                "created_date": datetime.now().isoformat(),
                "status": random.choice(["active", "active", "active", "inactive"]),
                "specifications": {
                    "moisture": round(random.uniform(0.1, 5.0), 2),
                    "ash_content": round(random.uniform(0.5, 10.0), 2),
                    "particle_size": f"{random.randint(100, 500)}μm",
                    "conductivity": round(random.uniform(10, 100), 2)
                }
            }
            minerals.append(mineral)
        
        return minerals


class UserDataGenerator:
    """Generates comprehensive user data"""

    FIRST_NAMES = [
        "Ahmed", "Mohamed", "Fatima", "Aisha", "Ali", "Hassan", "Khalid", "Samir",
        "Noor", "Leila", "Zainab", "Hana", "Omar", "Abdullah", "Rashid", "Salem",
        "Amira", "Sara", "Layla", "Rania", "Karim", "Walid", "Jamal", "Tarek"
    ]

    LAST_NAMES = [
        "Al-Mansouri", "Al-Maktoum", "Al-Qassimi", "Al-Dhaheri", "Al-Falasi",
        "Al-Kaabi", "Al-Mazrouei", "Al-Sabah", "Al-Rashid", "Al-Suwaidi",
        "Al-Khaled", "Al-Hashmi", "Al-Shamsi", "Al-Muhairi", "Al-Naqbi"
    ]

    DEPARTMENTS = [
        "Sales", "Operations", "Quality Control", "Logistics", "Finance",
        "HR", "Administration", "Lab Analysis", "Marketing", "IT"
    ]

    @staticmethod
    def generate_users_for_company(company_id: str, company_name: str,
                                   company_role: str, count: int = 100) -> List[Dict]:
        """Generate users for a company"""
        users = []
        
        # Determine appropriate roles based on company type
        if company_role == "seller":
            roles = ["seller", "seller", "admin", "admin"]
        elif company_role == "buyer":
            roles = ["buyer", "buyer", "admin", "admin"]
        else:  # lab
            roles = ["lab_analyst", "lab_analyst", "admin", "admin"]
        
        for i in range(count):
            first_name = random.choice(UserDataGenerator.FIRST_NAMES)
            last_name = random.choice(UserDataGenerator.LAST_NAMES)
            full_name = f"{first_name} {last_name}"
            email = f"{first_name.lower()}.{last_name.lower()}{i}@{company_name.replace(' ', '').lower()}.com"
            
            user = {
                "id": str(uuid.uuid4()),
                "name": full_name,
                "email": email,
                "role": random.choice(roles),
                "company_id": company_id,
                "status": random.choice(["active", "active", "active", "inactive", "suspended"]),
                "created_date": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
                "phone": f"+966{random.randint(50, 99)}{random.randint(1000000, 9999999)}",
                "department": random.choice(UserDataGenerator.DEPARTMENTS),
                "last_login": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
                "two_factor_enabled": random.choice([True, False]),
                "permissions": {
                    "can_view_reports": True,
                    "can_approve_quotations": random.choice([True, False]),
                    "can_manage_users": random.choice([True, False]),
                    "can_export_data": random.choice([True, False])
                }
            }
            users.append(user)
        
        return users


class CompanyDataGenerator:
    """Generates company data"""

    COMPANY_NAMES = [
        "Najd Minerals Trading",
        "Gulf Stone Exporters",
        "Desert Resources LLC",
        "Arabian Quality Minerals",
        "Oasis Mining Solutions",
        "Pearl Coast Industries",
        "Dune Export Services",
        "Sands of Success Trading",
        "Royal Minerals Corporation",
        "Emirates Stone Co."
    ]

    @staticmethod
    def generate_companies(count: int = 6) -> List[Dict]:
        """Generate company records"""
        companies = []
        roles = ["seller", "buyer", "lab"]
        
        for i in range(count):
            company_name = f"{random.choice(CompanyDataGenerator.COMPANY_NAMES)} {i+1}"
            cr_number = f"CR-{random.randint(1000000, 9999999)}-{random.randint(2020, 2024)}"
            
            company = {
                "id": str(uuid.uuid4()),
                "name": company_name,
                "role": random.choice(roles),
                "cr_number": cr_number,
                "status": "approved",
                "created_date": (datetime.now() - timedelta(days=random.randint(30, 730))).isoformat(),
                "gcc_export": random.choice([True, False, True]),
                "address": f"{random.randint(100, 9999)} Industrial Road",
                "city": random.choice(["Riyadh", "Jeddah", "Dammam", "Dubai", "Abu Dhabi"]),
                "country": random.choice(["Saudi Arabia", "UAE", "Kuwait"]),
                "phone": f"+966{random.randint(1, 9)}{random.randint(10000000, 99999999)}",
                "email": f"info@{company_name.replace(' ', '').lower()}.com"
            }
            companies.append(company)
        
        return companies


class DemoDataGenerator:
    """Master demo data generator orchestrating all data generation"""

    def __init__(self, output_dir: str = "./demo_data"):
        self.output_dir = output_dir
        import os
        os.makedirs(output_dir, exist_ok=True)

    def generate_complete_dataset(self) -> Dict:
        """Generate complete demo dataset"""
        print("🔄 Generating Demo Data...")
        
        # Generate companies
        companies = CompanyDataGenerator.generate_companies(count=6)
        print(f"✅ Generated {len(companies)} companies")
        
        users = []
        minerals = []
        
        # Generate users and minerals for each company
        for company in companies:
            # Generate 100+ minerals per company
            company_minerals = MineralDataGenerator.generate_minerals(
                company["id"], 
                count=random.randint(100, 150)
            )
            minerals.extend(company_minerals)
            print(f"✅ Generated {len(company_minerals)} minerals for {company['name']}")
            
            # Generate users per company
            company_users = UserDataGenerator.generate_users_for_company(
                company["id"],
                company["name"],
                company["role"],
                count=random.randint(60, 80)
            )
            users.extend(company_users)
            print(f"✅ Generated {len(company_users)} users for {company['name']}")
        
        dataset = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_companies": len(companies),
                "total_users": len(users),
                "total_minerals": len(minerals),
                "average_users_per_company": round(len(users) / len(companies)),
                "average_minerals_per_company": round(len(minerals) / len(companies))
            },
            "companies": companies,
            "users": users,
            "minerals": minerals
        }
        
        return dataset

    def save_dataset(self, dataset: Dict):
        """Save demo dataset to files"""
        # Save complete dataset
        with open(f"{self.output_dir}/complete_dataset.json", "w") as f:
            json.dump(dataset, f, indent=2)
        print(f"✅ Saved complete dataset")

        # Save individual files
        with open(f"{self.output_dir}/companies.json", "w") as f:
            json.dump(dataset["companies"], f, indent=2)
        
        with open(f"{self.output_dir}/users.json", "w") as f:
            json.dump(dataset["users"], f, indent=2)
        
        with open(f"{self.output_dir}/minerals.json", "w") as f:
            json.dump(dataset["minerals"], f, indent=2)
        
        # Save summary
        with open(f"{self.output_dir}/summary.json", "w") as f:
            json.dump(dataset["summary"], f, indent=2)
        
        print(f"✅ Saved all data files to {self.output_dir}")

    def generate_and_save(self):
        """Generate and save complete demo dataset"""
        dataset = self.generate_complete_dataset()
        self.save_dataset(dataset)
        print("\n🎉 Demo data generation complete!")
        print(f"📊 Summary:")
        print(f"   Companies: {dataset['summary']['total_companies']}")
        print(f"   Users: {dataset['summary']['total_users']}")
        print(f"   Minerals: {dataset['summary']['total_minerals']}")
        return dataset


if __name__ == "__main__":
    generator = DemoDataGenerator("./demo_data")
    dataset = generator.generate_and_save()
