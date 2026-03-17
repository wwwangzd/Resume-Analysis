import json
import re
import urllib.request


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


def extract_resume_by_llm(resume_text, settings):
	llm_settings = settings['llm']
	api_key = llm_settings['api_key'].strip()
	api_base = llm_settings['api_base'].rstrip('/')
	model = llm_settings['model']
	timeout_seconds = llm_settings['timeout_seconds']
	system_prompt, user_requirements, output_schema = _get_prompt_settings(settings)

	if not api_key:
		raise ValueError('llm.api_key is empty in settings.json.')

	payload = {
		'model': model,
		'temperature': 0,
		'response_format': {'type': 'json_object'},
		'messages': [
			{'role': 'system', 'content': system_prompt},
			{'role': 'user', 'content': _build_user_prompt(resume_text, user_requirements, output_schema)}
		]
	}

	req = urllib.request.Request(
		f'{api_base}/chat/completions',
		data=json.dumps(payload).encode('utf-8'),
		method='POST'
	)
	req.add_header('Authorization', f'Bearer {api_key}')
	req.add_header('Content-Type', 'application/json')

	with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
		response = json.loads(resp.read().decode('utf-8', errors='ignore'))

	content = response['choices'][0]['message']['content']
	parsed = _extract_json_object(content)
	return _normalize_schema(parsed, output_schema)
