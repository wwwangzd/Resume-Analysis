import json
import re
from typing import Any

import config
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate

from config.logger import get_logger, log_stage_timing, start_timer


logger = get_logger('resume_analysis.llm')
llm_instance_cache: dict[str, Any] = {}
prompt_template_cache: ChatPromptTemplate | None = None
chain_cache: dict[str, Any] = {}


def get_prompt_settings():
    prompt_settings = config.get_llm_prompt_config()
    system_prompt = prompt_settings['system_prompt']
    user_requirements = prompt_settings['user_requirements']
    output_schema = prompt_settings['output_schema']
    return system_prompt, user_requirements, output_schema


def build_user_prompt(resume_text, user_requirements, output_schema):
    requirements_text = '\n'.join(str(item) for item in user_requirements)
    return (
        '请将简历文本抽取为以下固定 JSON 结构。\n'
        '要求：\n'
        f'{requirements_text}\n\n'
        f'JSON 模板:\n{json.dumps(output_schema, ensure_ascii=False)}\n\n'
        f'简历文本:\n{resume_text}'
    )


def build_langchain_model(llm_settings):
    model_name = llm_settings['model']
    return ChatTongyi(model=model_name)  # type: ignore


def get_llm_cache_key(llm_settings) -> str:
    return json.dumps(llm_settings, ensure_ascii=False, sort_keys=True)


def get_or_create_prompt_template() -> ChatPromptTemplate:
    global prompt_template_cache

    if prompt_template_cache is None:
        prompt_template_cache = ChatPromptTemplate.from_messages([
            ('system', '{system_prompt}'),
            ('user', '{user_prompt}'),
        ])
    return prompt_template_cache


def get_or_create_llm_instance(llm_settings):
    cache_key = get_llm_cache_key(llm_settings)
    cached_instance = llm_instance_cache.get(cache_key)
    if cached_instance is not None:
        return cached_instance, True

    llm_instance = build_langchain_model(llm_settings)
    llm_instance_cache[cache_key] = llm_instance
    return llm_instance, False


def get_or_create_llm_chain(llm_settings):
    cache_start = start_timer()
    cache_key = get_llm_cache_key(llm_settings)
    cached_chain = chain_cache.get(cache_key)
    if cached_chain is not None:
        log_stage_timing(logger, 'llm_chain_cache', cache_start, cache_hit=True)
        return cached_chain

    prompt_template = get_or_create_prompt_template()
    llm_instance, llm_cache_hit = get_or_create_llm_instance(llm_settings)
    llm_chain = prompt_template | llm_instance
    chain_cache[cache_key] = llm_chain
    log_stage_timing(
        logger,
        'llm_chain_cache',
        cache_start,
        cache_hit=False,
        llm_cache_hit=llm_cache_hit,
    )
    return llm_chain


def is_noise_line(line: str) -> bool:
    compact_line = line.replace(' ', '')
    if len(compact_line) < 20:
        return False

    ascii_chars = sum(1 for char in compact_line if char.isascii())
    digit_chars = sum(1 for char in compact_line if char.isdigit())
    alpha_chars = sum(1 for char in compact_line if char.isalpha())
    cjk_chars = sum(1 for char in compact_line if '\u4e00' <= char <= '\u9fff')
    ascii_ratio = ascii_chars / max(len(compact_line), 1)

    return ascii_ratio > 0.85 and digit_chars > 0 and alpha_chars > 0 and cjk_chars == 0


def normalize_resume_lines(resume_text: str, preprocess_config) -> list[str]:
    collapse_spaces = preprocess_config.get('collapse_internal_spaces', True)
    dedupe_lines = preprocess_config.get('dedupe_consecutive_lines', True)
    remove_noise_lines = preprocess_config.get('remove_noise_lines', True)

    normalized_lines = []
    previous_line = None

    for raw_line in resume_text.splitlines():
        line = raw_line.strip()
        if collapse_spaces:
            line = re.sub(r'[ \t\u3000]+', ' ', line).strip()
        if not line:
            continue
        if remove_noise_lines and is_noise_line(line):
            continue
        if dedupe_lines and line == previous_line:
            continue
        normalized_lines.append(line)
        previous_line = line

    return normalized_lines


def truncate_resume_text(resume_text: str, preprocess_config) -> str:
    max_input_chars = preprocess_config.get('max_input_chars', 5000)
    preserve_tail_chars = preprocess_config.get('preserve_tail_chars', 1200)

    if max_input_chars <= 0 or len(resume_text) <= max_input_chars:
        return resume_text

    if preserve_tail_chars <= 0 or preserve_tail_chars >= max_input_chars:
        return resume_text[:max_input_chars]

    head_chars = max_input_chars - preserve_tail_chars
    truncated_text = resume_text[:head_chars].rstrip()
    preserved_tail = resume_text[-preserve_tail_chars:].lstrip()
    return f'{truncated_text}\n...\n{preserved_tail}'


def prepare_resume_text_for_llm(resume_text: str) -> str:
    preprocess_config = config.get_llm_preprocess_config()
    if not preprocess_config.get('enabled', True):
        return resume_text

    preprocess_start = start_timer()
    normalized_lines = normalize_resume_lines(resume_text, preprocess_config)
    normalized_text = '\n'.join(normalized_lines)
    prepared_text = truncate_resume_text(normalized_text, preprocess_config)
    log_stage_timing(
        logger,
        'llm_text_preprocess',
        preprocess_start,
        raw_length=len(resume_text),
        prepared_length=len(prepared_text),
        removed_chars=len(resume_text) - len(prepared_text),
        line_count=len(normalized_lines),
    )
    return prepared_text


def extract_json_object(raw_text):
    try:
        return json.loads(raw_text)
    except Exception:
        pass

    match = re.search(r'\{[\s\S]*\}', raw_text)
    if not match:
        raise ValueError('LLM response does not contain JSON object.')
    return json.loads(match.group(0))


def normalize_schema(data, output_schema):
    form_data = json.loads(json.dumps(output_schema, ensure_ascii=False))
    if not isinstance(data, dict):
        return form_data

    for key in form_data:
        if key in data:
            form_data[key] = data[key]

    return form_data


def extract_resume_by_llm(resume_text):
    total_start = start_timer()
    llm_settings = config.get_llm_config()
    system_prompt, user_requirements, output_schema = get_prompt_settings()
    prepared_resume_text = prepare_resume_text_for_llm(resume_text)
    chain = get_or_create_llm_chain(llm_settings)

    invoke_start = start_timer()
    response = chain.invoke(
        {
            'system_prompt': system_prompt,
            'user_prompt': build_user_prompt(prepared_resume_text, user_requirements, output_schema),
        }
    )
    log_stage_timing(
        logger,
        'llm_invoke',
        invoke_start,
        model=llm_settings['model'],
        input_length=len(prepared_resume_text),
    )

    content = response.content
    if isinstance(content, list):
        content = ''.join(
            part.get('text', '') if isinstance(part, dict) else str(part)
            for part in content
        )
    if not isinstance(content, str):
        content = str(content)

    parsed = extract_json_object(content)
    normalized_data = normalize_schema(parsed, output_schema)
    log_stage_timing(
        logger,
        'llm_extract_total',
        total_start,
        model=llm_settings['model'],
        output_keys=len(normalized_data.keys()) if isinstance(normalized_data, dict) else 0,
    )
    return normalized_data
