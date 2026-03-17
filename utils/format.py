import re
from datetime import datetime


BIRTH_CORRECT_PATTERN = r"(\d{4})[-./年\s]+(\d{1,2})[-./月\s]*(\d{1,2})?"


# 规范时间格式
def re_date(date):
    date = date.replace('年', '.').replace('月', '')
    if date[-1:] == '年':
        date = date[:-1]
    if '.' not in date:
        date = date + '.01'
    return date


def format_date(data):
    if data == '':
        return ''

    match = re.match(BIRTH_CORRECT_PATTERN, data)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3) if match.group(3) else 1)  # TODO: 如果没有日，则默认为 1，日期格式确认
        return datetime(year, month, day).isoformat()

    return ''


def snake_to_camel(snake_str):
    components = snake_str.split('_')  # 以下划线分割
    return components[0] + ''.join(x.title() for x in components[1:])


def convert_keys_to_camel_case(input_data):
    if isinstance(input_data, dict):
        # 如果是字典，递归转换每一个key
        return {snake_to_camel(key): convert_keys_to_camel_case(value) for key, value in input_data.items()}
    elif isinstance(input_data, list):
        # 如果是列表，递归转换列表中的每个元素
        return [convert_keys_to_camel_case(item) for item in input_data]
    else:
        # 如果是其他类型，直接返回
        return input_data
