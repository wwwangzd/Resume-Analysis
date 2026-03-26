import json
import re

from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate

import config
from config.logger import get_logger, log_stage_timing, start_timer


logger = get_logger('resume_analysis.llm')


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

    for key in form_data.keys():
        if key in data:
            form_data[key] = data[key]

    return form_data


def build_langchain_model(llm_settings):
    model_name = llm_settings['model']
    return ChatTongyi(model=model_name)  # type: ignore


def extract_resume_by_llm(resume_text):
    total_start = start_timer()
    llm_settings = config.get_llm_config()
    system_prompt, user_requirements, output_schema = get_prompt_settings()

    prompt = ChatPromptTemplate.from_messages([
        ('system', '{system_prompt}'),
        ('user', '{user_prompt}')
    ])
    llm = build_langchain_model(llm_settings)
    chain = prompt | llm

    invoke_start = start_timer()
    response = chain.invoke({
        'system_prompt': system_prompt,
        'user_prompt': build_user_prompt(resume_text, user_requirements, output_schema)
    })
    log_stage_timing(
        logger,
        'llm_invoke',
        invoke_start,
        model=llm_settings['model'],
        input_length=len(resume_text),
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
