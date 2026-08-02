import json


def json_format_tool(data):
    return json.dumps(data, ensure_ascii=False,indent=4)