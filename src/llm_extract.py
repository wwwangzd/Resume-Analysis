import json
import re

from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate


def _get_prompt_settings(settings):
    prompt_settings = settings['llm']['prompt']
    system_prompt = prompt_settings['system_prompt']
    user_requirements = prompt_settings['user_requirements']
    output_schema = prompt_settings['output_schema']
    return system_prompt, user_requirements, output_schema


def _build_user_prompt(resume_text, user_requirements, output_schema):
    requirements_text = '\n'.join(str(item) for item in user_requirements)
    return (
        '请将简历文本抽取为以下固定 JSON 结构。\n'
        '要求：\n'
        f'{requirements_text}\n\n'
        f'JSON 模板:\n{json.dumps(output_schema, ensure_ascii=False)}\n\n'
        f'简历文本:\n{resume_text}'
    )


def _extract_json_object(raw_text):
	try:
		return json.loads(raw_text)
	except Exception:
		pass

	match = re.search(r'\{[\s\S]*\}', raw_text)
	if not match:
		raise ValueError('LLM response does not contain JSON object.')
	return json.loads(match.group(0))


def _normalize_schema(data, output_schema):
	form_data = json.loads(json.dumps(output_schema, ensure_ascii=False))
	if not isinstance(data, dict):
		return form_data

	for key in form_data.keys():
		if key in data:
			form_data[key] = data[key]

	return form_data


def _build_langchain_model(llm_settings):
	model_name = llm_settings['model']
	return ChatTongyi(model=model_name) # type: ignore


def extract_resume_by_llm(resume_text, settings):
	llm_settings = settings['llm']
	system_prompt, user_requirements, output_schema = _get_prompt_settings(settings)

	prompt = ChatPromptTemplate.from_messages([
		('system', '{system_prompt}'),
		('user', '{user_prompt}')
	])
	llm = _build_langchain_model(llm_settings)
	chain = prompt | llm

	response = chain.invoke({
		'system_prompt': system_prompt,
		'user_prompt': _build_user_prompt(resume_text, user_requirements, output_schema)
	})
	
	content = response.content
	if isinstance(content, list):
		content = ''.join(
			part.get('text', '') if isinstance(part, dict) else str(part)
			for part in content
		)
	if not isinstance(content, str):
		content = str(content)

	parsed = _extract_json_object(content)
	return _normalize_schema(parsed, output_schema)
