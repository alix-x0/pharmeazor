import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from apis.models import Drug


class Command(BaseCommand):
    help = "Load drugs from Algerian registry CSV into the Drug table"

    def handle(self, *args, **options):
        base = Path(__file__).resolve().parent.parent.parent.parent.parent  # hackathon root
        csv_path = base / "backend" / "liste-des-medicaments-enrgistres-2025.csv"

        if not csv_path.exists():
            self.stderr.write(f"CSV not found: {csv_path}")
            return

        Drug.objects.all().delete()
        self.stdout.write("Cleared existing drug records.")

        header_found = False
        batch = []
        count = 0

        with csv_path.open(encoding="utf-8-sig", errors="replace") as fh:
            for row in csv.reader(fh):
                if not header_found:
                    if row and row[0].strip() == "N":
                        header_found = True
                    continue
                if len(row) < 5 or not row[0].strip().isdigit():
                    continue
                batch.append(Drug(
                    registration_number=row[1].strip() if len(row) > 1 else "",
                    code=row[2].strip() if len(row) > 2 else "",
                    generic_name=row[3].strip() if len(row) > 3 else "",
                    brand_name=row[4].strip() if len(row) > 4 else "",
                    form=row[5].strip() if len(row) > 5 else "",
                    dosage=row[6].strip() if len(row) > 6 else "",
                    packaging=row[7].strip() if len(row) > 7 else "",
                ))
                count += 1
                if len(batch) >= 500:
                    Drug.objects.bulk_create(batch)
                    batch = []

        if batch:
            Drug.objects.bulk_create(batch)

        self.stdout.write(self.style.SUCCESS(f"Loaded {count} drugs into the database."))
