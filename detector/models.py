from django.db import models
from django.contrib.auth.models import User
import uuid


class Analysis(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('extracting', 'Extracting Citations'),
        ('analyzing', 'Analyzing Context'),
        ('verifying', 'Verifying Sources'),
        ('detecting', 'Detecting Hallucinations'),
        ('reporting', 'Generating Report'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analyses')
    title = models.CharField(max_length=500, blank=True, default='Untitled Analysis')
    input_text = models.TextField(blank=True)
    input_file = models.FileField(upload_to='uploads/', blank=True, null=True)
    input_type = models.CharField(max_length=10, choices=[
        ('text', 'Pasted Text'),
        ('pdf', 'PDF File'),
        ('docx', 'Word File'),
    ], default='text')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Analysis'
        verbose_name_plural = 'Analyses'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.title} ({self.get_status_display()})'


class Citation(models.Model):
    SEVERITY_CHOICES = [
        ('green', 'Verified'),
        ('yellow', 'Questionable'),
        ('red', 'Hallucinated'),
    ]

    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name='citations')
    citation_text = models.TextField()
    context_before = models.TextField(blank=True)
    context_after = models.TextField(blank=True)
    claimed_source = models.CharField(max_length=500, blank=True)
    claimed_year = models.IntegerField(blank=True, null=True)
    confidence_score = models.FloatField(default=0.0)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='yellow')
    explanation = models.TextField(blank=True)
    suggestion = models.TextField(blank=True)
    is_hallucinated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Citation'
        verbose_name_plural = 'Citations'
        ordering = ['-confidence_score']

    def __str__(self) -> str:
        return f'Citation: {self.citation_text[:80]}...'


class AnalysisReport(models.Model):
    analysis = models.OneToOneField(Analysis, on_delete=models.CASCADE, related_name='report')
    summary = models.TextField()
    total_citations = models.IntegerField(default=0)
    verified_citations = models.IntegerField(default=0)
    questionable_citations = models.IntegerField(default=0)
    hallucinated_citations = models.IntegerField(default=0)
    overall_credibility_score = models.FloatField(default=0.0)
    agent_logs = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Analysis Report'
        verbose_name_plural = 'Analysis Reports'

    def __str__(self) -> str:
        return f'Report for {self.analysis.title}'


class AgentLog(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name='agent_logs')
    agent_name = models.CharField(max_length=100)
    action = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=[
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='running')
    details = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['started_at']

    def __str__(self) -> str:
        return f'{self.agent_name}: {self.action}'
