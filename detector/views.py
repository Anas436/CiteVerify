import json
import os
import threading
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from PyPDF2 import PdfReader
from docx import Document

from .models import Analysis, Citation, AnalysisReport, AgentLog
from .agents import (
    AgentOrchestrator, CitationExtractorAgent, ContextAnalyzerAgent,
    SourceVerificationAgent, HallucinationDetectorAgent, ReportGeneratorAgent,
)


def _parse_year(value):
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _run_analysis_in_background(analysis_id: str):
    from django.db import connection
    connection.close()

    try:
        analysis = Analysis.objects.get(id=analysis_id)
        text = analysis.input_text
        all_logs = []

        # --- Agent 1: Citation Extractor ---
        analysis.status = 'extracting'
        analysis.progress = 10
        analysis.save()

        AgentLog.objects.create(
            analysis=analysis, agent_name='Citation Extractor',
            action='Extracting citations from text...', status='running',
        )
        extractor = CitationExtractorAgent()
        extract_result = extractor.run(text)
        all_logs.extend(extract_result.logs)
        AgentLog.objects.filter(analysis=analysis, agent_name='Citation Extractor', status='running').update(
            status='completed', completed_at=datetime.now(),
        )
        if not extract_result.success:
            analysis.status = 'failed'
            analysis.error_message = extract_result.error
            analysis.save()
            return
        citations = extract_result.data

        # --- Agent 2: Context Analyzer ---
        analysis.status = 'analyzing'
        analysis.progress = 30
        analysis.save()

        AgentLog.objects.create(
            analysis=analysis, agent_name='Context Analyzer',
            action='Analyzing context of each citation...', status='running',
        )
        context_agent = ContextAnalyzerAgent()
        context_result = context_agent.run(citations, text)
        all_logs.extend(context_result.logs)
        AgentLog.objects.filter(analysis=analysis, agent_name='Context Analyzer', status='running').update(
            status='completed', completed_at=datetime.now(),
        )
        context_data = context_result.data if context_result.success else []

        # --- Agent 3: Source Verifier ---
        analysis.status = 'verifying'
        analysis.progress = 50
        analysis.save()

        AgentLog.objects.create(
            analysis=analysis, agent_name='Source Verifier',
            action='Verifying source plausibility...', status='running',
        )
        verifier = SourceVerificationAgent()
        verify_result = verifier.run(citations, text)
        all_logs.extend(verify_result.logs)
        AgentLog.objects.filter(analysis=analysis, agent_name='Source Verifier', status='running').update(
            status='completed', completed_at=datetime.now(),
        )
        verification_data = verify_result.data if verify_result.success else []

        # --- Agent 4: Hallucination Detector ---
        analysis.status = 'detecting'
        analysis.progress = 70
        analysis.save()

        AgentLog.objects.create(
            analysis=analysis, agent_name='Hallucination Detector',
            action='Cross-referencing evidence to detect hallucinations...', status='running',
        )
        detector = HallucinationDetectorAgent()
        detect_result = detector.run(citations, context_data, verification_data)
        all_logs.extend(detect_result.logs)
        AgentLog.objects.filter(analysis=analysis, agent_name='Hallucination Detector', status='running').update(
            status='completed', completed_at=datetime.now(),
        )
        detection_results = detect_result.data if detect_result.success else []

        # --- Agent 5: Report Generator ---
        analysis.status = 'reporting'
        analysis.progress = 85
        analysis.save()

        AgentLog.objects.create(
            analysis=analysis, agent_name='Report Generator',
            action='Generating comprehensive report...', status='running',
        )
        report_input = {
            'citations': citations,
            'context_analysis': context_data,
            'verification': verification_data,
            'results': detection_results,
        }
        reporter = ReportGeneratorAgent()
        report_result = reporter.run(report_input)
        all_logs.extend(report_result.logs)
        AgentLog.objects.filter(analysis=analysis, agent_name='Report Generator', status='running').update(
            status='completed', completed_at=datetime.now(),
        )
        report_data = report_result.data if report_result.success else {}

        # --- Save Results ---
        analysis.progress = 90
        analysis.save()

        for i, cit in enumerate(citations):
            ctx = context_data[i] if i < len(context_data) else {}
            ver = verification_data[i] if i < len(verification_data) else {}
            det = detection_results[i] if i < len(detection_results) else {}

            severity = det.get('severity', 'yellow') if isinstance(det, dict) else 'yellow'
            conf = det.get('confidence', ver.get('confidence_score', 0.5)) if isinstance(det, dict) else 0.5

            Citation.objects.create(
                analysis=analysis,
                citation_text=cit.get('citation_text', ''),
                context_before=cit.get('context_before', ''),
                context_after=cit.get('context_after', ''),
                claimed_source=cit.get('claimed_source', ''),
                claimed_year=_parse_year(cit.get('claimed_year')),
                confidence_score=conf,
                severity=severity if severity in ('green', 'yellow', 'red') else 'yellow',
                explanation=det.get('reason', '') if isinstance(det, dict) else '',
                suggestion=ctx.get('claim_summary', '') if isinstance(ctx, dict) else '',
                is_hallucinated=det.get('is_hallucinated', False) if isinstance(det, dict) else False,
            )

        AnalysisReport.objects.create(
            analysis=analysis,
            summary=report_data.get('summary', ''),
            total_citations=report_data.get('total_citations', len(citations)),
            verified_citations=report_data.get('verified_citations', 0),
            questionable_citations=report_data.get('questionable_citations', 0),
            hallucinated_citations=report_data.get('hallucinated_citations', 0),
            overall_credibility_score=report_data.get('overall_credibility_score', 0.0),
            agent_logs=all_logs,
            recommendations=report_data.get('recommendations', []),
        )

        analysis.status = 'completed'
        analysis.progress = 100
        analysis.completed_at = datetime.now()
        analysis.save()

    except Exception as e:
        try:
            analysis = Analysis.objects.get(id=analysis_id)
            analysis.status = 'failed'
            analysis.error_message = str(e)
            analysis.save()
        except Exception:
            pass


@login_required
def dashboard(request):
    analyses = Analysis.objects.filter(user=request.user)
    recent = analyses[:6]
    stats = {
        'total': analyses.count(),
        'completed': analyses.filter(status='completed').count(),
        'hallucinated': sum(a.citations.filter(is_hallucinated=True).count() for a in analyses.filter(status='completed')),
        'total_citations': sum(a.citations.count() for a in analyses.filter(status='completed')),
    }
    ctx = {'analyses': recent, 'stats': stats}
    return render(request, 'detector/dashboard.html', ctx)


@login_required
def new_analysis(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip() or 'Untitled Analysis'
        input_text = request.POST.get('input_text', '')
        uploaded_file = request.FILES.get('input_file')

        if uploaded_file:
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext == '.pdf':
                input_type = 'pdf'
                try:
                    reader = PdfReader(uploaded_file)
                    input_text = ''.join(page.extract_text() or '' for page in reader.pages)
                except Exception:
                    messages.error(request, 'Failed to read PDF file. Please try pasting the text instead.')
                    return render(request, 'detector/upload.html')
            elif ext == '.docx':
                input_type = 'docx'
                try:
                    doc = Document(uploaded_file)
                    input_text = '\n'.join(p.text for p in doc.paragraphs)
                except Exception:
                    messages.error(request, 'Failed to read Word file. Please try pasting the text instead.')
                    return render(request, 'detector/upload.html')
            else:
                messages.error(request, 'Unsupported file type. Please upload a PDF or DOCX file.')
                return render(request, 'detector/upload.html')

            if not input_text.strip():
                messages.error(request, 'Could not extract any text from the file. Please try pasting the text instead.')
                return render(request, 'detector/upload.html')
        else:
            input_type = 'text'
            if not input_text.strip():
                messages.error(request, 'Please enter some text to analyze.')
                return render(request, 'detector/upload.html')

        analysis = Analysis.objects.create(
            user=request.user,
            title=title,
            input_text=input_text,
            input_file=uploaded_file,
            input_type=input_type,
            status='pending',
            progress=0,
        )

        thread = threading.Thread(
            target=_run_analysis_in_background,
            args=(str(analysis.id),),
            daemon=True,
        )
        thread.start()

        messages.success(request, 'Analysis started!')
        return redirect('detector:analysis_progress', analysis_id=analysis.id)

    return render(request, 'detector/upload.html')


@login_required
def analysis_progress(request, analysis_id):
    analysis = get_object_or_404(Analysis, id=analysis_id, user=request.user)
    ctx = {'analysis': analysis}
    return render(request, 'detector/progress.html', ctx)


@login_required
def analysis_status_api(request, analysis_id):
    analysis = get_object_or_404(Analysis, id=analysis_id, user=request.user)
    logs = AgentLog.objects.filter(analysis=analysis).values(
        'agent_name', 'action', 'status', 'started_at'
    )[:20]
    return JsonResponse({
        'status': analysis.status,
        'progress': analysis.progress,
        'error_message': analysis.error_message,
        'logs': list(logs),
    })


@login_required
def analysis_results(request, analysis_id):
    analysis = get_object_or_404(Analysis, id=analysis_id, user=request.user)
    if analysis.status != 'completed':
        return redirect('detector:analysis_progress', analysis_id=analysis.id)

    citations = analysis.citations.all()
    report = getattr(analysis, 'report', None)
    severity_counts = {
        'red': citations.filter(severity='red').count(),
        'yellow': citations.filter(severity='yellow').count(),
        'green': citations.filter(severity='green').count(),
    }

    ctx = {
        'analysis': analysis,
        'citations': citations,
        'report': report,
        'severity_counts': severity_counts,
    }
    return render(request, 'detector/results.html', ctx)


@login_required
def report_detail(request, analysis_id):
    analysis = get_object_or_404(Analysis, id=analysis_id, user=request.user)
    report = getattr(analysis, 'report', None)
    if not report:
        messages.warning(request, 'Report not yet available.')
        return redirect('detector:analysis_progress', analysis_id=analysis.id)

    citations = analysis.citations.all()
    ctx = {
        'analysis': analysis,
        'report': report,
        'citations': citations,
    }
    return render(request, 'detector/report_detail.html', ctx)


@login_required
def analysis_history(request):
    analyses = Analysis.objects.filter(user=request.user)
    ctx = {'analyses': analyses}
    return render(request, 'detector/history.html', ctx)


@login_required
@require_POST
def delete_analysis(request, analysis_id):
    analysis = get_object_or_404(Analysis, id=analysis_id, user=request.user)
    analysis.delete()
    messages.success(request, 'Analysis deleted.')
    return redirect('detector:dashboard')
