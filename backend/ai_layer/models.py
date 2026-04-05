from django.db import models
from django.contrib.auth.models import User
from mastersconfig.models import RetailMaster


class NLQueryLog(models.Model):
    retail = models.ForeignKey(RetailMaster, on_delete=models.CASCADE, related_name='ai_queries')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    query_text = models.TextField()
    response_text = models.TextField()
    tool_calls_json = models.JSONField(default=list)
    tokens_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'NL Query Log'
        verbose_name_plural = 'NL Query Logs'

    def __str__(self):
        return f"{self.user} — {self.query_text[:60]}"
