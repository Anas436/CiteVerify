import re
import json
import time
from typing import Any
from dataclasses import dataclass, field, asdict

from django.conf import settings
from groq import Groq


@dataclass
class AgentResult:
    success: bool
    data: Any = None
    error: str = ''
    logs: list = field(default_factory=list)


class BaseAgent:
    name: str = 'Base Agent'
    description: str = ''

    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        self.model = settings.GROQ_MODEL
        self.logs: list = []

    def _log(self, action: str, detail: str = '') -> None:
        self.logs.append({
            'agent': self.name,
            'action': action,
            'detail': detail,
            'timestamp': time.time(),
        })

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
        if not self.client:
            msg = 'GROQ_API_KEY not configured. Set it in .env file.'
            self._log('API Call Failed', msg)
            raise RuntimeError(msg)

        self._log('API Call', f'Calling {self.model} with temperature={temperature}')
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=temperature,
            max_tokens=4096,
        )
        result = response.choices[0].message.content.strip()
        self._log('API Response', f'Received {len(result)} characters')
        return result

    def run(self, *args, **kwargs) -> AgentResult:
        raise NotImplementedError


class CitationExtractorAgent(BaseAgent):
    name = 'Citation Extractor'
    description = 'Extracts all citations from research paper text using pattern matching and LLM analysis'

    SYSTEM_PROMPT = '''You are an expert citation extraction specialist. Your task is to identify ALL citation 
    markers in academic text, including: author-year citations (Smith, 2020), numbered citations [1], [2-4], 
    footnote markers, IEEE-style [1], ACM-style, APA-style in-text citations, and any reference to prior work.
    
    For each citation you find, extract:
    1. The exact citation text as it appears
    2. The sentence or phrase that contains it (context)
    3. The claimed source (author names, year, title if available)
    4. The type of citation (author-year, numeric, footnote, etc.)
    
    Return your analysis as a JSON array of objects with keys: citation_text, context_before, context_after, 
    claimed_source, claimed_year, citation_type. If no citations are found, return an empty array [].

    IMPORTANT: Return ONLY valid JSON. No markdown, no explanation.'''

    def _extract_citations_regex(self, text: str) -> list[dict]:
        citations = []
        patterns = [
            # Author-year: (Author, Year) or (Author et al., Year)
            r'\([^)]*\d{4}[^)]*\)',
            # Bracketed numbers: [1], [1,2], [1-3]
            r'\[[\d,\-\s]+\]',
            # Superscript-style: AuthorName \d+
            r'(?:^|\s)([A-Z][a-z]+(?:\s(?:et\s+al\.?|&\s+[A-Z][a-z]+))?)(?:\s*,\s*)(\d{4})',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                start = max(0, match.start() - 200)
                end = min(len(text), match.end() + 200)
                before = text[start:match.start()].strip()
                after = text[match.end():end].strip()
                citations.append({
                    'citation_text': match.group().strip(),
                    'context_before': before[-200:] if before else '',
                    'context_after': after[:200] if after else '',
                    'claimed_source': '',
                    'claimed_year': '',
                    'citation_type': 'regex_match',
                })
        return citations

    def _extract_citations_llm(self, text: str) -> list[dict]:
        max_chars = 8000
        truncated = text[:max_chars] + ('...' if len(text) > max_chars else '')
        prompt = f'''Extract all citations from this research paper text. Return ONLY a JSON array:

{truncated}'''
        system = self.SYSTEM_PROMPT + '\n\nReturn ONLY valid JSON array. No other text.'
        response = self._call_llm(system, prompt, temperature=0.1)
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        response = response.strip()
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            self._log('LLM Parse Error', f'Failed to parse LLM response as JSON: {response[:200]}')
            return []

    def run(self, text: str) -> AgentResult:
        self._log('Starting Extraction', f'Input text length: {len(text)} chars')
        try:
            regex_citations = self._extract_citations_regex(text)
            self._log('Regex Extraction', f'Found {len(regex_citations)} citations via regex')

            llm_citations = self._extract_citations_llm(text)
            self._log('LLM Extraction', f'Found {len(llm_citations)} citations via LLM')

            seen = set()
            combined = []
            for cit in regex_citations + llm_citations:
                key = cit.get('citation_text', '')[:100]
                if key not in seen:
                    seen.add(key)
                    combined.append(cit)

            self._log('Extraction Complete', f'Total unique citations: {len(combined)}')
            return AgentResult(success=True, data=combined, logs=self.logs)

        except Exception as e:
            self._log('Extraction Failed', str(e))
            return AgentResult(success=False, error=str(e), logs=self.logs)


class ContextAnalyzerAgent(BaseAgent):
    name = 'Context Analyzer'
    description = 'Analyzes the surrounding context of each citation to understand the claim being made'

    SYSTEM_PROMPT = '''You are an expert at understanding academic paper context. For each citation, analyze:
    1. What claim is being made in the sentence containing this citation?
    2. Is the citation being used to support a specific fact, a general statement, or as a related work reference?
    3. What type of claim is it? (factual claim, numerical result, methodological claim, comparative claim, definition)
    4. How strong is the claim? (definitive statement vs tentative suggestion)
    
    Return a JSON array with objects: {citation_text, claim_type, claim_strength, claim_summary, 
    is_verifiable, reasoning}. Return ONLY valid JSON.'''

    def run(self, citations: list[dict], full_text: str) -> AgentResult:
        self._log('Starting Context Analysis', f'Analyzing {len(citations)} citations')
        try:
            analyzed = []
            for i, cit in enumerate(citations):
                if i < 50:
                    text = cit.get('citation_text', '')
                    before = cit.get('context_before', '')
                    after = cit.get('context_after', '')
                    prompt = f'''Citation: {text}
Context before: {before}
Context after: {after}

Analyze the claim being made with this citation. Return a single JSON object.'''
                    try:
                        response = self._call_llm(self.SYSTEM_PROMPT, prompt, temperature=0.2)
                        response = response.strip()
                        if response.startswith('```json'):
                            response = response[7:]
                        if response.startswith('```'):
                            response = response[3:]
                        if response.endswith('```'):
                            response = response[:-3]
                        result = json.loads(response.strip())
                        if isinstance(result, list) and result:
                            analyzed.append(result[0])
                        elif isinstance(result, dict):
                            analyzed.append(result)
                        else:
                            analyzed.append({'citation_text': text, 'claim_type': 'unknown', 'claim_strength': 'unknown', 'claim_summary': '', 'is_verifiable': False})
                    except (json.JSONDecodeError, Exception) as e:
                        self._log(f'Citation {i} Parse Error', str(e)[:100])
                        analyzed.append({'citation_text': text, 'claim_type': 'unknown', 'claim_strength': 'unknown', 'claim_summary': '', 'is_verifiable': False})
                else:
                    analyzed.append({'citation_text': cit.get('citation_text', ''), 'claim_type': 'batch_processed', 'claim_strength': 'unknown', 'claim_summary': '', 'is_verifiable': False})

            self._log('Context Analysis Complete', f'Analyzed {len(analyzed)} citations')
            return AgentResult(success=True, data=analyzed, logs=self.logs)

        except Exception as e:
            self._log('Context Analysis Failed', str(e))
            return AgentResult(success=False, error=str(e), logs=self.logs)


class SourceVerificationAgent(BaseAgent):
    name = 'Source Verifier'
    description = 'Verifies whether cited sources plausibly exist and support the claimed statements'

    SYSTEM_PROMPT = '''You are an expert academic fact-checker and reference librarian. For each citation, evaluate:
    1. Does this citation look legitimate? (Author names that sound real, proper formatting)
    2. Is the year mentioned plausible for the claimed content?
    3. Does the source seem to exist based on the description? (Look for hallmarks of hallucination:
       - Authors that are too generic or famous
       - Years that don't match the topic's timeline
       - Claimed findings that sound too perfect or convenient
       - Mixing of real concepts from different domains)
    4. Rate confidence: 0.0 (certainly hallucinated) to 1.0 (certainly real)
    
    Return a JSON array with objects: {citation_text, is_plausible, confidence_score, 
    verification_notes, red_flags[], green_flags[], severity: "green"|"yellow"|"red"}
    
    severity guide:
    - "red": appears fabricated/non-existent
    - "yellow": questionable, needs manual verification
    - "green": appears legitimate
    
    Return ONLY valid JSON.'''

    def run(self, citations: list[dict], full_text: str) -> AgentResult:
        self._log('Starting Source Verification', f'Verifying {len(citations)} sources')
        try:
            verified = []
            batch_size = 15
            for batch_start in range(0, min(len(citations), 60), batch_size):
                batch = citations[batch_start:batch_start + batch_size]
                batch_input = json.dumps([
                    {'citation_text': c.get('citation_text', ''), 'claimed_source': c.get('claimed_source', '')}
                    for c in batch
                ])
                prompt = f'''Verify these citations. Return ONLY a JSON array of verification results:

{batch_input}'''
                try:
                    response = self._call_llm(self.SYSTEM_PROMPT, prompt, temperature=0.1)
                    response = response.strip()
                    if response.startswith('```json'):
                        response = response[7:]
                    if response.startswith('```'):
                        response = response[3:]
                    if response.endswith('```'):
                        response = response[:-3]
                    results = json.loads(response.strip())
                    if isinstance(results, list):
                        verified.extend(results)
                    self._log(f'Batch {batch_start//batch_size + 1}', f'Verified {len(results)} citations')
                except (json.JSONDecodeError, Exception) as e:
                    self._log(f'Batch {batch_start//batch_size + 1} Failed', str(e)[:100])
                    for c in batch:
                        verified.append({
                            'citation_text': c.get('citation_text', ''),
                            'is_plausible': True,
                            'confidence_score': 0.5,
                            'verification_notes': 'Verification unavailable',
                            'red_flags': [],
                            'green_flags': [],
                            'severity': 'yellow',
                        })

            remaining = citations[60:]
            for c in remaining:
                verified.append({
                    'citation_text': c.get('citation_text', ''),
                    'is_plausible': True,
                    'confidence_score': 0.5,
                    'verification_notes': 'Batch processed',
                    'red_flags': [],
                    'green_flags': [],
                    'severity': 'yellow',
                })

            self._log('Verification Complete', f'Verified {len(verified)} sources total')
            return AgentResult(success=True, data=verified, logs=self.logs)

        except Exception as e:
            self._log('Verification Failed', str(e))
            return AgentResult(success=False, error=str(e), logs=self.logs)


class HallucinationDetectorAgent(BaseAgent):
    name = 'Hallucination Detector'
    description = 'Final detection layer that cross-references all evidence to identify hallucinated citations'

    SYSTEM_PROMPT = '''You are the final judge in a multi-agent citation verification system. You receive:
    1. The extracted citations with their context
    2. The context analysis results
    3. The source verification results
    
    Your job is to make the FINAL DETERMINATION for each citation:
    - Is this citation HALLUCINATED (fabricated, doesn't exist) or LEGITIMATE?
    
    Consider these hallmarks of hallucinated citations:
    - Non-existent or suspicious author names
    - Years that don't align with the claimed findings
    - Results that seem "too perfect" (convenient statistics, exactly round numbers)
    - Mixture of real and fake elements (e.g., real author + fake paper)
    - Generic descriptions that lack specificity
    - Claims that contradict well-established knowledge
    
    Return JSON array: [{citation_text, is_hallucinated: bool, confidence: 0.0-1.0, 
    reason: string, severity: "green"|"yellow"|"red"}]
    
    Return ONLY valid JSON.'''

    def run(self, citations: list[dict], context_analysis: list[dict],
            verification: list[dict]) -> AgentResult:
        self._log('Starting Hallucination Detection',
                  f'Cross-referencing {len(citations)} citations')
        try:
            input_data = []
            for i, cit in enumerate(citations):
                ctx = context_analysis[i] if i < len(context_analysis) else {}
                ver = verification[i] if i < len(verification) else {}
                input_data.append({
                    'citation': cit.get('citation_text', ''),
                    'context_summary': ctx.get('claim_summary', ''),
                    'claim_type': ctx.get('claim_type', ''),
                    'verification_score': ver.get('confidence_score', 0.5),
                    'verification_notes': ver.get('verification_notes', ''),
                    'red_flags': ver.get('red_flags', []),
                    'green_flags': ver.get('green_flags', []),
                })

            results = []
            batch_size = 10
            for batch_start in range(0, min(len(input_data), 60), batch_size):
                batch = input_data[batch_start:batch_start + batch_size]
                prompt = json.dumps(batch)
                try:
                    response = self._call_llm(self.SYSTEM_PROMPT, prompt, temperature=0.1)
                    response = response.strip()
                    if response.startswith('```json'):
                        response = response[7:]
                    if response.startswith('```'):
                        response = response[3:]
                    if response.endswith('```'):
                        response = response[:-3]
                    batch_results = json.loads(response.strip())
                    if isinstance(batch_results, list):
                        results.extend(batch_results)
                    self._log(f'Hallucination Batch {batch_start//batch_size + 1}',
                              f'Detected {sum(1 for r in batch_results if isinstance(r, dict) and r.get("is_hallucinated"))} hallucinations')
                except (json.JSONDecodeError, Exception) as e:
                    self._log(f'Detection Batch {batch_start//batch_size + 1} Failed', str(e)[:100])
                    for item in batch:
                        ver_score = item.get('verification_score', 0.5)
                        is_hall = ver_score < 0.3
                        results.append({
                            'citation_text': item.get('citation', ''),
                            'is_hallucinated': is_hall,
                            'confidence': ver_score,
                            'reason': 'Fallback: based on source verification score',
                            'severity': 'red' if is_hall else ('yellow' if ver_score < 0.6 else 'green'),
                        })

            remaining_input = input_data[60:]
            for item in remaining_input:
                ver_score = item.get('verification_score', 0.5)
                is_hall = ver_score < 0.3
                results.append({
                    'citation_text': item.get('citation', ''),
                    'is_hallucinated': is_hall,
                    'confidence': ver_score,
                    'reason': 'Batch processed (limit reached)',
                    'severity': 'red' if is_hall else ('yellow' if ver_score < 0.6 else 'green'),
                })

            hall_count = sum(1 for r in results if isinstance(r, dict) and r.get('is_hallucinated'))
            self._log('Detection Complete',
                      f'Total: {len(results)}, Hallucinated: {hall_count}')
            return AgentResult(success=True, data=results, logs=self.logs)

        except Exception as e:
            self._log('Detection Failed', str(e))
            return AgentResult(success=False, error=str(e), logs=self.logs)


class ReportGeneratorAgent(BaseAgent):
    name = 'Report Generator'
    description = 'Generates a comprehensive, professional analysis report'

    SYSTEM_PROMPT = '''You are a professional academic report writer. Create a concise, insightful summary of 
    the citation analysis results. Focus on:
    1. Overall credibility assessment
    2. Key findings and patterns
    3. Most concerning hallucinations
    4. Specific recommendations for the author
    
    Keep it professional, actionable, and clear.'''

    def run(self, analysis_data: dict) -> AgentResult:
        self._log('Generating Report', 'Creating comprehensive analysis report')
        try:
            citations_data = analysis_data.get('citations', [])
            results = analysis_data.get('results', [])
            total = len(results)
            hallucinated = sum(1 for r in results if isinstance(r, dict) and r.get('is_hallucinated'))
            questionable = sum(1 for r in results if isinstance(r, dict) and r.get('severity') == 'yellow')
            verified = total - hallucinated - questionable
            credibility = max(0.0, 1.0 - (hallucinated / max(total, 1)) * 0.8 - (questionable / max(total, 1)) * 0.3)

            prompt = f'''Generate an analysis report summary based on these findings:
Total Citations: {total}
Verified: {verified}
Questionable: {questionable}
Hallucinated: {hallucinated}
Overall Credibility Score: {credibility:.2f}

Hallucinated citations:
{json.dumps([r for r in results if isinstance(r, dict) and r.get('is_hallucinated')], indent=2)}

Return a JSON object with: summary, recommendations (array of strings), key_findings (array of strings)'''
            try:
                response = self._call_llm(self.SYSTEM_PROMPT, prompt, temperature=0.3)
                response = response.strip()
                if response.startswith('```json'):
                    response = response[7:]
                if response.startswith('```'):
                    response = response[3:]
                if response.endswith('```'):
                    response = response[:-3]
                report_data = json.loads(response.strip())
            except (json.JSONDecodeError, Exception):
                report_data = {
                    'summary': f'Analysis of {total} citations found {hallucinated} potentially hallucinated citations.',
                    'recommendations': [
                        'Review all red-flagged citations for accuracy',
                        'Verify questionable citations against original sources',
                        'Consider using a reference manager for accuracy',
                    ],
                    'key_findings': [
                        f'{hallucinated} out of {total} citations appear to be hallucinated',
                        f'{questionable} citations require manual verification',
                    ],
                }

            report = {
                'summary': report_data.get('summary', ''),
                'total_citations': total,
                'verified_citations': verified,
                'questionable_citations': questionable,
                'hallucinated_citations': hallucinated,
                'overall_credibility_score': round(credibility, 4),
                'recommendations': report_data.get('recommendations', []),
                'key_findings': report_data.get('key_findings', []),
            }

            self._log('Report Generated', f'Credibility score: {credibility:.2f}')
            return AgentResult(success=True, data=report, logs=self.logs)

        except Exception as e:
            self._log('Report Generation Failed', str(e))
            return AgentResult(success=False, error=str(e), logs=self.logs)


class AgentOrchestrator:
    def __init__(self):
        self.extractor = CitationExtractorAgent()
        self.context_analyzer = ContextAnalyzerAgent()
        self.verifier = SourceVerificationAgent()
        self.detector = HallucinationDetectorAgent()
        self.reporter = ReportGeneratorAgent()
        self.all_logs: list = []

    def run_analysis(self, text: str) -> dict:
        self.all_logs = []

        extract_result = self.extractor.run(text)
        self.all_logs.extend(extract_result.logs)
        if not extract_result.success:
            return {'status': 'failed', 'error': extract_result.error, 'logs': self.all_logs}
        citations = extract_result.data

        context_result = self.context_analyzer.run(citations, text)
        self.all_logs.extend(context_result.logs)
        context_analysis = context_result.data if context_result.success else []

        verify_result = self.verifier.run(citations, text)
        self.all_logs.extend(verify_result.logs)
        verification = verify_result.data if verify_result.success else []

        detect_result = self.detector.run(citations, context_analysis, verification)
        self.all_logs.extend(detect_result.logs)
        detection_results = detect_result.data if detect_result.success else []

        report_data = {
            'citations': citations,
            'context_analysis': context_analysis,
            'verification': verification,
            'results': detection_results,
        }
        report_result = self.reporter.run(report_data)
        self.all_logs.extend(report_result.logs)
        report = report_result.data if report_result.success else {}

        return {
            'status': 'completed',
            'citations': citations,
            'context_analysis': context_analysis,
            'verification': verification,
            'results': detection_results,
            'report': report,
            'logs': self.all_logs,
        }
