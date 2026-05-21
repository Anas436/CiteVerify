from django.contrib import admin
from .models import Analysis, Citation, AnalysisReport, AgentLog


class CitationInline(admin.TabularInline):
    model = Citation
    extra = 0
    fields = ('citation_text', 'severity', 'confidence_score', 'is_hallucinated')
    readonly_fields = ('citation_text', 'confidence_score')


class AgentLogInline(admin.TabularInline):
    model = AgentLog
    extra = 0
    fields = ('agent_name', 'action', 'status', 'started_at', 'completed_at')
    readonly_fields = ('agent_name', 'action', 'started_at', 'completed_at')


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'input_type', 'status', 'progress', 'created_at')
    list_filter = ('status', 'input_type', 'created_at')
    search_fields = ('title', 'user__username', 'user__email')
    inlines = [CitationInline, AgentLogInline]
    readonly_fields = ('id', 'created_at', 'updated_at', 'completed_at')


@admin.register(Citation)
class CitationAdmin(admin.ModelAdmin):
    list_display = ('citation_text', 'analysis', 'severity', 'confidence_score', 'is_hallucinated')
    list_filter = ('severity', 'is_hallucinated')
    search_fields = ('citation_text', 'claimed_source')


@admin.register(AnalysisReport)
class AnalysisReportAdmin(admin.ModelAdmin):
    list_display = ('analysis', 'total_citations', 'overall_credibility_score', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('analysis__title',)


@admin.register(AgentLog)
class AgentLogAdmin(admin.ModelAdmin):
    list_display = ('agent_name', 'action', 'status', 'analysis', 'started_at')
    list_filter = ('agent_name', 'status')
