import csv
import os
from django.core.management.base import BaseCommand
from apis.models import Drug

class Command(BaseCommand):
    help = 'Import drugs from liste-des-medicaments-enrgistres-2025.csv'

    def handle(self, *args, **options):
        file_name = 'liste-des-medicaments-enrgistres-2025.csv'
        file_path = os.path.join(os.getcwd(), file_name)
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File {file_path} not found'))
            return

        # Delete existing drugs
        Drug.objects.all().delete()
        self.stdout.write('Clearing existing drugs...')

        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            # Skip the first 17 lines (16 header lines + 1 title line with indices)
            # Actually, line 17 is the header: N,N°ENREGISTREMENT,CODE...
            # So we skip 17 lines to start at the first data row (line 18)
            for _ in range(17):
                next(reader)
            
            drugs_to_create = []
            count = 0
            
            for row in reader:
                if not row or len(row) < 8:
                    continue
                
                # Manual index mapping for maximum reliability
                try:
                    n_val = int(row[0]) if row[0].strip().isdigit() else None
                    reg_num = row[1].strip()
                    code = row[2].strip()
                    generic = row[3].strip()
                    brand = row[4].strip()
                    form = row[5].strip()
                    dosage = row[6].strip()
                    packaging = row[7].strip()

                    if not brand and not generic:
                        continue
                    
                    drug = Drug(
                        registration_number=reg_num,
                        code=code,
                        generic_name=generic,
                        brand_name=brand,
                        form=form,
                        dosage=dosage,
                        packaging=packaging
                    )
                    drugs_to_create.append(drug)
                    count += 1
                except (IndexError, ValueError) as e:
                    self.stdout.write(self.style.WARNING(f'Skipping row due to error: {e}'))
                    continue
                
                if len(drugs_to_create) >= 500:
                    Drug.objects.bulk_create(drugs_to_create)
                    drugs_to_create = []
            
            if drugs_to_create:
                Drug.objects.bulk_create(drugs_to_create)

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} drugs from {file_name}'))
