"""Load test dashboard reads: locust -f scripts/locustfile.py --host http://localhost:8000"""
from locust import HttpUser, between, task


class Dashboard(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(3)
    def districts(self):
        self.client.get("/analytics/districts/soil-carbon?months=6", name="districts")

    @task(2)
    def region_summary(self):
        self.client.get("/analytics/regions/1/summary?months=6", name="region_summary")

    @task(1)
    def region_monthly(self):
        self.client.get("/analytics/regions/1/monthly?months=6", name="region_monthly")
