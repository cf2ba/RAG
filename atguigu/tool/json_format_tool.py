import json
from typing import Any

from bson import ObjectId


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


def json_format_tool(data):
    return json.dumps(data, ensure_ascii=False,indent=4,cls=NumpyEncoder)