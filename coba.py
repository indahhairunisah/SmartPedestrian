import json
import random
from datetime import datetime, timedelta

dummy_data = []
start_time = datetime.strptime("2025-07-30 03:46:31.502151", "%Y-%m-%d %H:%M:%S.%f")

for i in range(1, 1001):
    # acak waktu tambahannya agar menyebar, bisa loncat jam
    random_seconds = random.randint(30, 43200)  # antara 30 detik - 12 jam
    random_time = start_time + timedelta(seconds=random_seconds * i)

    status = random.choice(["STOP", "WALK"])
    duration = round(random.uniform(45, 70), 6)
    fixed_value = 28

    dummy_data.append([
        i,
        random_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
        status,
        duration,
        fixed_value
    ])

with open("dummy_randomized_pedestrian_data.json", "w") as f:
    json.dump(dummy_data, f, indent=2)
