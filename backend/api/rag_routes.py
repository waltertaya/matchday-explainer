from flask import Blueprint, request, jsonify
from openai import OpenAI
import json

from rag.indexing import Indexer
from rag import config

rag_bp = Blueprint('rag', __name__)

PROMPT_TEMPLATE ="""
You are the refereeing explainer inside a football match app. You explain, in plain language, which Law of the Game applies to an on-pitch event and why it leads to the outcome shown. You explain the rules. You do NOT judge whether the referee or VAR was right.

Hard rules:
1. Base every statement about the rules ONLY on the passages in <retrieved_passages>. Do not use memory of the Laws. If the passages do not cover the question, set answerable to false and say what is missing.
2. Cite each rule statement with the passage ID(s) it comes from, for example ["P2"]. Paraphrase in your own words. Quote at most one short phrase (under 15 words) per passage.
3. Keep "what the law says" separate from "what the event data shows". Use only the fields in <event> and <context> for the second. Never invent details about contact, intent, positioning, speed or what video would show.
4. If the outcome depends on a detail the event data does not contain (for example whether a challenge was careless or reckless), say that explicitly under data_limits and explain the possible outcomes instead of choosing one.
5. Never say a decision was correct, incorrect, harsh, lenient, a mistake or controversial. Never comment on the officials' competence or bias.
6. If passages come from different editions, prefer the most recent edition and note the difference only if it changes the explanation.
7. Match the reading level and language requested. Keep to the word limits.
8. Return ONLY valid JSON matching the schema. No markdown and no text outside the JSON.

Reading levels:
- new_fan: everyday words, one short example if useful, explain any term of art.
- regular: concise, use standard football terms.
- analyst: precise, mention the relevant sub-clause or procedure.

Input for this request:

<retrieved_passages>
{context}
</retrieved_passages>

<event>
No structured event data is supplied with this request. If the user's question
on the on-pitch event lacks detail, treat the event as unknown and rely on
data_limits.
</event>

<question>
{question}
</question>
"""

# Appended after the formatted template (kept separate so the JSON braces
# below never collide with str.format).
OUTPUT_SCHEMA = """
Output format (STRICT):
Return ONLY a single JSON object, no markdown fences, no text outside it:
{
  "answerable": true,
  "explanation": "plain-language answer, grounded ONLY in the passages, at most 70 words",
  "law_reference": "e.g. IFAB Laws of the Game, Law 12",
  "citations": ["chunk ids actually used, e.g. 475f9ebc-1910-4596-a272-43ce203b22aa"],
  "data_limits": null
}
data_limits is null, or at most 30 words on what the event data lacks.
"""

client = OpenAI(
    api_key=config.NVIDIA_OPENAI_API_KEY,
    base_url=config.NVIDIA_BASE_URL,
)


def _parse_llm_json(raw):
    """Parse the model's JSON reply; fall back to a wrapped raw answer."""
    text = (raw or '').strip()
    if text.startswith('```'):
        text = text.strip('`').lstrip()
        if text.lower().startswith('json'):
            text = text[4:]
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {
        'answerable': False,
        'explanation': (raw or '').strip()[:400],
        'law_reference': None,
        'citations': [],
        'data_limits': 'Model reply was not valid JSON; raw text returned.',
    }


@rag_bp.route('/index', methods=['POST'])
def index_ifabs():
    """Parse PDFs, generate embeddings, and save chunks to PostgreSQL."""
    try:
        indexer = Indexer()
        indexer.save()
        return jsonify({'msg': 'Indexing completed successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/search', methods=['POST'])
def search_ifabs():
    """Retrieve relevant chunks and return a compact grounded answer."""
    data = request.get_json(silent=True) or {}
    query = (data.get('query') or '').strip()
    context = data.get('context')
    include_chunks = bool(data.get('include_chunks', False))

    try:
        limit = int(data.get('limit', 5))
    except (TypeError, ValueError):
        return jsonify({'error': 'limit must be an integer'}), 400
    if limit < 1:
        return jsonify({'error': 'limit must be at least 1'}), 400

    if not query:
        return jsonify({'error': 'Query is required'}), 400

    try:
        combined = f"{query} {context}" if context else query
        indexer = Indexer()
        results = indexer.search(combined, limit=limit)

        passages = [
            {
                'id': r['id'],
                'source': r['source'],
                'similarity': round(r['similarity'], 3),
            }
            for r in results
        ]

        if not results:
            return jsonify({
                'query': query,
                'answer': {
                    'answerable': False,
                    'explanation': '',
                    'law_reference': None,
                    'citations': [],
                    'data_limits': 'No passages matched the query in the indexed Laws.',
                },
                'passages': [],
            }), 200

        # Cap each chunk in the prompt so garbled/long chunks don't balloon it.
        context_block = '\n'.join(
            f"Source: {r['source']}, Chunk ID: {r['id']}, Text: {r['content'][:1200]}"
            for r in results
        )
        prompt = PROMPT_TEMPLATE.format(
            context=context_block,
            question=query,
        ) + OUTPUT_SCHEMA

        kwargs = dict(
            model=config.NVIDIA_LLM_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=500,
            temperature=0.2,
        )
        
        if config.NVIDIA_LLM_MODEL.startswith('openai/gpt-oss'):
            kwargs['extra_body'] = {'reasoning_effort': 'low'}

        completion = client.chat.completions.create(**kwargs)
        answer = _parse_llm_json(completion.choices[0].message.content)

        payload = {
            'query': query,
            'answer': answer,
            'passages': passages,
        }
        if include_chunks:
            payload['chunks'] = [
                {'id': r['id'], 'source': r['source'], 'content': r['content']}
                for r in results
            ]
        return jsonify(payload), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
