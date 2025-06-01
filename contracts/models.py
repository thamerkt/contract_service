from django.db import models

CONTRACT_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('signed', 'Signed'),
    ('active', 'Active'),
    ('expired', 'Expired'),
    ('terminated', 'Terminated'),
]

class Contract(models.Model):
    client_name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255, null=True, blank=True)
    equipment = models.CharField(max_length=255, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=CONTRACT_STATUS_CHOICES, default='draft')
    total_value = models.DecimalField(max_digits=10, decimal_places=2)
    signed_date = models.DateField(null=True, blank=True)
    contract_text = models.TextField(null=True, blank=True)  # ✅ Removed max_length

    def __str__(self):
        return f"Contract between {self.owner_name} & {self.client_name} ({self.status})"